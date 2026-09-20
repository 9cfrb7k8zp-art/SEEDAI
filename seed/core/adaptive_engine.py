# ============================================================
# FILE: adaptive_engine.py
# PATH: C:\SEED_ROOT\seed\core\adaptive\adaptive_engine.py
#
# VERSION: 0.9.0
# STATUS: Stable / Async / Dynamic / Qbit-Integrated /
#         QueueLoop-Bound / Resource-Aware
# PLATFORM: Cross-platform
#
# SEED MODULE: Adaptive / Optimization Engine
# COMPONENT: Autonomous Learning & Resource Management
#
# ARCHITECTURE:
#
# SEEDEventBus   -> feedback + resource request transport
# Qbit           -> cognitive state / task carrier / identity
# QbitQueueLoop  -> authoritative Qbit transport
# QbitDialer     -> authoritative command authority
# TrackSystem    -> execution / feedback / track authority
# Analytics      -> performance observation
# Memory         -> historical reinforcement
# ResourceMgr    -> authoritative resource allocation
#
# RESOURCE FLOW:
#
# AdaptiveEngine
#       |
#       v
# RESOURCE_REQUEST
#       |
#       v
# Authoritative Resource Manager
#       |
#       v
# RESOURCE_RESPONSE
#       |
#       v
# AdaptiveEngine
#
# RULES:
#
# AdaptiveEngine NEVER:
#
# - creates a competing Qbit
# - creates a competing QbitDialer
# - creates a competing QbitQueueLoop
# - executes commands directly through another authority
# - allocates protected system resources by itself
# - bypasses QbitDialer command authority
# - replaces the authoritative Qbit
# - replaces the authoritative QbitQueueLoop
#
# AdaptiveEngine MAY:
#
# - analyze system conditions
# - identify resource requirements
# - submit resource requests
# - attach to an authoritative resource manager
# - attach to the authoritative QbitQueueLoop
# - receive resource decisions
# - learn from granted / denied / deferred requests
#
# ============================================================

import asyncio
import logging
import threading
import time
import tracemalloc
import uuid
from collections import deque
from typing import Dict, Optional, Callable, Any

import requests

from seed.core.event_bus import (
    SEEDEventBus,
    COMMAND_EXECUTED,
    SYSTEM_WARNING,
)

from seed.core.dialers.qbit_dialer import QbitDialer
from seed.core.qbit import Qbit
from seed.core.actuator_engine import ActuatorEngine
from seed.systemutils.instruction_decoder import InstructionDecoder


logger = logging.getLogger("AdaptiveEngine")
logger.setLevel(logging.INFO)


class SEEDAdaptiveEngine:

    VERSION = "0.9.0"

    # ========================================================
    # EVENT NAMES
    # ========================================================

    RESOURCE_REQUEST_EVENT = "RESOURCE_REQUEST"
    RESOURCE_RESPONSE_EVENT = "RESOURCE_RESPONSE"

    # ========================================================
    # RESOURCE STATES
    # ========================================================

    RESOURCE_PENDING = "PENDING"
    RESOURCE_GRANTED = "GRANTED"
    RESOURCE_DENIED = "DENIED"
    RESOURCE_DEFERRED = "DEFERRED"
    RESOURCE_FAILED = "FAILED"

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        *,
        emit= None,
        task=None,
        track=None,
        qbit_dialer=None,
        qbit=None,
        qbit_queue_loop=None,
        queue_loop=None,
        sparkplug=None,
        event_bus=None,
        actuator_engine=None,
        scheduler=None,
        registry=None,
        nodes=None,
        seedcore=None,
        memory_manager=None,
        analytics_engine=None,
        seed_init_event=None,
        intent_engine=None,
        adaptive_priority_engine=None,
        growth_tree=None,
        agent_manager=None,
        track_system=None,
        track_context=None,
        constraint_guardian=None,
        ethics_manager=None,
        instruction_decoder=None,
        resource_manager=None,
        check_interval=60.0,
        resource_request_timeout=10.0,
    ):
        # ====================================================
        # CORE STATE
        # ====================================================

        self.task = task
        self.track = track
        self.track_system = track_system
        self.track_context = track_context

        self.event_bus = event_bus
        if self.event_bus is not None:
            self._attach_event_bus(self.event_bus)
        
        self.emit = emit

        # ----------------------------------------------------
        # Authoritative cognitive / transport references.
        #
        # These are injected only.
        # AdaptiveEngine never creates replacements.
        # ----------------------------------------------------

        self.qbit = qbit
        self.decoder = instruction_decoder
        if self.qbit is not None:
            self.attach_qbit(self.qbit)

        self.queue_loop = None
        self.qbit_queue_loop = None
        self.qbit_dialer = qbit_dialer
        if self.qbit_dialer is not None:
            self.attach_qbit_dialer(self.qbit_dialer)

        # ======================================================
        # AUTHORITATIVE QBIT QUEUE LOOP
        # ======================================================

        if (
            queue_loop is not None
            and qbit_queue_loop is not None
            and queue_loop is not qbit_queue_loop
        ):
            raise RuntimeError(
                "[AdaptiveEngine] QbitQueueLoop identity mismatch "
                "between queue_loop and qbit_queue_loop"
            )

        self.queue_loop = (
            qbit_queue_loop 
            if qbit_queue_loop is not None
            else queue_loop
        )

        if self.queue_loop is not None:
            self.attach_queue_loop(self.queue_loop)


        self.sparkplug = sparkplug
        self.actuator_engine = actuator_engine
        self.scheduler = scheduler
        self.memory_manager = memory_manager
        self.analytics_engine = analytics_engine
        self.constraint_guardian = constraint_guardian
        self.ethics_manager = ethics_manager
        self.instruction_decoder = instruction_decoder
        self.resource_manager = resource_manager

        self.intent_engine = intent_engine
        self.adaptive_priority_engine = adaptive_priority_engine
        self.growth_tree = growth_tree
        self.analytics_engine = analytics_engine
        self.agent_manager = agent_manager
        self.memory_manager = memory_manager
        self.seed_init_event = seed_init_event

        self.thought_packet = None
        self.cognitive_result = None
        self.last_intent = None
        self.last_action = None
        self.last_learning_result = None

        self.cognitive_history = deque(maxlen=5000)
        self.learning_history = deque(maxlen=5000)
        self.autonomous_decision_history = deque(maxlen=2000)

        self._cognitive_lock = asyncio.Lock()
        self._autonomous_cycle = 0
        self._idle_cognition_enabled = True
        self._learning_enabled = True

        # ======================================================
        # TRACK / IDENTITY RUNTIME
        # ======================================================

        self.track_system = track_system
        self.track_context = track_context
        self.registry = registry
        self.nodes = nodes
        self.seedcore = seedcore


        # ====================================================
        # RESOURCE AUTHORITY
        #
        # This is an injected authoritative resource manager.
        #
        # AdaptiveEngine does NOT create one.
        # ====================================================

        self.resource_manager = None

        self.resource_request_timeout = max(
            float(resource_request_timeout),
            0.25,
        )

        self.pending_resource_requests = {}

        self.resource_history = deque(
            maxlen=2000
        )

        self.resource_statistics = {
            "requested": 0,
            "granted": 0,
            "denied": 0,
            "deferred": 0,
            "failed": 0,
        }

        self.check_interval = max(
            float(check_interval),
            0.25,
        )

        self._running = False
        self._monitor_task = None
        self._lock = threading.RLock()

        # ====================================================
        # FEEDBACK STATE
        # ====================================================

        self.performance_log = deque(
            maxlen=5000
        )

        self.knowledge_cache = {}

        self.feedback_history = deque(
            maxlen=1000
        )

        self.last_feedback = None
        self.last_qbit_feedback = None
        self.last_command_feedback = None
        self.last_pipeline_update = None
        self.tool_adapter = None
        self._last_tool_request_at = 0.0

        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0

        self.signals = {
            "unknown_intent": 0,
            "repeated_failure": 0,
            "missing_data": 0,
            "confidence_low": 0,
            "resource_pressure": 0,
            "resource_denied": 0,
        }

        self.signal_thresholds = {
            "unknown_intent": 3,
            "repeated_failure": 3,
            "missing_data": 3,
            "confidence_low": 3,
            "resource_pressure": 3,
            "resource_denied": 3,
        }

        # ====================================================
        # ASYNC SKILL QUEUE
        # ====================================================

        self.skill_queue = asyncio.Queue()

        self.skills: Dict[str, Callable] = {}

        # ====================================================
        # TELEMETRY
        # ====================================================

        self._tracemalloc_started = False

        try:
            tracemalloc.start()
            self._tracemalloc_started = True
        except Exception:
            pass

        # ====================================================
        # AUTHORITATIVE DEPENDENCY ATTACHMENT
        # ====================================================

        if self.event_bus is not None:
            self._attach_event_bus(
                self.event_bus
            )

        if qbit is not None:
            self.attach_qbit(
                qbit
            )

        if queue_loop is not None:
            self.attach_queue_loop(
                queue_loop
            )

        if qbit_dialer is not None:
            self.attach_qbit_dialer(
                qbit_dialer
            )

        if resource_manager is not None:
            self.attach_resource_manager(
                resource_manager
            )

        if (
            self.decoder is not None
            and self.qbit_dialer is not None
        ):
            self._attach_decoder()

        logger.info(
            "[AdaptiveEngine] Initialized | "
            "version=%s | "
            "event_bus=%s | "
            "qbit=%s | "
            "queue_loop=%s | "
            "qbit_dialer=%s | "
            "track_system=%s | "
            "analytics=%s | "
            "memory=%s | "
            "resource_manager=%s",
            self.VERSION,
            type(self.event_bus).__name__
            if self.event_bus
            else "NONE",
            type(self.qbit).__name__
            if self.qbit
            else "NONE",
            type(self.queue_loop).__name__
            if self.queue_loop
            else "NONE",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer
            else "NONE",
            type(self.track_system).__name__
            if self.track_system
            else "NONE",
            type(self.analytics_engine).__name__
            if self.analytics_engine
            else "NONE",
            type(self.memory_manager).__name__
            if self.memory_manager
            else "NONE",
            type(self.resource_manager).__name__
            if self.resource_manager
            else "NONE",
        )

    # ========================================================
    # RUNTIME BINDING
    # ========================================================

    def _get_seed_module_context(self):

        init_event = getattr(
            self,
            "seed_init_event",
            None,
        )

        if init_event is None:
            return {}

        context = {}

        for name in (
            "qbit_dialer",
            "intent_engine",
            "analytics_engine",
            "agent_manager",
            "memory_manager",
            "registry",
            "node_registry",
            "node_manager",
            "control_layer",
            "orchestrator",
        ):
            value = getattr(
                init_event,
                name,
                None,
            )

            if value is not None:
                context[name] = value

        capabilities = getattr(
            init_event,
            "runtime_capabilities",
            None,
        )

        if isinstance(capabilities, dict):
            context["runtime_capabilities"] = dict(
                capabilities
            )

        return context

    def ingest_cognitive_input(
        self,
        *,
        source,
        payload,
        qbit=None,
        thought_packet=None,
        cognitive_result=None,
        intent=None,
        analytics=None,
    ):

        record = {
            "source": source,
            "timestamp": time.time(),
            "qbit": qbit,
            "thought_packet": thought_packet,
            "cognitive_result": cognitive_result,
            "intent": intent,
            "analytics": analytics,
            "payload": payload,
        }

        self.cognitive_history.append(
            record
        )

        if thought_packet is not None:
            self.thought_packet = (
                thought_packet
            )

        if cognitive_result is not None:
            self.cognitive_result = (
                cognitive_result
            )

        if intent is not None:
            self.last_intent = intent
 
        return record

    async def ingest_thought_packet(
        self,
        thought_packet,
        *,
        qbit=None,
        metadata=None,
    ):

        self.ingest_cognitive_input(
            source="ThoughtPacket",
            payload=metadata or {},
            qbit=qbit,
            thought_packet=thought_packet,
        )

        await self._learn_from_thought(
            thought_packet
        )

        return True

    async def ingest_cognitive_result(
        self,
        cognitive_result,
    ):

        if not isinstance(
            cognitive_result,
            dict,
        ):
            return False

        self.cognitive_result = (
            cognitive_result
        )

        self.ingest_cognitive_input(
            source="CognitiveResult",
            payload=cognitive_result,
            qbit=cognitive_result.get(
                "qbit"
            ),
            thought_packet=cognitive_result.get(
                "thought"
            ),
            cognitive_result=cognitive_result,
            intent=cognitive_result.get(
                "intent"
            ),
        )

        await self._learn_from_cognitive_result(
            cognitive_result
        )

        return True

    async def _evaluate_intent(
        self,
        cognitive_context,
    ):

        engine = getattr(
            self,
            "intent_engine",
            None,
        )

        if engine is None:
            return None

        result = None

        for method_name in (
            "score_intents",
            "evaluate",
            "process",
            "handle",
            "ingest",
        ):

            method = getattr(
                engine,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                if method_name == "score_intents":
                    result = method(
                        resonance=cognitive_context.get(
                            "resonance",
                            0.0,
                        ),
                        sensors=cognitive_context.get(
                            "sensors",
                            {},
                        ),
                    )
                else:
                    result = method(
                        inputs=cognitive_context,
                        source="AdaptiveEngine",
                    )

                if asyncio.iscoroutine(result):
                    result = await result

                if method_name == "score_intents":
                    if isinstance(result, tuple):
                        result = {
                            "intent": result[0],
                            "scores": result[1],
                            "source": "AdaptiveEngine",
                        }

                    priority = getattr(
                        self,
                        "adaptive_priority_engine",
                        None,
                    )
                    if priority is not None:
                        priority.record_intent(
                            result,
                            source="AdaptiveEngine",
                            qbit=getattr(
                                self,
                                "qbit",
                                None,
                            ),
                        )

                return result

            except TypeError:

                try:

                    result = method(
                        cognitive_context
                    )

                    if asyncio.iscoroutine(result):
                        result = await result

                    return result

                except Exception:
                    continue

            except Exception:
                continue

        return None

    async def _analyze_cognitive_history(
        self,
    ):

        analytics = getattr(
            self,
            "analytics_engine",
            None,
        )

        if analytics is None:
            return None

        snapshot = {
            "source": "AdaptiveEngine",
            "cycle": self._autonomous_cycle,
            "thought": self.thought_packet,
            "cognitive_result": self.cognitive_result,
            "intent": self.last_intent,
            "feedback": self.last_feedback,
            "command_feedback":
                self.last_command_feedback,
            "history_depth":
                len(self.cognitive_history),
        }

        for method_name in (
            "analyze",
            "process",
            "record",
            "record_event",
            "track",
            "ingest",
        ):

            method = getattr(
                analytics,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    snapshot
                )

                if asyncio.iscoroutine(result):
                    result = await result

                return result

            except TypeError:

                try:

                    result = method(
                        event=snapshot
                    )

                    if asyncio.iscoroutine(result):
                        result = await result

                    return result

                except Exception:
                    continue

            except Exception:
                continue

        return None


    async def _autonomous_idle_cycle(
        self,
    ):

        if not self._idle_cognition_enabled:
            return None

        qbit = getattr(
            self,
            "qbit",
            None,
        )

        context = {
            "source": "AdaptiveEngine",
            "mode": "IDLE_COGNITION",
            "autonomous": True,
            "user_input_required": False,
            "cycle":
                self._autonomous_cycle,
            "qbit": qbit,
            "thought_packet":
                self.thought_packet,
            "cognitive_result":
                self.cognitive_result,
            "last_intent":
                self.last_intent,
            "last_feedback":
                self.last_feedback,
            "last_command_feedback":
                self.last_command_feedback,
            "resource_status":
                self.resource_status(),
            "signals":
                dict(self.signals),
            "seed_modules":
                self._get_seed_module_context(),
        }

        intent_result = (
            await self._evaluate_intent(
                context
            )
        )

        analytics_result = (
            await self._analyze_cognitive_history()
        )

        decision = {
            "source": "AdaptiveEngine",
            "mode": "IDLE_COGNITION",
            "intent": intent_result,
            "analytics": analytics_result,
            "context": context,
            "timestamp": time.time(),
        }

        self.autonomous_decision_history.append(
            decision
        )

        return decision

    async def _hand_off_to_qbit_dialer(
        self,
        cognitive_input,
    ):

        dialer = getattr(
            self,
            "qbit_dialer",
            None,
        )

        if dialer is None:
            return {
                "status": "no_dialer"
            }

        payload = {
            "source":
                "AdaptiveEngine",
            "authority":
                "QbitDialer",
            "stage":
                "AUTONOMOUS_COGNITION",
            "autonomous":
                True,
            "idle":
                True,
            "qbit":
                getattr(
                    self,
                    "qbit",
                    None,
                ),
            "thought_packet":
                self.thought_packet,
            "cognitive_result":
                self.cognitive_result,
            "intent":
                self.last_intent,
            "adaptive_decision":
                cognitive_input,
            "command_authority":
                "QbitDialer",
            "command_admission":
                "submit_command",
            "execution_owner":
                "QbitQueueLoop",
            "execute":
                False,
            "submit":
                False,
        }

        for method_name in (
            "_process_received_qbit",
            "receive_qbit",
        ):

            method = getattr(
                dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                authoritative_qbit = getattr(
                    self,
                    "qbit",
                    None,
                )

                if authoritative_qbit is None:
                    return {
                        "status": "no_qbit",
                        "reason": "authoritative_qbit_unavailable",
                    }

                if method_name == "_process_received_qbit":
                    result = method(
                        authoritative_qbit,
                        metadata=payload,
                    )
                else:
                    result = method(
                        authoritative_qbit,
                        adaptive_context=payload,
                    )

                if asyncio.iscoroutine(result):
                    result = await result

                return result

            except TypeError:
                continue

            except Exception:
                logger.exception(
                    "[AdaptiveEngine] "
                    "QbitDialer cognitive handoff failed"
                )
                return {
                    "status": "handoff_failed"
                }

        return {
            "status":
                "dialer_has_no_cognitive_ingress"
        }

    async def _autonomous_cognitive_cycle(
        self,
    ):

        async with self._cognitive_lock:

            self._autonomous_cycle += 1

            try:

                decision = (
                    await self._autonomous_idle_cycle()
                )

                if decision is None:
                    return None

                result = (
                    await self._hand_off_to_qbit_dialer(
                        decision
                    )
                )

                learning_record = {
                    "cycle":
                        self._autonomous_cycle,
                    "decision":
                        decision,
                    "dialer_result":
                        result,
                    "timestamp":
                        time.time(),
                }

                self.learning_history.append(
                    learning_record
                )

                self.last_learning_result = (
                    learning_record
                )

                self._emit(
                    "ADAPTIVE_COGNITIVE_CYCLE",
                    learning_record,
                )

                return learning_record

            except Exception as exc:

                logger.exception(
                    "[AdaptiveEngine] "
                    "Autonomous cognitive cycle failed"
                )

                self._emit(
                    SYSTEM_WARNING,
                    {
                        "source":
                            "AdaptiveEngine",
                        "operation":
                            "autonomous_cognitive_cycle",
                        "error":
                            str(exc),
                    },
                )

                return None

    # ==========================================================

    # RUNTIME BINDING

    # ==========================================================

    def bind_runtime(
        self,
        *,
        event_bus=None,
        emit=None,
        qbit=None,
        qbit_dialer=None,
        queue_loop=None,
        qbit_queue_loop=None,
        track_system=None,
        track_context=None,
        registry=None,
        nodes=None,
        seedcore=None,
        analytics_engine=None,
        memory_manager=None,
        intent_engine=None,
        adaptive_priority_engine=None,
        growth_tree=None,
        constraint_guardian=None,
        ethics_manager=None,
        instruction_decoder=None,
        decoder=None,
        resource_manager=None,
        scheduler=None,
        actuator_engine=None,
    ):

        # ------------------------------------------------------
        # QueueLoop identity
        # ------------------------------------------------------

        if (
            queue_loop is not None
            and qbit_queue_loop is not None
            and queue_loop is not qbit_queue_loop
        ):
            raise RuntimeError(
                "[AdaptiveEngine] QbitQueueLoop identity mismatch "
                "between queue_loop and qbit_queue_loop"
            )

        resolved_queue_loop = (
            qbit_queue_loop
            if qbit_queue_loop is not None
            else queue_loop
        )

        if resolved_queue_loop is not None:
            self.attach_queue_loop(resolved_queue_loop)

        # ------------------------------------------------------
        # Qbit identity
        # ------------------------------------------------------

        if (
            qbit is not None
            and getattr(self, "qbit", None) is not None
            and self.qbit is not qbit
        ):
            raise RuntimeError(
                "[AdaptiveEngine] Qbit identity mismatch"
            )

        if qbit is not None:
            self.attach_qbit(qbit)

        # ------------------------------------------------------
        # QbitDialer identity
        # ------------------------------------------------------

        if (
            qbit_dialer is not None
            and getattr(self, "qbit_dialer", None) is not None
            and self.qbit_dialer is not qbit_dialer
        ):
            raise RuntimeError(
                "[AdaptiveEngine] QbitDialer identity mismatch"
            )

        if qbit_dialer is not None:
            self.attach_qbit_dialer(qbit_dialer)

        # ------------------------------------------------------
        # EventBus identity
        # ------------------------------------------------------

        if (
            event_bus is not None
            and getattr(self, "event_bus", None) is not None
            and self.event_bus is not event_bus
        ):
            raise RuntimeError(
                "[AdaptiveEngine] EventBus identity mismatch"
            )

        if event_bus is not None:
            self._attach_event_bus(event_bus)

        if emit is not None:
            self.emit = emit

        # ------------------------------------------------------
        # Runtime references
        # ------------------------------------------------------

        if track_system is not None:
            self.track_system = track_system

        if track_context is not None:
            self.track_context = track_context

        if registry is not None:
            self.registry = registry

        if nodes is not None:
            self.nodes = nodes

        if seedcore is not None:
            self.seedcore = seedcore

        # ------------------------------------------------------
        # Adaptive services
        # ------------------------------------------------------

        if analytics_engine is not None:
            self.analytics_engine = analytics_engine

        if intent_engine is not None:
            self.intent_engine = intent_engine

        if adaptive_priority_engine is not None:
            self.adaptive_priority_engine = adaptive_priority_engine

        if growth_tree is not None:
            self.growth_tree = growth_tree

        if memory_manager is not None:
            self.memory_manager = memory_manager

        if constraint_guardian is not None:
            self.constraint_guardian = constraint_guardian

        if ethics_manager is not None:
            self.ethics_manager = ethics_manager

        if instruction_decoder is not None:
            self.instruction_decoder = instruction_decoder

        if decoder is not None:
            self.decoder = decoder

        if resource_manager is not None:
            self.resource_manager = resource_manager

        if scheduler is not None:
            self.scheduler = scheduler

        if actuator_engine is not None:
            self.actuator_engine = actuator_engine

        logger.info(
            "[AdaptiveEngine] Runtime bound | "
            "event_bus=%s | qbit=%s | queue_loop=%s | "
            "qbit_dialer=%s | track_system=%s | "
            "registry=%s | nodes=%s | analytics=%s | memory=%s",
            type(self.event_bus).__name__
            if getattr(self, "event_bus", None) is not None
            else "NONE",
            type(self.qbit).__name__
            if getattr(self, "qbit", None) is not None
            else "NONE",
            type(self.queue_loop).__name__
            if getattr(self, "queue_loop", None) is not None
            else "NONE",
            type(self.qbit_dialer).__name__
            if getattr(self, "qbit_dialer", None) is not None
            else "NONE",
            type(self.track_system).__name__
            if getattr(self, "track_system", None) is not None
            else "NONE",
            type(self.registry).__name__
            if getattr(self, "registry", None) is not None
            else "NONE",
            type(self.nodes).__name__
            if getattr(self, "nodes", None) is not None
            else "NONE",
            type(self.analytics_engine).__name__
            if getattr(self, "analytics_engine", None) is not None
            else "NONE",
            type(self.memory_manager).__name__
            if getattr(self, "memory_manager", None) is not None
            else "NONE",
        )

        return True

    # ========================================================
    # EVENT EMISSION
    # ========================================================

    def _emit(
        self,
        event_name,
        payload=None,
    ):

        payload = payload or {}

        try:

            if (
                self.event_bus
                and callable(
                    getattr(
                        self.event_bus,
                        "emit",
                        None,
                    )
                )
            ):
                return self.event_bus.emit(
                    event_name,
                    payload,
                )

            if callable(self.emit):
                return self.emit(
                    event_name,
                    payload,
                )

        except Exception as exc:

            logger.warning(
                "[AdaptiveEngine] Feedback emit failed | "
                "event=%s | error=%s",
                event_name,
                exc,
            )

        return None

    # ========================================================
    # EVENT BUS
    # ========================================================

    def _attach_event_bus(
        self,
        event_bus,
    ):

        if event_bus is None:
            return False

        try:

            self.event_bus = event_bus

            subscribe = getattr(
                event_bus,
                "subscribe",
                None,
            )

            if callable(subscribe):

                try:
                    subscribe(
                        COMMAND_EXECUTED,
                        self._on_command_executed,
                    )
                except Exception as exc:

                    logger.debug(
                        "[AdaptiveEngine] "
                        "COMMAND_EXECUTED subscription "
                        "deferred: %s",
                        exc,
                    )

                try:
                    subscribe(
                        SYSTEM_WARNING,
                        self._on_system_warning,
                    )
                except Exception as exc:

                    logger.debug(
                        "[AdaptiveEngine] "
                        "SYSTEM_WARNING subscription "
                        "deferred: %s",
                        exc,
                    )

                try:
                    subscribe(
                        self.RESOURCE_RESPONSE_EVENT,
                        self._on_resource_response,
                    )
                except Exception as exc:
                    logger.debug(
                        "[AdaptiveEngine] RESOURCE_RESPONSE subscription deferred: %s",
                        exc,
                    )

                # Full cognitive lifecycle observation. AdaptiveEngine
                # learns from the pipeline; it never becomes command authority.
                for event_name, handler in (
                    ("INTENT_SCORED", self._on_pipeline_event),
                    ("ACTION_PROPOSAL", self._on_pipeline_event),
                    ("COGNITIVE_FEEDBACK", self._on_pipeline_event),
                    ("SEED_RUNTIME_READY", self._on_pipeline_event),
                    ("ORACLE_INPUT_ADMITTED", self._on_pipeline_event),
                    ("ORACLE_INPUT_REJECTED", self._on_pipeline_event),
                ):
                    try:
                        subscribe(event_name, handler)
                    except Exception as event_exc:
                        logger.debug(
                            "[AdaptiveEngine] pipeline subscription deferred | event=%s | %s",
                            event_name,
                            event_exc,
                        )

            logger.info(
                "[AdaptiveEngine] EventBus attached | %s",
                type(event_bus).__name__,
            )

            return True

        except Exception as exc:

            logger.warning(
                "[AdaptiveEngine] EventBus attach failed: %s",
                exc,
            )

            return False

    # ========================================================
    # QBIT ATTACHMENT
    # ========================================================

    def attach_qbit(
        self,
        qbit,
    ):

        if qbit is None:
            return False

        # ----------------------------------------------------
        # Once an authoritative Qbit is attached, do not
        # silently replace it with another Qbit instance.
        # ----------------------------------------------------

        if (
            self.qbit is not None
            and self.qbit is not qbit
        ):
            raise RuntimeError(
                "[SEEDAdaptiveEngine] "
                "Qbit identity mismatch"
            )

        self.qbit = qbit

        if self.event_bus is not None:

            try:

                if hasattr(
                    qbit,
                    "event_bus",
                ):
                    qbit.event_bus = (
                        self.event_bus
                    )

                if (
                    hasattr(qbit, "emit")
                    and callable(
                        getattr(
                            self.event_bus,
                            "emit",
                            None,
                        )
                    )
                ):
                    qbit.emit = (
                        self.event_bus.emit
                    )

            except Exception as exc:

                logger.debug(
                    "[AdaptiveEngine] "
                    "Qbit EventBus binding deferred: %s",
                    exc,
                )

        logger.info(
            "[AdaptiveEngine] Qbit attached | "
            "type=%s | identity=%s",
            type(qbit).__name__,
            hex(id(qbit)),
        )

        return True

    # ========================================================
    # QBIT QUEUE LOOP ATTACHMENT
    # ========================================================

    # ==========================================================
    # AUTHORITATIVE QBIT QUEUE LOOP
    # ==========================================================

    def attach_queue_loop(self, queue_loop):


        if queue_loop is None:
            return False

        if (
            getattr(self, "queue_loop", None) is not None
            and self.queue_loop is not queue_loop
        ):
            raise RuntimeError(
                "[AdaptiveEngine] QbitQueueLoop identity mismatch"
            )

        self.queue_loop = queue_loop

        logger.info(
            "[AdaptiveEngine] Authoritative QbitQueueLoop attached | %s",
            type(queue_loop).__name__,
        )

        return True

    # ========================================================
    # QBIT DIALER ATTACHMENT
    # ========================================================

    def attach_qbit_dialer(
        self,
        dialer,
    ):

        if dialer is None:
            return False

        if (
            self.qbit_dialer is not None
            and self.qbit_dialer is not dialer
        ):
            raise RuntimeError(
                "[SEEDAdaptiveEngine] "
                "QbitDialer identity mismatch"
            )

        self.qbit_dialer = dialer

        if self.event_bus is not None:

            try:

                if hasattr(
                    dialer,
                    "event_bus",
                ):
                    dialer.event_bus = (
                        self.event_bus
                    )

                if hasattr(
                    dialer,
                    "emit",
                ):
                    dialer.emit = (
                        self._emit
                    )

            except Exception as exc:

                logger.debug(
                    "[AdaptiveEngine] "
                    "Dialer EventBus binding deferred: %s",
                    exc,
                )

        if self.qbit is not None:

            try:

                dialer_qbit = getattr(
                    dialer,
                    "qbit",
                    None,
                )

                if (
                    dialer_qbit is not None
                    and dialer_qbit is not self.qbit
                ):
                    raise RuntimeError(
                        "[SEEDAdaptiveEngine] "
                        "QbitDialer Qbit identity mismatch"
                    )

                if hasattr(
                    dialer,
                    "qbit",
                ):
                    dialer.qbit = (
                        self.qbit
                    )

            except RuntimeError:
                raise

            except Exception as exc:

                logger.debug(
                    "[AdaptiveEngine] "
                    "Dialer Qbit binding deferred: %s",
                    exc,
                )

        self._attach_decoder()

        logger.info(
            "[AdaptiveEngine] QbitDialer attached | "
            "authority=%s | qbit=%s | "
            "event_bus=%s | identity=%s",
            getattr(
                dialer,
                "authority",
                "QbitDialer",
            ),
            type(
                getattr(
                    dialer,
                    "qbit",
                    None,
                )
            ).__name__
            if getattr(
                dialer,
                "qbit",
                None,
            )
            else "NONE",
            type(
                getattr(
                    dialer,
                    "event_bus",
                    None,
                )
            ).__name__
            if getattr(
                dialer,
                "event_bus",
                None,
            )
            else "NONE",
            hex(id(dialer)),
        )

        return True

    # ========================================================
    # DECODER
    # ========================================================

    def _attach_decoder(self):

        if (
            not self.qbit_dialer
            or not self.decoder
        ):
            return False

        try:

            attach_decoder = getattr(
                self.qbit_dialer,
                "attach_decoder",
                None,
            )

            if callable(
                attach_decoder
            ):
                attach_decoder(
                    self.decoder
                )

            return True

        except Exception as exc:

            logger.warning(
                "[AdaptiveEngine] "
                "Decoder attachment failed: %s",
                exc,
            )

            return False

    # ========================================================
    # SUBSYSTEM ATTACHMENT
    # ========================================================

    def attach_scheduler(
        self,
        scheduler,
    ):

        self.scheduler = scheduler

        logger.info(
            "[AdaptiveEngine] Scheduler attached"
        )

        return True

    def attach_memory(
        self,
        memory_manager,
    ):

        self.memory_manager = (
            memory_manager
        )

        logger.info(
            "[AdaptiveEngine] "
            "Memory manager attached"
        )

        return True

    def attach_analytics(
        self,
        analytics_engine,
    ):

        self.analytics_engine = (
            analytics_engine
        )

        logger.info(
            "[AdaptiveEngine] "
            "Analytics engine attached"
        )

        return True

    def attach_sparkplug(
        self,
        sparkplug,
    ):

        self.sparkplug = sparkplug

        logger.info(
            "[AdaptiveEngine] "
            "Sparkplug attached"
        )

        return True

    def attach_actuator(
        self,
        actuator_engine,
    ):

        self.actuator_engine = (
            actuator_engine
        )

        logger.info(
            "[AdaptiveEngine] "
            "ActuatorEngine attached"
        )

        return True

    def attach_track_system(
        self,
        track_system,
    ):

        self.track_system = (
            track_system
        )

        logger.info(
            "[AdaptiveEngine] "
            "TrackSystem attached"
        )

        return True

    # ========================================================
    # RESOURCE MANAGER ATTACHMENT
    # ========================================================

    def attach_resource_manager(
        self,
        resource_manager,
    ):

        if resource_manager is None:
            return False

        if (
            self.resource_manager is not None
            and self.resource_manager is not resource_manager
        ):
            raise RuntimeError(
                "[SEEDAdaptiveEngine] "
                "ResourceManager identity mismatch"
            )

        self.resource_manager = (
            resource_manager
        )

        logger.info(
            "[AdaptiveEngine] "
            "Resource manager attached | "
            "type=%s | identity=%s",
            type(
                resource_manager
            ).__name__,
            hex(id(resource_manager)),
        )

        return True

    # ========================================================
    # RESOURCE IDENTITY
    # ========================================================

    def _resolve_track_id(self):

        if self.track is not None:

            if isinstance(
                self.track,
                str,
            ):
                return self.track

            for attr in (
                "track_id",
                "id",
            ):

                value = getattr(
                    self.track,
                    attr,
                    None,
                )

                if value:
                    return value

        if self.qbit is not None:

            value = getattr(
                self.qbit,
                "track_id",
                None,
            )

            if value:
                return value

        if self.track_system is not None:

            for attr in (
                "current_track_id",
                "track_id",
            ):

                value = getattr(
                    self.track_system,
                    attr,
                    None,
                )

                if value:
                    return value

        return None

    def _resolve_qbit_id(self):

        if self.qbit is None:
            return None

        return getattr(
            self.qbit,
            "qbit_id",
            getattr(
                self.qbit,
                "id",
                None,
            ),
        )

    # ========================================================
    # RESOURCE REQUEST
    # ========================================================

    def request_resource(
        self,
        resource,
        *,
        amount=1,
        priority="MEDIUM",
        reason=None,
        constraints=None,
        duration=None,
        metadata=None,
        wait=False,
        timeout=None,
    ):

        request_id = (
            "RESREQ-"
            + uuid.uuid4().hex
        )

        track_id = (
            self._resolve_track_id()
        )

        qbit_id = (
            self._resolve_qbit_id()
        )

        request = {
            "request_id": request_id,
            "resource": str(
                resource
            ),
            "amount": amount,
            "priority": priority,
            "reason": reason,
            "constraints": dict(
                constraints or {}
            ),
            "duration": duration,
            "metadata": dict(
                metadata or {}
            ),
            "source": "AdaptiveEngine",
            "track_id": track_id,
            "qbit_id": qbit_id,
            "timestamp": time.time(),
            "status": self.RESOURCE_PENDING,
        }

        if self.qbit is not None:
            request["qbit"] = self.qbit

        with self._lock:

            self.pending_resource_requests[
                request_id
            ] = request

            self.resource_statistics[
                "requested"
            ] += 1

            self.resource_history.append(
                dict(request)
            )

        if self.resource_manager is not None:

            try:

                result = (
                    self._delegate_resource_request(
                        request
                    )
                )

                if asyncio.iscoroutine(
                    result
                ):
                    try:
                        loop = asyncio.get_running_loop()

                        loop.create_task(
                            self._consume_resource_result(
                                request_id,
                                result,
                            )
                        )

                    except RuntimeError:
                        pass

                elif result is not None:

                    self._consume_resource_result_sync(
                        request_id,
                        result,
                    )

            except Exception as exc:

                logger.warning(
                    "[AdaptiveEngine] "
                    "Resource manager delegation failed | "
                    "request=%s | error=%s",
                    request_id,
                    exc,
                )

        emitted = self._emit(
            self.RESOURCE_REQUEST_EVENT,
            request,
        )

        if emitted is None:

            logger.debug(
                "[AdaptiveEngine] "
                "Resource request emitted without "
                "EventBus result | request=%s",
                request_id,
            )

        if wait:

            try:
                asyncio.get_running_loop()

                return self._wait_for_resource_response(
                    request_id,
                    timeout=(
                        timeout
                        if timeout is not None
                        else self.resource_request_timeout
                    ),
                )

            except RuntimeError:

                logger.warning(
                    "[AdaptiveEngine] "
                    "wait=True requires a running "
                    "asyncio loop | request=%s",
                    request_id,
                )

        return request

    # ========================================================
    # RESOURCE DELEGATION
    # ========================================================

    def _delegate_resource_request(
        self,
        request,
    ):

        manager = (
            self.resource_manager
        )

        for method_name in (
            "request_resource",
            "request",
            "allocate_request",
        ):

            method = getattr(
                manager,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                return method(
                    request
                )

            except TypeError:

                try:

                    return method(
                        resource=request[
                            "resource"
                        ],
                        amount=request[
                            "amount"
                        ],
                        priority=request[
                            "priority"
                        ],
                        reason=request[
                            "reason"
                        ],
                        constraints=request[
                            "constraints"
                        ],
                        metadata=request[
                            "metadata"
                        ],
                    )

                except TypeError:
                    continue

        logger.debug(
            "[AdaptiveEngine] "
            "Resource manager exposes no compatible "
            "request method"
        )

        return None

    # ========================================================
    # ASYNC RESOURCE RESULT CONSUMER
    # ========================================================

    async def _consume_resource_result(
        self,
        request_id,
        awaitable,
    ):

        try:

            result = await awaitable

            self._consume_resource_result_sync(
                request_id,
                result,
            )

            return result

        except Exception as exc:

            self._mark_resource_failed(
                request_id,
                str(exc),
            )

            return None

    # ========================================================
    # RESOURCE RESULT NORMALIZATION
    # ========================================================

    def _consume_resource_result_sync(
        self,
        request_id,
        result,
    ):

        if not isinstance(
            result,
            dict,
        ):
            result = {
                "result": result
            }

        response = dict(result)

        response.setdefault(
            "request_id",
            request_id,
        )

        self._apply_resource_response(
            response
        )

    # ========================================================
    # RESOURCE RESPONSE
    # ========================================================

    def _on_resource_response(
        self,
        event,
    ):

        try:

            payload = (
                event.get(
                    "payload",
                    {},
                )
                if isinstance(
                    event,
                    dict,
                )
                else event
            )

            if not isinstance(
                payload,
                dict,
            ):
                payload = {
                    "result": payload
                }

            self._apply_resource_response(
                payload
            )

        except Exception as exc:

            logger.warning(
                "[AdaptiveEngine] "
                "Resource response processing failed: %s",
                exc,
            )

    # ========================================================
    # APPLY RESOURCE RESPONSE
    # ========================================================

    def _apply_resource_response(
        self,
        response,
    ):

        request_id = response.get(
            "request_id"
        )

        if not request_id:
            return False

        with self._lock:

            request = (
                self.pending_resource_requests.get(
                    request_id
                )
            )

        if request is None:

            logger.debug(
                "[AdaptiveEngine] "
                "Unknown resource response | "
                "request=%s",
                request_id,
            )

            return False

        status = str(
            response.get(
                "status",
                self.RESOURCE_FAILED,
            )
        ).upper()

        if status in {
            "GRANTED",
            "ALLOCATED",
            "APPROVED",
            "SUCCESS",
            "OK",
        }:
            normalized_status = (
                self.RESOURCE_GRANTED
            )

            self.resource_statistics[
                "granted"
            ] += 1

        elif status in {
            "DENIED",
            "REJECTED",
        }:
            normalized_status = (
                self.RESOURCE_DENIED
            )

            self.resource_statistics[
                "denied"
            ] += 1

            self.signals[
                "resource_denied"
            ] += 1

        elif status in {
            "DEFERRED",
            "QUEUED",
            "WAITING",
        }:
            normalized_status = (
                self.RESOURCE_DEFERRED
            )

            self.resource_statistics[
                "deferred"
            ] += 1

        else:
            normalized_status = (
                self.RESOURCE_FAILED
            )

            self.resource_statistics[
                "failed"
            ] += 1

        request.update(
            {
                "status": normalized_status,
                "response": response,
                "response_timestamp": time.time(),
            }
        )

        self.resource_history.append(
            dict(request)
        )

        self.pending_resource_requests.pop(
            request_id,
            None,
        )

        self._emit(
            "ADAPTIVE_RESOURCE_RESULT",
            {
                "source": "AdaptiveEngine",
                "request_id": request_id,
                "resource": request.get(
                    "resource"
                ),
                "status": normalized_status,
                "response": response,
                "track_id": request.get(
                    "track_id"
                ),
                "qbit_id": request.get(
                    "qbit_id"
                ),
            },
        )

        logger.info(
            "[AdaptiveEngine] "
            "Resource response | "
            "request=%s | resource=%s | status=%s",
            request_id,
            request.get(
                "resource"
            ),
            normalized_status,
        )

        return True

    # ========================================================
    # RESOURCE FAILURE
    # ========================================================

    def _mark_resource_failed(
        self,
        request_id,
        error,
    ):

        return self._apply_resource_response(
            {
                "request_id": request_id,
                "status": self.RESOURCE_FAILED,
                "error": str(error),
            }
        )

    # ========================================================
    # RESOURCE WAIT
    # ========================================================

    async def _wait_for_resource_response(
        self,
        request_id,
        timeout=None,
    ):

        timeout = (
            self.resource_request_timeout
            if timeout is None
            else max(
                float(timeout),
                0.25,
            )
        )

        deadline = (
            time.monotonic()
            + timeout
        )

        while time.monotonic() < deadline:

            with self._lock:

                request = (
                    self.pending_resource_requests.get(
                        request_id
                    )
                )

            if request is None:

                for item in reversed(
                    self.resource_history
                ):

                    if (
                        item.get(
                            "request_id"
                        )
                        == request_id
                    ):
                        return item

            await asyncio.sleep(
                0.05
            )

        self._mark_resource_failed(
            request_id,
            "resource request timeout",
        )

        return {
            "request_id": request_id,
            "status": self.RESOURCE_FAILED,
            "error": "resource request timeout",
        }

    # ========================================================
    # RESOURCE SNAPSHOT
    # ========================================================

    def resource_status(self):

        manager = (
            self.resource_manager
        )

        manager_status = None

        if manager is not None:

            try:

                status_method = getattr(
                    manager,
                    "status",
                    None,
                )

                if callable(
                    status_method
                ):
                    manager_status = (
                        status_method()
                    )

            except Exception as exc:

                manager_status = {
                    "error": str(exc)
                }

        return {
            "resource_manager": (
                type(manager).__name__
                if manager
                else None
            ),
            "resource_manager_attached": (
                manager is not None
            ),
            "pending_requests": len(
                self.pending_resource_requests
            ),
            "history": len(
                self.resource_history
            ),
            "statistics": dict(
                self.resource_statistics
            ),
            "manager_status": (
                manager_status
            ),
        }

    # ========================================================
    # FEEDBACK LOOP
    # ========================================================

    def _record_feedback(
        self,
        feedback,
    ):

        if not isinstance(
            feedback,
            dict,
        ):
            feedback = {
                "value": feedback
            }

        feedback = dict(
            feedback
        )

        feedback.setdefault(
            "timestamp",
            time.time(),
        )

        self.last_feedback = (
            feedback
        )

        self.feedback_history.append(
            feedback
        )

        self.performance_log.append(
            feedback
        )

        status = str(
            feedback.get(
                "status",
                feedback.get(
                    "result",
                    "",
                ),
            )
        ).lower()

        if status in {
            "success",
            "completed",
            "complete",
            "ok",
            "true",
        }:

            self.success_count += 1

        elif status in {
            "failed",
            "failure",
            "error",
            "false",
        }:

            self.failure_count += 1

            self.signals[
                "repeated_failure"
            ] += 1

        self.execution_count += 1

    # ========================================================
    # COMMAND FEEDBACK
    # ========================================================

    def _on_command_executed(
        self,
        event,
    ):

        try:

            payload = (
                event.get(
                    "payload",
                    {},
                )
                if isinstance(
                    event,
                    dict,
                )
                else event
            )

            if not isinstance(
                payload,
                dict,
            ):
                payload = {
                    "payload": payload
                }

            self.last_command_feedback = (
                payload
            )

            self._record_feedback(
                {
                    "source":
                        "COMMAND_EXECUTED",
                    **payload,
                }
            )

            self._evaluate_feedback_signals(
                payload
            )

        except Exception as exc:

            logger.warning(
                "[AdaptiveEngine] "
                "Command feedback error: %s",
                exc,
            )

    # ========================================================
    # PIPELINE FEEDBACK / ADAPTIVE UPDATE
    # ========================================================

    def _on_pipeline_event(self, event):
        try:
            payload = event.get("payload", event) if isinstance(event, dict) else event
            if not isinstance(payload, dict):
                payload = {"payload": payload}

            event_name = event.get("event", event.get("type")) if isinstance(event, dict) else None
            update = {
                "timestamp": time.time(),
                "source": "AdaptiveEngine",
                "event": event_name,
                "stage": payload.get("stage") or payload.get("cognitive_stage"),
                "qbit_id": payload.get("qbit_id"),
                "track_id": payload.get("track_id"),
                "intent": payload.get("intent") or payload.get("dominant"),
                "action": payload.get("action") or payload.get("name"),
                "command": payload.get("command") or payload.get("command_name"),
                "status": payload.get("status"),
                "feedback": payload.get("feedback"),
            }
            self.last_pipeline_update = update
            self.learning_history.append({"pipeline_update": update})
            self._evaluate_feedback_signals(payload)
            self._emit("ADAPTIVE_PIPELINE_UPDATE", update)
            return update
        except Exception as exc:
            logger.debug("[AdaptiveEngine] pipeline update failed | %s", exc)
            return None

    # ========================================================
    # SYSTEM WARNING
    # ========================================================

    def _on_system_warning(
        self,
        event,
    ):

        try:

            payload = (
                event.get(
                    "payload",
                    {},
                )
                if isinstance(
                    event,
                    dict,
                )
                else event
            )

            self.performance_log.append(
                {
                    "source":
                        "SYSTEM_WARNING",
                    "warning":
                        payload,
                    "timestamp":
                        time.time(),
                }
            )

            if isinstance(
                payload,
                dict,
            ):
                self._evaluate_feedback_signals(
                    payload
                )

        except Exception as exc:

            logger.debug(
                "[AdaptiveEngine] "
                "Warning feedback error: %s",
                exc,
            )

    # ========================================================
    # FEEDBACK SIGNALS
    # ========================================================

    def _evaluate_feedback_signals(
        self,
        payload,
    ):

        if not isinstance(
            payload,
            dict,
        ):
            return

        error_text = str(
            payload.get(
                "error",
                payload.get(
                    "reason",
                    "",
                ),
            )
        ).lower()

        if (
            "unknown" in error_text
            or "intent" in error_text
        ):
            self.signals[
                "unknown_intent"
            ] += 1

        if error_text:
            self.signals[
                "repeated_failure"
            ] += 1

        if (
            payload.get("data")
            is None
            or payload.get(
                "missing_data"
            ) is True
        ):
            self.signals[
                "missing_data"
            ] += 1

        confidence = payload.get(
            "confidence"
        )

        if confidence is not None:

            try:

                if float(
                    confidence
                ) < 0.5:

                    self.signals[
                        "confidence_low"
                    ] += 1

            except (
                TypeError,
                ValueError,
            ):
                pass

        resource_pressure = (
            payload.get(
                "resource_pressure"
            )
        )

        if (
            resource_pressure is True
            or str(
                payload.get(
                    "resource_status",
                    "",
                )
            ).upper()
            in {
                "PRESSURE",
                "CRITICAL",
                "EXHAUSTED",
            }
        ):

            self.signals[
                "resource_pressure"
            ] += 1

            # Pressure is a signal to request an external skill/tool,
            # not permission for AdaptiveEngine to execute one. The
            # resulting TOOL_REQUEST returns through the normal Dialer
            # authority path.
            now = time.time()
            if now - self._last_tool_request_at >= 60.0:
                try:
                    if self.tool_adapter is None:
                        from seed.tools.desktop_commander_adapter import DesktopCommanderAdapter
                        self.tool_adapter = DesktopCommanderAdapter(
                            event_bus=self.event_bus,
                            dialer=self.qbit_dialer,
                        )
                    self.tool_adapter.request(
                        skill="resource_pressure_diagnosis",
                        reason="AdaptiveEngine detected sustained resource pressure",
                        pressure={
                            "resource_pressure": True,
                            "resource_status": payload.get("resource_status"),
                            "cpu": payload.get("cpu"),
                            "memory": payload.get("memory"),
                            "error_count": self.signals.get("repeated_failure", 0),
                        },
                        inputs={"last_event": payload},
                    )
                    self._last_tool_request_at = now
                except Exception as exc:
                    logger.debug("[AdaptiveEngine] tool request deferred | %s", exc)

    # ========================================================
    # MONITOR LOOP
    # ========================================================

    async def monitor_loop(
        self,
    ):

        logger.info(
            "[AdaptiveEngine] "
            "Autonomous cognitive loop ONLINE"
        )

        while self._running:

            cycle_start = time.monotonic()

            try:

            # ------------------------------------------
            # 1. Observe
            # ------------------------------------------

                await self._analyze_performance()

            # ------------------------------------------
            # 2. Adapt resources
            # ------------------------------------------

                await self._apply_optimizations()

            # ------------------------------------------
            # 3. Process queued skills
            # ------------------------------------------

                await self._process_skills()

            # ------------------------------------------
            # 4. Autonomous cognition
            #
            # IDLE IS A THINKING STATE.
            # ------------------------------------------

                await self._autonomous_cognitive_cycle()

            # ------------------------------------------
            # 5. Existing autonomous skills
            # ------------------------------------------

                await self._autonomous_skill_trigger()

            # ------------------------------------------
            # 6. Publish feedback
                # ------------------------------------------

                await self._publish_adaptive_feedback()

            except asyncio.CancelledError:
                break

            except Exception as exc:

                logger.exception(
                    "[AdaptiveEngine] "
                    "Monitor exception: %s",
                    exc,
                )

                self._emit(
                    SYSTEM_WARNING,
                    {
                        "source":
                            "AdaptiveEngine",
                        "error":
                            str(exc),
                    },
                )

            elapsed = (
                time.monotonic()
                - cycle_start
            )

            delay = max(
                0.05,
                self.check_interval
                - elapsed,
            )

            try:
                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                break

        logger.info(
            "[AdaptiveEngine] "
            "Autonomous cognitive loop OFFLINE"
        )

    async def _learn_from_cognitive_result(
        self,
        result,
    ):

        if not self._learning_enabled:
            return None

        if not isinstance(
            result,
            dict,
        ):
            return None

        learning = {
            "timestamp":
                time.time(),
            "source":
                "AdaptiveEngine",
            "qbit_id":
                result.get("qbit_id"),
            "track_id":
                result.get("track_id"),
            "intent":
                result.get("intent"),
            "action":
                result.get("action"),
            "command":
                result.get("command"),
            "status":
                result.get("status"),
            "feedback":
                result.get("feedback"),
        }

        self.learning_history.append(
            learning
        )

        memory = getattr(
            self,
            "memory_manager",
            None,
        )

        if memory is not None:

            record = getattr(
                memory,
                "record",
                None,
            )

            if callable(record):

                try:

                    value = record(
                        event_type=
                            "adaptive_cognitive_learning",
                        payload=learning,
                    )

                    if asyncio.iscoroutine(value):
                        await value

                except Exception:

                    logger.debug(
                        "[AdaptiveEngine] "
                        "Memory learning record deferred",
                        exc_info=True,
                    )

        return learning

    # ========================================================
    # PERFORMANCE ANALYSIS
    # ========================================================

    async def _analyze_performance(
        self,
    ):

        if not self.analytics_engine:
            return

        try:

            metrics = getattr(
                self.analytics_engine,
                "metrics",
                {},
            )

            devices = metrics.get(
                "devices",
                {},
            )

            for (
                device_id,
                data,
            ) in devices.items():

                history = data.get(
                    "history",
                    [],
                )

                if not history:
                    continue

                latest = history[-1]

                success_rate = latest.get(
                    "success_rate",
                    100,
                )

                try:
                    success_rate = float(
                        success_rate
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if success_rate < 50:

                    recommendation = {
                        "device_id":
                            device_id,
                        "success_rate":
                            success_rate,
                        "recommendation":
                            "Increase monitoring "
                            "or adjust scheduling",
                        "source":
                            "AdaptiveEngine",
                    }

                    self._emit(
                        "OPTIMIZATION_RECOMMENDATION",
                        recommendation,
                    )

        except Exception as exc:

            logger.warning(
                "[AdaptiveEngine] "
                "Performance analysis failed: %s",
                exc,
            )

    # ========================================================
    # OPTIMIZATION
    # ========================================================

    async def _apply_optimizations(
        self,
    ):

        if self.memory_manager:

            try:

                short_term = getattr(
                    self.memory_manager,
                    "short_term",
                    [],
                )

                short_len = len(
                    short_term
                )

                if short_len > 1000:

                    if (
                        self.scheduler
                        and hasattr(
                            self.scheduler,
                            "update_task_interval",
                        )
                    ):

                        self.scheduler.update_task_interval(
                            "memory_prune",
                            300,
                        )

                    self._emit(
                        "ADAPTIVE_MEMORY_PRESSURE",
                        {
                            "source":
                                "AdaptiveEngine",
                            "short_term_size":
                                short_len,
                            "action":
                                "memory_prune_adjustment",
                        },
                    )

            except Exception as exc:

                logger.debug(
                    "[AdaptiveEngine] "
                    "Memory optimization deferred: %s",
                    exc,
                )

        if (
            self.signals[
                "repeated_failure"
            ]
            >= self.signal_thresholds[
                "repeated_failure"
            ]
        ):

            self._emit(
                "ADAPTIVE_FAILURE_SIGNAL",
                {
                    "source":
                        "AdaptiveEngine",
                    "signal":
                        "repeated_failure",
                    "count":
                        self.signals[
                            "repeated_failure"
                        ],
                },
            )

            self.signals[
                "repeated_failure"
            ] = 0

        if (
            self.signals[
                "resource_pressure"
            ]
            >= self.signal_thresholds[
                "resource_pressure"
            ]
        ):

            self._emit(
                "ADAPTIVE_RESOURCE_PRESSURE",
                {
                    "source":
                        "AdaptiveEngine",
                    "signal":
                        "resource_pressure",
                    "count":
                        self.signals[
                            "resource_pressure"
                        ],
                },
            )

            self.signals[
                "resource_pressure"
            ] = 0

    # ========================================================
    # ADAPTIVE FEEDBACK OUTPUT
    # ========================================================

    async def _publish_adaptive_feedback(
        self,
    ):

        total = (
            self.success_count
            + self.failure_count
        )

        if total <= 0:
            return

        success_rate = (
            self.success_count
            / total
        ) * 100.0

        feedback = {
            "source":
                "AdaptiveEngine",
            "success_rate":
                round(
                    success_rate,
                    2,
                ),
            "executions":
                self.execution_count,
            "successes":
                self.success_count,
            "failures":
                self.failure_count,
            "signals":
                dict(self.signals),
            "qbit_connected":
                self.qbit is not None,
            "queue_loop_connected":
                self.queue_loop is not None,
            "qbit_dialer_connected":
                self.qbit_dialer is not None,
            "resource_manager_connected":
                self.resource_manager is not None,
            "pending_resource_requests":
                len(
                    self.pending_resource_requests
                ),
        }

        self.last_qbit_feedback = (
            feedback
        )

        self._emit(
            "ADAPTIVE_FEEDBACK",
            feedback,
        )

    # ========================================================
    # SKILL SYSTEM
    # ========================================================

    async def _process_skills(
        self,
    ):

        while not self.skill_queue.empty():

            try:

                skill_fn, params = (
                    await self.skill_queue.get()
                )

                try:

                    result = skill_fn(
                        **params
                    )

                    if asyncio.iscoroutine(
                        result
                    ):
                        await result

                except Exception as exc:

                    self._emit(
                        SYSTEM_WARNING,
                        {
                            "source":
                                "AdaptiveEngine",
                            "error":
                                str(exc),
                            "skill":
                                getattr(
                                    skill_fn,
                                    "__name__",
                                    "unknown",
                                ),
                        },
                    )

                finally:

                    self.skill_queue.task_done()

            except asyncio.QueueEmpty:

                break

    # ========================================================
    # SKILL REGISTRATION
    # ========================================================

    def add_skill(
        self,
        name,
        func,
    ):

        if not callable(func):
            raise TypeError(
                "AdaptiveEngine skill "
                "must be callable"
            )

        self.skills[name] = func

        logger.info(
            "[AdaptiveEngine] "
            "Skill registered | %s",
            name,
        )

    # ========================================================
    # SKILL EXECUTION
    # ========================================================

    async def run_skill(
        self,
        name,
        **kwargs,
    ):

        skill = self.skills.get(
            name
        )

        if skill is None:

            logger.warning(
                "[AdaptiveEngine] "
                "Unknown skill | %s",
                name,
            )

            return False

        await self.skill_queue.put(
            (
                skill,
                kwargs,
            )
        )

        return True

    # ========================================================
    # AUTONOMOUS TRIGGERS
    # ========================================================

    async def _autonomous_skill_trigger(
        self,
    ):

        if not self.sparkplug:
            return

        if (
            self.signals[
                "missing_data"
            ]
            < self.signal_thresholds[
                "missing_data"
            ]
        ):
            return

        try:

            execute = getattr(
                self.sparkplug,
                "execute",
                None,
            )

            if not callable(execute):
                return

            result = await asyncio.to_thread(
                execute,
                "network_fetcher",
                {
                    "context":
                        "missing_data",
                    "source":
                        "AdaptiveEngine",
                },
            )

            if self.memory_manager:

                record = getattr(
                    self.memory_manager,
                    "record",
                    None,
                )

                if callable(record):

                    record(
                        event_type=
                            "skill_execution",
                        payload={
                            "skill":
                                "network_fetcher",
                            "result":
                                result,
                        },
                    )

        except Exception as exc:

            self._emit(
                SYSTEM_WARNING,
                {
                    "source":
                        "AdaptiveEngine",
                    "error":
                        str(exc),
                    "operation":
                        "autonomous_skill_trigger",
                },
            )

        finally:

            self.signals[
                "missing_data"
            ] = 0

    # ========================================================
    # NETWORK KNOWLEDGE
    # ========================================================

    async def fetch_knowledge(
        self,
        url,
        key=None,
    ):

        try:

            response = await asyncio.to_thread(
                lambda: requests.get(
                    url,
                    timeout=5,
                )
            )

            response.raise_for_status()

            result = response.text

            self.knowledge_cache[
                key or url
            ] = result

            self._emit(
                "KNOWLEDGE_FETCHED",
                {
                    "source":
                        "AdaptiveEngine",
                    "url":
                        url,
                    "key":
                        key or url,
                },
            )

            return result

        except Exception as exc:

            logger.error(
                "[AdaptiveEngine] "
                "Fetch failed: %s",
                exc,
            )

            self._emit(
                SYSTEM_WARNING,
                {
                    "source":
                        "AdaptiveEngine",
                    "error":
                        str(exc),
                    "operation":
                        "fetch_knowledge",
                },
            )

            return None

    # ========================================================
    # STATUS
    # ========================================================

    def status(
        self,
    ):

        return {
            "version":
                self.VERSION,
            "running":
                self._running,
            "event_bus":
                self.event_bus is not None,
            "qbit":
                self.qbit is not None,
            "queue_loop":
                self.queue_loop is not None,
            "qbit_dialer":
                self.qbit_dialer is not None,
            "track_system":
                self.track_system is not None,
            "scheduler":
                self.scheduler is not None,
            "memory_manager":
                self.memory_manager is not None,
            "analytics_engine":
                self.analytics_engine is not None,
            "actuator_engine":
                self.actuator_engine is not None,
            "resource_manager":
                self.resource_manager is not None,
            "pending_resource_requests":
                len(
                    self.pending_resource_requests
                ),
            "resource_statistics":
                dict(
                    self.resource_statistics
                ),
            "feedback_events":
                len(
                    self.feedback_history
                ),
            "executions":
                self.execution_count,
            "successes":
                self.success_count,
            "failures":
                self.failure_count,
        }

    # ========================================================
    # CONTROL
    # ========================================================

    async def start(
        self,
    ):

        if self._running:

            logger.info(
                "[AdaptiveEngine] "
                "Start ignored | already running"
            )

            return self

        self._running = True

        try:

            loop = asyncio.get_running_loop()

        except RuntimeError:

            self._running = False

            logger.warning(
                "[AdaptiveEngine] "
                "Start requested without "
                "running asyncio loop"
            )

            return self

        self._monitor_task = (
            loop.create_task(
                self.monitor_loop(),
                name=
                    "SEEDAdaptiveEngine.monitor",
            )
        )

        logger.info(
            "[AdaptiveEngine] STARTED | "
            "Qbit=%s | QueueLoop=%s | "
            "Dialer=%s | EventBus=%s | "
            "ResourceManager=%s",
            self.qbit is not None,
            self.queue_loop is not None,
            self.qbit_dialer is not None,
            self.event_bus is not None,
            self.resource_manager is not None,
        )

        self._emit(
            "ADAPTIVE_ENGINE_STARTED",
            self.status(),
        )

        return self

    # ========================================================
    # STOP
    # ========================================================

    async def stop(
        self,
    ):

        if not self._running:
            return

        self._running = False

        task = self._monitor_task

        self._monitor_task = None

        if task is not None:

            try:

                task.cancel()

                await task

            except asyncio.CancelledError:

                pass

            except Exception as exc:

                logger.debug(
                    "[AdaptiveEngine] "
                    "Monitor shutdown: %s",
                    exc,
                )

        self._emit(
            "ADAPTIVE_ENGINE_STOPPED",
            self.status(),
        )

        logger.info(
            "[AdaptiveEngine] STOPPED"
        )