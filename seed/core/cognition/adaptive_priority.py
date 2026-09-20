# ==========================================================
# FILE: adaptive_priority.py
# PATH: seed/core/cognition/adaptive_priority.py
#
# SYSTEM: SEED AI OS
# COMPONENT: AdaptivePriorityEngine
# VERSION: 2.0.0
# BUILD: PASSIVE / THREAD-SAFE / QBIT-DUAL-FORMAT /
#        MEMORY-AWARE / BOUNDED-SCORING
# UPDATED: 2026-08-19
#
# PURPOSE:
# ----------------------------------------------------------
# AdaptivePriorityEngine calculates workload priority from:
#
#   - intent
#   - recent intent activity
#   - learned intent scores
#   - optional memory-system weighting
#   - hard safety priorities
#
# IMPORTANT:
# ----------------------------------------------------------
# This component is PASSIVE.
#
# It MUST NOT:
#
#   - start threads
#   - create event loops
#   - start worker tasks
#   - start subsystems
#   - execute Qbit work
#   - modify queue contents
#   - invoke the queue loop
#   - control Heartbeat
#   - control QbitDialer
#
# It ONLY:
#
#   - learn from supplied work
#   - calculate priority
#   - expose diagnostics
#
# ==========================================================

from __future__ import annotations

import logging
import threading
from collections import defaultdict, deque
from typing import Any, Dict, Optional


log = logging.getLogger("AdaptivePriority")


# ==========================================================
# PRIORITY LEVELS
# ==========================================================

class PriorityLevel:

    CRITICAL = "CRITICAL"
    NORMAL = "NORMAL"
    BACKGROUND = "BACKGROUND"


# ==========================================================
# HARD-PRIORITY INTENTS
# ==========================================================

CRITICAL_INTENTS = frozenset(
    {
        "HANDLE_ERROR",
        "REPAIR",
        "SYSTEM_ALERT",
    }
)


# ==========================================================
# ADAPTIVE PRIORITY ENGINE
# ==========================================================

class AdaptivePriorityEngine:

    VERSION = "2.0.0"
    NAME = "AdaptivePriorityEngine"

    def __init__(
        self,
        *,
        memory_system=None,
        boost_factor: float = 1.2,
        decay_factor: float = 0.95,
        history_size: int = 100,
        max_intent_score: float = 10.0,
        growth_tree=None,
        intent_engine=None,
    ):
       

        # --------------------------------------------------
        # Optional memory provider.
        # --------------------------------------------------

        self.memory_system = memory_system
        self.growth_tree = growth_tree
        self.intent_engine = intent_engine
        self.skill_registry = None

        # --------------------------------------------------
        # Intent / skill scoring.
        # --------------------------------------------------

        self.skill_scores = defaultdict(float)

        # --------------------------------------------------
        # Intent scoring.
        # --------------------------------------------------

        self.intent_scores = defaultdict(float)

        # --------------------------------------------------
        # Recent behavior tracking.
        # --------------------------------------------------

        self.recent_intents = deque(
            maxlen=max(
                1,
                int(history_size),
            )
        )

        # --------------------------------------------------
        # Learning parameters.
        # --------------------------------------------------

        try:
            boost_factor = float(
                boost_factor
            )
        except (
            TypeError,
            ValueError,
        ):
            boost_factor = 1.2

        try:
            decay_factor = float(
                decay_factor
            )
        except (
            TypeError,
            ValueError,
        ):
            decay_factor = 0.95

        self.boost_factor = max(
            0.0,
            boost_factor,
        )

        self.decay_factor = max(
            0.0,
            min(
                1.0,
                decay_factor,
            ),
        )

        self.max_intent_score = max(
            1.0,
            float(max_intent_score),
        )

        # --------------------------------------------------
        # Diagnostics.
        # --------------------------------------------------

        self.learn_count = 0
        self.priority_count = 0

        self.last_intent: Optional[str] = None
        self.last_priority: Optional[str] = None
        self.last_score = 0.0
        self.last_error = None

        # --------------------------------------------------
        # Thread safety.
        #
        # The engine does not create threads, but multiple
        # SEED components may call it concurrently.
        # --------------------------------------------------

        self._lock = threading.RLock()

        log.info(
            "[AdaptivePriorityEngine] initialized | "
            "version=%s | "
            "decay=%.3f | "
            "boost=%.3f",
            self.VERSION,
            self.decay_factor,
            self.boost_factor,
        )

    # ======================================================
    # QBIT VALUE ACCESS
    # ======================================================

    @staticmethod
    def _get_value(
        qbit: Any,
        key: str,
        default=None,
    ):
      

        if qbit is None:
            return default

        # --------------------------------------------------
        # Dictionary-style Qbit.
        # --------------------------------------------------

        if isinstance(
            qbit,
            dict,
        ):

            if key in qbit:
                return qbit.get(
                    key,
                    default,
                )

            metadata = qbit.get(
                "metadata"
            )

            if isinstance(
                metadata,
                dict,
            ):

                return metadata.get(
                    key,
                    default,
                )

            return default

        # --------------------------------------------------
        # Object-style Qbit.
        # --------------------------------------------------

        try:

            value = getattr(
                qbit,
                key,
                default,
            )

            if value is not None:
                return value

        except Exception:
            pass

        # --------------------------------------------------
        # Optional metadata fallback.
        # --------------------------------------------------

        try:

            metadata = getattr(
                qbit,
                "metadata",
                None,
            )

            if isinstance(
                metadata,
                dict,
            ):

                return metadata.get(
                    key,
                    default,
                )

        except Exception:
            pass

        return default

    # ======================================================
    # INTENT NORMALIZATION
    # ======================================================

    @staticmethod
    def _normalize_intent(
        intent,
    ) -> Optional[str]:
        

        if intent is None:
            return None

        try:
            intent = str(
                intent
            ).strip()

        except Exception:
            return None

        if not intent:
            return None

        return intent.upper()

    # ======================================================
    # UPDATE LEARNING FROM FLOW
    # ======================================================

    def learn(
        self,
        qbit,
    ) -> Optional[float]:
        

        intent = self._normalize_intent(
            self._get_value(
                qbit,
                "intent",
            )
        )
        skill = self._normalize_skill(
            self._get_value(qbit, "skill")
        )

        if not intent and not skill:
            return None

        if skill:
            self.learn_skill(skill)

        if not intent:
            return self.get_skill_score(skill)

        with self._lock:

            self.recent_intents.append(
                intent
            )

            # ----------------------------------------------
            # Reinforce the active intent.
            # ----------------------------------------------

            reinforcement = (
                0.1
                * self.boost_factor
            )

            self.intent_scores[
                intent
            ] += reinforcement

            # ----------------------------------------------
            # Decay all learned intents.
            # ----------------------------------------------

            for key in list(
                self.intent_scores.keys()
            ):

                self.intent_scores[
                    key
                ] *= self.decay_factor

                # ------------------------------------------
                # Remove negligible scores.
                # ------------------------------------------

                if (
                    self.intent_scores[key]
                    < 0.0001
                ):

                    del self.intent_scores[
                        key
                    ]

            # ----------------------------------------------
            # Bound the active score.
            # ----------------------------------------------

            if intent in self.intent_scores:

                self.intent_scores[
                    intent
                ] = min(
                    self.max_intent_score,
                    max(
                        0.0,
                        self.intent_scores[
                            intent
                        ],
                    ),
                )

            self.learn_count += 1
            self.last_intent = intent
            self.last_error = None

            score = self.intent_scores.get(
                intent,
                0.0,
            )

        log.debug(
            "[AdaptivePriorityEngine] "
            "learn | intent=%s | score=%.4f",
            intent,
            score,
        )

        return score

    # ======================================================
    # SKILL INTEGRATION
    # ======================================================

    @staticmethod
    def _normalize_skill(skill):
        if skill is None:
            return None
        try:
            value = str(skill).strip()
        except Exception:
            return None
        return value.upper() if value else None

    def bind_skill_registry(self, skill_registry=None):
        if skill_registry is not None:
            self.skill_registry = skill_registry
        return self

    def learn_skill(self, skill, weight=None):
        skill = self._normalize_skill(skill)
        if not skill:
            return None
        try:
            increment = 0.1 * self.boost_factor if weight is None else float(weight)
        except (TypeError, ValueError):
            increment = 0.1 * self.boost_factor
        with self._lock:
            self.skill_scores[skill] += max(0.0, increment)
            for key in list(self.skill_scores):
                self.skill_scores[key] *= self.decay_factor
                if self.skill_scores[key] < 0.0001:
                    del self.skill_scores[key]
            if skill in self.skill_scores:
                self.skill_scores[skill] = min(self.max_intent_score, max(0.0, self.skill_scores[skill]))
            return float(self.skill_scores.get(skill, 0.0))

    def get_skill_score(self, skill):
        skill = self._normalize_skill(skill)
        if not skill:
            return 0.0
        with self._lock:
            return float(self.skill_scores.get(skill, 0.0))

    # ======================================================
    # INTENT / GROWTH INTEGRATION
    # ======================================================

    def bind_intent_growth(
        self,
        *,
        intent_engine=None,
        growth_tree=None,
    ):
        if intent_engine is not None:
            self.intent_engine = intent_engine

        if growth_tree is not None:
            self.growth_tree = growth_tree

        return self

    def record_intent(
        self,
        intent_result,
        *,
        source="AdaptivePriorityEngine",
        qbit=None,
    ):
        if not isinstance(intent_result, dict):
            return False

        intent = self._normalize_intent(
            intent_result.get("intent")
            or intent_result.get("dominant")
        )

        if intent:
            learning_qbit = qbit
            if learning_qbit is None:
                learning_qbit = {"intent": intent}
            self.learn(learning_qbit)

        growth_tree = self.growth_tree
        if growth_tree is not None:
            try:
                growth_tree.record_intent(
                    intent_result,
                    source=source,
                    qbit=qbit,
                )
            except Exception as exc:
                self.last_error = (
                    f"growth intent record failed: {exc}"
                )
                log.debug(
                    "[AdaptivePriorityEngine] "
                    "growth intent record unavailable: %s",
                    exc,
                )

        return bool(intent)

    # ======================================================
    # MEMORY WEIGHT
    # ======================================================

    def _memory_weight(
        self,
        intent: str,
    ) -> float:
        

        memory = self.memory_system

        if memory is None:
            return 0.0

        try:

            getter = getattr(
                memory,
                "get_weight",
                None,
            )

            if not callable(getter):
                return 0.0

            value = getter(
                intent
            )

            try:
                return float(
                    value
                )
            except (
                TypeError,
                ValueError,
            ):
                return 0.0

        except Exception as exc:

            self.last_error = (
                f"memory weight failed: {exc}"
            )

            log.debug(
                "[AdaptivePriorityEngine] "
                "memory weight unavailable: %s",
                exc,
            )

            return 0.0

    # ======================================================
    # DECIDE PRIORITY
    # ======================================================

    def get_priority(
        self,
        qbit,
    ) -> str:
        

        intent = self._normalize_intent(
            self._get_value(
                qbit,
                "intent",
            )
        )

        # --------------------------------------------------
        # No intent.
        # --------------------------------------------------

        if not intent:

            with self._lock:

                self.priority_count += 1
                self.last_intent = None
                self.last_score = 0.0
                self.last_priority = (
                    PriorityLevel.BACKGROUND
                )

            return PriorityLevel.BACKGROUND

        # --------------------------------------------------
        # HARD SAFETY RULES FIRST.
        # --------------------------------------------------

        if intent in CRITICAL_INTENTS:

            with self._lock:

                self.priority_count += 1
                self.last_intent = intent
                self.last_score = (
                    self.intent_scores.get(
                        intent,
                        0.0,
                    )
                )
                self.last_priority = (
                    PriorityLevel.CRITICAL
                )
                self.last_error = None

            return PriorityLevel.CRITICAL

        # --------------------------------------------------
        # Adaptive score.
        # --------------------------------------------------

        with self._lock:

            score = self.intent_scores.get(
                intent,
                0.0,
            )

        # --------------------------------------------------
        # Memory influence.
        #
        # Memory contributes to scoring but does not bypass
        # hard safety rules.
        # --------------------------------------------------

        memory_weight = self._memory_weight(
            intent
        )

        score += memory_weight
        skill = self._normalize_skill(
            self._get_value(qbit, "skill")
        )
        if skill:
            score += self.get_skill_score(skill)

        # --------------------------------------------------
        # Priority decision.
        # --------------------------------------------------

        if score > 2.0:

            priority = (
                PriorityLevel.CRITICAL
            )

        elif score > 0.8:

            priority = (
                PriorityLevel.NORMAL
            )

        else:

            priority = (
                PriorityLevel.BACKGROUND
            )

        with self._lock:

            self.priority_count += 1

            self.last_intent = intent
            self.last_score = score
            self.last_priority = priority

        log.debug(
            "[AdaptivePriorityEngine] "
            "priority | intent=%s | "
            "score=%.4f | memory=%.4f | "
            "priority=%s",
            intent,
            score,
            memory_weight,
            priority,
        )

        return priority

    # ======================================================
    # SCORE QUERY
    # ======================================================

    def get_score(
        self,
        intent: str,
    ) -> float:
        

        intent = self._normalize_intent(
            intent
        )

        if not intent:
            return 0.0

        with self._lock:

            return float(
                self.intent_scores.get(
                    intent,
                    0.0,
                )
            )

    # ======================================================
    # MEMORY-AWARE SCORE
    # ======================================================

    def get_effective_score(
        self,
        intent: str,
    ) -> float:
        

        intent = self._normalize_intent(
            intent
        )

        if not intent:
            return 0.0

        return (
            self.get_score(intent)
            + self._memory_weight(intent)
        )

    # ======================================================
    # RESET
    # ======================================================

    def reset(
        self,
        intent: Optional[str] = None,
    ) -> None:
       

        with self._lock:

            if intent is None:

                self.intent_scores.clear()
                self.recent_intents.clear()

            else:

                normalized = (
                    self._normalize_intent(
                        intent
                    )
                )

                if normalized:

                    self.intent_scores.pop(
                        normalized,
                        None,
                    )

                    self.recent_intents = deque(
                        (
                            value
                            for value in self.recent_intents
                            if value
                            != normalized
                        ),
                        maxlen=(
                            self.recent_intents.maxlen
                        ),
                    )

            self.last_intent = None
            self.last_priority = None
            self.last_score = 0.0
            self.last_error = None

        log.info(
            "[AdaptivePriorityEngine] reset | "
            "intent=%s",
            intent if intent else "ALL",
        )

    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def diagnostics(
        self,
    ) -> Dict[str, Any]:
        

        with self._lock:

            scores = dict(
                self.intent_scores
            )

            recent = list(
                self.recent_intents
            )

            return {
                "name": self.NAME,
                "version": self.VERSION,
                "intent_count": len(
                    scores
                ),
                "recent_count": len(
                    recent
                ),
                "intent_scores": scores,
                "skill_scores": dict(self.skill_scores),
                "recent_intents": recent,
                "boost_factor": (
                    self.boost_factor
                ),
                "decay_factor": (
                    self.decay_factor
                ),
                "max_intent_score": (
                    self.max_intent_score
                ),
                "learn_count": (
                    self.learn_count
                ),
                "priority_count": (
                    self.priority_count
                ),
                "last_intent": (
                    self.last_intent
                ),
                "last_priority": (
                    self.last_priority
                ),
                "last_score": (
                    self.last_score
                ),
                "memory_system": (
                    self.memory_system is not None
                ),
                "last_error": (
                    self.last_error
                ),
            }

    # ======================================================
    # STATUS ALIAS
    # ======================================================

    def status(
        self,
    ) -> Dict[str, Any]:

        return self.diagnostics()

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(
        self,
    ) -> str:

        with self._lock:

            return (
                "AdaptivePriorityEngine("
                f"version={self.VERSION!r}, "
                f"intents="
                f"{len(self.intent_scores)}, "
                f"learn_count="
                f"{self.learn_count}, "
                f"priority_count="
                f"{self.priority_count}"
                ")"
            )


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "PriorityLevel",
    "AdaptivePriorityEngine",
]