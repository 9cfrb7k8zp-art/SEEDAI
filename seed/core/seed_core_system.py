# ==========================================================
# FILE: seed_core_full_system.py
# PATH: SEED_ROOT/seed/core/seed_core_full_system.py
#
# SYSTEM: SEED AI OS
# COMPONENT: SEED Core Integration Hub
# VERSION: 6.0.0
# BUILD: PASSIVE-INTEGRATION / EVENT-CORRELATION / TRACK-AWARE
# UPDATED: 2026-08-18
#
# PURPOSE:
# ----------------------------------------------------------
# This module is NO LONGER a second SEED boot system.
#
# It is a passive integration and coordination layer for
# systems that have ALREADY been created and started by the
# authoritative SEED lifecycle.
#
# Responsibilities:
#
#   Qbit
#      |
#      +----> Intent
#      |
#      +----> Analytics
#      |
#      +----> Agent
#      |
#      +----> Actuator
#      |
#      +----> Track
#      |
#      +----> adaptive telemetry
#
# This module:
#
# - DOES NOT instantiate QbitDialer
# - DOES NOT instantiate AgentManager
# - DOES NOT instantiate HeartbeatEmitter
# - DOES NOT instantiate SparkPlug
# - DOES NOT instantiate SparkPlugLoader
# - DOES NOT instantiate ActuatorEngine
# - DOES NOT instantiate IntentEngine
# - DOES NOT instantiate AnalyticsEngine
# - DOES NOT create an asyncio loop
# - DOES NOT create a thread
# - DOES NOT start Qbit loops
# - DOES NOT start AgentManager
# - DOES NOT start a heartbeat
# - DOES NOT subscribe itself to EventBus
# - DOES NOT own system shutdown
#
# Lifecycle authority remains with SEED main/core boot.
#
# ==========================================================
#
# ARCHITECTURE
# ----------------------------------------------------------
#
#                 SEED LIFECYCLE
#                       |
#                       v
#              already-running systems
#                       |
#                       v
#             +--------------------+
#             | SEEDCoreFullSystem |
#             |   Integration Hub  |
#             +--------------------+
#                |    |    |    |
#                v    v    v    v
#              Qbit Intent Agent Actuator
#                |
#                +---- Analytics
#                |
#                +---- Track
#                |
#                +---- Trends
#                |
#                +---- Diagnostics
#
# ==========================================================

from __future__ import annotations

import logging
import threading
import time
from collections import Counter, deque
from copy import deepcopy
from typing import Any, Dict, Optional


logger = logging.getLogger("SEEDCoreFullSystem")


# ==========================================================
# CONSTANTS
# ==========================================================

VERSION = "6.0.0"

DEFAULT_TREND_WINDOW = 50

EVENT_QBIT = "qbit"
EVENT_INTENT = "intent"
EVENT_AGENT = "agent"
EVENT_ACTUATOR = "actuator"
EVENT_ANALYTICS = "analytics"
EVENT_HEARTBEAT = "heartbeat"
EVENT_SYSTEM = "system"


# ==========================================================
# PASSIVE INTEGRATION HUB
# ==========================================================

class SEEDCoreFullSystem:
   

    VERSION = VERSION
    NAME = "SEEDCoreIntegrationHub"

    TREND_WINDOW = DEFAULT_TREND_WINDOW

    # ------------------------------------------------------
    # Construction
    # ------------------------------------------------------

    def __init__(
        self,
        analytics_engine=None,
        emit=None,
        heartbeatemitter=None,
        orchestrator_command=None,
        qbit_loop=None,
        qbit_queue=None,
        heartbeat=None,
        qbit=None,
        task=None,
        track_id=None,
        track=None,
        event_bus=None,
        intent_engine=None,
        actuator_engine=None,
        qbit_dialer=None,
        agent_manager=None,
        sparkplug=None,
        sparkplug_loader=None,
        core_loop=None,
        memory_graph=None,
        track_system=None,
        **kwargs,
    ):
       

        self._lock = threading.RLock()

        # --------------------------------------------------
        # Lifecycle state of THIS integration object.
        # --------------------------------------------------

        self._created_at = time.time()
        self._enabled = True
        self._stopped = False

        # --------------------------------------------------
        # Existing system references.
        # --------------------------------------------------

        self.analytics_engine = analytics_engine
        self.emit = emit
        self.heartbeatemitter = heartbeatemitter
        self.orchestrator_command = orchestrator_command

        self.qbit_loop = qbit_loop
        self.qbit_queue = qbit_queue
        self.heartbeat = heartbeat

        self.qbit = qbit

        self.task = task

        self.track_id = track_id
        self.track = track
        self.track_system = track_system

        self.event_bus = event_bus

        self.intent_engine = intent_engine
        self.actuator_engine = actuator_engine
        self.qbit_dialer = qbit_dialer
        self.agent_manager = agent_manager

        self.sparkplug = sparkplug
        self.sparkplug_loader = sparkplug_loader

        self.core_loop = core_loop
        self.memory_graph = memory_graph

        # Preserve unknown compatibility arguments without
        # allowing them to become hidden startup triggers.
        self.extra = dict(kwargs)

        # --------------------------------------------------
        # Trend memory.
        # --------------------------------------------------

        self.qbit_trend = deque(
            maxlen=self.TREND_WINDOW
        )

        self.intent_trend = deque(
            maxlen=self.TREND_WINDOW
        )

        self.actuator_trend = deque(
            maxlen=self.TREND_WINDOW
        )

        self.analytics_trend = deque(
            maxlen=self.TREND_WINDOW
        )

        self.confidence_trend = deque(
            maxlen=self.TREND_WINDOW
        )

        self.event_trend = deque(
            maxlen=self.TREND_WINDOW
        )

        # --------------------------------------------------
        # Counters.
        # --------------------------------------------------

        self._event_counts = Counter()

        self._processed_count = 0
        self._error_count = 0

        self._last_event_at: Optional[float] = None
        self._last_event_type: Optional[str] = None
        self._last_error: Optional[str] = None

        logger.info(
            "[SEEDCoreIntegrationHub] READY | "
            "passive=true | "
            "startup_owner=false"
        )

    # ======================================================
    # LIFECYCLE
    # ======================================================

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def running(self) -> bool:
       
        with self._lock:
            return self._enabled and not self._stopped

    def start(self):
    

        with self._lock:
            self._enabled = True
            self._stopped = False

        logger.info(
            "[SEEDCoreIntegrationHub] ENABLED | "
            "no subsystem startup performed"
        )

        return self

    def stop(self, reason="shutdown_requested"):
       

        with self._lock:
            self._enabled = False
            self._stopped = True
            self._last_event_type = "system"
            self._last_event_at = time.time()

        logger.info(
            "[SEEDCoreIntegrationHub] DISABLED | "
            f"reason={reason}"
        )

        return True

    def reset(self):
      
        with self._lock:

            self.qbit_trend.clear()
            self.intent_trend.clear()
            self.actuator_trend.clear()
            self.analytics_trend.clear()
            self.confidence_trend.clear()
            self.event_trend.clear()

            self._event_counts.clear()

            self._processed_count = 0
            self._error_count = 0

            self._last_event_at = None
            self._last_event_type = None
            self._last_error = None

            self._stopped = False
            self._enabled = True

        logger.info(
            "[SEEDCoreIntegrationHub] RESET"
        )

        return True

    # ======================================================
    # COMPONENT ATTACHMENT
    # ======================================================

    def attach(
        self,
        name: str,
        component: Any,
    ) -> bool:
      
        if not name:
            return False

        with self._lock:
            setattr(self, str(name), component)

        logger.debug(
            "[SEEDCoreIntegrationHub] attached | %s=%s",
            name,
            type(component).__name__
            if component is not None
            else "None",
        )

        return True

    def detach(self, name: str) -> bool:
      

        if not name:
            return False

        with self._lock:

            if hasattr(self, name):
                setattr(self, name, None)
                return True

        return False

    # ======================================================
    # COMPONENT STATUS
    # ======================================================

    def component_status(self) -> Dict[str, Any]:
        

        with self._lock:

            components = {
                "event_bus": self.event_bus,
                "qbit": self.qbit,
                "qbit_loop": self.qbit_loop,
                "qbit_queue": self.qbit_queue,
                "qbit_dialer": self.qbit_dialer,
                "heartbeat": self.heartbeat,
                "heartbeat_emitter": self.heartbeatemitter,
                "agent_manager": self.agent_manager,
                "intent_engine": self.intent_engine,
                "analytics_engine": self.analytics_engine,
                "actuator_engine": self.actuator_engine,
                "sparkplug": self.sparkplug,
                "sparkplug_loader": self.sparkplug_loader,
                "core_loop": self.core_loop,
                "track": self.track,
                "track_system": self.track_system,
                "memory_graph": self.memory_graph,
            }

            return {
                name: {
                    "attached": value is not None,
                    "type": (
                        type(value).__name__
                        if value is not None
                        else None
                    ),
                }
                for name, value in components.items()
            }

    # ======================================================
    # EVENT NORMALIZATION
    # ======================================================

    @staticmethod
    def _normalize_event(
        event_type: str,
        payload: Any = None,
    ) -> Dict[str, Any]:
        
        now = time.time()

        if isinstance(payload, dict):
            data = deepcopy(payload)
        else:
            data = {
                "value": payload,
            }

        return {
            "event_type": str(event_type or EVENT_SYSTEM),
            "timestamp": now,
            "payload": data,
        }

    # ======================================================
    # EVENT RECORDING
    # ======================================================

    def record_event(
        self,
        event_type: str,
        payload: Any = None,
    ) -> Dict[str, Any]:
       

        if not self.enabled:
            return {}

        envelope = self._normalize_event(
            event_type,
            payload,
        )

        with self._lock:

            self.event_trend.append(
                envelope
            )

            self._event_counts[
                envelope["event_type"]
            ] += 1

            self._processed_count += 1

            self._last_event_at = (
                envelope["timestamp"]
            )

            self._last_event_type = (
                envelope["event_type"]
            )

        return envelope

    # ======================================================
    # QBIT INGESTION
    # ======================================================

    def receive_qbit(
        self,
        qbit,
        track_id=None,
    ) -> Dict[str, Any]:
        

        if qbit is None:
            return {}

        payload = self._extract_qbit_payload(qbit)

        if track_id is None:
            track_id = (
                payload.get("track_id")
                or payload.get("track")
                or self.track_id
            )

        event = self.record_event(
            EVENT_QBIT,
            {
                "qbit": payload,
                "track_id": track_id,
            },
        )

        with self._lock:

            numeric_value = self._extract_numeric_qbit(
                payload
            )

            self.qbit_trend.append(
                numeric_value
            )

            confidence = self._extract_confidence(
                payload
            )

            self.confidence_trend.append(
                confidence
            )

        return event

    # ======================================================
    # INTENT INGESTION
    # ======================================================

    def receive_intent(
        self,
        intent,
        track_id=None,
    ) -> Dict[str, Any]:
       

        if isinstance(intent, dict):

            intent_payload = deepcopy(intent)

            label = (
                intent_payload.get("intent")
                or intent_payload.get("dominant_intent")
                or intent_payload.get("name")
                or "unknown"
            )

        else:

            label = str(intent)

            intent_payload = {
                "intent": label,
            }

        event = self.record_event(
            EVENT_INTENT,
            {
                "intent": intent_payload,
                "track_id": (
                    track_id
                    if track_id is not None
                    else self.track_id
                ),
            },
        )

        with self._lock:
            self.intent_trend.append(
                str(label)
            )

        return event

    # ======================================================
    # AGENT INGESTION
    # ======================================================

    def receive_agent_data(
        self,
        pulse: dict,
    ) -> Dict[str, Any]:
    

        if not isinstance(pulse, dict):
            pulse = {
                "value": pulse,
            }

        self._update_trends(pulse)

        return self.record_event(
            EVENT_AGENT,
            pulse,
        )

    # ======================================================
    # ACTUATOR INGESTION
    # ======================================================

    def receive_actuator(
        self,
        actuator_state,
        track_id=None,
    ) -> Dict[str, Any]:
       
        if actuator_state is None:
            actuator_state = {}

        if not isinstance(
            actuator_state,
            dict,
        ):
            actuator_state = {
                "value": actuator_state,
            }

        with self._lock:
            self.actuator_trend.append(
                deepcopy(actuator_state)
            )

        return self.record_event(
            EVENT_ACTUATOR,
            {
                "state": deepcopy(actuator_state),
                "track_id": (
                    track_id
                    if track_id is not None
                    else self.track_id
                ),
            },
        )

    # ======================================================
    # ANALYTICS INGESTION
    # ======================================================

    def receive_analytics(
        self,
        analytics,
        track_id=None,
    ) -> Dict[str, Any]:
      

        if isinstance(analytics, dict):
            data = deepcopy(analytics)
        else:
            data = {
                "value": analytics,
            }

        with self._lock:
            self.analytics_trend.append(
                deepcopy(data)
            )

        return self.record_event(
            EVENT_ANALYTICS,
            {
                "analytics": data,
                "track_id": (
                    track_id
                    if track_id is not None
                    else self.track_id
                ),
            },
        )

    # ======================================================
    # HEARTBEAT INGESTION
    # ======================================================

    def receive_heartbeat(
        self,
        heartbeat,
    ) -> Dict[str, Any]:
       

        return self.record_event(
            EVENT_HEARTBEAT,
            heartbeat,
        )

    # ======================================================
    # PULSE CORRELATION
    # ======================================================

    def correlate_pulse(
        self,
        pulse: Optional[dict] = None,
        *,
        qbit=None,
        intent=None,
        analytics=None,
        actuator=None,
        track_id=None,
    ) -> Dict[str, Any]:
       

        pulse = (
            deepcopy(pulse)
            if isinstance(pulse, dict)
            else {}
        )

        snapshot = {
            "timestamp": time.time(),

            "track_id": (
                track_id
                if track_id is not None
                else (
                    pulse.get("track_id")
                    or self.track_id
                )
            ),

            "qbit": (
                self._extract_qbit_payload(qbit)
                if qbit is not None
                else pulse.get("qbit")
                or pulse.get("qbit_input")
            ),

            "intent": (
                deepcopy(intent)
                if intent is not None
                else pulse.get("intent")
                or pulse.get("dominant_intent")
            ),

            "analytics": (
                deepcopy(analytics)
                if analytics is not None
                else pulse.get("analytics")
            ),

            "actuator": (
                deepcopy(actuator)
                if actuator is not None
                else pulse.get("actuator_state")
            ),

            "agent": pulse,
        }

        snapshot["confidence"] = (
            pulse.get(
                "confidence",
                self._current_confidence(),
            )
        )

        snapshot["trend"] = (
            self.trend_snapshot()
        )

        return snapshot

    # ======================================================
    # TREND UPDATE
    # ======================================================

    def _update_trends(
        self,
        pulse: dict,
    ) -> None:
        

        if not isinstance(pulse, dict):
            return

        action_data = pulse.get(
            "action_data",
            {},
        )

        if not isinstance(action_data, dict):
            action_data = {}

        qbit_input = action_data.get(
            "qbit_input",
            pulse.get("qbit_input", 0.0),
        )

        if isinstance(
            qbit_input,
            (int, float),
        ):
            self.qbit_trend.append(
                float(qbit_input)
            )

        dominant_intent = pulse.get(
            "dominant_intent",
            pulse.get("intent", "idle"),
        )

        self.intent_trend.append(
            str(dominant_intent)
        )

        actuator_state = pulse.get(
            "actuator_state",
            {},
        )

        if isinstance(
            actuator_state,
            dict,
        ):
            self.actuator_trend.append(
                deepcopy(actuator_state)
            )

        confidence = pulse.get(
            "confidence",
            0.0,
        )

        if isinstance(
            confidence,
            (int, float),
        ):
            self.confidence_trend.append(
                float(confidence)
            )

    # ======================================================
    # TREND SNAPSHOT
    # ======================================================

    def trend_snapshot(self) -> Dict[str, Any]:
      
        with self._lock:

            qbit_values = [
                value
                for value in self.qbit_trend
                if isinstance(
                    value,
                    (int, float),
                )
            ]

            confidence_values = [
                value
                for value in self.confidence_trend
                if isinstance(
                    value,
                    (int, float),
                )
            ]

            avg_qbit = (
                sum(qbit_values)
                / len(qbit_values)
                if qbit_values
                else 0.0
            )

            avg_confidence = (
                sum(confidence_values)
                / len(confidence_values)
                if confidence_values
                else 0.0
            )

            intent_counts = Counter(
                self.intent_trend
            )

            dominant_intent = (
                intent_counts.most_common(1)[0][0]
                if intent_counts
                else "idle"
            )

            return {
                "window": self.TREND_WINDOW,

                "samples": {
                    "qbit": len(
                        self.qbit_trend
                    ),
                    "intent": len(
                        self.intent_trend
                    ),
                    "actuator": len(
                        self.actuator_trend
                    ),
                    "analytics": len(
                        self.analytics_trend
                    ),
                    "confidence": len(
                        self.confidence_trend
                    ),
                },

                "average_qbit": round(
                    avg_qbit,
                    6,
                ),

                "average_confidence": round(
                    avg_confidence,
                    6,
                ),

                "dominant_intent": (
                    dominant_intent
                ),

                "intent_distribution": dict(
                    intent_counts
                ),
            }

    # ======================================================
    # ADAPTIVE SIGNAL
    # ======================================================

    def adaptive_signal(self) -> Dict[str, Any]:
       

        trend = self.trend_snapshot()

        confidence = trend[
            "average_confidence"
        ]

        qbit_value = trend[
            "average_qbit"
        ]

        # Simple normalized signal.
        strength = (
            abs(qbit_value)
            * max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            )
        )

        return {
            "timestamp": time.time(),
            "dominant_intent": trend[
                "dominant_intent"
            ],
            "average_qbit": qbit_value,
            "average_confidence": confidence,
            "adaptive_strength": round(
                strength,
                6,
            ),
            "recommendation": (
                "observe"
                if confidence < 0.5
                else "evaluate"
            ),
        }

    # ======================================================
    # QBIT HELPERS
    # ======================================================

    @staticmethod
    def _extract_qbit_payload(
        qbit,
    ) -> Dict[str, Any]:
       

        if qbit is None:
            return {}

        if isinstance(qbit, dict):
            return deepcopy(qbit)

        for method_name in (
            "to_dict",
            "as_dict",
        ):

            method = getattr(
                qbit,
                method_name,
                None,
            )

            if callable(method):

                try:

                    value = method()

                    if isinstance(
                        value,
                        dict,
                    ):
                        return deepcopy(value)

                except Exception:
                    pass

        payload = getattr(
            qbit,
            "payload",
            None,
        )

        if isinstance(
            payload,
            dict,
        ):
            return deepcopy(payload)

        data = getattr(
            qbit,
            "data",
            None,
        )

        if isinstance(
            data,
            dict,
        ):
            return deepcopy(data)

        try:

            value = vars(qbit)

            if isinstance(
                value,
                dict,
            ):
                return deepcopy(value)

        except TypeError:
            pass

        return {
            "value": qbit,
        }

    @staticmethod
    def _extract_numeric_qbit(
        payload: dict,
    ) -> float:
        
        if not isinstance(
            payload,
            dict,
        ):
            return 0.0

        for key in (
            "value",
            "amplitude",
            "strength",
            "score",
            "energy",
            "probability",
            "confidence",
        ):

            value = payload.get(key)

            if isinstance(
                value,
                (int, float),
            ):
                return float(value)

        return 0.0

    @staticmethod
    def _extract_confidence(
        payload: dict,
    ) -> float:
        

        if not isinstance(
            payload,
            dict,
        ):
            return 0.0

        value = payload.get(
            "confidence",
            0.0,
        )

        if not isinstance(
            value,
            (int, float),
        ):
            return 0.0

        return max(
            0.0,
            min(
                1.0,
                float(value),
            ),
        )

    # ======================================================
    # CONFIDENCE
    # ======================================================

    def _current_confidence(self) -> float:
        with self._lock:

            if not self.confidence_trend:
                return 0.0

            values = [
                value
                for value in self.confidence_trend
                if isinstance(
                    value,
                    (int, float),
                )
            ]

            if not values:
                return 0.0

            return max(
                0.0,
                min(
                    1.0,
                    sum(values)
                    / len(values),
                ),
            )

    # ======================================================
    # DIAGNOSTICS
    # ======================================================

    def diagnostics(self) -> Dict[str, Any]:
       

        with self._lock:

            return {
                "name": self.NAME,
                "version": self.VERSION,

                "enabled": self._enabled,
                "stopped": self._stopped,

                "lifecycle": {
                    "passive": True,
                    "startup_owner": False,
                    "creates_subsystems": False,
                    "creates_threads": False,
                    "creates_asyncio_loops": False,
                    "starts_qbit_dialer": False,
                    "starts_agent_manager": False,
                    "starts_heartbeat": False,
                },

                "components": (
                    self.component_status()
                ),

                "telemetry": {
                    "processed": (
                        self._processed_count
                    ),
                    "errors": (
                        self._error_count
                    ),
                    "last_event": (
                        self._last_event_type
                    ),
                    "last_event_at": (
                        self._last_event_at
                    ),
                    "last_error": (
                        self._last_error
                    ),
                },

                "trend": (
                    self.trend_snapshot()
                ),

                "adaptive": (
                    self.adaptive_signal()
                ),

                "track": {
                    "track_id": self.track_id,
                    "track_attached": (
                        self.track is not None
                    ),
                    "track_system_attached": (
                        self.track_system
                        is not None
                    ),
                },

                "created_at": self._created_at,
            }

    # ======================================================
    # STATUS
    # ======================================================

    def status(self) -> Dict[str, Any]:
       

        with self._lock:

            return {
                "component": self.NAME,
                "version": self.VERSION,
                "enabled": self._enabled,
                "running": (
                    self._enabled
                    and not self._stopped
                ),
                "passive": True,
                "startup_owner": False,
                "events_processed": (
                    self._processed_count
                ),
            }

    # ======================================================
    # LEGACY COMPATIBILITY
    # ======================================================

    async def trigger_qbit_cycle(
        self,
        qbit_signal=None,
    ):
      

        if qbit_signal is None:

            logger.debug(
                "[SEEDCoreIntegrationHub] "
                "trigger_qbit_cycle ignored | "
                "no externally supplied qbit"
            )

            return None

        return self.receive_qbit(
            qbit_signal
        )

    async def main_loop(
        self,
        update_interval=0.05,
    ):
       

        logger.warning(
            "[SEEDCoreIntegrationHub] main_loop() is "
            "deprecated | integration hub does not own "
            "a background loop"
        )

        return self.status()

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(self) -> str:

        with self._lock:

            return (
                "SEEDCoreFullSystem("
                f"version={self.VERSION!r}, "
                f"enabled={self._enabled!r}, "
                f"passive=True, "
                f"startup_owner=False, "
                f"qbit_dialer="
                f"{self.qbit_dialer is not None!r}, "
                f"agent_manager="
                f"{self.agent_manager is not None!r}"
                ")"
            )


# ==========================================================
# MODERN ALIAS
# ==========================================================
#
# New code should use:
#
#     SEEDCoreIntegrationHub
#
# Existing code may continue importing:
#
#     SEEDCoreFullSystem
#
# ==========================================================

SEEDCoreIntegrationHub = SEEDCoreFullSystem


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "SEEDCoreFullSystem",
    "SEEDCoreIntegrationHub",
    "VERSION",
]


# ==========================================================
# IMPORTANT
# ==========================================================
#
# THERE IS INTENTIONALLY NO:
#
#     if __name__ == "__main__":
#         ...
#
# There is no standalone boot mode anymore.
#
# This module belongs to the SEED runtime and must not become
# another competing runtime.
#
# ==========================================================