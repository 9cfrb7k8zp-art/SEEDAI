# ==========================================================
# FILE: event_bus.py
# PATH: SEED_ROOT/seed/core/event_bus.py
# VERSION: 7.0.0
# BUILD: BOOT-SAFE / QBIT-SAFE / TIME-TRAVEL-SAFE
#        / PRESSURE-AWARE / ASYNC-GUARDED
# UPDATED: 2026-08-17
#
# PURPOSE:
#   Central SEED event authority.
#
# PRIMARY DESIGN:
#
#   Heartbeat
#       |
#       v
#   EventBus
#       |
#       +--> ConstraintGuardian admission
#       |
#       +--> Subscribers
#       |
#       +--> QbitDialer
#       |
#       +--> TimeTravelEngine
#
# IMPORTANT:
#   EventBus is a traffic governor.
#
#   It must NEVER allow background event floods to
#   overwhelm the system.
#
# COMPATIBILITY:
#   - legacy emit()
#   - publish()
#   - _emit()
#   - lowercase event aliases
#   - uppercase event names
#   - callback objects with handle_event()
#   - synchronous callbacks
#   - asynchronous callbacks
#   - legacy EmitWrapper objects
#   - QbitDialer
#   - TimeTravelEngine
#   - ConstraintGuardian
#   - QbitChannelControl
#
# SAFETY:
#   EventBus failures NEVER intentionally terminate the
#   producer that emitted the event.
# ==========================================================

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
import tracemalloc

from collections import defaultdict, deque
from enum import Enum
from typing import Any, Optional

from seed.core.tracked_data import TrackedData
from seed.core.track_id_manager import TrackIDManager

try:
    from COM.quantum_object import QuantumObject
except Exception:
    QuantumObject = None


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("SEEDEventBus")
logger.setLevel(logging.INFO)


# ==========================================================
# SYSTEM EVENT CONSTANTS
# ==========================================================

SYSTEM_WARNING = "SYSTEM_WARNING"
SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
SYSTEM_LIMP = "SYSTEM_LIMP"
SYSTEM_BOOT = "SYSTEM_BOOT"

COMMAND_EXECUTED = "COMMAND_EXECUTED"
ANALYTICS_UPDATED = "ANALYTICS_UPDATED"
HEARTBEAT = "HEARTBEAT"

DEVICE_CONNECTED = "DEVICE_CONNECTED"
DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"
DEVICE_INPUT = "DEVICE_INPUT"
DEVICE_SELECTED = "DEVICE_SELECTED"
DEVICE_DESELECTED = "DEVICE_DESELECTED"

SKILL_LOADED = "SKILL_LOADED"
SKILL_FAILED = "SKILL_FAILED"
SKILL_COMMAND = "SKILL_COMMAND"

CUSTOM_EVENT = "CUSTOM_EVENT"

QBIT_TICK = "QBIT_TICK"
QBIT_RESULT = "QBIT_RESULT"
QBIT = "QBIT"
QBIT_DIALER = "QBIT_DIALER"
QBIT_PHASE = "QBIT_PHASE"
QBIT_CORE = "QBIT_CORE"
QBIT_EXECUTE = "QBIT_EXECUTE"
QBIT_CHANNEL_CONTROL = "QBIT_CHANNEL_CONTROL"

INTENT_UPDATED = "INTENT_UPDATED"
INTENT_STATE = "INTENT_STATE"
ARBITRATED_INTENT = "ARBITRATED_INTENT"
INENT = "INTENT"

EVENT_BUS_READY = "EVENT_BUS_READY"
EVENT_BUS = "EVENT_BUS"
EVENT_EMIT = "EVENT_EMIT"
EVENT_WRAPPER = "EMIT_WRAPPER"
EMIT = "EMIT"

INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
FLOOD_MSG = "FLOOD_MSG"

SEED = "SEED"
SEED_CLI_COMMAND = "SEED_CLI_COMMAND"
SEED_USER_INPUT = "SEED_USER_INPUT"
SEED_INPUT = "SEED_INPUT"
SEED_OUTPUT = "SEED_OUTPUT"
SEED_ERROR = "SEED_ERROR"

SEED_START = "SEED_START"
SEED_STOP = "SEED_STOP"
SEED_PAUSE = "SEED_PAUSE"
SEED_SNAPSHOT = "SEED_SNAPSHOT"
SEED_STATUS = "SEED_STATUS"
SEED_HEARTBEAT = "SEED_HEARTBEAT"
SEED_COMMAND = "SEED_COMMAND"
SEED_COMMAND_DENIED = "SEED_COMMAND_DENIED"
SEED_COMMAND_RESULT = "SEED_COMMAND_RESULT"

HUD_MESSAGE = "HUD_MESSAGE"
HUD_ALERT = "HUD_ALERT"
HUD_ACTIVATE = "HUD_ACTIVATE"
HUD_DEACTIVATED = "HUD_DEACTIVATED"

STATUS = "STATUS"
CENTER_CMD = "CENTER_CMD"
THOUGHT = "THOUGHT"
STATE = "STATE"
LOOP_CONTROL = "LOOP_CONTROL"
INTROSPECT = "INTROSPECT"
RUNNING = "RUNNING"
LOCKED = "LOCKED"
PAUSE = "PAUSE"
MEMORY = "MEMORY"

UI_REQUEST = "UI_REQUEST"
UI_MAIN_LAUNCH = "UI_MAIN_LAUNCH"
UI_MAIN_SHUTDOWN = "UI_MAIN_SHUTDOWN"

LOAD_MODULE = "LOAD_MODULE"
ISOLATE = "ISOLATE"

NODE_CONNECTED = "NODE_CONNECTED"
NODE_DISCONNECTED = "NODE_DISCONNECTED"

SEED_AUDIO = "SEED_AUDIO"
SEED_STATE = "SEED_STATE"
SEED_QBIT = "SEED_QBIT"

DEVELOPER = "DEVELOPER"
USER = "USER"
MAIN = "MAIN"

ACTUATOR_COMMAND = "ACTUATOR_COMMAND"

CHANNEL_MANAGER = "CHANNEL_MANAGER"
USER_CHANNEL_MANAGER = "USER_CHANNEL_MANAGER"
CHANNEL_CONTROLLER = "CHANNEL_CONTROLLER"
CHANNEL_NODE = "CHANNEL_NODE"

AI_INPUT = "AI_INPUT"

CLI_PAUSE = "CLI_PAUSE"
CLI_SAMPLE = "CLI_SAMPLE"

POLICY = "POLICY"
PERMISSION_REQUEST = "PERMISSION_REQUEST"

SNAPSHOT = "SNAPSHOT"
STOP = "STOP"

DEVICE_001 = "DEVICE_001"
DEVICE_002 = "DEVICE_002"

RESULT = "RESULT"

CONSTRAINT_STATE = "CONSTRAINT_STATE"
IDLE_READ_TICK = "IDLE_READ_TICK"
LIMP_STATE_CLEARED = "LIMP_STATE_CLEARED"

# ==========================================================
# EVENT ALIASES
# ==========================================================

EVENT_ALIASES = {
    "device.input": DEVICE_INPUT,
    "device.output": "DEVICE_OUTPUT",
    "device.registered": "DEVICE_REGISTERED",

    "qbit.execute": QBIT_EXECUTE,
    "qbit.result": QBIT_RESULT,
    "qbit.tick": QBIT_TICK,

    "heartbeat": HEARTBEAT,
    "seed.heartbeat": SEED_HEARTBEAT,

    "system.boot": SYSTEM_BOOT,
    "system.shutdown": SYSTEM_SHUTDOWN,

    "event.bus.ready": EVENT_BUS_READY,

    "idle.read.tick": IDLE_READ_TICK,
}


# ==========================================================
# CHANNEL ENUM
# ==========================================================

class ChannelID(str, Enum):

    CORE = "core"
    QBIT = "qbit"
    ANALYTICS = "analytics"
    DEVICE = "device"
    SYSTEM = "system"
    USER = "user"
    NETWORK = "network"


# ==========================================================
# TRACK CONTEXT
# ==========================================================

class TrackContext:

    _current = None

    @classmethod
    def get_current(cls):
        return cls._current

    @classmethod
    def set_current(cls, track_id):
        cls._current = track_id

    @classmethod
    def clear(cls):
        cls._current = None


# ==========================================================
# EVENT BUS
# ==========================================================

class SEEDEventBus:

    VERSION = "7.0.0"

    CACHE_EXPIRATION_SEC = 5.0

    # ------------------------------------------------------
    # Event admission defaults
    # ------------------------------------------------------

    DEFAULT_BACKGROUND_RATE = 2.0
    DEFAULT_NORMAL_RATE = 50.0

    # ------------------------------------------------------
    # Singleton
    # ------------------------------------------------------

    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):

        with cls._singleton_lock:

            if cls._instance is None:

                cls._instance = super().__new__(cls)

        return cls._instance

    # ======================================================
    # INITIALIZATION
    # ======================================================

    def __init__(
        self,
        qbit=None,
        emit=None,
        callable_flag=True,
        task=None,
        payload=None,
        loop=None,
        qbit_dialer=None,
        time_travel_engine=None,
        stoarge_root="./SEED_ROOT",
        storage_root=None,
        ethics_manager=None,
        track=None,
        track_id_manager=TrackIDManager,
        debug=False,
        default_channel=ChannelID.CORE.value,
        qbit_instance=None,
        constraint_guardian=None,
        *args,
        **kwargs,
    ):

        # --------------------------------------------------
        # Existing singleton update
        # --------------------------------------------------

        if getattr(self, "_initialized", False):

            if qbit_dialer is not None:
                self.qbit_dialer = qbit_dialer

            if qbit_instance is not None:
                self.attach_qbit(qbit_instance)

            if time_travel_engine is not None:
                self.attach_time_travel(
                    time_travel_engine
                )

            if constraint_guardian is not None:
                self.attach_constraint_guardian(
                    constraint_guardian
                )

            if loop is not None:
                self.loop = loop

            if ethics_manager is not None:
                self.ethics_manager = ethics_manager

            return

        # --------------------------------------------------
        # Core state
        # --------------------------------------------------

        self._initialized = False

        self._running = False
        self.ready = False
        self._ready = False
#        self.emit = emit
        self._emit_enabled = True
        self._emit_hook = None

        self.ethics_manager = ethics_manager

        self.storage_root = (
            storage_root
            if storage_root is not None
            else stoarge_root
        )

        self.payload = payload
        self.track = track
        self.task = task

        self.qbit = (
            qbit_instance
            if qbit_instance is not None
            else qbit
        )

        self.qbit_dialer = qbit_dialer

        self.time_travel_engine = (
            time_travel_engine
        )

        self.constraint_guardian = (
            constraint_guardian
        )

        self.default_channel = (
            default_channel
            or ChannelID.CORE.value
        )

        self.limp_mode = False
        self._debug = debug

        self.loop = loop

        self._lock = threading.RLock()

        # --------------------------------------------------
        # Async task governor
        # --------------------------------------------------

        self._pending_async_tasks = set()

        self._max_async_tasks = 256

        # --------------------------------------------------
        # Event counters
        # --------------------------------------------------

        self._event_counts = defaultdict(int)
        self._event_dropped = defaultdict(int)
        self._event_last_emit = {}

        self._last_event_timestamp = {}

        # --------------------------------------------------
        # Diagnostics
        # --------------------------------------------------

        self._processed_events = deque(
            maxlen=512
        )

        self._cooldowns = {}

        self._module_status = defaultdict(
            lambda: {
                "booted": False,
                "last_post": 0,
                "good_standing": False,
            }
        )

        # --------------------------------------------------
        # Track ID manager
        # --------------------------------------------------

        try:

            self._track_id_manager = (
                track_id_manager()
                if track_id_manager
                else None
            )

        except Exception:

            self._track_id_manager = None

        # --------------------------------------------------
        # External emit hook
        # --------------------------------------------------

        if isinstance(emit, bool):

            self._emit_enabled = emit

        elif callable(emit):

            self._emit_hook = emit

        # --------------------------------------------------
        # Subscribers
        # --------------------------------------------------

        self._subscribers = defaultdict(list)

        self._register_default_events()

        # --------------------------------------------------
        # Async loop detection
        # --------------------------------------------------

        try:

            if self.loop is None:

                self.loop = (
                    asyncio.get_running_loop()
                )

        except RuntimeError:

            self.loop = None

        # --------------------------------------------------
        # Tracemalloc
        # --------------------------------------------------

        try:

            if not tracemalloc.is_tracing():

                tracemalloc.start()

        except Exception:

            pass

        # --------------------------------------------------
        # Internal dispatch
        # --------------------------------------------------

        self._dispatch = self._dispatch_event

        SEEDEventBus._instance = self

        self._initialized = True
        self._ready = True
        self.ready = True

        if qbit_instance is not None:

            self.attach_qbit(
                qbit_instance
            )

        logger.info(
            "[EVENT BUS] Initialized | version=%s",
            self.VERSION,
        )

    # ======================================================
    # CONSTRAINT GUARDIAN
    # ======================================================

    def attach_constraint_guardian(
        self,
        guardian,
    ):

        if guardian is None:

            return False

        self.constraint_guardian = guardian

        logger.info(
            "[EVENT BUS] ConstraintGuardian attached"
        )

        return True

    # ======================================================
    # WORKLOAD CLASSIFICATION
    # ======================================================

    def _classify_workload(
        self,
        event_name,
        priority=0,
        workload=None,
    ):

        if workload:

            return str(
                workload
            ).lower()

        normalized = self.normalize_event(
            event_name
        )

        # --------------------------------------------------
        # Critical system events
        # --------------------------------------------------

        critical = {
            SYSTEM_SHUTDOWN,
            SYSTEM_BOOT,
            SYSTEM_WARNING,
            SYSTEM_LIMP,
            SEED_ERROR,
            ERROR,
            QBIT_EXECUTE,
            ACTUATOR_COMMAND,
            SEED_COMMAND,
            SEED_COMMAND_DENIED,
        }

        if normalized in critical:

            return "critical"

        # --------------------------------------------------
        # High-priority events
        # --------------------------------------------------

        if priority is not None:

            try:

                if int(priority) >= 8:

                    return "critical"

            except Exception:

                pass

        # --------------------------------------------------
        # Background events
        # --------------------------------------------------

        background = {
            IDLE_READ_TICK,
            QBIT_TICK,
            ANALYTICS_UPDATED,
            STATUS,
            MEMORY,
            INTROSPECT,
        }

        if normalized in background:

            return "background"

        # --------------------------------------------------
        # Heartbeat remains normal.
        #
        # It is not background work because it is the
        # system timing source.
        # --------------------------------------------------

        if normalized in {
            HEARTBEAT,
            SEED_HEARTBEAT,
        }:

            return "normal"

        return "normal"

    # ======================================================
    # EVENT RATE GOVERNOR
    # ======================================================

    def _rate_limit_event(
        self,
        event_name,
        workload,
    ):

        now = time.monotonic()

        normalized = self.normalize_event(
            event_name
        )

        if workload == "critical":

            return True

        if workload == "background":

            interval = (
                1.0
                / self.DEFAULT_BACKGROUND_RATE
            )

        else:

            interval = (
                1.0
                / self.DEFAULT_NORMAL_RATE
            )

        last = self._event_last_emit.get(
            normalized,
            0.0,
        )

        if (
            last > 0.0
            and (now - last) < interval
        ):

            self._event_dropped[
                normalized
            ] += 1

            return False

        self._event_last_emit[
            normalized
        ] = now

        return True

    # ======================================================
    # CONSTRAINT ADMISSION
    # ======================================================

    def _allow_event(
        self,
        event_name,
        priority=0,
        workload="normal",
    ):

        normalized = self.normalize_event(
            event_name
        )

        workload = self._classify_workload(
            normalized,
            priority=priority,
            workload=workload,
        )

        guardian = getattr(
            self,
            "constraint_guardian",
            None,
        )

        # --------------------------------------------------
        # Critical events always pass.
        # --------------------------------------------------

        if workload == "critical":

            return True

        # --------------------------------------------------
        # Local rate governor.
        #
        # This protects the EventBus even if the guardian
        # is unavailable.
        # --------------------------------------------------

        if not self._rate_limit_event(
            normalized,
            workload,
        ):

            return False

        # --------------------------------------------------
        # No guardian attached.
        # --------------------------------------------------

        if guardian is None:

            return True

        try:

            # --------------------------------------------------
            # Limp mode.
            # --------------------------------------------------

            if getattr(
                guardian,
                "limp_mode",
                False,
            ):

                if workload in {
                    "background",
                    "deferred",
                }:

                    return False

            # --------------------------------------------------
            # Background work.
            # --------------------------------------------------

            if workload == "background":

                allow_background = getattr(
                    guardian,
                    "allow_background_work",
                    None,
                )

                if callable(
                    allow_background
                ):

                    return bool(
                        allow_background()
                    )

                # Conservative fallback.
                return False

            # --------------------------------------------------
            # Deferred work.
            # --------------------------------------------------

            if workload == "deferred":

                allow_deferred = getattr(
                    guardian,
                    "allow_deferred_work",
                    None,
                )

                if callable(
                    allow_deferred
                ):

                    return bool(
                        allow_deferred()
                    )

                return False

            # --------------------------------------------------
            # Normal work.
            # --------------------------------------------------

            allow_work = getattr(
                guardian,
                "allow_work",
                None,
            )

            if callable(allow_work):

                return bool(
                    allow_work("normal")
                )

            # --------------------------------------------------
            # Legacy check() compatibility.
            #
            # If only check() exists, use current process
            # measurements when possible.
            # --------------------------------------------------

            return True

        except Exception as exc:

            logger.debug(
                "[EventBus] Guardian admission skipped: %s",
                exc,
            )

            # EventBus remains fail-open for normal/critical
            # events. Background work remains rate limited.
            return workload != "background"

    # ======================================================
    # TIME TRAVEL ATTACHMENT
    # ======================================================

    def attach_time_travel(
        self,
        engine,
    ):

        if engine is None:

            return False

        record = getattr(
            engine,
            "record",
            None,
        )

        if not callable(record):

            logger.warning(
                "[EventBus] Invalid TimeTravelEngine attachment"
            )

            return False

        self.time_travel_engine = engine

        logger.info(
            "[EventBus] TimeTravelEngine attached"
        )

        return True

    # ======================================================
    # TIME TRAVEL RECORDING
    # ======================================================

    def _record_time_travel(
        self,
        event_name,
        payload=None,
        *,
        source=None,
        channel=None,
        track_id=None,
        parent_id=None,
        device_id=None,
        priority=0,
        reasoning_input=None,
    ):

        engine = getattr(
            self,
            "time_travel_engine",
            None,
        )

        if engine is None:

            return False

        record = getattr(
            engine,
            "record",
            None,
        )

        if not callable(record):

            return False

        event_payload = {}

        if isinstance(
            payload,
            dict,
        ):

            event_payload.update(
                payload
            )

        elif payload is not None:

            event_payload[
                "data"
            ] = payload

        # --------------------------------------------------
        # Metadata
        # --------------------------------------------------

        if source is not None:

            event_payload.setdefault(
                "source",
                source,
            )

        if channel is not None:

            event_payload.setdefault(
                "channel",
                channel,
            )

        if track_id is not None:

            event_payload.setdefault(
                "track_id",
                track_id,
            )

        if parent_id is not None:

            event_payload.setdefault(
                "parent_id",
                parent_id,
            )

        if device_id is not None:

            event_payload.setdefault(
                "device_id",
                device_id,
            )

        if priority is not None:

            event_payload.setdefault(
                "priority",
                priority,
            )

        if reasoning_input is not None:

            event_payload.setdefault(
                "reasoning_input",
                reasoning_input,
            )

        try:

            record(
                event_name,
                event_payload,
            )

            return True

        except Exception:

            logger.exception(
                "[EventBus] TimeTravel recording failed | "
                "event=%s",
                event_name,
            )

            return False

    # ======================================================
    # DEFAULT EVENTS
    # ======================================================

    def _register_default_events(self):

        events = [

            SYSTEM_WARNING,
            SYSTEM_SHUTDOWN,
            SYSTEM_BOOT,
            SYSTEM_LIMP,

            COMMAND_EXECUTED,
            ANALYTICS_UPDATED,
            HEARTBEAT,

            DEVICE_CONNECTED,
            DEVICE_DISCONNECTED,
            DEVICE_INPUT,
            "DEVICE_OUTPUT",
            "DEVICE_REGISTERED",
            DEVICE_SELECTED,
            DEVICE_DESELECTED,

            SKILL_LOADED,
            SKILL_FAILED,
            SKILL_COMMAND,

            CUSTOM_EVENT,

            QBIT_TICK,
            QBIT_RESULT,
            QBIT,
            QBIT_DIALER,
            QBIT_PHASE,
            QBIT_CORE,
            QBIT_EXECUTE,
            QBIT_CHANNEL_CONTROL,

            INTENT_UPDATED,
            INTENT_STATE,
            ARBITRATED_INTENT,

            EVENT_BUS_READY,
            EVENT_BUS,
            EVENT_EMIT,
            EVENT_WRAPPER,
            EMIT,

            INFO,
            WARNING,
            ERROR,
            FLOOD_MSG,

            SEED,
            SEED_CLI_COMMAND,
            SEED_USER_INPUT,
            SEED_INPUT,
            SEED_OUTPUT,
            SEED_ERROR,

            SEED_START,
            SEED_STOP,
            SEED_PAUSE,
            SEED_SNAPSHOT,
            SEED_STATUS,
            SEED_HEARTBEAT,
            SEED_COMMAND,
            SEED_COMMAND_DENIED,
            SEED_COMMAND_RESULT,

            HUD_MESSAGE,
            HUD_ALERT,
            HUD_ACTIVATE,
            HUD_DEACTIVATED,

            STATUS,
            CENTER_CMD,
            THOUGHT,
            STATE,
            LOOP_CONTROL,
            INTROSPECT,
            RUNNING,
            LOCKED,
            PAUSE,
            MEMORY,

            UI_REQUEST,
            UI_MAIN_LAUNCH,
            UI_MAIN_SHUTDOWN,

            LOAD_MODULE,
            ISOLATE,

            NODE_CONNECTED,
            NODE_DISCONNECTED,

            SEED_AUDIO,
            SEED_STATE,
            SEED_QBIT,

            DEVELOPER,
            USER,
            MAIN,

            ACTUATOR_COMMAND,

            CHANNEL_MANAGER,
            USER_CHANNEL_MANAGER,
            CHANNEL_CONTROLLER,
            CHANNEL_NODE,

            AI_INPUT,

            CLI_PAUSE,
            CLI_SAMPLE,

            POLICY,
            PERMISSION_REQUEST,

            SNAPSHOT,
            STOP,

            DEVICE_001,
            DEVICE_002,

            RESULT,

            CONSTRAINT_STATE,
            IDLE_READ_TICK,
            LIMP_STATE_CLEARED,
        ]

        with self._lock:

            for event_name in events:

                self._subscribers.setdefault(
                    event_name,
                    [],
                )

    # ======================================================
    # EVENT NORMALIZATION
    # ======================================================

    def normalize_event(
        self,
        event_name,
    ):

        if event_name is None:

            return HEARTBEAT

        if not isinstance(
            event_name,
            str,
        ):

            event_name = str(
                event_name
            )

        event_name = event_name.strip()

        if not event_name:

            return HEARTBEAT

        event_name = EVENT_ALIASES.get(
            event_name,
            event_name,
        )

        if event_name in self._subscribers:

            return event_name

        upper_name = event_name.upper()

        if upper_name in self._subscribers:

            return upper_name

        with self._lock:

            self._subscribers.setdefault(
                upper_name,
                [],
            )

        return upper_name

    # ======================================================
    # PUBLIC EMIT CONTRACT
    # ======================================================

    def emit(
        self,
        event_type=HEARTBEAT,
        payload=None,
        *args,
        source="EventBus",
        channel=None,
        track_id=None,
        parent_id=None,
        device_id=None,
        priority=0,
        reasoning_input=None,
        workload=None,
        **kwargs,
    ):

        try:

            # --------------------------------------------------
            # Legacy event_name compatibility
            # --------------------------------------------------

            legacy_event_name = kwargs.pop(
                "event_name",
                None,
            )

            if legacy_event_name is not None:

                if (
                    event_type == HEARTBEAT
                ):

                    event_type = (
                        legacy_event_name
                    )

            event_name = self.normalize_event(
                event_type
            )

            # --------------------------------------------------
            # Positional compatibility
            # --------------------------------------------------

            if args:

                if payload is None:

                    payload = args[0]

                elif len(args) > 0:

                    kwargs.setdefault(
                        "args",
                        args,
                    )

            # --------------------------------------------------
            # Payload copy
            # --------------------------------------------------

            if payload is None:

                dispatch_payload = {}

            elif isinstance(
                payload,
                dict,
            ):

                dispatch_payload = dict(
                    payload
                )

            else:

                dispatch_payload = payload

            # --------------------------------------------------
            # Prevent duplicate event metadata.
            # --------------------------------------------------

            if isinstance(
                dispatch_payload,
                dict,
            ):

                dispatch_payload.pop(
                    "event_name",
                    None,
                )

            # --------------------------------------------------
            # Admission control
            # --------------------------------------------------

            if not self._allow_event(
                event_name,
                priority=priority,
                workload=workload,
            ):

                self._event_dropped[
                    event_name
                ] += 1

                return False

            # --------------------------------------------------
            # Dispatch
            # --------------------------------------------------

            return self._dispatch_public(
                event_name,
                dispatch_payload,
                source=source,
                channel=channel,
                track_id=track_id,
                parent_id=parent_id,
                device_id=device_id,
                priority=priority,
                reasoning_input=reasoning_input,
                workload=workload,
                **kwargs,
            )

        except Exception as exc:

            logger.exception(
                "[EventBus] emit failed | event=%r | error=%s",
                event_type,
                exc,
            )

            return False

    # ======================================================
    # INTERNAL PUBLIC DISPATCH
    # ======================================================

    def _dispatch_public(
        self,
        event_name,
        payload=None,
        *,
        source="EventBus",
        channel=None,
        track_id=None,
        parent_id=None,
        device_id=None,
        priority=0,
        reasoning_input=None,
        workload=None,
        **kwargs,
    ):

        event_name = self.normalize_event(
            event_name
        )

        self._event_counts[
            event_name
        ] += 1

        self._last_event_timestamp[
            event_name
        ] = time.time()

        self._processed_events.append(
            (
                time.time(),
                event_name,
                source,
            )
        )

        # --------------------------------------------------
        # Subscriber dispatch
        # --------------------------------------------------

        self._notify_subscribers(
            event_name,
            payload,
        )

        # --------------------------------------------------
        # External hook
        # --------------------------------------------------

        if self._emit_hook:

            try:

                self._call_emit_hook(
                    self._emit_hook,
                    event_name,
                    payload,
                )

            except Exception:

                logger.exception(
                    "[EventBus] External emit hook failed | "
                    "event=%s",
                    event_name,
                )

        # --------------------------------------------------
        # Qbit forwarding
        #
        # Background events are not forwarded when the
        # guardian is actively suppressing them.
        #
        # Admission already occurred above.
        # --------------------------------------------------

        if self.qbit_dialer is not None:

            try:

                qbit_emit = getattr(
                    self.qbit_dialer,
                    "emit",
                    None,
                )

                if callable(qbit_emit):

                    result = qbit_emit(
                        event_name,
                        payload,
                    )

                    if asyncio.iscoroutine(
                        result
                    ):

                        self._schedule_coroutine(
                            result
                        )

            except Exception:

                logger.exception(
                    "[EventBus] QbitDialer emission failed | "
                    "event=%s",
                    event_name,
                )

        # --------------------------------------------------
        # TimeTravel
        #
        # Only admitted events reach this point.
        # --------------------------------------------------

        self._record_time_travel(
            event_name,
            payload,
            source=source,
            channel=channel,
            track_id=track_id,
            parent_id=parent_id,
            device_id=device_id,
            priority=priority,
            reasoning_input=reasoning_input,
        )

        return True

    # ======================================================
    # EMIT HOOK COMPATIBILITY
    # ======================================================

    def _call_emit_hook(
        self,
        hook,
        event_name,
        payload,
    ):

        try:

            result = hook(
                event_name,
                payload,
            )

            if asyncio.iscoroutine(
                result
            ):

                self._schedule_coroutine(
                    result
                )

            return True

        except TypeError:

            try:

                result = hook(
                    event_name
                )

                if asyncio.iscoroutine(
                    result
                ):

                    self._schedule_coroutine(
                        result
                    )

                return True

            except TypeError:

                result = hook()

                if asyncio.iscoroutine(
                    result
                ):

                    self._schedule_coroutine(
                        result
                    )

                return True

    # ======================================================
    # SAFE COROUTINE SCHEDULING
    # ======================================================

    def _schedule_coroutine(
        self,
        coroutine,
    ):

        if coroutine is None:

            return False

        # --------------------------------------------------
        # Async task governor.
        # --------------------------------------------------

        if (
            len(
                self._pending_async_tasks
            )
            >= self._max_async_tasks
        ):

            try:

                coroutine.close()

            except Exception:

                pass

            logger.warning(
                "[EventBus] Async task admission denied | "
                "pending=%s",
                len(
                    self._pending_async_tasks
                ),
            )

            return False

        try:

            running_loop = (
                asyncio.get_running_loop()
            )

            task = (
                running_loop.create_task(
                    coroutine
                )
            )

            self._pending_async_tasks.add(
                task
            )

            task.add_done_callback(
                self._async_task_done
            )

            return True

        except RuntimeError:

            if (
                self.loop
                and self.loop.is_running()
            ):

                try:

                    future = (
                        asyncio.run_coroutine_threadsafe(
                            coroutine,
                            self.loop,
                        )
                    )

                    return True

                except Exception:

                    logger.exception(
                        "[EventBus] Threadsafe coroutine "
                        "submission failed"
                    )

                    try:

                        coroutine.close()

                    except Exception:

                        pass

                    return False

            # --------------------------------------------------
            # No permanent loop creation.
            # --------------------------------------------------

            try:

                asyncio.run(
                    coroutine
                )

                return True

            except Exception:

                logger.exception(
                    "[EventBus] Coroutine dispatch failed"
                )

                return False

    def _async_task_done(
        self,
        task,
    ):

        self._pending_async_tasks.discard(
            task
        )

        try:

            task.result()

        except asyncio.CancelledError:

            pass

        except Exception:

            logger.exception(
                "[EventBus] Async subscriber failed"
            )

    # ======================================================
    # LOW-LEVEL EMIT
    # ======================================================

    def _emit(
        self,
        event_name=None,
        event_type=HEARTBEAT,
        payload=None,
        *args,
        source="EventBus",
        channel=None,
        track_id=None,
        parent_id=None,
        device_id=None,
        priority=0,
        reasoning_input=None,
        workload=None,
        **kwargs,
    ):

        # --------------------------------------------------
        # Legacy callers sometimes use event_type only.
        # --------------------------------------------------

        if event_name is None:

            event_name = event_type

        return self.emit(
            event_type=event_name,
            payload=payload,
            *args,
            source=source,
            channel=channel,
            track_id=track_id,
            parent_id=parent_id,
            device_id=device_id,
            priority=priority,
            reasoning_input=reasoning_input,
            workload=workload,
            **kwargs,
        )

    # ======================================================
    # SUBSCRIBE
    # ======================================================

    def subscribe(
        self,
        event_name,
        callback,
        **kwargs,
    ):

        if not isinstance(
            event_name,
            str,
        ):

            raise TypeError(
                "[EVENTBUS] event_name must be str"
            )

        normalized_event = (
            self.normalize_event(
                event_name
            )
        )

        if not callable(
            callback
        ):

            handler = getattr(
                callback,
                "handle_event",
                None,
            )

            if callable(handler):

                callback = handler

            else:

                raise TypeError(
                    f"[EVENTBUS] Callback for "
                    f"'{normalized_event}' "
                    f"is not callable"
                )

        with self._lock:

            if (
                callback
                not in self._subscribers[
                    normalized_event
                ]
            ):

                self._subscribers[
                    normalized_event
                ].append(
                    callback
                )

        return callback

    on = subscribe

    # ======================================================
    # UNSUBSCRIBE
    # ======================================================

    def unsubscribe(
        self,
        event_name,
        callback,
    ):

        normalized_event = (
            self.normalize_event(
                event_name
            )
        )

        with self._lock:

            handlers = (
                self._subscribers.get(
                    normalized_event,
                    [],
                )
            )

            if callback in handlers:

                handlers.remove(
                    callback
                )

                return True

        return False

    # ======================================================
    # PUBLISH
    # ======================================================

    def publish(
        self,
        event_name,
        payload=None,
        *,
        task_id="unknown",
        channel=None,
        track_id=None,
        parent_id=None,
        device_id=None,
        priority=0,
        reasoning_input=None,
        workload="normal",
        source="EventBus",
        **kwargs,
    ):

        return self.emit(
            event_type=event_name,
            payload=payload,
            source=source,
            channel=channel,
            track_id=track_id,
            parent_id=parent_id,
            device_id=device_id,
            priority=priority,
            reasoning_input=reasoning_input,
            workload=workload,
            task_id=task_id,
            **kwargs,
        )

    # ======================================================
    # NOTIFY SUBSCRIBERS
    # ======================================================

    def _notify_subscribers(
        self,
        event,
        payload=None,
    ):

        if not self._emit_enabled:

            return True

        event_name = (
            self.normalize_event(
                event
            )
        )

        with self._lock:

            handlers = list(
                self._subscribers.get(
                    event_name,
                    [],
                )
            )

        for handler in handlers:

            try:

                if isinstance(
                    handler,
                    dict,
                ):

                    callback = handler.get(
                        "callback"
                    )

                else:

                    callback = handler

                if not callable(
                    callback
                ):

                    continue

                if asyncio.iscoroutinefunction(
                    callback
                ):

                    self._schedule_coroutine(
                        callback(payload)
                    )

                else:

                    result = callback(
                        payload
                    )

                    if asyncio.iscoroutine(
                        result
                    ):

                        self._schedule_coroutine(
                            result
                        )

            except Exception:

                logger.exception(
                    "[EventBus] Handler failed | "
                    "event=%s",
                    event_name,
                )

        return True

    # ======================================================
    # SEMANTIC DISPATCH
    # ======================================================

    def _dispatch_event(
        self,
        event_name,
        payload=None,
        *args,
        source="unknown",
        channel=None,
        track_id=None,
        parent_id=None,
        device_id=None,
        priority=0,
        reasoning_input=None,
        workload=None,
        **kwargs,
    ):

        event_name = (
            self.normalize_event(
                event_name
            )
        )

        channel = (
            channel
            or self.default_channel
        )

        parent_id = (
            parent_id
            or TrackContext.get_current()
        )

        # --------------------------------------------------
        # Track ID
        # --------------------------------------------------

        if not track_id:

            try:

                manager = (
                    self._track_id_manager
                )

                generator = getattr(
                    manager,
                    "new",
                    None,
                )

                if callable(
                    generator
                ):

                    track_id = generator(
                        channel=channel,
                        skill=source,
                        parent_id=parent_id,
                        reasoning_input=reasoning_input,
                    )

            except Exception:

                logger.debug(
                    "[EventBus] TrackID generation fallback"
                )

        if not track_id:

            track_id = (
                f"EVENT-{uuid.uuid4().hex[:12]}"
            )

        # --------------------------------------------------
        # Quantum payload compatibility
        # --------------------------------------------------

        event_payload = payload

        if (
            QuantumObject
            and isinstance(
                payload,
                QuantumObject,
            )
        ):

            try:

                event_payload = TrackedData(
                    data=payload.as_dict(),
                    payload=payload,
                    source_id=source,
                    channel=channel,
                    track_id=track_id,
                    parent_id=parent_id,
                    device_id=device_id,
                    priority=priority,
                    **kwargs,
                )

            except Exception:

                event_payload = payload

        elif isinstance(
            payload,
            TrackedData,
        ):

            event_payload = payload

        # --------------------------------------------------
        # Dispatch
        # --------------------------------------------------

        return self._dispatch_public(
            event_name=event_name,
            payload=event_payload,
            source=source,
            channel=channel,
            track_id=track_id,
            parent_id=parent_id,
            device_id=device_id,
            priority=priority,
            reasoning_input=reasoning_input,
            workload=workload,
            **kwargs,
        )

    # ======================================================
    # QBIT CHANNEL EVENT
    # ======================================================

    def emit_qbit_channel_event(
        self,
        payload=None,
        channel=None,
    ):

        event_name = (
            QBIT_CHANNEL_CONTROL
        )

        if payload is None:

            payload = {}

        if not isinstance(
            payload,
            dict,
        ):

            payload = {
                "data": payload
            }

        payload = dict(
            payload
        )

        payload.setdefault(
            "event",
            event_name,
        )

        payload.setdefault(
            "channel",
            channel,
        )

        payload.setdefault(
            "timestamp",
            time.time(),
        )

        return self.publish(
            event_name,
            payload=payload,
            source="QbitChannelControl",
            channel=(
                channel
                or ChannelID.QBIT.value
            ),
            workload="normal",
        )

    # ======================================================
    # START
    # ======================================================

    def start(self):

        self._running = True
        self.ready = True
        self._ready = True

        self.emit(
            EVENT_BUS_READY,
            {
                "event": EVENT_BUS_READY,
                "timestamp": time.time(),
            },
            source="SEEDEventBus",
            workload="critical",
        )

        logger.info(
            "[EVENT BUS] Started"
        )

        return True

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        self._running = False
        self.ready = False
        self._ready = False

        # --------------------------------------------------
        # Cancel EventBus-owned async subscriber tasks.
        # --------------------------------------------------

        tasks = list(
            self._pending_async_tasks
        )

        for task in tasks:

            try:

                task.cancel()

            except Exception:

                pass

        self._pending_async_tasks.clear()

        logger.info(
            "[EVENT BUS] Stopped"
        )

        return True

    # ======================================================
    # QBIT ATTACH
    # ======================================================

    def attach_qbit(
        self,
        qbit_instance,
    ):

        if qbit_instance is None:

            return False

        self.qbit = qbit_instance

        try:

            attach = getattr(
                qbit_instance,
                "attach_event_bus",
                None,
            )

            if callable(
                attach
            ):

                attach(self)

        except Exception as exc:

            logger.error(
                "[EventBus] Qbit attach failed: %s",
                exc,
            )

        return True

    # ======================================================
    # QBIT DIALER ATTACH
    # ======================================================

    def attach_qbit_dialer(
        self,
        dialer,
    ):

        if dialer is None:

            return False

        self.qbit_dialer = dialer

        logger.info(
            "[EVENT BUS] QbitDialer attached"
        )

        return True

    # ======================================================
    # LIMP MODE
    # ======================================================

    def set_limp_mode(
        self,
        enabled=True,
    ):

        self.limp_mode = bool(
            enabled
        )

        logger.warning(
            "[EVENT BUS] Limp mode=%s",
            self.limp_mode,
        )

        return self.limp_mode

    # ======================================================
    # STATUS
    # ======================================================

    def status(self):

        return {
            "initialized":
                self._initialized,

            "running":
                self._running,

            "ready":
                self.ready,

            "subscriber_events":
                len(
                    self._subscribers
                ),

            "qbit_attached":
                self.qbit is not None,

            "qbit_dialer_attached":
                self.qbit_dialer is not None,

            "time_travel_attached":
                self.time_travel_engine is not None,

            "constraint_guardian_attached":
                self.constraint_guardian is not None,

            "emit_enabled":
                self._emit_enabled,

            "limp_mode":
                self.limp_mode,

            "pending_async_tasks":
                len(
                    self._pending_async_tasks
                ),

            "max_async_tasks":
                self._max_async_tasks,

            "event_count":
                sum(
                    self._event_counts.values()
                ),

            "dropped_events":
                sum(
                    self._event_dropped.values()
                ),

            "version":
                self.VERSION,
        }

    # ======================================================
    # EVENT STATISTICS
    # ======================================================

    def event_stats(
        self,
    ):

        return {
            "counts":
                dict(
                    self._event_counts
                ),

            "dropped":
                dict(
                    self._event_dropped
                ),

            "pending_async":
                len(
                    self._pending_async_tasks
                ),
        }

    # ======================================================
    # DEBUG
    # ======================================================

    def __repr__(self):

        return (
            "<SEEDEventBus "
            f"version={self.VERSION} "
            f"ready={self.ready} "
            f"running={self._running} "
            f"subscribers="
            f"{len(self._subscribers)}>"
        )


# ==========================================================
# QBIT CHANNEL CONTROL
# ==========================================================

class QbitChannelControl:

    def __init__(self):

        self.channels = {
            "camera": [],
            "audio": [],
            "data": [],
            "network": [],
        }

        self.channel_states = {
            channel: "pause"
            for channel in self.channels
        }

        self.eq_settings = defaultdict(
            lambda: {
                "bands": [],
                "gain": 1.0,
            }
        )

        self._lock = threading.RLock()

    # ======================================================
    # VALIDATION
    # ======================================================

    def _validate_channel(
        self,
        channel,
    ):

        if channel not in self.channels:

            raise ValueError(
                f"Channel {channel!r} not recognized"
            )

    # ======================================================
    # RUN
    # ======================================================

    def run(
        self,
        channel,
    ):

        self._validate_channel(
            channel
        )

        with self._lock:

            self.channel_states[
                channel
            ] = "run"

        logger.info(
            "[QCC] Channel '%s' running",
            channel,
        )

        return True

    # ======================================================
    # PAUSE
    # ======================================================

    def pause(
        self,
        channel,
    ):

        self._validate_channel(
            channel
        )

        with self._lock:

            self.channel_states[
                channel
            ] = "pause"

        logger.info(
            "[QCC] Channel '%s' paused",
            channel,
        )

        return True

    # ======================================================
    # REWIND
    # ======================================================

    def rewind(
        self,
        channel,
    ):

        self._validate_channel(
            channel
        )

        with self._lock:

            self.channel_states[
                channel
            ] = "rewind"

        logger.info(
            "[QCC] Channel '%s' rewinding",
            channel,
        )

        return True

    # ======================================================
    # OVERLAY
    # ======================================================

    def overlay(
        self,
        channel,
    ):

        self._validate_channel(
            channel
        )

        with self._lock:

            self.channel_states[
                channel
            ] = "overlay"

        logger.info(
            "[QCC] Channel '%s' overlay mode",
            channel,
        )

        return True

    # ======================================================
    # EQ
    # ======================================================

    def set_eq(
        self,
        channel,
        bands,
        gain,
    ):

        self._validate_channel(
            channel
        )

        with self._lock:

            self.eq_settings[
                channel
            ] = {
                "bands": list(
                    bands or []
                ),
                "gain": float(
                    gain
                ),
            }

        logger.info(
            "[QCC] EQ updated for channel '%s'",
            channel,
        )

        return True

    # ======================================================
    # PUSH SIGNAL
    # ======================================================

    def push_signal(
        self,
        channel,
        data,
    ):

        self._validate_channel(
            channel
        )

        with self._lock:

            self.channels[
                channel
            ].append(
                data
            )

        return True

    # ======================================================
    # PULL SIGNAL
    # ======================================================

    def pull_signal(
        self,
        channel,
    ):

        self._validate_channel(
            channel
        )

        with self._lock:

            if not self.channels[
                channel
            ]:

                return None

            return self.channels[
                channel
            ].pop(0)

    # ======================================================
    # EVENT HANDLER
    # ======================================================

    def handle_event(
        self,
        event,
    ):

        if isinstance(
            event,
            TrackedData,
        ):

            try:

                event = (
                    event.payload
                    if isinstance(
                        event.payload,
                        dict,
                    )
                    else event.data
                )

            except Exception:

                return False

        if not isinstance(
            event,
            dict,
        ):

            logger.warning(
                "[QCC] Ignoring non-dict event: %r",
                event,
            )

            return False

        action = event.get(
            "action"
        )

        channel = event.get(
            "channel"
        )

        if not action:

            logger.warning(
                "[QCC] Missing action"
            )

            return False

        if channel not in self.channels:

            logger.warning(
                "[QCC] Unknown channel: %r",
                channel,
            )

            return False

        if action == "run":

            return self.run(
                channel
            )

        if action == "pause":

            return self.pause(
                channel
            )

        if action == "rewind":

            return self.rewind(
                channel
            )

        if action == "overlay":

            return self.overlay(
                channel
            )

        if action == "set_eq":

            return self.set_eq(
                channel,
                event.get(
                    "bands",
                    [],
                ),
                event.get(
                    "gain",
                    1.0,
                ),
            )

        logger.warning(
            "[QCC] Unknown action '%s' "
            "for channel '%s'",
            action,
            channel,
        )

        return False

    # ======================================================
    # ASYNC EVENTBUS INTEGRATION
    # ======================================================

    async def emit_event(
        self,
        event_bus,
        channel,
        payload,
    ):

        if event_bus is None:

            logger.warning(
                "[QCC] EventBus unavailable | channel=%s",
                channel,
            )

            return False

        await asyncio.sleep(0)

        try:

            emitter = getattr(
                event_bus,
                "emit_qbit_channel_event",
                None,
            )

            if callable(
                emitter
            ):

                result = emitter(
                    payload=payload,
                    channel=channel,
                )

                if asyncio.iscoroutine(
                    result
                ):

                    await result

                return bool(
                    result is not False
                )

            publisher = getattr(
                event_bus,
                "publish",
                None,
            )

            if callable(
                publisher
            ):

                result = publisher(
                    QBIT_CHANNEL_CONTROL,
                    payload={
                        "event":
                            QBIT_CHANNEL_CONTROL,

                        "channel":
                            channel,

                        "payload":
                            payload,

                        "timestamp":
                            time.time(),
                    },

                    source=
                        "QbitChannelControl",

                    channel=
                        channel,

                    workload=
                        "normal",
                )

                if asyncio.iscoroutine(
                    result
                ):

                    result = await result

                return bool(
                    result is not False
                )

        except Exception:

            logger.exception(
                "[QCC] EventBus emission failed | "
                "channel=%s",
                channel,
            )

        return False


# ==========================================================
# GLOBAL QBIT CHANNEL CONTROL
# ==========================================================

qbit_channel_control = (
    QbitChannelControl()
)


# ==========================================================
# GLOBAL EVENT BUS
# ==========================================================

def get_event_bus():

    return SEEDEventBus()


# ==========================================================
# EVENT BUS HEALTH
# ==========================================================

def event_bus_health():

    try:

        bus = SEEDEventBus()

        status = bus.status()

        status["healthy"] = bool(
            status.get(
                "initialized",
                False,
            )
        )

        return status

    except Exception as exc:

        return {
            "healthy": False,
            "error": str(exc),
        }