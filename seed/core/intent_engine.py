# ==========================================================
# FILE: intent_engine.py
# PATH: C:\SEED_ROOT\seed\core\intent\intent_engine.py
# VERSION: 10.1.0
#
# SEED AI OS — DYNAMIC INTENT ENGINE
#
# BUILD:
# FULL-MERGE / AUTHORITATIVE-QBIT / SINGLE-RUNTIME
# QBIT-INTEGRATED / EVENTBUS-SAFE / TRACK-SAFE
# ENCODED-INTENT / DYNAMIC-INTENT
# UNIQUE-INTENT-QBIT / PARENT-LINEAGE-SAFE
#
# AUTHORITY:
#
# IntentEngine
# measures and packages INTENT
#
# Qbit
# carries INTENT + cognitive context
#
# QbitQueueLoop
# transports the Qbit
#
# QbitDialer
# receives/processes the Qbit
#
# ComputeBrain
# computes the Qbit
#
# TransformerBrain
# transforms ThoughtPacket into a command proposal
#
# QbitDialer
# remains the ONLY command authority
#
# IMPORTANT:
#
# IntentEngine NEVER:
# - starts QbitDialer
# - executes commands
# - submits commands
# - owns command_queue
# - creates QbitQueueLoop
# - creates another runtime
# - replaces the authoritative runtime Qbit
#
# IntentEngine MAY:
# - score intent
# - create its module-level cognitive Qbit
# - annotate the Intent Qbit
# - encode the Intent Qbit
# - emit INTENT events
# - provide intent context to the cognitive pipeline
#
# QBIT LINEAGE:
#
# authoritative runtime Qbit
#          |
#          | parent_id / source_qbit_id
#          v
# new Intent Qbit
#          |
#          v
# authoritative QbitQueueLoop
#          |
#          v
# QbitDialer
#
# A source/runtime Qbit is NEVER reused as the newly-created
# Intent Qbit. This prevents duplicate admission caused by
# changing the track_id while retaining the same qbit_id.
# ==========================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import threading
import time
import uuid

from copy import deepcopy

from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
)

logger = logging.getLogger("IntentEngine")


# ==========================================================
# EVENTS
# ==========================================================

INTENT_UPDATED = "INTENT_UPDATED"
INTENT_SCORED = "INTENT_SCORED"
INTENT_QBIT_CREATED = "INTENT_QBIT_CREATED"
INTENT_QBIT_ROUTED = "INTENT_QBIT_ROUTED"


# ==========================================================
# INTENTS
# ==========================================================

DEFAULT_INTENTS = (
    "IDLE",
    "OBSERVE",
    "PROCESS",
    "ANALYZE",
    "RESPOND",
    "RECOVER",
    "HANDLE_ERROR",
)

INTENT_STATE = {
    name: name
    for name in DEFAULT_INTENTS
}

SYSTEM_ACTION = {
    name: name
    for name in DEFAULT_INTENTS
}


# ==========================================================
# SENSOR WEIGHTS
# ==========================================================

DEFAULT_WEIGHTS = {
    "seed": 1.00,
    "user": 1.25,
    "noise": -0.75,
    "audio": 0.80,
    "vision": 0.80,
    "resonance": 1.00,
}


# ==========================================================
# INTENT TRANSITION WEIGHTS
#
# These provide temporal stability without freezing intent.
# ==========================================================

DEFAULT_TRANSITIONS = {
    "IDLE": {
        "OBSERVE": 0.04,
        "PROCESS": 0.02,
        "ANALYZE": 0.01,
        "RESPOND": 0.01,
        "RECOVER": 0.03,
        "HANDLE_ERROR": 0.00,
    },
    "OBSERVE": {
        "OBSERVE": 0.08,
        "PROCESS": 0.05,
        "ANALYZE": 0.07,
        "RESPOND": 0.04,
        "RECOVER": 0.01,
        "HANDLE_ERROR": 0.01,
    },
    "PROCESS": {
        "OBSERVE": 0.03,
        "PROCESS": 0.09,
        "ANALYZE": 0.08,
        "RESPOND": 0.05,
        "RECOVER": 0.01,
        "HANDLE_ERROR": 0.02,
    },
    "ANALYZE": {
        "OBSERVE": 0.03,
        "PROCESS": 0.07,
        "ANALYZE": 0.10,
        "RESPOND": 0.07,
        "RECOVER": 0.01,
        "HANDLE_ERROR": 0.02,
    },
    "RESPOND": {
        "OBSERVE": 0.03,
        "PROCESS": 0.04,
        "ANALYZE": 0.05,
        "RESPOND": 0.10,
        "RECOVER": 0.02,
        "HANDLE_ERROR": 0.01,
    },
    "RECOVER": {
        "OBSERVE": 0.04,
        "PROCESS": 0.02,
        "ANALYZE": 0.01,
        "RESPOND": 0.01,
        "RECOVER": 0.12,
        "HANDLE_ERROR": 0.08,
    },
    "HANDLE_ERROR": {
        "OBSERVE": 0.01,
        "PROCESS": 0.01,
        "ANALYZE": 0.03,
        "RESPOND": 0.02,
        "RECOVER": 0.10,
        "HANDLE_ERROR": 0.14,
    },
}


# ==========================================================
# SAFE NUMERIC HELPERS
# ==========================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        value = float(value)

        if not math.isfinite(value):
            return default

        return value

    except (
        TypeError,
        ValueError,
    ):
        return default


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 1.0,
) -> float:
    return max(
        low,
        min(
            high,
            _safe_float(value),
        ),
    )


# ==========================================================
# OPTIONAL QBIT IMPORT
#
# Boot-safe.
# ==========================================================

try:
    from seed.core.qbit.qbit import Qbit
except Exception:
    Qbit = None


# ==========================================================
# OPTIONAL ENCODER
#
# Uses the existing SEED Qbit binary encoder.
# ==========================================================

try:
    from seed.core.cognition.qbit_binary_encoder import (
        QbitBinaryEncoder,
    )
except Exception:
    QbitBinaryEncoder = None


# ==========================================================
# TRACK ID
# ==========================================================

def _generate_intent_track_id() -> str:
    return (
        "INTENT_"
        "QBIT_"
        f"{uuid.uuid4().hex[:12].upper()}"
    )


# ==========================================================
# INTENT ENGINE
# ==========================================================

class IntentEngine:

    # ======================================================
    # CONSTRUCTOR
    # ======================================================

    def __init__(
        self,
        *,
        emit=None,
        event_bus=None,
        qbit=None,
        qbit_queue_loop=None,
        qbit_dialer=None,
        heartbeat=None,
        track_system=None,
        track_context=None,
        registry=None,
        system_registry=None,
        node_registry=None,
        nodes=None,
        kernel_bus=None,
        fathud=None,
        fat_layer=None,
        encoder=None,
        intents: Optional[Iterable[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        history_size: int = 512,
        momentum: float = 0.18,
    ):

        self.emit = emit

        self.event_bus = event_bus

        # --------------------------------------------------
        # IMPORTANT:
        #
        # self.qbit is the authoritative runtime/source Qbit.
        # It is NOT replaced when an Intent Qbit is created.
        # --------------------------------------------------

        self.qbit = qbit

        self.qbit_dialer = qbit_dialer
        self.queue_loop = qbit_queue_loop
        self.adaptive_priority_engine = None
        self.growth_tree = None
        self.track_system = track_system
        self.track_context = track_context
        self.heartbeat = heartbeat
        self.registry = registry
        self.system_registry = system_registry
        self.node_registry = node_registry or nodes
        self.nodes = nodes or node_registry
        self.fat_layer = fat_layer
        self.fathud = fathud
        self.kernel_bus = kernel_bus

        # --------------------------------------------------
        # Encoder belongs to the data boundary.
        # --------------------------------------------------

        self.encoder = encoder

        if self.encoder is None:
            try:
                if QbitBinaryEncoder is not None:
                    self.encoder = QbitBinaryEncoder()
            except Exception:
                self.encoder = None

        self.intents = tuple(
            intents
            if intents is not None
            else DEFAULT_INTENTS
        )

        self.weights = dict(
            DEFAULT_WEIGHTS
        )

        if weights:
            self.weights.update(
                weights
            )

        self.transitions = deepcopy(
            DEFAULT_TRANSITIONS
        )

        self.history_size = max(
            1,
            int(history_size),
        )

        self.momentum = _clamp(
            momentum,
            0.0,
            0.95,
        )

        self._history: List[
            Dict[str, Any]
        ] = []

        self._lock = threading.RLock()

        self._sequence = 0

        self._last_scores: Dict[
            str,
            float,
        ] = {}

        self._last_dominant = "IDLE"

        self._previous_dominant = "IDLE"

        self._last_resonance = 0.0

        self._last_sensors: Dict[
            str,
            float,
        ] = {}

        self._last_result: Optional[
            Dict[str, Any]
        ] = None

        # --------------------------------------------------
        # Last CREATED Intent Qbit.
        #
        # This is intentionally separate from self.qbit.
        # --------------------------------------------------

        self._last_qbit = None

        self._last_encoded_qbit = None

        self._intent_qbit_sequence = 0

        self.operational = True

        logger.info(
            "[IntentEngine] Initialized | "
            "intents=%d | encoder=%s | "
            "qbit=%s | dialer=%s",
            len(self.intents),
            type(self.encoder).__name__
            if self.encoder is not None
            else "NONE",
            type(self.qbit).__name__
            if self.qbit is not None
            else "NONE",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer is not None
            else "NONE",
        )

    # ======================================================
    # RUNTIME BINDING
    # ======================================================

    def bind_runtime(
        self,
        *,
        emit=None,
        event_bus=None,
        qbit=None,
        qbit_queue_loop=None,
        qbit_dialer=None,
        track_system=None,
        encoder=None,
        node_registry=None,
        nodes=None,
    ):

        if emit is not None:
            self.emit = emit

        if event_bus is not None:
            self.event_bus = event_bus

        if qbit_queue_loop is not None:
            self.queue_loop = qbit_queue_loop

        if qbit is not None:
            self.qbit = qbit

        if qbit_dialer is not None:
            self.qbit_dialer = qbit_dialer

        if track_system is not None:
            self.track_system = track_system

        if node_registry is not None:
            self.node_registry = node_registry
            self.nodes = node_registry
        elif nodes is not None:
            self.nodes = nodes
            self.node_registry = nodes

        if encoder is not None:
            self.encoder = encoder

        return self

    def bind_adaptive_growth(
        self,
        *,
        adaptive_priority_engine=None,
        growth_tree=None,
    ):
        if adaptive_priority_engine is not None:
            self.adaptive_priority_engine = adaptive_priority_engine

        if growth_tree is not None:
            self.growth_tree = growth_tree

        return self

    # ======================================================
    # SAFE EMIT
    # ======================================================

    def _emit(
        self,
        event: str,
        payload=None,
    ):

        if payload is None:
            payload = {}

        callback = self.emit

        if callable(callback):
            try:
                result = callback(
                    event,
                    payload,
                )

                if inspect.isawaitable(result):
                    self._schedule_awaitable(
                        result
                    )

                return result

            except Exception:
                logger.exception(
                    "[IntentEngine] emit failed | "
                    "event=%s",
                    event,
                )

        bus = self.event_bus

        if bus is None:
            return None

        for name in (
            "publish",
            "emit",
            "dispatch",
            "post",
        ):

            method = getattr(
                bus,
                name,
                None,
            )

            if not callable(method):
                continue

            try:
                result = method(
                    event,
                    payload,
                )

                if inspect.isawaitable(result):
                    self._schedule_awaitable(
                        result
                    )

                return result

            except TypeError:
                try:
                    result = method(
                        event,
                        payload=payload,
                    )

                    if inspect.isawaitable(result):
                        self._schedule_awaitable(
                            result
                        )

                    return result

                except Exception:
                    continue

            except Exception:
                logger.exception(
                    "[IntentEngine] EventBus "
                    "emission failed | event=%s",
                    event,
                )

                return None

        return None

    @staticmethod
    def _schedule_awaitable(
        awaitable,
    ):

        try:
            loop = (
                asyncio
                .get_running_loop()
            )

            loop.create_task(
                awaitable
            )

        except RuntimeError:
            close = getattr(
                awaitable,
                "close",
                None,
            )

            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    # ======================================================
    # SENSOR NORMALIZATION
    # ======================================================

    def normalize_sensors(
        self,
        sensors=None,
    ) -> Dict[str, float]:

        if not isinstance(
            sensors,
            dict,
        ):
            sensors = {}

        normalized = {}

        for key, value in sensors.items():
            normalized[
                str(key)
            ] = _clamp(
                _safe_float(value)
            )

        for key in (
            "seed",
            "user",
            "noise",
            "audio",
            "vision",
        ):
            normalized.setdefault(
                key,
                0.0,
            )

        return normalized

    # ======================================================
    # RESONANCE
    # ======================================================

    def normalize_resonance(
        self,
        resonance,
    ) -> float:

        return _clamp(
            _safe_float(
                resonance
            )
        )

    # ======================================================
    # SCORE INTENTS
    # ======================================================

    def score_intents(
        self,
        resonance=0.0,
        sensors=None,
    ) -> Tuple[
        str,
        Dict[str, float],
    ]:

        resonance_value = (
            self.normalize_resonance(
                resonance
            )
        )

        normalized = (
            self.normalize_sensors(
                sensors
            )
        )

        raw_scores = (
            self._calculate_scores(
                resonance_value,
                normalized,
            )
        )

        scores = (
            self._apply_temporal_dynamics(
                raw_scores
            )
        )

        dominant = (
            self._select_dominant(
                scores
            )
        )

        previous = (
            self._last_dominant
        )

        transition = (
            self.transitions
            .get(
                previous,
                {},
            )
            .get(
                dominant,
                0.0,
            )
        )

        confidence = (
            self._calculate_confidence(
                scores,
                dominant,
                normalized,
                resonance_value,
            )
        )

        urgency = (
            self._calculate_urgency(
                dominant,
                normalized,
                resonance_value,
            )
        )

        novelty = (
            self._calculate_novelty(
                dominant
            )
        )

        stability = (
            self._calculate_stability(
                dominant
            )
        )

        ambiguity = (
            1.0
            - confidence
        )

        with self._lock:
            self._sequence += 1

            self._previous_dominant = (
                previous
            )

            self._last_dominant = (
                dominant
            )

            self._last_resonance = (
                resonance_value
            )

            self._last_sensors = dict(
                normalized
            )

            self._last_scores = dict(
                scores
            )

        result = {
            "type":
                "IntentMeasurement",

            "sequence":
                self._sequence,

            "intent":
                dominant,

            "dominant":
                dominant,

            "scores":
                dict(scores),

            "resonance":
                resonance_value,

            "confidence":
                confidence,

            "urgency":
                urgency,

            "novelty":
                novelty,

            "stability":
                stability,

            "ambiguity":
                ambiguity,

            "transition":
                transition,

            "previous_intent":
                previous,

            "sensors":
                dict(normalized),

            "timestamp":
                time.time(),
        }

        with self._lock:
            self._last_result = (
                deepcopy(result)
            )

            self._history.append(
                deepcopy(result)
            )

            if len(
                self._history
            ) > self.history_size:

                del self._history[
                    :-self.history_size
                ]

        self._emit(
            INTENT_SCORED,
            deepcopy(result),
        )

        priority_engine = getattr(
            self,
            "adaptive_priority_engine",
            None,
        )
        if priority_engine is not None:
            try:
                priority_engine.record_intent(
                    result,
                    source="IntentEngine",
                    qbit=self.qbit,
                )
            except Exception as exc:
                logger.debug(
                    "[IntentEngine] adaptive priority record unavailable | %s",
                    exc,
                )

        growth_tree = getattr(
            self,
            "growth_tree",
            None,
        )
        if growth_tree is not None and priority_engine is None:
            try:
                growth_tree.record_intent(
                    result,
                    source="IntentEngine",
                    qbit=self.qbit,
                )
            except Exception as exc:
                logger.debug(
                    "[IntentEngine] growth intent record unavailable | %s",
                    exc,
                )

        return (
            dominant,
            scores,
        )

    # ======================================================
    # RAW INTENT SCORING
    # ======================================================

    def _calculate_scores(
        self,
        resonance,
        sensors,
    ) -> Dict[str, float]:

        seed = sensors.get(
            "seed",
            0.0,
        )

        user = sensors.get(
            "user",
            0.0,
        )

        noise = sensors.get(
            "noise",
            0.0,
        )

        audio = sensors.get(
            "audio",
            0.0,
        )

        vision = sensors.get(
            "vision",
            0.0,
        )

        activity = _clamp(
            (
                seed
                * self.weights["seed"]

                + user
                * self.weights["user"]

                + audio
                * self.weights["audio"]

                + vision
                * self.weights["vision"]

                + resonance
                * self.weights["resonance"]
            )
            /
            max(
                1.0,
                (
                    self.weights["seed"]
                    + self.weights["user"]
                    + self.weights["audio"]
                    + self.weights["vision"]
                    + self.weights["resonance"]
                ),
            )
        )

        effective_activity = _clamp(
            activity
            -
            (
                noise
                * abs(
                    self.weights["noise"]
                )
            )
            /
            max(
                1.0,
                sum(
                    abs(v)
                    for v in self.weights.values()
                ),
            )
        )

        return {
            "IDLE":
                _clamp(
                    1.0
                    - effective_activity
                ),

            "OBSERVE":
                _clamp(
                    (
                        vision
                        + audio
                        + resonance
                    )
                    / 3.0
                ),

            "PROCESS":
                _clamp(
                    (
                        seed
                        + effective_activity
                        + resonance
                    )
                    / 3.0
                ),

            "ANALYZE":
                _clamp(
                    (
                        seed
                        + vision
                        + resonance
                        + (1.0 - noise)
                    )
                    / 4.0
                ),

            "RESPOND":
                _clamp(
                    (
                        user
                        + audio
                        + effective_activity
                    )
                    / 3.0
                ),

            "RECOVER":
                _clamp(
                    (
                        noise
                        + (1.0 - resonance)
                    )
                    / 2.0
                ),

            "HANDLE_ERROR":
                _clamp(
                    noise
                ),
        }

    # ======================================================
    # TEMPORAL INTENT DYNAMICS
    # ======================================================

    def _apply_temporal_dynamics(
        self,
        scores,
    ) -> Dict[str, float]:

        previous = (
            self._last_dominant
        )

        previous_score = (
            scores.get(
                previous,
                0.0,
            )
        )

        result = {}

        for intent, score in scores.items():

            score = _clamp(
                score
            )

            # ------------------------------------------
            # Momentum keeps active cognition stable.
            # ------------------------------------------

            if intent == previous:
                score = _clamp(
                    score
                    + (
                        previous_score
                        * self.momentum
                    )
                )

            # ------------------------------------------
            # Transition matrix gives legitimate paths
            # slightly more weight.
            # ------------------------------------------

            transition = (
                self.transitions
                .get(
                    previous,
                    {},
                )
                .get(
                    intent,
                    0.0,
                )
            )

            score = _clamp(
                score
                + transition
            )

            result[
                intent
            ] = score

        return result

    # ======================================================
    # CONFIDENCE
    # ======================================================

    def _calculate_confidence(
        self,
        scores,
        dominant,
        sensors,
        resonance,
    ) -> float:

        ordered = sorted(
            scores.values(),
            reverse=True,
        )

        if not ordered:
            return 0.05

        best = ordered[0]

        second = (
            ordered[1]
            if len(ordered) > 1
            else 0.0
        )

        separation = _clamp(
            best - second
        )

        signal_strength = _clamp(
            (
                sum(
                    sensors.values()
                )
                / max(
                    1,
                    len(sensors),
                )
            )
        )

        confidence = _clamp(
            (
                best * 0.50
                + separation * 0.30
                + resonance * 0.20
            )
        )

        confidence *= (
            0.55
            + (
                signal_strength
                * 0.45
            )
        )

        return _clamp(
            confidence
        )

    # ======================================================
    # URGENCY
    # ======================================================

    def _calculate_urgency(
        self,
        dominant,
        sensors,
        resonance,
    ) -> float:

        noise = sensors.get(
            "noise",
            0.0,
        )

        user = sensors.get(
            "user",
            0.0,
        )

        urgency = 0.0

        if dominant in (
            "HANDLE_ERROR",
            "RECOVER",
        ):
            urgency += 0.55

        if dominant == "RESPOND":
            urgency += (
                user * 0.35
            )

        urgency += (
            noise * 0.25
        )

        urgency += (
            resonance * 0.15
        )

        return _clamp(
            urgency
        )

    # ======================================================
    # NOVELTY
    # ======================================================

    def _calculate_novelty(
        self,
        dominant,
    ) -> float:

        if not self._history:
            return 1.0

        recent = self._history[
            -16:
        ]

        count = sum(
            1
            for item in recent
            if item.get(
                "intent"
            ) == dominant
        )

        return _clamp(
            1.0
            - (
                count
                / max(
                    1,
                    len(recent),
                )
            )
        )

    # ======================================================
    # STABILITY
    # ======================================================

    def _calculate_stability(
        self,
        dominant,
    ) -> float:

        if not self._history:
            return 0.0

        recent = self._history[
            -8:
        ]

        if not recent:
            return 0.0

        same = sum(
            1
            for item in recent
            if item.get(
                "intent"
            ) == dominant
        )

        return _clamp(
            same
            / len(recent)
        )

    # ======================================================
    # DOMINANT INTENT
    # ======================================================

    def _select_dominant(
        self,
        scores,
    ) -> str:

        if not scores:
            return "IDLE"

        best_name = "IDLE"
        best_score = -1.0

        for intent in self.intents:

            score = _safe_float(
                scores.get(
                    intent,
                    0.0,
                )
            )

            if score > best_score:
                best_score = score
                best_name = intent

        return best_name

    # ======================================================
    # EVALUATE
    #
    # IMPORTANT:
    #
    # qbit is treated as the SOURCE/AUTHORITATIVE runtime
    # Qbit. It is never reused as the new Intent Qbit.
    # ======================================================

    def evaluate(
        self,
        sensors=None,
        resonance=0.0,
        *,
        qbit=None,
        create_qbit=True,
    ) -> Dict[str, Any]:

        dominant, scores = (
            self.score_intents(
                resonance,
                sensors,
            )
        )

        result = (
            deepcopy(
                self._last_result
            )
            or {}
        )

        source_qbit = (
            qbit
            if qbit is not None
            else self.qbit
        )

        if create_qbit:

            intent_qbit = (
                self.create_intent_qbit(
                    result,
                    source_qbit=source_qbit,
                )
            )

            if intent_qbit is not None:

                self.submit_intent_qbit(
                    intent_qbit
                )

        elif source_qbit is not None:

            self.attach_to_qbit(
                source_qbit,
                result,
            )

        self._emit(
            INTENT_UPDATED,
            deepcopy(result),
        )

        return result

    # ======================================================
    # CREATE MODULE-LEVEL INTENT QBIT
    #
    # THIS IS DATA CREATION ONLY.
    #
    # It does NOT:
    # - create QbitDialer
    # - create command_queue
    # - create QbitQueueLoop
    # - execute anything
    #
    # CRITICAL:
    #
    # source_qbit is lineage only.
    #
    # A NEW Qbit is always created.
    #
    # This fixes:
    #
    #   same qbit_id
    #   different track_id
    #
    # which was causing QbitQueueLoop duplicate admission
    # protection to reject repeated admissions.
    # ======================================================

    def create_intent_qbit(
        self,
        result,
        *,
        source_qbit=None,
    ):

        if not isinstance(
            result,
            dict,
        ):
            result = {}

        dominant = (
            result.get(
                "intent"
            )
            or result.get(
                "dominant"
            )
            or "IDLE"
        )

        sequence = (
            result.get(
                "sequence",
                self._sequence,
            )
        )

        source_qbit_id = (
            self._qbit_id(
                source_qbit
            )
        )

        source_of_start = self._extract_qbit_field(source_qbit, "source", None)
        if source_of_start is None:
            source_of_start = self._extract_qbit_field(source_qbit, "origin", None)
        if source_of_start is None:
            source_of_start = "IntentEngine"
        source_classification = self._extract_qbit_field(source_qbit, "classification", None)
        if source_classification is None:
            source_classification = self._extract_qbit_field(source_qbit, "data_class", None)
        skill = result.get("skill") or self._extract_qbit_field(source_qbit, "skill", None)
        command = result.get("command") or self._extract_qbit_field(source_qbit, "command", None)
        command_type = result.get("command_type") or self._extract_qbit_field(source_qbit, "command_type", None)

        self._intent_qbit_sequence += 1

        qbit_track_id = (
            _generate_intent_track_id()
        )

        intent_payload = {

            # ------------------------------------------
            # PRIMARY SEMANTIC FIELD
            # ------------------------------------------

            "INTENT":
                dominant,

            # ------------------------------------------
            # Structured intent state
            # ------------------------------------------

            "intent": {

                "name":
                    dominant,

                "confidence":
                    _clamp(
                        result.get(
                            "confidence"
                        )
                    ),

                "score":
                    _clamp(
                        result.get(
                            "scores",
                            {},
                        ).get(
                            dominant,
                            0.0,
                        )
                    ),

                "resonance":
                    _clamp(
                        result.get(
                            "resonance"
                        )
                    ),

                "urgency":
                    _clamp(
                        result.get(
                            "urgency"
                        )
                    ),

                "novelty":
                    _clamp(
                        result.get(
                            "novelty"
                        )
                    ),

                "stability":
                    _clamp(
                        result.get(
                            "stability"
                        )
                    ),

                "ambiguity":
                    _clamp(
                        result.get(
                            "ambiguity"
                        )
                    ),

                "previous":
                    result.get(
                        "previous_intent"
                    ),

                "sequence":
                    sequence,

                "source":
                    "IntentEngine",
            },

            # ------------------------------------------
            # WHO
            # ------------------------------------------

            "source":
                source_of_start,

            "source_of_start":
                source_of_start,

            "classification":
                source_classification,

            "module":
                "intent_engine",

            "component":
                "intent_processor",

            # ------------------------------------------
            # WHAT
            # ------------------------------------------

            "data":
                deepcopy(
                    result
                ),

            "intent_scores":
                deepcopy(
                    result.get(
                        "scores",
                        {},
                    )
                ),

            # ------------------------------------------
            # WHY
            # ------------------------------------------

            "purpose":
                dominant,

            "reason":
                dominant,

            # ------------------------------------------
            # HOW
            # ------------------------------------------

            "action":
                command or "COMPUTE_BRAIN",

            "skill":
                skill,

            "command":
                command,

            "command_type":
                command_type or ("SKILL" if skill else None),

            "processing":
                "COMPUTE_BRAIN",

            "cognitive_stage":
                "INTENT",

            # ------------------------------------------
            # WHERE
            # ------------------------------------------

            "channel":
                "QBIT",

            "channel_id":
                "QBIT",

            "track_id":
                qbit_track_id,

            # ------------------------------------------
            # RELATIONSHIP
            # ------------------------------------------

            # The source Qbit is the parent/lineage.
            # It is NOT the Intent Qbit itself.
            "parent_id":
                source_qbit_id,

            "source_qbit_id":
                source_qbit_id,

            "relationships":
                {
                    "intent_engine":
                        "producer",

                    "source_qbit":
                        "parent",

                    "compute_brain":
                        "consumer",

                    "qbit_dialer":
                        "processing_authority",

                    "transformer_brain":
                        "downstream",
                },

            # ------------------------------------------
            # QBIT CONTROL FLAGS
            # ------------------------------------------

            "flags":
                {
                    "intent_qbit":
                        True,

                    "cognitive_input":
                        True,

                    "command_authorized":
                        False,

                    "command":
                        False,

                    "compute_action":
                        True,

                    "encoded":
                        False,

                    "parent_qbit":
                        source_qbit_id,
                },

            "sequence":
                sequence,

            "intent_qbit_sequence":
                self._intent_qbit_sequence,

            "timestamp":
                time.time(),
        }

        # ==================================================
        # ALWAYS BUILD A NEW INTENT QBIT
        #
        # DO NOT:
        #
        #     active_qbit = source_qbit
        #
        # That was the duplicate identity bug.
        # ==================================================

        active_qbit = (
            self._build_qbit(
                intent_payload
            )
        )

        if active_qbit is None:

            logger.error(
                "[IntentEngine] Unable to "
                "create Intent Qbit"
            )

            return None

        # ==================================================
        # VERIFY / PRESERVE UNIQUE IDENTITY
        #
        # If Qbit construction exposed an existing identity,
        # ensure the newly-created object has its own identity.
        #
        # We do not replace the authoritative source Qbit.
        # ==================================================

        self._ensure_intent_qbit_identity(
            active_qbit,
            qbit_track_id,
            source_qbit_id,
        )

        # ==================================================
        # ANNOTATE THE NEW INTENT QBIT
        # ==================================================

        self.attach_to_qbit(
            active_qbit,
            result,
        )

        # ==================================================
        # ADD FULL INTENT CARRIER
        # ==================================================

        self._write_qbit_payload(
            active_qbit,
            intent_payload,
        )

        # ==================================================
        # IMPORTANT:
        #
        # Do NOT assign:
        #
        #     self.qbit = active_qbit
        #
        # self.qbit remains the authoritative runtime/source
        # Qbit injected by main3.
        # ==================================================

        self._last_qbit = active_qbit

        # ==================================================
        # ENCODE FOR SEED TRANSPORT
        # ==================================================

        encoded = (
            self.encode_qbit(
                active_qbit
            )
        )

        if encoded is not None:

            self._last_encoded_qbit = (
                encoded
            )

            try:

                if hasattr(
                    active_qbit,
                    "flags",
                ):

                    active_qbit.flags[
                        "encoded"
                    ] = True

            except Exception:
                pass

        # ==================================================
        # EMIT SAFE EVENT PAYLOAD
        #
        # The event carries the Qbit reference for internal
        # runtime observers, but identity/lineage are explicit.
        # ==================================================

        self._emit(
            INTENT_QBIT_CREATED,
            {
                "qbit":
                    active_qbit,

                "qbit_id":
                    self._qbit_id(
                        active_qbit
                    ),

                "track_id":
                    self._extract_qbit_field(
                        active_qbit,
                        "track_id",
                        qbit_track_id,
                    ),

                "parent_id":
                    source_qbit_id,

                "source_qbit_id":
                    source_qbit_id,

                "intent":
                    dominant,

                "encoded":
                    encoded is not None,

                "sequence":
                    sequence,
            },
        )

        logger.info(
            "[IntentEngine] Intent Qbit created | "
            "qbit_id=%s | track_id=%s | "
            "parent_id=%s | INTENT=%s | "
            "action=COMPUTE_BRAIN | encoded=%s",
            self._qbit_id(
                active_qbit
            ),
            self._extract_qbit_field(
                active_qbit,
                "track_id",
                qbit_track_id,
            ),
            source_qbit_id,
            dominant,
            encoded is not None,
        )

        return active_qbit

    # ======================================================
    # INTENT QBIT IDENTITY
    #
    # Ensures the newly-created Intent Qbit is distinct from
    # its parent/source Qbit.
    # ======================================================

    def _ensure_intent_qbit_identity(
        self,
        qbit,
        track_id,
        parent_id=None,
    ) -> None:

        if qbit is None:
            return

        try:

            current_id = (
                self._qbit_id(
                    qbit
                )
            )

            # --------------------------------------------------
            # If construction somehow returned the same object
            # as the authoritative source, do not silently
            # mutate that source object.
            #
            # _build_qbit() normally creates a new object, so
            # this is defensive validation.
            # --------------------------------------------------

            if (
                parent_id is not None
                and current_id == parent_id
            ):
                logger.error(
                    "[IntentEngine] Qbit factory returned "
                    "source Qbit identity | "
                    "parent_id=%s",
                    parent_id,
                )

            # --------------------------------------------------
            # Track identity belongs to the newly-created
            # Intent Qbit.
            # --------------------------------------------------

            try:
                if hasattr(
                    qbit,
                    "track_id",
                ):
                    qbit.track_id = track_id
            except Exception:
                pass

            try:
                payload = getattr(
                    qbit,
                    "payload",
                    None,
                )

                if isinstance(
                    payload,
                    dict,
                ):
                    payload[
                        "track_id"
                    ] = track_id

                    payload[
                        "parent_id"
                    ] = parent_id

                    payload[
                        "source_qbit_id"
                    ] = parent_id

            except Exception:
                pass

            try:
                data = getattr(
                    qbit,
                    "data",
                    None,
                )

                if isinstance(
                    data,
                    dict,
                ):
                    data[
                        "track_id"
                    ] = track_id

                    data[
                        "parent_id"
                    ] = parent_id

                    data[
                        "source_qbit_id"
                    ] = parent_id

            except Exception:
                pass

            try:
                flags = getattr(
                    qbit,
                    "flags",
                    None,
                )

                if isinstance(
                    flags,
                    dict,
                ):
                    flags[
                        "intent_qbit"
                    ] = True

                    flags[
                        "command_authorized"
                    ] = False

                    flags[
                        "parent_qbit"
                    ] = parent_id

            except Exception:
                pass

        except Exception:
            logger.exception(
                "[IntentEngine] Failed to enforce "
                "Intent Qbit identity"
            )

    # ======================================================
    # AUTHORITATIVE INTENT TRANSPORT
    #
    # IntentEngine produces cognitive input.
    #
    # It does NOT:
    # - create a QbitQueueLoop
    # - create a command queue
    # - execute commands
    # - bypass QbitQueueLoop
    #
    # The existing authoritative QueueLoop receives the Qbit.
    #
    # The QueueLoop is responsible for dispatching it to the
    # already-bound QbitDialer.
    # ======================================================

    def submit_intent_qbit(
        self,
        qbit=None,
        *,
        priority=None,
    ):

        active_qbit = (
            qbit
            if qbit is not None
            else self._last_qbit
        )

        if active_qbit is None:

            logger.warning(
                "[IntentEngine] Intent Qbit transport rejected | "
                "qbit=None"
            )

            return False

        queue_loop = self.queue_loop

        if queue_loop is None:

            logger.warning(
                "[IntentEngine] Intent Qbit transport deferred | "
                "authoritative QbitQueueLoop unavailable"
            )

            return False

        # ------------------------------------------------------
        # AUTHORITY CHECK
        #
        # The IntentEngine does not execute or submit commands.
        # It only hands the cognitive Qbit to the authoritative
        # QueueLoop.
        # ------------------------------------------------------

        if self.qbit_dialer is None:

            logger.warning(
                "[IntentEngine] Intent Qbit transport deferred | "
                "QbitDialer unavailable"
            )

            return False

        # ------------------------------------------------------
        # NEVER create another QueueLoop.
        #
        # The object injected by main3 is the authority.
        # ------------------------------------------------------

        try:

            put = getattr(
                queue_loop,
                "put",
                None,
            )

            if not callable(put):

                logger.error(
                    "[IntentEngine] Authoritative "
                    "QbitQueueLoop has no put() contract"
                )

                return False

            selected_priority = priority

            if selected_priority is None:

                # Let QbitQueueLoop resolve the priority
                # from the Qbit itself.
                accepted = put(
                    active_qbit
                )

            else:

                accepted = put(
                    active_qbit,
                    priority=selected_priority,
                )

            if accepted:

                qbit_id = self._qbit_id(
                    active_qbit
                )

                track_id = (
                    self._extract_qbit_field(
                        active_qbit,
                        "track_id",
                        None,
                    )
                )

                parent_id = (
                    self._extract_qbit_field(
                        active_qbit,
                        "parent_id",
                        None,
                    )
                )

                self._emit(
                    INTENT_QBIT_ROUTED,
                    {
                        "qbit":
                            active_qbit,

                        "qbit_id":
                            qbit_id,

                        "track_id":
                            track_id,

                        "parent_id":
                            parent_id,

                        "intent":
                            self._extract_intent_name(
                                active_qbit
                            ),

                        "action":
                            "COMPUTE_BRAIN",

                        "destination":
                            "QbitQueueLoop",

                        "authority":
                            "QbitDialer",
                    },
                )

                logger.info(
                    "[IntentEngine] Intent Qbit routed | "
                    "qbit_id=%s | track_id=%s | "
                    "destination=QbitQueueLoop | "
                    "authority=QbitDialer",
                    qbit_id,
                    track_id,
                )

                return True

            logger.warning(
                "[IntentEngine] Intent Qbit rejected by "
                "authoritative QbitQueueLoop | "
                "qbit_id=%s | track_id=%s",
                self._qbit_id(
                    active_qbit
                ),
                self._extract_qbit_field(
                    active_qbit,
                    "track_id",
                    None,
                ),
            )

            return False

        except Exception:

            logger.exception(
                "[IntentEngine] Intent Qbit transport failed"
            )

            return False

    # ======================================================
    # QBIT FACTORY
    #
    # Prefer existing Qbit.create_command().
    # Never create QbitDialer here.
    #
    # This function MUST create a new Qbit object.
    # ======================================================

    def _build_qbit(
        self,
        payload,
    ):

        if Qbit is None:
            return None

        try:

            create_command = getattr(
                Qbit,
                "create_command",
                None,
            )

            if callable(
                create_command
            ):

                return create_command(
                    intent=
                        payload.get(
                            "INTENT",
                            "IDLE",
                        ),

                    action=
                        "COMPUTE_BRAIN",

                    data=
                        payload,

                    meta={
                        "source":
                            "IntentEngine",

                        "module":
                            "intent_engine",

                        "channel":
                            "QBIT",

                        "track_id":
                            payload.get(
                                "track_id"
                            ),

                        "intent":
                            payload.get(
                                "INTENT"
                            ),

                        "command_authorized":
                            False,

                        "parent_id":
                            payload.get(
                                "parent_id"
                            ),

                        "source_qbit_id":
                            payload.get(
                                "source_qbit_id"
                            ),

                        "intent_qbit":
                            True,
                    },
                )

            # --------------------------------------------------
            # Constructor fallback.
            # --------------------------------------------------

            return Qbit(
                payload=deepcopy(
                    payload
                )
            )

        except Exception:

            logger.exception(
                "[IntentEngine] Qbit construction failed"
            )

            return None

    # ======================================================
    # WRITE PAYLOAD SAFELY
    # ======================================================

    def _write_qbit_payload(
        self,
        qbit,
        payload,
    ):

        try:

            safe_payload = deepcopy(
                payload
            )

            if hasattr(
                qbit,
                "payload",
            ):

                existing = getattr(
                    qbit,
                    "payload",
                    None,
                )

                if isinstance(
                    existing,
                    dict,
                ):

                    existing.update(
                        safe_payload
                    )

                else:

                    qbit.payload = (
                        safe_payload
                    )

            elif hasattr(
                qbit,
                "data",
            ):

                existing = getattr(
                    qbit,
                    "data",
                    None,
                )

                if isinstance(
                    existing,
                    dict,
                ):

                    existing.update(
                        safe_payload
                    )

                else:

                    qbit.data = (
                        safe_payload
                    )

        except Exception:

            logger.exception(
                "[IntentEngine] Failed to "
                "write Intent payload"
            )

    # ======================================================
    # QBIT ANNOTATION
    #
    # attach_qbit() is a runtime binding operation.
    #
    # It may bind an externally supplied runtime Qbit to the
    # engine. It does NOT create a new Qbit.
    # ======================================================

    def attach_qbit(
        self,
        qbit,
    ):

        if qbit is None:
            return None

        self.qbit = qbit

        try:

            if hasattr(
                qbit,
                "flags",
            ):

                qbit.flags[
                    "intent_engine"
                ] = True

                qbit.flags[
                    "intent_qbit"
                ] = True

        except Exception:

            logger.exception(
                "[IntentEngine] "
                "Failed to annotate Qbit"
            )

        return qbit

    # ======================================================
    # ATTACH INTENT TO QBIT
    # ======================================================

    def attach_to_qbit(
        self,
        qbit,
        result,
    ):

        if qbit is None:
            return None

        if not isinstance(
            result,
            dict,
        ):
            return qbit

        dominant = (
            result.get(
                "intent"
            )
            or result.get(
                "dominant"
            )
            or "IDLE"
        )

        scores = result.get(
            "scores",
            {},
        )

        try:

            # ==============================================
            # FLAGS
            # ==============================================

            if hasattr(
                qbit,
                "flags",
            ):

                qbit.flags[
                    "intent_engine"
                ] = True

                qbit.flags[
                    "intent_qbit"
                ] = True

                qbit.flags[
                    "dominant_intent"
                ] = dominant

                qbit.flags[
                    "INTENT"
                ] = dominant

                qbit.flags[
                    "intent_scores"
                ] = dict(
                    scores
                )

                qbit.flags[
                    "intent_confidence"
                ] = _clamp(
                    result.get(
                        "confidence"
                    )
                )

                qbit.flags[
                    "intent_resonance"
                ] = _clamp(
                    result.get(
                        "resonance"
                    )
                )

                qbit.flags[
                    "intent_urgency"
                ] = _clamp(
                    result.get(
                        "urgency"
                    )
                )

                qbit.flags[
                    "intent_novelty"
                ] = _clamp(
                    result.get(
                        "novelty"
                    )
                )

                qbit.flags[
                    "intent_stability"
                ] = _clamp(
                    result.get(
                        "stability"
                    )
                )

                qbit.flags[
                    "command_authorized"
                ] = False

                qbit.flags[
                    "command"
                ] = False

                qbit.flags[
                    "compute_action"
                ] = True

            # ==============================================
            # RUNTIME CONTEXT
            # ==============================================

            if hasattr(
                qbit,
                "runtime_context",
            ):

                context = (
                    qbit.runtime_context
                )

                if not isinstance(
                    context,
                    dict,
                ):

                    context = {}

                    qbit.runtime_context = (
                        context
                    )

                context[
                    "INTENT"
                ] = dominant

                context[
                    "intent"
                ] = dominant

                context[
                    "intent_scores"
                ] = dict(
                    scores
                )

                context[
                    "intent_confidence"
                ] = _clamp(
                    result.get(
                        "confidence"
                    )
                )

                context[
                    "intent_resonance"
                ] = _clamp(
                    result.get(
                        "resonance"
                    )
                )

                context[
                    "intent_urgency"
                ] = _clamp(
                    result.get(
                        "urgency"
                    )
                )

                context[
                    "intent_novelty"
                ] = _clamp(
                    result.get(
                        "novelty"
                    )
                )

                context[
                    "intent_stability"
                ] = _clamp(
                    result.get(
                        "stability"
                    )
                )

                context[
                    "action"
                ] = "COMPUTE_BRAIN"

                context[
                    "command_authorized"
                ] = False

            return qbit

        except Exception:

            logger.exception(
                "[IntentEngine] Failed to attach "
                "Intent metadata to Qbit"
            )

            return qbit

    # ======================================================
    # QBIT ENCODER
    #
    # Serialization only.
    #
    # It does NOT:
    # - execute
    # - submit
    # - create commands
    # - call QbitDialer
    # ======================================================

    def encode_qbit(
        self,
        qbit=None,
    ):

        active_qbit = (
            qbit
            if qbit is not None
            else self._last_qbit
        )

        if active_qbit is None:
            return None

        encoder = self.encoder

        if encoder is None:
            return None

        try:

            encode = getattr(
                encoder,
                "encode",
                None,
            )

            if not callable(
                encode
            ):
                return None

            envelope = (
                self._qbit_encode_envelope(
                    active_qbit
                )
            )

            encoded = encode(
                envelope
            )

            if inspect.isawaitable(
                encoded
            ):

                # IntentEngine is synchronous.
                # Do not create a runtime here.
                return None

            return encoded

        except Exception:

            logger.exception(
                "[IntentEngine] "
                "Intent Qbit encoding failed"
            )

            return None

    # ======================================================
    # ENCODER ENVELOPE
    #
    # IMPORTANT:
    #
    # Do not put the live Qbit object into the serialized
    # envelope. The encoder receives an immutable/safe data
    # representation.
    # ======================================================

    def _qbit_encode_envelope(
        self,
        qbit,
    ) -> Dict[str, Any]:

        payload = self._extract_qbit_field(
            qbit,
            "payload",
            None,
        )

        if payload is None:

            payload = self._extract_qbit_field(
                qbit,
                "data",
                {},
            )

        if not isinstance(
            payload,
            dict,
        ):

            payload = {
                "data":
                    payload
            }

        safe_payload = deepcopy(
            payload
        )

        qbit_id = (
            self._qbit_id(
                qbit
            )
        )

        track_id = (
            self._extract_qbit_field(
                qbit,
                "track_id",
                None,
            )
        )

        parent_id = (
            self._extract_qbit_field(
                qbit,
                "parent_id",
                safe_payload.get(
                    "parent_id"
                ),
            )
        )

        intent_name = (
            self._extract_intent_name(
                qbit
            )
        )

        skill = self._extract_qbit_field(qbit, "skill", None)
        command = self._extract_qbit_field(qbit, "command", None)
        command_type = self._extract_qbit_field(qbit, "command_type", None)

        return {

            "id":
                qbit_id,

            "qbit_id":
                qbit_id,

            "track_id":
                track_id,

            "parent_id":
                parent_id,

            "source_qbit_id":
                safe_payload.get(
                    "source_qbit_id",
                    parent_id,
                ),

            "channel_id":
                "QBIT",

            "source":
                "IntentEngine",

            "module":
                "intent_engine",

            "component":
                "intent_processor",

            "intent":
                intent_name,

            "action":
                command or "COMPUTE_BRAIN",

            "skill":
                skill,

            "command":
                command,

            "command_type":
                command_type or ("SKILL" if skill else None),

            "processing":
                "COMPUTE_BRAIN",

            "state":
                "INTENT",

            "payload":
                safe_payload,

            "flags":
                {
                    "intent_qbit":
                        True,

                    "cognitive_input":
                        True,

                    "command_authorized":
                        False,

                    "command":
                        False,

                    "compute_action":
                        True,
                },

            "timestamp":
                time.time(),
        }

    # ======================================================
    # QBIT FIELD EXTRACTION
    # ======================================================

    @staticmethod
    def _extract_qbit_field(
        qbit,
        name,
        default=None,
    ):

        if qbit is None:
            return default

        try:

            value = getattr(
                qbit,
                name,
                None,
            )

            if value is not None:
                return value

        except Exception:
            pass

        try:

            data = getattr(
                qbit,
                "data",
                None,
            )

            if isinstance(
                data,
                dict,
            ):

                if name in data:
                    return data[
                        name
                    ]

        except Exception:
            pass

        try:

            payload = getattr(
                qbit,
                "payload",
                None,
            )

            if isinstance(
                payload,
                dict,
            ):

                if name in payload:
                    return payload[
                        name
                    ]

        except Exception:
            pass

        return default

    # ======================================================
    # INTENT NAME EXTRACTION
    # ======================================================

    @classmethod
    def _extract_intent_name(
        cls,
        qbit,
    ):

        payload = cls._extract_qbit_field(
            qbit,
            "payload",
            None,
        )

        if isinstance(
            payload,
            dict,
        ):

            intent = payload.get(
                "INTENT"
            )

            if intent:
                return intent

            structured = payload.get(
                "intent"
            )

            if isinstance(
                structured,
                dict,
            ):

                return (
                    structured.get(
                        "name"
                    )
                    or structured.get(
                        "intent"
                    )
                    or "IDLE"
                )

            if isinstance(
                structured,
                str,
            ):

                return structured

        data = cls._extract_qbit_field(
            qbit,
            "data",
            None,
        )

        if isinstance(
            data,
            dict,
        ):

            intent = data.get(
                "INTENT"
            )

            if intent:
                return intent

        return cls._extract_qbit_field(
            qbit,
            "intent",
            "IDLE",
        )

    # ======================================================
    # QBIT ID
    # ======================================================

    @classmethod
    def _qbit_id(
        cls,
        qbit,
    ):

        return (
            cls._extract_qbit_field(
                qbit,
                "qbit_id",
                None,
            )
            or
            cls._extract_qbit_field(
                qbit,
                "id",
                None,
            )
        )

    # ======================================================
    # INGEST RESULT
    # ======================================================

    def ingest_qbit_result(
        self,
        result,
    ):

        if not isinstance(
            result,
            dict,
        ):
            return None

        dominant = (
            result.get(
                "intent"
            )
            or result.get(
                "dominant"
            )
        )

        scores = result.get(
            "scores"
        )

        with self._lock:

            if isinstance(
                dominant,
                str,
            ):

                self._last_dominant = (
                    dominant
                )

            if isinstance(
                scores,
                dict,
            ):

                self._last_scores = {
                    str(k):
                        _safe_float(v)
                    for k, v
                    in scores.items()
                }

        return result

    # ======================================================
    # STATE
    # ======================================================

    @property
    def dominant(self):

        with self._lock:
            return (
                self._last_dominant
            )

    @property
    def last_scores(self):

        with self._lock:
            return dict(
                self._last_scores
            )

    @property
    def last_resonance(self):

        with self._lock:
            return (
                self._last_resonance
            )

    @property
    def last_sensors(self):

        with self._lock:
            return dict(
                self._last_sensors
            )

    @property
    def last_result(self):

        with self._lock:
            return deepcopy(
                self._last_result
            )

    @property
    def intent_qbit(self):

        return self._last_qbit

    @property
    def encoded_intent_qbit(self):

        return self._last_encoded_qbit

    # ======================================================
    # HISTORY
    # ======================================================

    def get_history(
        self,
        limit=None,
    ):

        with self._lock:

            history = deepcopy(
                self._history
            )

        if limit is None:
            return history

        limit = max(
            0,
            int(limit),
        )

        if limit == 0:
            return []

        return history[
            -limit:
        ]

    # ======================================================
    # SNAPSHOT
    # ======================================================

    def snapshot(self):

        with self._lock:

            return {

                "operational":
                    self.operational,

                "sequence":
                    self._sequence,

                "dominant":
                    self._last_dominant,

                "previous":
                    self._previous_dominant,

                "scores":
                    dict(
                        self._last_scores
                    ),

                "resonance":
                    self._last_resonance,

                "sensors":
                    dict(
                        self._last_sensors
                    ),

                "history_size":
                    len(
                        self._history
                    ),

                "configured_history_size":
                    self.history_size,

                # Last created Intent Qbit.
                "intent_qbit":
                    self._qbit_id(
                        self._last_qbit
                    ),

                # Authoritative runtime/source Qbit.
                "authoritative_qbit":
                    self._qbit_id(
                        self.qbit
                    ),

                "encoded":
                    self._last_encoded_qbit
                    is not None,

                "encoder":
                    type(
                        self.encoder
                    ).__name__
                    if self.encoder is not None
                    else None,

                "qbit_dialer":
                    type(
                        self.qbit_dialer
                    ).__name__
                    if self.qbit_dialer is not None
                    else None,

                "qbit_queue_loop":
                    type(
                        self.queue_loop
                    ).__name__
                    if self.queue_loop is not None
                    else None,

                "event_bus":
                    type(
                        self.event_bus
                    ).__name__
                    if self.event_bus is not None
                    else None,

                "emit_bound":
                    callable(
                        self.emit
                    ),

            }

    # ======================================================
    # HEALTH
    # ======================================================

    def health(self):

        return {

            "module":
                "IntentEngine",

            "operational":
                bool(
                    self.operational
                ),

            "dominant":
                self.dominant,

            "sequence":
                self._sequence,

            # Last generated Intent Qbit.
            "intent_qbit":
                self._qbit_id(
                    self._last_qbit
                ),

            # Authoritative runtime Qbit.
            "authoritative_qbit":
                self._qbit_id(
                    self.qbit
                ),

            "encoded":
                self._last_encoded_qbit
                is not None,

            "emit":
                callable(
                    self.emit
                ),

            "event_bus":
                self.event_bus
                is not None,

            "qbit":
                self.qbit
                is not None,

            "qbit_queue_loop":
                self.queue_loop
                is not None,

            "qbit_dialer":
                self.qbit_dialer
                is not None,

            "encoder":
                self.encoder
                is not None,

        }

    # ======================================================
    # START / STOP
    # ======================================================

    def start(self):

        self.operational = True

        logger.info(
            "[IntentEngine] ONLINE"
        )

        return self

    def stop(self):

        self.operational = False

        logger.info(
            "[IntentEngine] OFFLINE"
        )

        return self


# ==========================================================
# FACTORY
# ==========================================================

def create_intent_engine(
    *,
    emit=None,
    event_bus=None,
    qbit=None,
    qbit_queue_loop=None,
    qbit_dialer=None,
    track_system=None,
    encoder=None,
    **kwargs,
):

    return IntentEngine(

        emit=emit,

        event_bus=event_bus,

        qbit=qbit,

        qbit_queue_loop=qbit_queue_loop,

        qbit_dialer=qbit_dialer,

        track_system=track_system,

        encoder=encoder,

        **kwargs,

    )


# ==========================================================
# MODULE-LEVEL INSTANCE
# ==========================================================

intent_engine: Optional[
    IntentEngine
] = None


def initialize_intent_engine(
    *,
    emit=None,
    event_bus=None,
    qbit=None,
    qbit_queue_loop=None,
    qbit_dialer=None,
    track_system=None,
    encoder=None,
    **kwargs,
):

    global intent_engine

    intent_engine = (
        create_intent_engine(

            emit=emit,

            event_bus=event_bus,

            qbit=qbit,

            qbit_queue_loop=qbit_queue_loop,

            qbit_dialer=qbit_dialer,

            track_system=track_system,

            encoder=encoder,

            **kwargs,

        )
    )

    return intent_engine


# ==========================================================
# PUBLIC EXPORTS
# ==========================================================

__all__ = [
    "IntentEngine",
    "create_intent_engine",
    "initialize_intent_engine",
    "intent_engine",
    "INTENT_UPDATED",
    "INTENT_SCORED",
    "INTENT_QBIT_CREATED",
    "INTENT_QBIT_ROUTED",
    "DEFAULT_INTENTS",
    "INTENT_STATE",
    "SYSTEM_ACTION",
]
