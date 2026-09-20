# ==========================================================
# FILE: memory_weighting.py
# PATH: SEED_ROOT/seed/core/cognition/memory_weighting.py
#
# VERSION: 2.0.0
# BUILD: PASSIVE-LEARNING / QBIT-SAFE / BOOT-SAFE /
#        THREAD-SAFE / BOUNDED-MEMORY / SYSTEM-SYNC
#
# PURPOSE:
# - Learn importance/strength of recurring Qbit intents
# - Provide memory influence to AdaptivePriorityEngine
# - Accept both dict-style and object-style Qbits
# - Reinforce active cognitive patterns
# - Apply controlled decay to inactive patterns
# - Prevent unbounded memory growth
# - Remain completely passive during boot
# - Never start background threads automatically
# - Never write directly to QbitQueueLoop
# - Never interfere with Heartbeat or Qbit control
#
# SYSTEM POSITION:
#
#       Qbit
#         |
#         v
#   CognitionMap
#         |
#         v
#   MemoryWeightingSystem
#         |
#         +------> AdaptivePriorityEngine
#         |
#         +------> CognitiveGovernor
#         |
#         v
#      cognition
#
# IMPORTANT:
# - This module is a LEARNING RESOURCE.
# - It is NOT an autonomous scheduler.
# - It is NOT a queue worker.
# - It does NOT start during import.
# - It does NOT create threads.
# - It does NOT inject Qbits.
# - It does NOT control system boot.
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, Optional


log = logging.getLogger("MemoryWeighting")


# ==========================================================
# STATUS MODES
# ==========================================================

class MemoryWeightingMode:

    IDLE = "idle"
    LEARNING = "learning"
    STABLE = "stable"
    PRESSURE = "pressure"
    PAUSED = "paused"
    SHUTDOWN = "shutdown"


# ==========================================================
# MEMORY WEIGHTING SYSTEM
# ==========================================================

class MemoryWeightingSystem:

    VERSION = "2.0.0"

    def __init__(
        self,
        *,
        reinforce_value: float = 0.2,
        decay_rate: float = 0.98,
        time_factor: float = 0.001,
        max_weight: float = 10.0,
        max_intents: int = 5000,
        min_retained_weight: float = 0.0001,
        decay_interval: float = 1.0,
    ):
        # --------------------------------------------------
        # Configuration
        # --------------------------------------------------

        self.reinforce_value = max(
            0.0,
            float(reinforce_value),
        )

        self.decay_rate = min(
            1.0,
            max(0.0, float(decay_rate)),
        )

        self.time_factor = max(
            0.0,
            float(time_factor),
        )

        self.max_weight = max(
            0.1,
            float(max_weight),
        )

        self.max_intents = max(
            10,
            int(max_intents),
        )

        self.min_retained_weight = max(
            0.0,
            float(min_retained_weight),
        )

        self.decay_interval = max(
            0.1,
            float(decay_interval),
        )

        # --------------------------------------------------
        # Learned memory
        # --------------------------------------------------

        self.weights = defaultdict(float)

        self.last_seen: Dict[str, float] = {}

        self.observation_count: Dict[str, int] = defaultdict(int)

        # --------------------------------------------------
        # Runtime state
        # --------------------------------------------------

        self._lock = threading.RLock()

        self._mode = MemoryWeightingMode.IDLE

        self._paused = False
        self._shutdown = False

        self.started_at = time.time()
        self.last_update = 0.0

        # --------------------------------------------------
        # Diagnostics
        # --------------------------------------------------

        self.total_updates = 0
        self.accepted_updates = 0
        self.rejected_updates = 0
        self.decay_operations = 0
        self.evictions = 0

        self.last_intent: Optional[str] = None
        self.last_reason = "initialization"

        # --------------------------------------------------
        # No thread.
        #
        # No timer.
        #
        # No queue connection.
        #
        # No autonomous startup.
        #
        # This is intentional.
        # --------------------------------------------------

        log.info(
            "[MemoryWeighting] Initialized | "
            f"version={self.VERSION} | "
            f"reinforce={self.reinforce_value:.3f} | "
            f"decay={self.decay_rate:.4f} | "
            f"max_intents={self.max_intents} | "
            "mode=idle | boot_safe=True"
        )

    # ======================================================
    # STATUS
    # ======================================================

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    def get_mode(self) -> str:
        return self.mode

    def set_mode(self, mode: str) -> str:

        mode = str(mode).lower().strip()

        valid = {
            MemoryWeightingMode.IDLE,
            MemoryWeightingMode.LEARNING,
            MemoryWeightingMode.STABLE,
            MemoryWeightingMode.PRESSURE,
            MemoryWeightingMode.PAUSED,
            MemoryWeightingMode.SHUTDOWN,
        }

        if mode not in valid:
            mode = MemoryWeightingMode.IDLE

        with self._lock:
            self._mode = mode

        return mode

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def pause(self) -> None:
       

        with self._lock:
            self._paused = True
            self._mode = MemoryWeightingMode.PAUSED
            self.last_reason = "manual_pause"

        log.info("[MemoryWeighting] Learning paused")

    def resume(self) -> None:
        

        with self._lock:

            if self._shutdown:
                return

            self._paused = False
            self._mode = MemoryWeightingMode.STABLE
            self.last_reason = "manual_resume"

        log.info("[MemoryWeighting] Learning resumed")

    def shutdown(self, reason: str = "shutdown_requested") -> None:
        

        with self._lock:
            self._shutdown = True
            self._paused = True
            self._mode = MemoryWeightingMode.SHUTDOWN
            self.last_reason = str(reason)

        log.info(
            "[MemoryWeighting] Shutdown | reason=%s",
            reason,
        )

    def reset_runtime(self) -> None:
        

        with self._lock:

            self._shutdown = False
            self._paused = False
            self._mode = MemoryWeightingMode.STABLE
            self.last_reason = "runtime_reset"

        log.info("[MemoryWeighting] Runtime reset")

    # ======================================================
    # QBIT EXTRACTION
    # ======================================================

    @staticmethod
    def _extract_intent(qbit: Any) -> Optional[str]:
       

        if qbit is None:
            return None

        try:

            if isinstance(qbit, dict):

                intent = qbit.get(
                    "intent",
                    None,
                )

                if intent is None:

                    metadata = qbit.get(
                        "metadata",
                        {},
                    )

                    if isinstance(
                        metadata,
                        dict,
                    ):
                        intent = metadata.get(
                            "intent"
                        )

            else:

                intent = getattr(
                    qbit,
                    "intent",
                    None,
                )

                if intent is None:

                    payload = getattr(
                        qbit,
                        "payload",
                        None,
                    )

                    if isinstance(
                        payload,
                        dict,
                    ):
                        intent = payload.get(
                            "intent"
                        )

            if intent is None:
                return None

            if callable(intent):
                return None

            intent = str(intent).strip()

            if not intent:
                return None

            return intent

        except Exception:
            return None

    # ======================================================
    # UPDATE MEMORY
    # ======================================================

    def update(
        self,
        qbit: Any,
    ) -> Optional[float]:
        

        with self._lock:

            self.total_updates += 1

            if self._shutdown:
                self.rejected_updates += 1
                self.last_reason = "shutdown"
                return None

            if self._paused:
                self.rejected_updates += 1
                self.last_reason = "paused"
                return None

            intent = self._extract_intent(qbit)

            if not intent:
                self.rejected_updates += 1
                self.last_reason = "missing_intent"
                return None

            now = time.time()

            previous_seen = self.last_seen.get(
                intent,
                now,
            )

            delta = max(
                0.0,
                now - previous_seen,
            )

            # --------------------------------------------------
            # Reinforcement
            # --------------------------------------------------

            boost = (
                self.reinforce_value
                + (
                    delta
                    * self.time_factor
                )
            )

            current = self.weights.get(
                intent,
                0.0,
            )

            new_weight = min(
                current + boost,
                self.max_weight,
            )

            self.weights[intent] = new_weight

            self.last_seen[intent] = now

            self.observation_count[intent] += 1

            self.last_intent = intent
            self.last_update = now

            self.accepted_updates += 1

            self._mode = MemoryWeightingMode.LEARNING
            self.last_reason = "qbit_observed"

            # --------------------------------------------------
            # Decay inactive memory.
            #
            # Only the current intent is reinforced.
            # --------------------------------------------------

            self._decay_locked(
                active_intent=intent,
            )

            # --------------------------------------------------
            # Bound memory.
            # --------------------------------------------------

            self._enforce_memory_limit_locked()

            self._mode = MemoryWeightingMode.STABLE

            return self.weights.get(
                intent,
                0.0,
            )

    # ======================================================
    # DECAY
    # ======================================================

    def decay(self) -> None:
        

        with self._lock:

            if self._shutdown:
                return

            if self._paused:
                return

            self._decay_locked()

            self._enforce_memory_limit_locked()

    def _decay_locked(
        self,
        active_intent: Optional[str] = None,
    ) -> None:

        for intent in list(
            self.weights.keys()
        ):

            if (
                active_intent is not None
                and intent == active_intent
            ):
                continue

            self.weights[intent] *= (
                self.decay_rate
            )

            if (
                self.weights[intent]
                < self.min_retained_weight
            ):

                del self.weights[intent]

                self.last_seen.pop(
                    intent,
                    None,
                )

                self.observation_count.pop(
                    intent,
                    None,
                )

                self.evictions += 1

        self.decay_operations += 1

    # ======================================================
    # MEMORY LIMIT
    # ======================================================

    def _enforce_memory_limit_locked(self) -> None:

        if len(self.weights) <= self.max_intents:
            return

        overflow = (
            len(self.weights)
            - self.max_intents
        )

        # Remove the weakest learned intents first.
        weakest = sorted(
            self.weights.items(),
            key=lambda item: item[1],
        )[:overflow]

        for intent, _ in weakest:

            self.weights.pop(
                intent,
                None,
            )

            self.last_seen.pop(
                intent,
                None,
            )

            self.observation_count.pop(
                intent,
                None,
            )

            self.evictions += 1

    # ======================================================
    # GET IMPORTANCE SCORE
    # ======================================================

    def get_weight(
        self,
        intent: Any,
    ) -> float:

        if intent is None:
            return 0.0

        try:
            key = str(intent).strip()
        except Exception:
            return 0.0

        if not key:
            return 0.0

        with self._lock:

            return float(
                self.weights.get(
                    key,
                    0.0,
                )
            )

    # ======================================================
    # SET WEIGHT
    # ======================================================

    def set_weight(
        self,
        intent: Any,
        weight: float,
    ) -> float:

        if intent is None:
            return 0.0

        try:
            key = str(intent).strip()
            value = float(weight)
        except Exception:
            return 0.0

        if not key:
            return 0.0

        value = max(
            0.0,
            min(
                value,
                self.max_weight,
            ),
        )

        with self._lock:

            self.weights[key] = value
            self.last_seen[key] = time.time()

            self._enforce_memory_limit_locked()

        return value

    # ======================================================
    # FORGET INTENT
    # ======================================================

    def forget(
        self,
        intent: Any,
    ) -> bool:

        if intent is None:
            return False

        try:
            key = str(intent).strip()
        except Exception:
            return False

        if not key:
            return False

        with self._lock:

            existed = key in self.weights

            self.weights.pop(
                key,
                None,
            )

            self.last_seen.pop(
                key,
                None,
            )

            self.observation_count.pop(
                key,
                None,
            )

            if existed:
                self.evictions += 1
                self.last_reason = (
                    "intent_forgotten"
                )

            return existed

    # ======================================================
    # TOP MEMORIES
    # ======================================================

    def top_weights(
        self,
        limit: int = 10,
    ):

        try:
            limit = max(
                1,
                int(limit),
            )
        except Exception:
            limit = 10

        with self._lock:

            return sorted(
                self.weights.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:limit]

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def snapshot(self) -> Dict[str, float]:

        with self._lock:
            return dict(
                self.weights
            )

    # ======================================================
    # STATISTICS
    # ======================================================

    def stats(self) -> Dict[str, Any]:

        with self._lock:

            return {
                "version": self.VERSION,
                "mode": self._mode,
                "active": (
                    not self._paused
                    and not self._shutdown
                ),
                "intent_count": len(
                    self.weights
                ),
                "max_intents": (
                    self.max_intents
                ),
                "total_updates": (
                    self.total_updates
                ),
                "accepted_updates": (
                    self.accepted_updates
                ),
                "rejected_updates": (
                    self.rejected_updates
                ),
                "decay_operations": (
                    self.decay_operations
                ),
                "evictions": (
                    self.evictions
                ),
                "last_intent": (
                    self.last_intent
                ),
                "last_update": (
                    self.last_update
                ),
                "last_reason": (
                    self.last_reason
                ),
                "top_weights": self.top_weights(
                    10
                ),
            }

    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def diagnostics(self) -> Dict[str, Any]:

        with self._lock:

            return {
                "component": (
                    "MemoryWeightingSystem"
                ),
                "version": self.VERSION,
                "mode": self._mode,
                "paused": self._paused,
                "shutdown": self._shutdown,
                "uptime": round(
                    time.time()
                    - self.started_at,
                    2,
                ),
                "intent_count": len(
                    self.weights
                ),
                "max_intents": (
                    self.max_intents
                ),
                "total_updates": (
                    self.total_updates
                ),
                "accepted_updates": (
                    self.accepted_updates
                ),
                "rejected_updates": (
                    self.rejected_updates
                ),
                "decay_operations": (
                    self.decay_operations
                ),
                "evictions": (
                    self.evictions
                ),
                "last_intent": (
                    self.last_intent
                ),
                "last_reason": (
                    self.last_reason
                ),
                "boot_safe": True,
                "autonomous_thread": False,
                "queue_injection": False,
            }

    # ======================================================
    # CLEAR MEMORY
    # ======================================================

    def clear(
        self,
        reason: str = "manual_clear",
    ) -> None:

        with self._lock:

            self.weights.clear()
            self.last_seen.clear()
            self.observation_count.clear()

            self.last_intent = None
            self.last_reason = str(reason)

            self._mode = (
                MemoryWeightingMode.IDLE
            )

        log.info(
            "[MemoryWeighting] Memory cleared | "
            "reason=%s",
            reason,
        )

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(self) -> str:

        with self._lock:

            return (
                "MemoryWeightingSystem("
                f"version={self.VERSION}, "
                f"mode={self._mode}, "
                f"intents={len(self.weights)}, "
                f"paused={self._paused}, "
                f"shutdown={self._shutdown}"
                ")"
            )


# ==========================================================
# COMPATIBILITY ALIAS
# ==========================================================

MemoryWeighting = MemoryWeightingSystem


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "MemoryWeightingMode",
    "MemoryWeightingSystem",
    "MemoryWeighting",
]