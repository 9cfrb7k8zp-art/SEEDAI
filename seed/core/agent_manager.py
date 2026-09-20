# ==========================================================
# FILE: agent_manager.py
# PATH: SEED_ROOT/seed/core/agent_manager.py
# VERSION: 6.0.0
# UPDATED: 2026-08-18
#
# SYSTEM LAYER:
#   CONTROL / RECOVERY / LIFECYCLE ORCHESTRATION
#
# LIFECYCLE MODEL:
#
#   CONSTRUCTED
#       |
#       v
#   INITIALIZING
#       |
#       |  explicit start()
#       v
#   STARTING
#       |
#       |  boot graph complete
#       v
#   RUNNING
#       |
#       |  explicit stop()
#       v
#   STOPPING
#       |
#       v
#   STOPPED
#
# CRITICAL RULE:
#
#   AgentManager MUST remain inert until start() is called.
#
#   No resource worker
#   No recovery worker
#   No maintenance worker
#   No idle loop
#   No automatic boot thread
#   No recovery command
#   No Qbit queue control
#   No LimpMode intervention
#
#   may execute while the lifecycle state is not RUNNING.
#
# ARCHITECTURE:
#   LimpModeController -> condition/state reporting
#   AgentManager       -> control/recovery orchestration
#   QbitDialer         -> Qbit brain / command endpoint
#   QbitQueueLoop      -> queue/execution layer
#   Heartbeat          -> heartbeat/signal source
#
# OWNERSHIP:
#   AgentManager DOES NOT own:
#       - QbitDialer
#       - QbitQueueLoop
#       - Heartbeat
#       - LimpModeController
#
#   AgentManager receives references to existing instances.
#
# SHUTDOWN CONTRACT:
#
#   SEEDMain
#       |
#       +--> AgentManager.stop()
#                  |
#                  +--> stop AgentManager workers
#                  +--> cancel AgentManager tasks
#                  +--> wait for AgentManager workers
#                  |
#                  +--> RETURN
#       |
#       +--> QbitDialer.stop()
#       |
#       +--> QbitQueueLoop.stop()
#
# This prevents AgentManager consumers from remaining alive while
# QbitQueueLoop is being destroyed.
#
# SAFETY:
#   - no duplicate QbitDialer
#   - no duplicate QbitQueueLoop
#   - no duplicate Heartbeat
#   - no duplicate LimpModeController
#   - no recursive idle threads
#   - no startup workers
#   - no recovery during startup
#   - no recovery during shutdown
#   - recovery serialized
#   - maintenance throttled
#   - shutdown idempotent
# ==========================================================

import asyncio
import contextvars
import importlib
import inspect
import logging
import os
import threading
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from seed.core.track_system import TrackSystem
from seed.core.track_context import TrackContext
from seed.core.event_bus import SEEDEventBus


# ==========================================================
# LOGGING
# ==========================================================

logger = logging.getLogger("AgentManager")

if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


# ==========================================================
# EVENT CONSTANTS
# ==========================================================

QBIT_RESULT = "QBIT_RESULT"
INTENT_STATE = "INTENT_STATE"
ANALYTICS_UPDATED = "ANALYTICS_UPDATED"
SYSTEM_LIMP = "SYSTEM_LIMP"

COMMAND_EXECUTED = "COMMAND_EXECUTED"

SYSTEM_RECOVERY = "SYSTEM_RECOVERY"
SYSTEM_HEALTH = "SYSTEM_HEALTH"
SYSTEM_THROTTLE = "SYSTEM_THROTTLE"
SYSTEM_MAINTENANCE = "SYSTEM_MAINTENANCE"


# ==========================================================
# LIFECYCLE CONSTANTS
# ==========================================================

LIFECYCLE_INITIALIZING = "INITIALIZING"
LIFECYCLE_STARTING = "STARTING"
LIFECYCLE_RUNNING = "RUNNING"
LIFECYCLE_STOPPING = "STOPPING"
LIFECYCLE_STOPPED = "STOPPED"


# ==========================================================
# TRANSFORMER PLANNER
# ==========================================================

class TransformerPlanner:

    def __init__(self, agent_manager=None):
        self.agent = agent_manager

    def plan(
        self,
        intent: str,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        intent = str(intent or "idle").lower()

        steps: List[Dict[str, Any]] = []

        if intent in (
            "boot",
            "initialize",
            "startup",
        ):
            steps.extend(
                [
                    {
                        "action": "ensure_module",
                        "target": "BuildManager",
                    },
                    {
                        "action": "ensure_module",
                        "target": "QbitDialer",
                    },
                    {
                        "action": "ensure_module",
                        "target": "QbitQueueLoop",
                    },
                ]
            )

        elif intent in (
            "build",
            "construct",
            "expand",
        ):
            steps.extend(
                [
                    {"action": "analyze_dependencies"},
                    {"action": "compile_modules"},
                    {"action": "link_systems"},
                ]
            )

        elif intent in (
            "optimize",
            "self_improve",
        ):
            steps.extend(
                [
                    {"action": "scan_health"},
                    {"action": "rebuild_failed"},
                    {"action": "optimize_paths"},
                ]
            )

        elif intent in (
            "recover",
            "recovery",
            "heal",
            "self_heal",
        ):
            steps.extend(
                [
                    {"action": "scan_health"},
                    {"action": "recover_system"},
                ]
            )

        else:
            steps.append(
                {
                    "action": "idle_monitor",
                }
            )

        return steps


# ==========================================================
# AGENT MANAGER
# ==========================================================

class AgentManager:

    MIN_EMIT_INTERVAL = 0.15

    CPU_WARNING = 70.0
    CPU_CRITICAL = 85.0

    MEM_WARNING = 75.0
    MEM_CRITICAL = 85.0

    RECOVERY_COOLDOWN = 10.0

    RESOURCE_INTERVAL = 5.0
    RECOVERY_INTERVAL = 2.0
    MAINTENANCE_INTERVAL = 300.0

    NORMAL_WORKLOAD = 1.0
    WARNING_WORKLOAD = 0.75
    CRITICAL_WORKLOAD = 0.50
    LIMP_WORKLOAD = 0.25

    WORKER_JOIN_TIMEOUT = 3.0

    def __init__(
        self,
        *,
        emit,
        sparkplug=None,
        track_id=None,
        task_id=None,
        ethics_manager=None,
        heartbeat=None,
        heartbeatemitter=None,
        intent_to_action_mapper=None,
        memory_crystallizer=None,
        time_travel_engine=None,
        orchestrator_command=None,
        track=None,
        actuator_engine=None,
        event_bus=None,
        memory_manager=None,
        hud_interface=None,
        seed_core=None,
        intent_engine=None,
        loop=None,
        qbit_dialer=None,
        qbit_queue_loop=None,
        build_manager=None,
        qbit=None,
        device_manager=None,
        constraint_guardian=None,
        limp_mode=None,
        skills_path=None,
        seed_root=None,
        auto_recovery=True,
        auto_maintenance=True,
        auto_resource_monitor=True,
        auto_boot=True,
        **kwargs,
    ):

        # ==================================================
        # HARD LIFECYCLE GATE
        #
        # AgentManager is INERT after construction.
        # ==================================================

        self.running = False
        self._shutdown_started = False
        self._started_once = False

        self.lifecycle_state = (
            LIFECYCLE_INITIALIZING
        )

        self._system_ready = False

        self._lifecycle_lock = Lock()

        # ==================================================
        # CONFIGURATION
        # ==================================================

        self.auto_recovery = bool(auto_recovery)
        self.auto_maintenance = bool(auto_maintenance)
        self.auto_resource_monitor = bool(
            auto_resource_monitor
        )
        self.auto_boot = bool(auto_boot)

        # ==================================================
        # EVENT BUS
        # ==================================================

        if event_bus is not None:
            self.event_bus = event_bus
        else:
            try:
                self.event_bus = SEEDEventBus()
            except Exception as exc:
                logger.exception(
                    "[AgentManager] Failed to initialize EventBus: %s",
                    exc,
                )
                self.event_bus = None

        if self.event_bus is None:
            raise RuntimeError(
                "[AgentManager] Cannot initialize without a valid EventBus"
            )

        logger.info(
            "[AgentManager] EventBus attached: %s",
            type(self.event_bus).__name__,
        )

        # ==================================================
        # TRACKING
        # ==================================================

        self.track_system = kwargs.get("track_system")

        if self.track_system is None:
            self.track_system = TrackSystem(
                event_bus=self.event_bus
            )

        self.track = self.track_system.track

        self.track_id = track_id
        self.task_id = task_id

        # ==================================================
        # REFERENCES
        # ==================================================

        self.emit = event_bus.emit
        self.sparkplug = sparkplug

        self.seed_core = seed_core
        self.ethics_manager = ethics_manager

        self.hud_interface = hud_interface

        self.time_travel_engine = (
            time_travel_engine
        )

        self.intent_engine = intent_engine

        self.device_manager = device_manager

        self.constraint_guardian = (
            constraint_guardian
        )

        # ==================================================
        # ACTUATOR
        # ==================================================

        if actuator_engine is not None:
            self.actuator_engine = actuator_engine
        else:
            try:
                from seed.core.actuator_engine import (
                    ActuatorEngine,
                )

                self.actuator_engine = ActuatorEngine

            except Exception:
                self.actuator_engine = None

        # ==================================================
        # EXISTING CONTROL REFERENCES
        # ==================================================

        self.heartbeat = heartbeat
        self.heartbeatemitter = heartbeatemitter

        self.qbit_dialer = qbit_dialer
        self.qbit_queue_loop = qbit_queue_loop
        self.qbit = qbit

        # ==================================================
        # CANONICAL LIMPMODE REFERENCE
        #
        # IMPORTANT:
        # Do NOT create another LimpModeController here.
        #
        # Main/SEEDCore must inject the canonical instance.
        # ==================================================

        self.limp_mode = limp_mode

        # ==================================================
        # BUILD MANAGER
        # ==================================================

        self.build_manager = build_manager

        if self.build_manager is None:
            try:
                from seed.core.build_manager import (
                    BuildManager,
                )

                self.build_manager = BuildManager()

            except Exception as exc:
                logger.warning(
                    "[AgentManager] BuildManager unavailable: %s",
                    exc,
                )

        # ==================================================
        # ORCHESTRATOR COMMAND
        # ==================================================

        self._orchestrator_command = (
            orchestrator_command
        )

        # ==================================================
        # ASYNC LOOP
        #
        # IMPORTANT:
        # No owned loop thread is started during construction.
        # ==================================================

        self._owns_loop = False
        self._loop_thread = None

        if loop is not None:
            self.loop = loop

        else:
            try:
                self.loop = asyncio.get_running_loop()

            except RuntimeError:
                self.loop = None
                self._owns_loop = True

        # ==================================================
        # MEMORY
        # ==================================================

        self.memory_manager = memory_manager

        # ==================================================
        # INTENT MEMORY
        # ==================================================

        self.intent_memory = None

        try:
            from seed.core.intent_memory import (
                IntentMemory,
            )

            self.intent_memory = IntentMemory(
                emit=self.emit,
                qbit_dialer=self.qbit_dialer,
                orchestrator_command=(
                    self._orchestrator_command
                ),
                event_bus=self.event_bus,
                time_travel_engine=(
                    self.time_travel_engine
                ),
            )

        except Exception as exc:
            logger.debug(
                "[AgentManager] IntentMemory initialization deferred: %s",
                exc,
            )

        # ==================================================
        # INTENT MAPPER
        # ==================================================
        self.memory_crystallizer = memory_crystallizer
        self.intent_to_action_mapper = (
            intent_to_action_mapper
        )

        if self.intent_to_action_mapper is None:
            try:
                from seed.core.intent_to_action_mapper import (
                    IntentToActionMapper,
                )

                try:
                    self.intent_to_action_mapper = (
                        IntentToActionMapper(
                            emit=self.emit,
                            event_bus=self.event_bus,
                            memory_crystallizer=self.memory_crystallizer,
                            actuators={
                                "actuator":
                                    self.actuator_engine
                            },
                            agent_manager=self,
                            intent_memory=(
                                self.intent_memory
                            ),
                        )
                    )

                except TypeError:
                    self.intent_to_action_mapper = (
                        IntentToActionMapper(
                            event_bus=self.event_bus,
                            ethics_manager=(
                                self.ethics_manager
                            ),
                            qbit=self.qbit,
                        )
                    )

            except Exception as exc:
                logger.warning(
                    "[AgentManager] Intent mapper unavailable: %s",
                    exc,
                )

        self.intent_mapper = (
            self.intent_to_action_mapper
        )

        # ==================================================
        # TRANSFORMER
        # ==================================================

        self.transformer = TransformerPlanner(self)

        # ==================================================
        # LOCKS
        # ==================================================

        self._lock = Lock()
        self._boot_lock = Lock()
        self._recovery_lock = Lock()
        self._maintenance_lock = Lock()

        # ==================================================
        # STATE
        # ==================================================

        self._last_intent = "idle"
        self._last_qbit = 0.0
        self._last_emit = 0.0
        self._last_recovery = 0.0
        self._last_maintenance = 0.0
        self._last_resource_state = "normal"

        self._current_workload_factor = (
            self.NORMAL_WORKLOAD
        )

        self._pulse_callback = None
        self._last_heartbeat = 0.0

        # ==================================================
        # WORKER STATE
        #
        # NONE OF THESE START DURING __init__.
        # ==================================================

        self._agent_idle_started = False
        self._agent_idle_task = None
        self._agent_idle_stop = threading.Event()

        self._recovery_thread = None
        self._recovery_stop = threading.Event()

        self._resource_thread = None
        self._resource_stop = threading.Event()

        self._maintenance_thread = None
        self._maintenance_stop = threading.Event()

        self._boot_complete = False

        # ==================================================
        # HEALTH
        # ==================================================

        self._modules_health = {
            "BuildManager": self._new_health(),
            "QbitDialer": self._new_health(),
            "QbitQueueLoop": self._new_health(),
            "Heartbeat": self._new_health(),
            "DeviceManager": self._new_health(),
            "ConstraintGuardian": self._new_health(),
            "py_seed": self._new_health(),
        }

        # ==================================================
        # MAINTENANCE PATHS
        # ==================================================

        self.seed_root = Path(
            seed_root
            or os.environ.get(
                "SEED_ROOT",
                "C:/SEED_ROOT",
            )
        )

        self.skills_path = Path(
            skills_path
            or (
                self.seed_root
                / "seed"
                / "skills"
            )
        )

        # ==================================================
        # EVENT SUBSCRIPTIONS
        # ==================================================

        self._subscriptions_attached = False

        self._attach_events()

        # ==================================================
        # INTENT WRAPPER
        # ==================================================

        self._intent_wrapper_installed = False
        self._wrap_intent_handler()

        # ==================================================
        # INITIAL TRACK
        #
        # Tracking is allowed during initialization.
        # CONTROL ACTIONS are not.
        # ==================================================

        self.track(
            "AG-INIT",
            "ENTER",
            priority="CRITICAL",
        )

        self.track(
            "AG-LINK",
            "QBIT_DIALER",
            priority="HIGH",
            note=(
                "attached"
                if self.qbit_dialer
                else "missing"
            ),
        )

        self.track(
            "AG-LINK",
            "QBIT_QUEUE",
            priority="HIGH",
            note=(
                "attached"
                if self.qbit_queue_loop
                else "missing"
            ),
        )

        self.track(
            "AG-LINK",
            "HEARTBEAT",
            priority="HIGH",
            note=(
                "attached"
                if self.heartbeat
                else "missing"
            ),
        )

        self.track(
            "AG-LIFECYCLE",
            LIFECYCLE_INITIALIZING,
            priority="CRITICAL",
        )

        # ==================================================
        # ABSOLUTE RULE:
        #
        # DO NOT START ANY BACKGROUND WORKERS HERE.
        #
        # The old implementation started:
        #   resource worker
        #   recovery worker
        #   maintenance worker
        #   boot worker
        #
        # during construction.
        #
        # That is removed.
        # ==================================================

        self.track(
            "AG-INIT",
            "COMPLETE",
            priority="CRITICAL",
            note="inert_until_start",
        )

    # ======================================================
    # HEALTH FACTORY
    # ======================================================

    @staticmethod
    def _new_health():

        return {
            "status": "unknown",
            "failures": 0,
            "last_error": None,
            "last_check": 0.0,
        }

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def _is_running(self):

        return (
            self.running
            and self.lifecycle_state
            == LIFECYCLE_RUNNING
            and not self._shutdown_started
        )

    def _is_starting(self):

        return (
            self.lifecycle_state
            == LIFECYCLE_STARTING
        )

    def _accepts_control(self):

        return self._is_running()

    def lifecycle(self):

        return {
            "state": self.lifecycle_state,
            "running": self.running,
            "system_ready": self._system_ready,
            "boot_complete": self._boot_complete,
            "shutdown_started": self._shutdown_started,
        }

    def mark_system_ready(self):

        with self._lifecycle_lock:

            if self.lifecycle_state in (
                LIFECYCLE_STOPPING,
                LIFECYCLE_STOPPED,
            ):
                return False

            self._system_ready = True

        self.track(
            "AG-LIFECYCLE",
            "SYSTEM_READY",
            priority="CRITICAL",
        )

        return True

    # Compatibility aliases.
    set_system_ready = mark_system_ready
    signal_system_ready = mark_system_ready

    # ======================================================
    # TRACK
    # ======================================================

    def _track(
        self,
        channel,
        state,
        *,
        priority="MED",
        note=None,
        **kwargs,
    ):

        metadata = kwargs.pop(
            "metadata",
            {},
        ) or {}

        if note is not None:
            metadata["note"] = note

        metadata["source"] = "AgentManager"
        metadata["state"] = state

        try:
            return self.track_system.begin(
                channel=channel,
                priority=priority,
                metadata=metadata,
                **kwargs,
            )

        except Exception as exc:
            logger.warning(
                "[AgentManager] TrackSystem emission failed: %s",
                exc,
            )

            return None

    # ======================================================
    # OWNED ASYNC LOOP
    # ======================================================

    def _run_owned_loop(self):

        if self.loop is None:
            return

        try:

            asyncio.set_event_loop(self.loop)

            self.loop.run_forever()

        except Exception:
            logger.exception(
                "[AgentManager] Async loop failed"
            )

    def _ensure_async_loop(self):

        if self.loop is not None:

            if self.loop.is_running():
                return True

        if not self._owns_loop:
            return False

        if self._shutdown_started:
            return False

        if self._loop_thread is not None:
            if self._loop_thread.is_alive():
                return (
                    self.loop is not None
                    and self.loop.is_running()
                )

        try:

            self.loop = asyncio.new_event_loop()

            self._loop_thread = threading.Thread(
                target=self._run_owned_loop,
                name="AgentManagerAsyncLoop",
                daemon=True,
            )

            self._loop_thread.start()

            deadline = (
                time.time() + 2.0
            )

            while (
                time.time() < deadline
                and not self.loop.is_running()
            ):
                time.sleep(0.01)

            return self.loop.is_running()

        except Exception as exc:

            logger.exception(
                "[AgentManager] Failed to start owned async loop: %s",
                exc,
            )

            return False

    # ======================================================
    # SAFE ASYNC SUBMISSION
    # ======================================================

    def _submit_async(self, coro):

        if not self._accepts_control():

            try:
                coro.close()

            except Exception:
                pass

            return None

        try:

            if (
                self.loop is not None
                and self.loop.is_running()
            ):

                return asyncio.run_coroutine_threadsafe(
                    coro,
                    self.loop,
                )

        except Exception as exc:

            logger.debug(
                "[AgentManager] async submission failed: %s",
                exc,
            )

        try:
            coro.close()

        except Exception:
            pass

        return None

    # ======================================================
    # ORCHESTRATOR COMMAND
    # ======================================================

    @property
    def orchestrator_command(self):

        if self.qbit_dialer is not None:

            command = getattr(
                self.qbit_dialer,
                "_command",
                None,
            )

            if callable(command):
                return command

            command = getattr(
                self.qbit_dialer,
                "command",
                None,
            )

            if callable(command):
                return command

        return self._orchestrator_command

    @orchestrator_command.setter
    def orchestrator_command(self, value):
        self._orchestrator_command = value

    # ======================================================
    # EVENT ATTACHMENT
    # ======================================================

    def _attach_events(self):

        if self._subscriptions_attached:
            return

        if self.event_bus is None:
            return

        subscribe = getattr(
            self.event_bus,
            "subscribe",
            None,
        )

        if not callable(subscribe):
            return

        subscriptions = [
            (QBIT_RESULT, self._on_qbit),
            (INTENT_STATE, self._on_intent_state),
            (ANALYTICS_UPDATED, self._on_insight),
            (SYSTEM_LIMP, self._on_limp),
            (COMMAND_EXECUTED, self._on_nlp_command),
        ]

        for event_name, callback in subscriptions:

            try:

                subscribe(
                    event_name,
                    callback,
                )

            except Exception as exc:

                logger.debug(
                    "[AgentManager] Event subscription failed %s: %s",
                    event_name,
                    exc,
                )

        self._subscriptions_attached = True

    # ======================================================
    # EVENT HELPERS
    # ======================================================

    @staticmethod
    def _payload(event):

        payload = getattr(
            event,
            "payload",
            event,
        )

        if isinstance(payload, dict):
            return payload

        data = getattr(
            event,
            "data",
            None,
        )

        if isinstance(data, dict):
            return data

        return {}

    # ======================================================
    # QBIT EVENT
    # ======================================================

    def _on_qbit(self, event):

        if not self._accepts_control():
            return

        payload = self._payload(event)

        value = payload.get(
            "value",
            payload.get(
                "qbit",
                0.0,
            ),
        )

        try:
            self._last_qbit = float(value)

        except Exception:
            self._last_qbit = 0.0

        now = time.time()

        if (
            now - self._last_emit
            >= self.MIN_EMIT_INTERVAL
        ):

            self._last_emit = now

            self.track(
                "AG-QBIT",
                "RECEIVED",
                note=str(value),
            )

        self._submit_actuator_intent(
            "QBIT",
            "qbit_update",
        )

    # ======================================================
    # INTENT EVENT
    # ======================================================

    def _on_intent_state(self, event):

        if not self._accepts_control():
            return

        self._process_intent_event(event)

    def _process_intent_event(self, event):

        if not self._accepts_control():
            return

        data = self._payload(event)

        intent = data.get(
            "intent",
            "idle",
        )

        self._last_intent = str(intent)

        now = time.time()

        if (
            now - self._last_emit
            >= self.MIN_EMIT_INTERVAL
        ):

            self._last_emit = now

            self.track(
                "AG-INTENT",
                "RECEIVED",
                note=str(intent),
            )

        self._submit_actuator_intent(
            "AGENT",
            str(intent),
        )

        try:

            plan = self.transformer.plan(
                str(intent),
                data,
            )

            self._execute_plan(plan)

        except Exception as exc:

            logger.exception(
                "[AgentManager] Intent plan failed"
            )

            self.track(
                "AG-INTENT",
                "FAILED",
                note=str(exc),
            )

        self._forward_intent_mapper(event)

    # ======================================================
    # ANALYTICS
    # ======================================================

    def _on_insight(self, event):

        if not self._accepts_control():
            return

        now = time.time()

        if (
            now - self._last_emit
            >= self.MIN_EMIT_INTERVAL
        ):

            self._last_emit = now

            self.track(
                "AG-INSIGHT",
                "UPDATED",
            )

    # ======================================================
    # LIMP EVENT
    # ======================================================

    def _on_limp(self, event):

        # --------------------------------------------------
        # CRITICAL:
        # Limp events received during startup/shutdown are
        # observations only. They MUST NOT initiate recovery.
        # --------------------------------------------------

        if not self._accepts_control():
            return

        payload = self._payload(event)

        reason = payload.get(
            "reason",
            "unknown",
        )

        state = payload.get(
            "state",
            "limp",
        )

        self._last_resource_state = str(
            state
        ).lower()

        now = time.time()

        if (
            now - self._last_emit
            >= self.MIN_EMIT_INTERVAL
        ):

            self._last_emit = now

            self.track(
                "AG-LIMP",
                "REPORTED",
                priority="HIGH",
                note=str(reason),
            )

        if self.auto_recovery:
            self.request_recovery(
                reason=str(reason),
                source="LimpMode",
            )

    # ======================================================
    # NLP COMMAND
    # ======================================================

    def _on_nlp_command(self, event):

        if not self._accepts_control():
            return

        payload = self._payload(event)

        command = payload.get("command")
        device = payload.get("device")

        if not command:
            return

        if self.intent_memory is not None:

            try:

                ingest = getattr(
                    self.intent_memory,
                    "ingest",
                    None,
                )

                if callable(ingest):

                    ingest(
                        {
                            "intent": command,
                            "device": device,
                            "confidence": 1.0,
                            "timestamp": time.time(),
                        }
                    )

            except Exception as exc:

                logger.debug(
                    "[AgentManager] IntentMemory ingest failed: %s",
                    exc,
                )

        self.send_qbit_command(
            command,
            device=device,
        )

    # ======================================================
    # ACTUATOR
    # ======================================================

    def _submit_actuator_intent(
        self,
        source,
        intent,
    ):

        if not self._accepts_control():
            return

        actuator = self.actuator_engine

        if actuator is None:
            return

        try:

            submit = getattr(
                actuator,
                "submit_agent_intent",
                None,
            )

            if callable(submit):
                submit(
                    source,
                    intent,
                )

        except Exception as exc:

            logger.debug(
                "[AgentManager] actuator submission failed: %s",
                exc,
            )

    # ======================================================
    # INTENT MAPPER
    # ======================================================

    def _forward_intent_mapper(self, event):

        if not self._accepts_control():
            return

        mapper = self.intent_to_action_mapper

        if mapper is None:
            return

        handler = getattr(
            mapper,
            "_handle_intent_event",
            None,
        )

        if not callable(handler):

            handler = getattr(
                mapper,
                "_handle_intent_state",
                None,
            )

        if not callable(handler):
            return

        try:

            handler(event)

        except TypeError:

            try:

                handler(
                    self._payload(event)
                )

            except Exception:

                logger.debug(
                    "[AgentManager] mapper forwarding failed",
                    exc_info=True,
                )

        except Exception:

            logger.debug(
                "[AgentManager] mapper forwarding failed",
                exc_info=True,
            )

    # ======================================================
    # INTENT WRAPPER
    # ======================================================

    def _wrap_intent_handler(self):

        if self._intent_wrapper_installed:
            return

        # EventBus already owns routing.
        # No monkey patching.
        self._intent_wrapper_installed = True

    # ======================================================
    # START
    # ======================================================

    async def start(self):

        with self._lifecycle_lock:

            if self.lifecycle_state == LIFECYCLE_RUNNING:
                return True

            if self.lifecycle_state == LIFECYCLE_STOPPING:
                return False

            if self.lifecycle_state == LIFECYCLE_STOPPED:
                logger.warning(
                    "[AgentManager] Refusing restart after STOPPED"
                )
                return False

            if self._started_once:
                return False

            self._started_once = True
            self.lifecycle_state = (
                LIFECYCLE_STARTING
            )
            self.running = True
            self._shutdown_started = False

        self.track(
            "AG-LIFECYCLE",
            LIFECYCLE_STARTING,
            priority="CRITICAL",
        )

        # The lifecycle call itself is the activation gate.
        self._system_ready = True

        # --------------------------------------------------
        # Start owned async loop only now.
        # --------------------------------------------------

        if not self._ensure_async_loop():

            self.running = False
            self.lifecycle_state = (
                LIFECYCLE_STOPPED
            )

            self.track(
                "AG-LIFECYCLE",
                "ASYNC_LOOP_FAILED",
                priority="CRITICAL",
            )

            return False

        # --------------------------------------------------
        # Boot existing references.
        # --------------------------------------------------

        boot_ok = await self._boot_modules()

        if not boot_ok:
            logger.warning(
                "[AgentManager] Boot completed with component failures"
            )

        if not self.running:
            return False

        # --------------------------------------------------
        # Only AFTER boot completes may workers start.
        # --------------------------------------------------

        self._boot_complete = True

        if self.auto_resource_monitor:
            self._start_resource_monitor()

        if self.auto_recovery:
            self._start_recovery_worker()

        if self.auto_maintenance:
            self._start_maintenance_worker()

        self._start_idle_read()

        with self._lifecycle_lock:

            if self._shutdown_started:
                return False

            self.lifecycle_state = (
                LIFECYCLE_RUNNING
            )

        self.track(
            "AG-LIFECYCLE",
            LIFECYCLE_RUNNING,
            priority="CRITICAL",
        )

        self.track(
            "AG-START",
            "LIVE",
            priority="CRITICAL",
        )

        return True

    # ======================================================
    # BOOT
    # ======================================================

    def _schedule_boot(self):

        # Compatibility method.
        #
        # It no longer creates a boot thread during __init__.
        #
        # Boot is owned by start().

        if not self._accepts_control():
            return False

        try:

            self._submit_async(
                self._boot_modules()
            )

            return True

        except Exception:

            logger.exception(
                "[AgentManager] Boot scheduling failed"
            )

            return False

    async def _boot_modules(self):

        if self._shutdown_started:
            return False

        if not self.running:
            return False

        if not self._boot_lock.acquire(
            blocking=False
        ):
            return False

        try:

            if self._shutdown_started:
                return False

            # ------------------------------------------
            # BuildManager
            # ------------------------------------------

            await self._boot_one(
                "BuildManager",
                self.build_manager,
            )

            if self._shutdown_started:
                return False

            # ------------------------------------------
            # QbitDialer
            # ------------------------------------------

            await self._boot_one(
                "QbitDialer",
                self.qbit_dialer,
            )

            if self._shutdown_started:
                return False

            # ------------------------------------------
            # QbitQueueLoop
            # ------------------------------------------

            await self._boot_one(
                "QbitQueueLoop",
                self.qbit_queue_loop,
            )

            if self._shutdown_started:
                return False

            # ------------------------------------------
            # Observation only
            # ------------------------------------------

            self._check_existing_component(
                "Heartbeat",
                self.heartbeat,
            )

            self._check_existing_component(
                "DeviceManager",
                self.device_manager,
            )

            self._check_existing_component(
                "ConstraintGuardian",
                self.constraint_guardian,
            )

            self._check_py_seed()

            self.track(
                "AG-BOOT",
                "COMPLETE",
                priority="CRITICAL",
            )

            return True

        finally:

            self._boot_lock.release()

    async def _boot_one(
        self,
        name,
        module,
    ):

        if not self.running:
            return False

        if self._shutdown_started:
            return False

        if module is None:

            self._set_health(
                name,
                "missing",
            )

            return False

        try:

            if name == "BuildManager":

                startup = getattr(
                    module,
                    "startup",
                    None,
                )

                if callable(startup):

                    result = startup()

                    if inspect.isawaitable(result):
                        await result

            elif name == "QbitDialer":

                initialize = getattr(
                    module,
                    "initialize",
                    None,
                )

                if callable(initialize):

                    result = initialize()

                    if inspect.isawaitable(result):
                        await result

            elif name == "QbitQueueLoop":

                self._connect_qbit_queue()

            self._set_health(
                name,
                "ok",
            )

            self.track(
                "AG-BOOT",
                "OK",
                note=name,
            )

            return True

        except Exception as exc:

            self._set_health(
                name,
                "failed",
                error=exc,
            )

            self.track(
                "AG-BOOT",
                "FAILED",
                priority="HIGH",
                note=f"{name}: {exc}",
            )

            # --------------------------------------------------
            # IMPORTANT:
            # Do NOT activate LimpMode/recovery while STARTING.
            # Recovery begins only once RUNNING.
            # --------------------------------------------------

            if self._accepts_control():
                self.request_recovery(
                    reason=(
                        f"{name} boot failure: "
                        f"{exc}"
                    ),
                    source="boot",
                )

            return False

    # ======================================================
    # HEALTH
    # ======================================================

    def _set_health(
        self,
        name,
        status,
        error=None,
    ):

        health = self._modules_health.setdefault(
            name,
            self._new_health(),
        )

        health["status"] = status
        health["last_check"] = time.time()

        if error is not None:

            health["failures"] += 1
            health["last_error"] = str(error)

        elif status == "ok":

            health["last_error"] = None

    def _check_existing_component(
        self,
        name,
        component,
    ):

        if component is None:

            self._set_health(
                name,
                "missing",
            )

            return False

        try:

            running = getattr(
                component,
                "running",
                None,
            )

            if running is False:
                status = "attached"
            else:
                status = "ok"

            self._set_health(
                name,
                status,
            )

            return True

        except Exception as exc:

            self._set_health(
                name,
                "failed",
                error=exc,
            )

            return False

    def _scan_health(self):

        if not self._accepts_control():
            return self._modules_health

        self._check_existing_component(
            "QbitDialer",
            self.qbit_dialer,
        )

        self._check_existing_component(
            "QbitQueueLoop",
            self.qbit_queue_loop,
        )

        self._check_existing_component(
            "Heartbeat",
            self.heartbeat,
        )

        self._check_existing_component(
            "DeviceManager",
            self.device_manager,
        )

        self._check_existing_component(
            "ConstraintGuardian",
            self.constraint_guardian,
        )

        self._check_py_seed()

        for name, health in self._modules_health.items():

            self.track(
                "AG-HEALTH",
                name,
                note=health["status"],
            )

        return self._modules_health

    # ======================================================
    # QBIT CONNECTION
    # ======================================================

    def _connect_qbit_queue(self):

        if not self._accepts_control() and not self._is_starting():
            return False

        queue = self.qbit_queue_loop
        dialer = self.qbit_dialer

        if queue is None or dialer is None:
            return False

        for method_name in (
            "attach_qbit_dialer",
            "set_qbit_dialer",
            "attach_dialer",
            "set_dialer",
        ):

            method = getattr(
                queue,
                method_name,
                None,
            )

            if callable(method):

                try:

                    method(dialer)

                    self.track(
                        "AG-LINK",
                        "QBIT_QUEUE_DIALER",
                        note=method_name,
                    )

                    return True

                except Exception as exc:

                    logger.debug(
                        "[AgentManager] queue attach %s failed: %s",
                        method_name,
                        exc,
                    )

        for method_name in (
            "attach_queue",
            "set_queue",
            "attach_qbit_queue",
            "set_qbit_queue",
        ):

            method = getattr(
                dialer,
                method_name,
                None,
            )

            if callable(method):

                try:

                    method(queue)

                    self.track(
                        "AG-LINK",
                        "QBIT_DIALER_QUEUE",
                        note=method_name,
                    )

                    return True

                except Exception as exc:

                    logger.debug(
                        "[AgentManager] dialer attach %s failed: %s",
                        method_name,
                        exc,
                    )

        return False

    # ======================================================
    # QBIT COMMAND ROUTING
    # ======================================================

    def send_qbit_command(
        self,
        command,
        device=None,
        **kwargs,
    ):

        if not self._accepts_control():
            return False

        dialer = self.qbit_dialer

        if dialer is None:

            self.track(
                "AG-QBIT",
                "NO_DIALER",
                priority="HIGH",
            )

            return False

        methods = (
            "send_command",
            "command",
            "dispatch_command",
            "_command",
        )

        for method_name in methods:

            method = getattr(
                dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                if device is not None:

                    try:

                        result = method(
                            command,
                            device,
                            **kwargs,
                        )

                    except TypeError:

                        result = method(
                            command,
                            **kwargs,
                        )

                else:

                    result = method(
                        command,
                        **kwargs,
                    )

                self.track(
                    "AG-QBIT",
                    "COMMAND_SENT",
                    priority="HIGH",
                    note=(
                        f"{command}"
                        + (
                            f" -> {device}"
                            if device
                            else ""
                        )
                    ),
                )

                return result

            except Exception as exc:

                logger.debug(
                    "[AgentManager] Qbit command %s failed: %s",
                    method_name,
                    exc,
                )

        self.track(
            "AG-QBIT",
            "COMMAND_FAILED",
            priority="HIGH",
            note=str(command),
        )

        return False

    # ======================================================
    # QBIT QUEUE CONTROL
    # ======================================================

    def control_qbit_queue(
        self,
        action,
        **kwargs,
    ):

        if not self._accepts_control():
            return False

        queue = self.qbit_queue_loop

        if queue is None:
            return False

        action = str(action).lower()

        action_methods = {

            "start": (
                "start",
                "run",
                "start_loop",
            ),

            "stop": (
                "stop",
                "shutdown",
            ),

            "pause": (
                "pause",
                "suspend",
            ),

            "resume": (
                "resume",
                "continue_loop",
            ),

            "flush": (
                "flush",
                "clear",
            ),

            "rewind": (
                "rewind",
            ),

            "replay": (
                "replay",
            ),
        }

        methods = action_methods.get(
            action,
            (),
        )

        for method_name in methods:

            method = getattr(
                queue,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(**kwargs)

                self.track(
                    "AG-QBIT-QUEUE",
                    action.upper(),
                    note=method_name,
                )

                return result

            except TypeError:

                try:

                    result = method()

                    self.track(
                        "AG-QBIT-QUEUE",
                        action.upper(),
                        note=method_name,
                    )

                    return result

                except Exception:
                    pass

            except Exception as exc:

                logger.debug(
                    "[AgentManager] queue action failed: %s",
                    exc,
                )

        return False

    # ======================================================
    # HEARTBEAT
    # ======================================================

    def connect_heartbeat(self):

        if not self._accepts_control():
            return False

        heartbeat = self.heartbeat

        if heartbeat is None:
            return False

        for method_name in (
            "register_callback",
            "add_callback",
            "subscribe",
            "attach_callback",
            "set_observer",
        ):

            method = getattr(
                heartbeat,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                method(
                    self._on_heartbeat
                )

                self.track(
                    "AG-LINK",
                    "HEARTBEAT",
                    note=method_name,
                )

                return True

            except Exception as exc:

                logger.debug(
                    "[AgentManager] heartbeat attach failed: %s",
                    exc,
                )

        return False

    def _on_heartbeat(
        self,
        *args,
        **kwargs,
    ):

        if not self._accepts_control():
            return False

        self._last_heartbeat = time.time()

        self.track(
            "AG-HEART",
            "PULSE",
            priority="LOW",
        )

        return True

    # ======================================================
    # RESOURCE MONITOR
    # ======================================================

    def _start_resource_monitor(self):

        if not self._accepts_control():
            return False

        if (
            self._resource_thread
            and self._resource_thread.is_alive()
        ):
            return False

        self._resource_stop.clear()

        self._resource_thread = threading.Thread(
            target=self._resource_monitor_loop,
            name="AgentManagerResourceMonitor",
            daemon=True,
        )

        self._resource_thread.start()

        return True

    def _resource_monitor_loop(self):

        while self._accepts_control() and not self._resource_stop.is_set():

            try:

                cpu, memory = self._read_resources()

                state = self._classify_resources(
                    cpu,
                    memory,
                )

                if state != self._last_resource_state:

                    previous = (
                        self._last_resource_state
                    )

                    self._last_resource_state = state

                    self.track(
                        "AG-RESOURCE",
                        state.upper(),
                        priority="HIGH",
                        note=(
                            f"CPU={cpu:.1f}% "
                            f"MEM={memory:.1f}% "
                            f"previous={previous}"
                        ),
                    )

                    self._apply_workload_policy(state)

                if state in (
                    "warning",
                    "critical",
                    "limp",
                ):

                    # Only RUNNING reaches here.
                    self._enter_limp_if_supported(
                        cpu,
                        memory,
                        state,
                    )

                    if self.auto_recovery:

                        self.request_recovery(
                            reason=(
                                f"resource pressure "
                                f"CPU={cpu:.1f}% "
                                f"MEM={memory:.1f}% "
                                f"state={state}"
                            ),
                            source="resource_monitor",
                        )

                elif state == "normal":

                    self._attempt_limp_recovery()

                self._resource_stop.wait(
                    self.RESOURCE_INTERVAL
                )

            except Exception as exc:

                logger.debug(
                    "[AgentManager] resource monitor error: %s",
                    exc,
                )

                self._resource_stop.wait(
                    self.RESOURCE_INTERVAL
                )

    def _read_resources(self):

        try:

            import psutil

            cpu = float(
                psutil.cpu_percent(
                    interval=0.1
                )
            )

            memory = float(
                psutil.virtual_memory().percent
            )

            return cpu, memory

        except Exception:

            return 0.0, 0.0

    def _classify_resources(
        self,
        cpu,
        memory,
    ):

        if (
            cpu >= self.CPU_CRITICAL
            or memory >= self.MEM_CRITICAL
        ):
            return "limp"

        if (
            cpu >= self.CPU_WARNING
            or memory >= self.MEM_WARNING
        ):
            return "warning"

        return "normal"

    # ======================================================
    # WORKLOAD THROTTLING
    # ======================================================

    def _apply_workload_policy(self, state):

        if not self._accepts_control():
            return False

        factors = {
            "normal": self.NORMAL_WORKLOAD,
            "warning": self.WARNING_WORKLOAD,
            "critical": self.CRITICAL_WORKLOAD,
            "limp": self.LIMP_WORKLOAD,
        }

        factor = factors.get(
            state,
            self.NORMAL_WORKLOAD,
        )

        self._current_workload_factor = factor

        guardian = self.constraint_guardian

        if guardian is not None:

            for method_name in (
                "set_workload_factor",
                "set_throttle",
                "throttle",
            ):

                method = getattr(
                    guardian,
                    method_name,
                    None,
                )

                if callable(method):

                    try:

                        method(factor)
                        break

                    except Exception:
                        pass

        queue = self.qbit_queue_loop

        if queue is not None:

            for method_name in (
                "set_workload_factor",
                "set_throttle",
                "set_rate_limit",
            ):

                method = getattr(
                    queue,
                    method_name,
                    None,
                )

                if callable(method):

                    try:

                        method(factor)
                        break

                    except Exception:
                        pass

        self.track(
            "AG-THROTTLE",
            state.upper(),
            priority="HIGH",
            note=f"factor={factor}",
        )

        self._emit_event(
            SYSTEM_THROTTLE,
            {
                "state": state,
                "factor": factor,
            },
        )

        return True

    # ======================================================
    # LIMP MODE
    # ======================================================

    def _enter_limp_if_supported(
        self,
        cpu,
        memory,
        state,
    ):

        if not self._accepts_control():
            return False

        limp = self.limp_mode

        if limp is None:
            return False

        reason = (
            f"AgentManager resource protection: "
            f"CPU={cpu:.1f}% "
            f"MEM={memory:.1f}% "
            f"state={state}"
        )

        for method_name in (
            "enter_limp_mode",
            "enter",
        ):

            method = getattr(
                limp,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                method(reason)
                return True

            except TypeError:

                try:

                    method()
                    return True

                except Exception:
                    pass

            except Exception as exc:

                logger.debug(
                    "[AgentManager] LimpMode entry failed: %s",
                    exc,
                )

        return False

    def _notify_limp(self, reason):

        if not self._accepts_control():
            return False

        limp = self.limp_mode

        if limp is None:
            return False

        for method_name in (
            "enter_limp_mode",
            "enter",
        ):

            method = getattr(
                limp,
                method_name,
                None,
            )

            if callable(method):

                try:

                    method(reason)
                    return True

                except TypeError:

                    try:

                        method()
                        return True

                    except Exception:
                        pass

                except Exception:
                    pass

        return False

    def _attempt_limp_recovery(self):

        if not self._accepts_control():
            return False

        limp = self.limp_mode

        if limp is None:
            return False

        for method_name in (
            "recover",
            "exit_limp_mode",
            "exit",
            "clear",
        ):

            method = getattr(
                limp,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method()

                self.track(
                    "AG-LIMP",
                    "RECOVERY_REQUESTED",
                    note=method_name,
                )

                return result

            except Exception:
                continue

        return False

    # ======================================================
    # RECOVERY
    # ======================================================

    def request_recovery(
        self,
        reason="unknown",
        source="AgentManager",
        force=False,
    ):

        # --------------------------------------------------
        # Absolute lifecycle gate.
        #
        # No recovery request is accepted while:
        # INITIALIZING
        # STARTING
        # STOPPING
        # STOPPED
        # --------------------------------------------------

        if not self._accepts_control():
            return False

        now = time.time()

        if (
            not force
            and now - self._last_recovery
            < self.RECOVERY_COOLDOWN
        ):
            return False

        self._last_recovery = now

        self.track(
            "AG-RECOVERY",
            "REQUESTED",
            priority="CRITICAL",
            note=(
                f"{source}: {reason}"
            ),
        )

        self._recovery_stop.clear()

        return True

    def _start_recovery_worker(self):

        if not self._accepts_control():
            return False

        if (
            self._recovery_thread
            and self._recovery_thread.is_alive()
        ):
            return False

        self._recovery_stop.clear()

        self._recovery_thread = threading.Thread(
            target=self._recovery_loop,
            name="AgentManagerRecovery",
            daemon=True,
        )

        self._recovery_thread.start()

        return True

    def _recovery_loop(self):

        while self._accepts_control() and not self._recovery_stop.is_set():

            try:

                if (
                    self._last_recovery > 0
                    and (
                        time.time()
                        - self._last_recovery
                        <= self.RECOVERY_INTERVAL
                    )
                ):

                    self._perform_recovery()

                self._recovery_stop.wait(
                    self.RECOVERY_INTERVAL
                )

            except Exception:

                logger.exception(
                    "[AgentManager] Recovery worker error"
                )

                self._recovery_stop.wait(
                    self.RECOVERY_INTERVAL
                )

    def _perform_recovery(self):

        if not self._accepts_control():
            return False

        if not self._recovery_lock.acquire(
            blocking=False
        ):
            return False

        try:

            if not self._accepts_control():
                return False

            self.track(
                "AG-RECOVERY",
                "START",
                priority="CRITICAL",
            )

            self._emit_event(
                SYSTEM_RECOVERY,
                {
                    "state": "start",
                    "timestamp": time.time(),
                },
            )

            self._scan_health()

            if not self._accepts_control():
                return False

            self._apply_workload_policy(
                "warning"
            )

            self._connect_qbit_queue()

            if self._health_is_bad(
                "BuildManager"
            ):
                self._recover_build_manager()

            if not self._accepts_control():
                return False

            if self._health_is_bad(
                "QbitDialer"
            ):
                self._recover_qbit_dialer()

            if not self._accepts_control():
                return False

            if self._health_is_bad(
                "QbitQueueLoop"
            ):
                self._recover_qbit_queue()

            if not self._accepts_control():
                return False

            if self._health_is_bad(
                "DeviceManager"
            ):
                self._recover_component(
                    "DeviceManager",
                    self.device_manager,
                )

            if self._health_is_bad(
                "py_seed"
            ):
                self._reload_py_seed()

            if not self._accepts_control():
                return False

            self._scan_health()

            cpu, memory = (
                self._read_resources()
            )

            state = self._classify_resources(
                cpu,
                memory,
            )

            self._apply_workload_policy(
                state
            )

            self.track(
                "AG-RECOVERY",
                "COMPLETE",
                priority="CRITICAL",
                note=(
                    f"CPU={cpu:.1f}% "
                    f"MEM={memory:.1f}%"
                ),
            )

            self._emit_event(
                SYSTEM_RECOVERY,
                {
                    "state": "complete",
                    "timestamp": time.time(),
                },
            )

            return True

        except Exception as exc:

            self.track(
                "AG-RECOVERY",
                "FAILED",
                priority="CRITICAL",
                note=str(exc),
            )

            self._emit_event(
                SYSTEM_RECOVERY,
                {
                    "state": "failed",
                    "error": str(exc),
                    "timestamp": time.time(),
                },
            )

            return False

        finally:

            self._recovery_lock.release()

    def _health_is_bad(self, name):

        health = self._modules_health.get(name)

        if health is None:
            return True

        return health.get("status") in (
            "failed",
            "missing",
            "unknown",
        )

    # ======================================================
    # MODULE RECOVERY
    # ======================================================

    def _recover_build_manager(self):

        if not self._accepts_control():
            return False

        manager = self.build_manager

        if manager is None:
            return False

        return self._recover_component(
            "BuildManager",
            manager,
        )

    def _recover_qbit_dialer(self):

        if not self._accepts_control():
            return False

        dialer = self.qbit_dialer

        if dialer is None:
            return False

        for method_name in (
            "reload",
            "restart",
            "reinitialize",
            "initialize",
        ):

            if not self._accepts_control():
                return False

            method = getattr(
                dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method()

                self._set_health(
                    "QbitDialer",
                    "ok",
                )

                self.track(
                    "AG-REPAIR",
                    "QBIT_DIALER",
                    note=method_name,
                )

                return result

            except Exception as exc:

                self._set_health(
                    "QbitDialer",
                    "failed",
                    error=exc,
                )

        return False

    def _recover_qbit_queue(self):

        if not self._accepts_control():
            return False

        queue = self.qbit_queue_loop

        if queue is None:
            return False

        self._connect_qbit_queue()

        for method_name in (
            "restart",
            "resume",
            "start",
        ):

            if not self._accepts_control():
                return False

            method = getattr(
                queue,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method()

                self._set_health(
                    "QbitQueueLoop",
                    "ok",
                )

                self.track(
                    "AG-REPAIR",
                    "QBIT_QUEUE",
                    note=method_name,
                )

                return result

            except Exception:
                continue

        return False

    def _recover_component(
        self,
        name,
        component,
    ):

        if not self._accepts_control():
            return False

        if component is None:
            return False

        for method_name in (
            "recover",
            "restart",
            "reload",
            "reinitialize",
            "initialize",
            "start",
        ):

            if not self._accepts_control():
                return False

            method = getattr(
                component,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method()

                self._set_health(
                    name,
                    "ok",
                )

                self.track(
                    "AG-REPAIR",
                    name,
                    note=method_name,
                )

                return result

            except Exception as exc:

                self._set_health(
                    name,
                    "failed",
                    error=exc,
                )

        return False

    # ======================================================
    # PY_SEED
    # ======================================================

    def _check_py_seed(self):

        try:

            module = importlib.import_module(
                "py_seed"
            )

            if module is not None:

                self._set_health(
                    "py_seed",
                    "ok",
                )

                return module

        except Exception as exc:

            self._set_health(
                "py_seed",
                "failed",
                error=exc,
            )

        return None

    def _reload_py_seed(self):

        if not self._accepts_control():
            return False

        try:

            module = importlib.import_module(
                "py_seed"
            )

            module = importlib.reload(
                module
            )

            self._set_health(
                "py_seed",
                "ok",
            )

            self.track(
                "AG-REPAIR",
                "PY_SEED_RELOADED",
                priority="HIGH",
            )

            return True

        except Exception as exc:

            self._set_health(
                "py_seed",
                "failed",
                error=exc,
            )

            self.track(
                "AG-REPAIR",
                "PY_SEED_FAILED",
                priority="HIGH",
                note=str(exc),
            )

            return False

    # ======================================================
    # BUILD MANAGER CONTROL
    # ======================================================

    def control_build_manager(
        self,
        action,
        **kwargs,
    ):

        if not self._accepts_control():
            return False

        manager = self.build_manager

        if manager is None:
            return False

        action = str(action).lower()

        methods = {
            "start": (
                "start",
                "startup",
            ),
            "stop": (
                "stop",
                "shutdown",
            ),
            "build": (
                "build",
                "compile",
                "run_build",
            ),
            "reload": (
                "reload",
                "restart",
            ),
        }.get(
            action,
            (),
        )

        for method_name in methods:

            method = getattr(
                manager,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(**kwargs)

                if inspect.isawaitable(result):
                    return self._submit_async(result)

                return result

            except TypeError:

                try:
                    return method()

                except Exception:
                    pass

            except Exception as exc:

                logger.debug(
                    "[AgentManager] BuildManager action failed: %s",
                    exc,
                )

        return False

    # ======================================================
    # DEVICE MANAGER
    # ======================================================

    def control_device_manager(
        self,
        action,
        **kwargs,
    ):

        if not self._accepts_control():
            return False

        manager = self.device_manager

        if manager is None:
            return False

        action = str(action).lower()

        methods = {
            "start": (
                "start",
                "initialize",
            ),
            "stop": (
                "stop",
                "shutdown",
            ),
            "reload": (
                "reload",
                "restart",
            ),
            "scan": (
                "scan",
                "discover",
                "refresh",
            ),
        }.get(
            action,
            (),
        )

        for method_name in methods:

            method = getattr(
                manager,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(**kwargs)

                if inspect.isawaitable(result):
                    return self._submit_async(result)

                return result

            except TypeError:

                try:
                    return method()

                except Exception:
                    pass

            except Exception:
                continue

        return False

    # ======================================================
    # CONSTRAINT GUARDIAN
    # ======================================================

    def guardian_state(self):

        guardian = self.constraint_guardian

        if guardian is None:
            return "clear"

        for method_name in (
            "get_state",
            "state",
        ):

            method = getattr(
                guardian,
                method_name,
                None,
            )

            if callable(method):

                try:

                    return str(
                        method()
                    ).lower()

                except Exception:
                    pass

        return "unknown"

    def guardian_allows_work(self):

        guardian = self.constraint_guardian

        if guardian is None:
            return True

        method = getattr(
            guardian,
            "allow_background_work",
            None,
        )

        if callable(method):

            try:
                return bool(method())

            except Exception:
                return True

        return True

    # ======================================================
    # MAINTENANCE
    # ======================================================

    def _start_maintenance_worker(self):

        if not self._accepts_control():
            return False

        if (
            self._maintenance_thread
            and self._maintenance_thread.is_alive()
        ):
            return False

        self._maintenance_stop.clear()

        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            name="AgentManagerMaintenance",
            daemon=True,
        )

        self._maintenance_thread.start()

        return True

    def _maintenance_loop(self):

        self._maintenance_stop.wait(30.0)

        while self._accepts_control() and not self._maintenance_stop.is_set():

            try:

                if (
                    self._current_workload_factor
                    >= self.WARNING_WORKLOAD
                ):

                    self.perform_maintenance()

                self._maintenance_stop.wait(
                    self.MAINTENANCE_INTERVAL
                )

            except Exception as exc:

                logger.debug(
                    "[AgentManager] maintenance worker error: %s",
                    exc,
                )

                self._maintenance_stop.wait(
                    self.MAINTENANCE_INTERVAL
                )

    def perform_maintenance(self):

        if not self._accepts_control():
            return False

        if not self._maintenance_lock.acquire(
            blocking=False
        ):
            return False

        try:

            if not self.skills_path.exists():

                self.track(
                    "AG-MAINTENANCE",
                    "SKILLS_PATH_MISSING",
                    note=str(
                        self.skills_path
                    ),
                )

                return False

            try:

                files = list(
                    self.skills_path.glob(
                        "*.py"
                    )
                )

            except Exception as exc:

                self.track(
                    "AG-MAINTENANCE",
                    "SCAN_FAILED",
                    note=str(exc),
                )

                return False

            self._last_maintenance = time.time()

            self.track(
                "AG-MAINTENANCE",
                "SCAN",
                note=f"{len(files)} skill files",
            )

            self._emit_event(
                SYSTEM_MAINTENANCE,
                {
                    "skills_path":
                        str(self.skills_path),
                    "file_count":
                        len(files),
                    "timestamp":
                        time.time(),
                },
            )

            return True

        finally:

            self._maintenance_lock.release()

    # ======================================================
    # IDLE LOOP
    # ======================================================

    def _start_idle_read(self):

        if not self._accepts_control():
            return False

        if self._agent_idle_started:
            return False

        if self.loop is None:
            return False

        if not self.loop.is_running():
            return False

        self._agent_idle_stop.clear()

        try:

            self._agent_idle_task = (
                asyncio.run_coroutine_threadsafe(
                    self.idle_read_loop(),
                    self.loop,
                )
            )

            self._agent_idle_started = True

            return True

        except Exception as exc:

            logger.debug(
                "[AgentManager] idle loop start failed: %s",
                exc,
            )

        return False

    async def idle_read_loop(self):

        if not self._accepts_control():
            return

        self._agent_idle_started = True

        try:

            while (
                self._accepts_control()
                and not self._agent_idle_stop.is_set()
            ):

                try:

                    if not self._accepts_control():
                        break

                    state = self.guardian_state()

                    allowed = (
                        self.guardian_allows_work()
                    )

                    if not allowed:
                        interval = 30.0

                    elif state == "pressure":
                        interval = 10.0

                    elif state == "warning":
                        interval = 20.0

                    elif state in (
                        "block",
                        "blocked",
                    ):
                        interval = 30.0

                    else:
                        interval = 5.0

                    if (
                        allowed
                        and state not in (
                            "block",
                            "blocked",
                        )
                        and self._accepts_control()
                    ):

                        process_tasks = getattr(
                            self,
                            "process_pending_tasks",
                            None,
                        )

                        if callable(process_tasks):

                            result = process_tasks()

                            if inspect.isawaitable(result):
                                await result

                    await asyncio.sleep(interval)

                except asyncio.CancelledError:
                    raise

                except Exception as exc:

                    logger.debug(
                        "[AgentManager] idle maintenance error: %s",
                        exc,
                    )

                    await asyncio.sleep(20.0)

        finally:

            self._agent_idle_started = False

            self.track(
                "AG-IDLE",
                "OFFLINE",
            )

    def stop_idle_read(self):

        self._agent_idle_stop.set()

        task = self._agent_idle_task

        if task is not None:

            try:
                task.cancel()

            except Exception:
                pass

        self._agent_idle_task = None
        self._agent_idle_started = False

        return True

    # ======================================================
    # PENDING TASK COMPATIBILITY
    # ======================================================

    def process_pending_tasks(self):

        if not self._accepts_control():
            return False

        # QbitQueueLoop remains authoritative.
        # AgentManager does not maintain another queue.
        return True

    # ======================================================
    # PLAN EXECUTION
    # ======================================================

    def _execute_plan(
        self,
        steps: List[Dict[str, Any]],
    ):

        if not self._accepts_control():
            return False

        for step in steps:

            if not self._accepts_control():
                break

            action = step.get("action")

            self.track(
                "AG-PLAN",
                "STEP",
                note=str(action),
            )

            try:

                if action == "ensure_module":

                    self._ensure_module(
                        step.get("target")
                    )

                elif action == "scan_health":

                    self._scan_health()

                elif action == "rebuild_failed":

                    self.request_recovery(
                        reason="transformer rebuild_failed",
                        source="Transformer",
                        force=True,
                    )

                elif action == "recover_system":

                    self.request_recovery(
                        reason="transformer recovery",
                        source="Transformer",
                        force=True,
                    )

                elif action == "analyze_dependencies":

                    self._analyze_dependencies()

                elif action == "compile_modules":

                    self.control_build_manager(
                        "build"
                    )

                elif action == "link_systems":

                    self._connect_control_layers()

                elif action == "optimize_paths":

                    self._apply_workload_policy(
                        self._last_resource_state
                    )

            except Exception as exc:

                self.track(
                    "AG-PLAN",
                    "FAILED",
                    priority="HIGH",
                    note=f"{action}: {exc}",
                )

        return True

    def _ensure_module(self, name):

        if not self._accepts_control():
            return False

        if name == "BuildManager":

            if self._health_is_bad(
                "BuildManager"
            ):
                return self._recover_build_manager()

        elif name == "QbitDialer":

            if self._health_is_bad(
                "QbitDialer"
            ):
                return self._recover_qbit_dialer()

        elif name == "QbitQueueLoop":

            if self._health_is_bad(
                "QbitQueueLoop"
            ):
                return self._recover_qbit_queue()

        else:

            self.track(
                "AG-MODULE",
                "UNKNOWN",
                note=str(name),
            )

        return False

    def _repair_modules(self):

        if not self._accepts_control():
            return False

        return self.request_recovery(
            reason="repair_modules",
            source="AgentManager",
            force=True,
        )

    def _analyze_dependencies(self):

        dependencies = {
            "QbitDialer":
                bool(self.qbit_dialer),

            "QbitQueueLoop":
                bool(self.qbit_queue_loop),

            "Heartbeat":
                bool(self.heartbeat),

            "BuildManager":
                bool(self.build_manager),

            "DeviceManager":
                bool(self.device_manager),

            "ConstraintGuardian":
                bool(self.constraint_guardian),

            "LimpMode":
                bool(self.limp_mode),
        }

        self.track(
            "AG-DEPENDENCY",
            "ANALYZED",
            note=str(dependencies),
        )

        return dependencies

    def _connect_control_layers(self):

        if not self._accepts_control():
            return False

        self._connect_qbit_queue()
        self.connect_heartbeat()
        self._analyze_dependencies()

        return True

    # ======================================================
    # PULSE
    # ======================================================

    def set_pulse_callback(self, callback):

        self._pulse_callback = callback

    async def _emit_pulse(self, pulse):

        if not self._accepts_control():
            return

        callback = self._pulse_callback

        if callback is None:
            return

        try:

            result = callback(pulse)

            if inspect.isawaitable(result):
                await result

        except Exception:

            logger.debug(
                "[AgentManager] pulse callback failed",
                exc_info=True,
            )

    # ======================================================
    # EXTERNAL INTENT MAPPER
    # ======================================================

    def attach_intent_mapper(self, mapper):

        self.intent_to_action_mapper = mapper
        self.intent_mapper = mapper

        # Do NOT resubscribe INTENT_STATE.
        #
        # _attach_events() already installed the canonical
        # AgentManager handler.
        #
        # This prevents duplicate intent callbacks.

        return True

    # ======================================================
    # EVENT EMISSION
    # ======================================================

    def _emit_event(
        self,
        event_name,
        payload,
    ):

        if self.event_bus is None:
            return False

        bus = self.event_bus

        for method_name in (
            "emit",
            "_emit",
            "publish",
        ):

            method = getattr(
                bus,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                return method(
                    event_name,
                    payload,
                )

            except TypeError:

                try:

                    return method(
                        {
                            "type": event_name,
                            "payload": payload,
                        }
                    )

                except Exception:
                    pass

            except Exception:
                pass

        return False

    # ======================================================
    # STATUS
    # ======================================================

    def status(self):

        cpu, memory = self._read_resources()

        return {
            "running":
                self.running,

            "lifecycle_state":
                self.lifecycle_state,

            "system_ready":
                self._system_ready,

            "boot_complete":
                self._boot_complete,

            "shutdown_started":
                self._shutdown_started,

            "resource_state":
                self._last_resource_state,

            "cpu_percent":
                cpu,

            "memory_percent":
                memory,

            "workload_factor":
                self._current_workload_factor,

            "last_intent":
                self._last_intent,

            "last_qbit":
                self._last_qbit,

            "qbit_dialer":
                self.qbit_dialer is not None,

            "qbit_queue_loop":
                self.qbit_queue_loop is not None,

            "heartbeat":
                self.heartbeat is not None,

            "build_manager":
                self.build_manager is not None,

            "device_manager":
                self.device_manager is not None,

            "constraint_guardian":
                self.constraint_guardian is not None,

            "limp_mode":
                self.limp_mode is not None,

            "workers": {
                "resource":
                    bool(
                        self._resource_thread
                        and self._resource_thread.is_alive()
                    ),

                "recovery":
                    bool(
                        self._recovery_thread
                        and self._recovery_thread.is_alive()
                    ),

                "maintenance":
                    bool(
                        self._maintenance_thread
                        and self._maintenance_thread.is_alive()
                    ),

                "idle":
                    self._agent_idle_started,
            },

            "health":
                dict(self._modules_health),
        }

    # ======================================================
    # STOP / SHUTDOWN
    # ======================================================

    def stop(self):

        with self._lifecycle_lock:

            if self._shutdown_started:
                return True

            self._shutdown_started = True
            self.running = False
            self.lifecycle_state = (
                LIFECYCLE_STOPPING
            )

        self.track(
            "AG-SHUTDOWN",
            "BEGIN",
            priority="CRITICAL",
        )

        # --------------------------------------------------
        # FIRST:
        # prevent ALL new AgentManager work.
        # --------------------------------------------------

        self._resource_stop.set()
        self._recovery_stop.set()
        self._maintenance_stop.set()
        self._agent_idle_stop.set()

        # --------------------------------------------------
        # Stop idle async work.
        # --------------------------------------------------

        self.stop_idle_read()

        # --------------------------------------------------
        # Wake all worker waits immediately.
        # --------------------------------------------------

        self._resource_stop.set()
        self._recovery_stop.set()
        self._maintenance_stop.set()

        # --------------------------------------------------
        # Join AgentManager worker threads.
        #
        # This is the critical change.
        #
        # stop() does not return until AgentManager's own
        # workers have had an opportunity to terminate.
        #
        # Therefore SEEDMain can safely execute:
        #
        #   agent_manager.stop()
        #   qbit_dialer.stop()
        #   qbit_queue_loop.stop()
        #
        # without AgentManager still consuming the queue.
        # --------------------------------------------------

        current = threading.current_thread()

        workers = (
            self._resource_thread,
            self._recovery_thread,
            self._maintenance_thread,
        )

        for worker in workers:

            if worker is None:
                continue

            if worker is current:
                continue

            try:

                if worker.is_alive():
                    worker.join(
                        timeout=self.WORKER_JOIN_TIMEOUT
                    )

            except Exception:
                pass

        # --------------------------------------------------
        # Cancel idle task again after worker shutdown.
        # --------------------------------------------------

        task = self._agent_idle_task

        if task is not None:

            try:
                task.cancel()

            except Exception:
                pass

        # --------------------------------------------------
        # Stop only AgentManager-owned async loop.
        #
        # NEVER stop:
        #   QbitDialer
        #   QbitQueueLoop
        #   Heartbeat
        # --------------------------------------------------

        if self._owns_loop and self.loop is not None:

            try:

                if self.loop.is_running():

                    self.loop.call_soon_threadsafe(
                        self.loop.stop
                    )

            except Exception:
                pass

            loop_thread = self._loop_thread

            if (
                loop_thread is not None
                and loop_thread is not current
            ):

                try:

                    if loop_thread.is_alive():
                        loop_thread.join(
                            timeout=self.WORKER_JOIN_TIMEOUT
                        )

                except Exception:
                    pass

        self._resource_thread = None
        self._recovery_thread = None
        self._maintenance_thread = None
        self._loop_thread = None

        self.lifecycle_state = (
            LIFECYCLE_STOPPED
        )

        self.track(
            "AG-SHUTDOWN",
            "COMPLETE",
            priority="CRITICAL",
        )

        return True

    shutdown = stop

    # ======================================================
    # LEGACY COMPATIBILITY
    # ======================================================

    def start_loops(self):

        # --------------------------------------------------
        # Legacy callers may still call start_loops().
        #
        # It is now lifecycle-safe.
        #
        # It NEVER starts workers unless AgentManager is
        # already RUNNING.
        # --------------------------------------------------

        if not self._accepts_control():
            return False

        self._start_resource_monitor()
        self._start_recovery_worker()
        self._start_maintenance_worker()
        self._start_idle_read()

        return True


# ==========================================================
# MODULE-LEVEL COMPATIBILITY
# ==========================================================

def ai_track(
    channel,
    state,
    **kwargs,
):

    logger.debug(
        "[AgentManager] ai_track: channel=%s state=%s metadata=%s",
        channel,
        state,
        kwargs,
    )

    return None