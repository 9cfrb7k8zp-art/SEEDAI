# ==========================================================
# FILE: py_seed.py
# PATH: SEED_ROOT/seed/core/py_seed.py
#
# SEED AI OS — PY-SEED BRIDGE
# VERSION: 2.0.0
#
# PURPOSE:
#   Stable Python bridge between:
#
#       Python SEEDCore
#              │
#              ▼
#          PySeedBridge
#          /    |     \
#         ▼     ▼      ▼
#      C++    Build   EventBus
#    bindings Manager   /
#                      ▼
#                 Track/Channel
#
# CORE RELATIONSHIPS:
#
#   HeartbeatEmitter
#       = system clock / lifecycle timing
#
#   QbitDialer
#       = command / cognitive control
#
#   QbitQueueLoop
#       = execution queue
#
#   SEEDEventBus
#       = system event transport
#
#   TrackID / ChannelID
#       = lineage / routing identity
#
#   ConstraintGuardian
#       = workload governance
#
#   LimpModeController
#       = degraded/recovery state
#
#   TimeTravelEngine
#       = historical event persistence
#
#   SEEDCore
#       = core runtime
#
#   BuildManager
#       = build orchestration
#
#   PySeedBridge
#       = boundary adapter only
#
# IMPORTANT:
#   This module MUST NOT create a competing system clock,
#   command brain, or independent Qbit execution architecture.
#
# BOOT REQUIREMENTS:
#   - Lazy imports
#   - Late binding
#   - Idempotent initialization
#   - Shutdown safe
#   - Partial-boot safe
#   - Thread safe
#   - Async safe
#   - EventBus signature tolerant
#   - TrackID aware
#   - ConstraintGuardian aware
#   - LimpMode aware
#
# UPDATED:
#   2026-08-17
# ==========================================================

from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import sys
import threading
import time
import types
import uuid

from collections import deque
from copy import deepcopy
from typing import (
    Any,
    Callable,
    Deque,
    Dict,
    Optional,
)


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("PySeedBridge")

if not logger.handlers:
    logger.addHandler(logging.NullHandler())

logger.setLevel(
    logging.INFO
)


# ==========================================================
# OPTIONAL IMPORTS
#
# Do NOT make py_seed fail during partial boot because one
# optional SEED subsystem has not been initialized yet.
# ==========================================================

try:
    from seed.core.channel_id import (
        ChannelID,
    )
except Exception:
    ChannelID = None


try:
    from seed.core.track_base import (
        TrackBase,
        TrackIDBase,
        TrackContextBase,
    )
except Exception:
    TrackBase = None
    TrackIDBase = None
    TrackContextBase = None


try:
    from seed.core.heartbeat import (
        TrackContext,
    )
except Exception:

    class TrackContext:
        @staticmethod
        def get():
            return None

        @staticmethod
        def write(_track_id):
            return None


try:
    from seed.core.event_bus import (
        TrackedData,
    )
except Exception:
    TrackedData = None


# ==========================================================
# PYTHON BINDING PLACEHOLDER
#
# The real native module may not exist during initial import.
#
# Do NOT import SEEDCore here.
# SEEDCore is late-bound through initialize().
# ==========================================================

_py_seed: Any = None


# A lightweight compatibility placeholder is registered only
# if the name does not already belong to a real native module.
#
# This prevents import explosions from modules doing:
#
#     import py_seed
#
# during partial boot.
#
# The placeholder is replaced by register_bindings().
# ==========================================================

if "py_seed" not in sys.modules:

    try:
        sys.modules["py_seed"] = types.ModuleType(
            "py_seed"
        )
    except Exception:
        pass


# ==========================================================
# TRACK HELPER
#
# The old module called track() everywhere without defining it.
# This implementation keeps tracking non-fatal.
# ==========================================================

def track(
    source: str,
    event: str,
    priority: str = "INFO",
    note: Optional[str] = None,
    **metadata,
) -> Optional[str]:

    try:

        track_id = _generate_track_id(
            skill_name=source
        )

        message = (
            f"[{source}] "
            f"{event}"
        )

        if note:
            message += (
                f" | {note}"
            )

        extra = (
            f" | TrackID={track_id}"
        )

        if metadata:
            extra += (
                f" | meta={metadata}"
            )

        level = str(
            priority
        ).upper()

        if level in (
            "CRITICAL",
            "HIGH",
        ):
            logger.warning(
                message + extra
            )

        elif level in (
            "MED",
            "MEDIUM",
            "WARNING",
        ):
            logger.info(
                message + extra
            )

        elif level == "LOW":
            logger.debug(
                message + extra
            )

        else:
            logger.info(
                message + extra
            )

        return track_id

    except Exception:
        return None


# ==========================================================
# TRACK ID HELPER
# ==========================================================

def _generate_track_id(
    skill_name: str = "PY-SEED",
) -> str:

    try:

        # --------------------------------------------------
        # Prefer the existing authoritative generator.
        # --------------------------------------------------

        from seed.core.channel_id import (
            generate_track_id,
        )

        try:
            result = generate_track_id(
                skill_name=skill_name
            )

            if result:
                return str(
                    result
                )

        except Exception:
            pass

    except Exception:
        pass

    # ------------------------------------------------------
    # Safe fallback.
    # ------------------------------------------------------

    return (
        f"{skill_name}"
        f"_{int(time.time() * 1000)}"
        f"_{uuid.uuid4().hex[:8]}"
    )


# ==========================================================
# CHANNEL ID HELPER
# ==========================================================

def _generate_channel_id(
    marker: str = "B",
) -> str:

    try:

        if ChannelID is not None:

            generator = getattr(
                ChannelID,
                "next",
                None,
            )

            if callable(generator):

                value = generator(
                    marker
                )

                if value is not None:
                    return str(
                        value
                    )

    except Exception:
        pass

    return (
        f"{marker}-"
        f"{int(time.time() * 1000)}-"
        f"{uuid.uuid4().hex[:6]}"
    )


# ==========================================================
# CONTEXT
# ==========================================================

class PySeedContext:

    _instance = None
    _instance_lock = threading.RLock()

    def __init__(self):

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        self.initialized = False
        self.shutdown = False

        # --------------------------------------------------
        # Binding state
        # --------------------------------------------------

        self.bindings = None
        self.binding_source = None

        # --------------------------------------------------
        # Core references
        # --------------------------------------------------

        self.seed_core = None
        self.event_bus = None
        self.build_manager = None

        self.qbit_dialer = None
        self.qbit_queue = None
        self.heartbeat = None

        self.constraint_guardian = None
        self.limp_controller = None
        self.time_travel_engine = None

        # --------------------------------------------------
        # Runtime context
        # --------------------------------------------------

        self.runtime_context = None

        # --------------------------------------------------
        # Async state
        #
        # This bridge does not automatically own the main
        # SEED event loop.
        # --------------------------------------------------

        self.event_loop = None
        self.loop_thread = None
        self.loop_owned = False

        # --------------------------------------------------
        # Build queue
        #
        # deque + lock avoids list-pop races.
        # --------------------------------------------------

        self.build_queue: Deque[
            Dict[str, Any]
        ] = deque()

        self.build_queue_lock = threading.RLock()

        self.build_worker_running = False
        self.build_worker_thread = None

        self.build_shutdown = threading.Event()

        # --------------------------------------------------
        # State
        # --------------------------------------------------

        self.retries = 0
        self.limp_mode = False

        self.last_post = None
        self.last_error = None
        self.last_call = None

        self.call_count = 0
        self.failure_count = 0

        # --------------------------------------------------
        # Lifecycle lock
        # --------------------------------------------------

        self._lock = threading.RLock()

    # ======================================================
    # SINGLETON
    # ======================================================

    @classmethod
    def get(
        cls,
    ) -> "PySeedContext":

        with cls._instance_lock:

            if cls._instance is None:

                cls._instance = (
                    PySeedContext()
                )

            return cls._instance


# ==========================================================
# CONTEXT ACCESS
# ==========================================================

def get_context() -> PySeedContext:

    return PySeedContext.get()


# ==========================================================
# LAZY NATIVE BINDING LOAD
# ==========================================================

def get_py_seed():

    global _py_seed

    ctx = PySeedContext.get()

    # ------------------------------------------------------
    # Already bound.
    # ------------------------------------------------------

    if (
        _py_seed is not None
        and not isinstance(
            _py_seed,
            types.ModuleType,
        )
        or (
            _py_seed is not None
            and getattr(
                _py_seed,
                "__name__",
                "",
            ) != "py_seed"
        )
    ):

        return _py_seed

    # ------------------------------------------------------
    # If context has real bindings.
    # ------------------------------------------------------

    if (
        ctx.bindings is not None
        and ctx.bindings is not _placeholder_module()
    ):

        _py_seed = ctx.bindings

        return _py_seed

    # ------------------------------------------------------
    # Late native import.
    # ------------------------------------------------------

    try:

        module = importlib.import_module(
            "py_seed"
        )

        # --------------------------------------------------
        # Avoid accepting our own placeholder.
        # --------------------------------------------------

        if (
            module is _placeholder_module()
        ):

            raise ModuleNotFoundError(
                "Native py_seed bindings are "
                "not registered yet"
            )

        _py_seed = module

        ctx.bindings = module
        ctx.binding_source = (
            "native-import"
        )

        track(
            "PY-SEED",
            "MODULE_LOADED",
            priority="MED",
        )

        return module

    except Exception as exc:

        ctx.last_error = str(
            exc
        )

        track(
            "PY-SEED",
            "MODULE_NOT_FOUND",
            priority="HIGH",
            note=str(exc),
        )

        raise


# ==========================================================
# PLACEHOLDER ACCESS
# ==========================================================

def _placeholder_module():

    return sys.modules.get(
        "py_seed"
    )


# ==========================================================
# REGISTER NATIVE BINDINGS
# ==========================================================

def register_bindings(
    bindings_module,
):

    global _py_seed

    if bindings_module is None:

        raise ValueError(
            "bindings_module cannot be None"
        )

    ctx = PySeedContext.get()

    with ctx._lock:

        ctx.bindings = (
            bindings_module
        )

        ctx.binding_source = (
            "registered"
        )

        _py_seed = (
            bindings_module
        )

        try:

            sys.modules[
                "py_seed"
            ] = bindings_module

        except Exception:
            pass

        ctx.initialized = True
        ctx.shutdown = False

    track(
        "PY-SEED",
        "BINDINGS_REGISTERED",
        priority="MED",
        note=(
            f"module="
            f"{getattr(bindings_module, '__name__', type(bindings_module).__name__)}"
        ),
    )

    return ctx


# ==========================================================
# INITIALIZATION
#
# IMPORTANT:
# There is intentionally ONLY ONE initialize().
# ==========================================================

def initialize(
    bindings_module=None,
    event_bus=None,
    seed_core_instance=None,
    build_manager=None,
    qbit_dialer=None,
    qbit_queue=None,
    heartbeat=None,
    constraint_guardian=None,
    limp_controller=None,
    time_travel_engine=None,
    runtime_context=None,
):

    global _py_seed

    ctx = PySeedContext.get()

    with ctx._lock:

        # --------------------------------------------------
        # Update references even if already initialized.
        #
        # This allows late boot wiring.
        # --------------------------------------------------

        if event_bus is not None:
            ctx.event_bus = event_bus

        if seed_core_instance is not None:
            ctx.seed_core = (
                seed_core_instance
            )

        if build_manager is not None:
            ctx.build_manager = (
                build_manager
            )

        if qbit_dialer is not None:
            ctx.qbit_dialer = (
                qbit_dialer
            )

        if qbit_queue is not None:
            ctx.qbit_queue = (
                qbit_queue
            )

        if heartbeat is not None:
            ctx.heartbeat = (
                heartbeat
            )

        if constraint_guardian is not None:
            ctx.constraint_guardian = (
                constraint_guardian
            )

        if limp_controller is not None:
            ctx.limp_controller = (
                limp_controller
            )

        if time_travel_engine is not None:
            ctx.time_travel_engine = (
                time_travel_engine
            )

        if runtime_context is not None:
            ctx.runtime_context = (
                runtime_context
            )

        # --------------------------------------------------
        # Bind native module if supplied.
        # --------------------------------------------------

        if bindings_module is not None:

            ctx.bindings = (
                bindings_module
            )

            ctx.binding_source = (
                "initialize"
            )

            _py_seed = (
                bindings_module
            )

        elif (
            ctx.bindings is None
            and _py_seed is not None
            and _py_seed is not _placeholder_module()
        ):

            ctx.bindings = (
                _py_seed
            )

        # --------------------------------------------------
        # Event loop.
        #
        # Prefer the currently running SEED loop.
        # Never create a competing loop if one exists.
        # --------------------------------------------------

        try:

            running_loop = (
                asyncio.get_running_loop()
            )

            ctx.event_loop = (
                running_loop
            )

            ctx.loop_owned = False

        except RuntimeError:

            try:

                current_loop = (
                    asyncio.get_event_loop()
                )

            except RuntimeError:

                current_loop = (
                    asyncio.new_event_loop()
                )

            ctx.event_loop = (
                current_loop
            )

            ctx.loop_owned = False

        # --------------------------------------------------
        # Lifecycle.
        # --------------------------------------------------

        was_initialized = (
            ctx.initialized
        )

        ctx.initialized = True
        ctx.shutdown = False

    if was_initialized:

        track(
            "PY-SEED",
            "LATE_BINDING_UPDATE",
            priority="LOW",
        )

    else:

        track(
            "PY-SEED",
            "INITIALIZED",
            priority="CRITICAL",
        )

    return ctx


# ==========================================================
# RUNTIME LINKING
#
# Allows SEEDCore/main boot to wire existing systems without
# forcing py_seed to construct those systems.
# ==========================================================

def link_runtime(
    *,
    seed_core=None,
    event_bus=None,
    build_manager=None,
    qbit_dialer=None,
    qbit_queue=None,
    heartbeat=None,
    constraint_guardian=None,
    limp_controller=None,
    time_travel_engine=None,
    runtime_context=None,
):

    return initialize(
        event_bus=event_bus,
        seed_core_instance=seed_core,
        build_manager=build_manager,
        qbit_dialer=qbit_dialer,
        qbit_queue=qbit_queue,
        heartbeat=heartbeat,
        constraint_guardian=constraint_guardian,
        limp_controller=limp_controller,
        time_travel_engine=time_travel_engine,
        runtime_context=runtime_context,
    )


# ==========================================================
# GOVERNANCE
# ==========================================================

def _governor_state(
    ctx: PySeedContext,
) -> str:

    guardian = (
        ctx.constraint_guardian
    )

    if guardian is None:

        # Try runtime context.
        runtime = (
            ctx.runtime_context
        )

        if runtime is not None:

            guardian = getattr(
                runtime,
                "constraint_guardian",
                None,
            )

            if guardian is None:

                guardian = getattr(
                    runtime,
                    "constraintGuardian",
                    None,
                )

    if guardian is not None:

        try:

            getter = getattr(
                guardian,
                "get_state",
                None,
            )

            if callable(getter):

                return str(
                    getter()
                ).lower()

        except Exception:
            pass

    # ------------------------------------------------------
    # Limp mode is a secondary signal.
    # ------------------------------------------------------

    if ctx.limp_mode:

        return "pressure"

    limp = (
        ctx.limp_controller
    )

    if limp is not None:

        try:

            if bool(
                getattr(
                    limp,
                    "active",
                    False,
                )
            ):

                return "pressure"

        except Exception:
            pass

    return "clear"


def _background_allowed(
    ctx: PySeedContext,
) -> bool:

    state = _governor_state(
        ctx
    )

    # ------------------------------------------------------
    # Build work is explicitly background work.
    #
    # Critical command traffic remains outside this bridge.
    # ------------------------------------------------------

    if state in (
        "warning",
        "block",
    ):

        return False

    guardian = (
        ctx.constraint_guardian
    )

    if guardian is not None:

        try:

            checker = getattr(
                guardian,
                "allow_background_work",
                None,
            )

            if callable(checker):

                return bool(
                    checker()
                )

        except Exception:
            pass

    return True


# ==========================================================
# SAFE EVENT BUS PUBLISH
#
# Different SEED versions have used different EventBus
# signatures. Keep this boundary tolerant.
# ==========================================================

def _publish_event(
    ctx: PySeedContext,
    event_type: str,
    payload: Any,
    *,
    source: str = "py_seed",
    channel: str = "PY_SEED",
    priority: Any = 5,
    track_id: Optional[str] = None,
):

    bus = ctx.event_bus

    if bus is None:
        return False

    tid = (
        track_id
        or _generate_track_id(
            "PY-SEED-EVENT"
        )
    )

    # ------------------------------------------------------
    # Prefer TrackedData when available.
    # ------------------------------------------------------

    event_payload = payload

    if TrackedData is not None:

        try:

            parent_id = None

            try:
                parent_id = (
                    TrackContext.get()
                )
            except Exception:
                pass

            event_payload = TrackedData(
                track_id=tid,
                parent_id=parent_id,
                channel=channel,
                payload=payload,
                priority=priority,
            )

        except Exception:
            event_payload = payload

    # ------------------------------------------------------
    # Preferred modern signature.
    # ------------------------------------------------------

    publisher = getattr(
        bus,
        "publish",
        None,
    )

    if callable(publisher):

        attempts = [

            lambda: publisher(
                event_type,
                event_payload,
                source=source,
                channel=channel,
                priority=priority,
            ),

            lambda: publisher(
                event_type,
                payload=event_payload,
                source=source,
                channel=channel,
                priority=priority,
            ),

            lambda: publisher(
                event_type,
                event_payload,
            ),

        ]

        for attempt in attempts:

            try:

                attempt()

                ctx.last_post = time.time()

                return True

            except TypeError:
                continue

            except Exception as exc:

                ctx.last_error = str(
                    exc
                )

                logger.debug(
                    "[PySeedBridge] "
                    f"EventBus publish failed: {exc}"
                )

                return False

    # ------------------------------------------------------
    # Some older EventBus implementations expose emit().
    # ------------------------------------------------------

    emitter = getattr(
        bus,
        "emit",
        None,
    )

    if callable(emitter):

        try:

            emitter(
                event_type,
                event_payload,
            )

            ctx.last_post = time.time()

            return True

        except Exception as exc:

            logger.debug(
                "[PySeedBridge] "
                f"EventBus emit failed: {exc}"
            )

    return False


# ==========================================================
# CLI / CORE COMMAND
# ==========================================================

def cli_command(
    cmd_name: str,
    *args,
    **kwargs,
):

    ctx = PySeedContext.get()

    if ctx.shutdown:

        raise RuntimeError(
            "PySeedBridge is shutting down"
        )

    core = (
        ctx.seed_core
    )

    if core is None:

        raise RuntimeError(
            "SEEDCore not initialized. "
            "Cannot execute CLI commands."
        )

    if not cmd_name:

        raise ValueError(
            "cmd_name is required"
        )

    func = getattr(
        core,
        cmd_name,
        None,
    )

    if not callable(func):

        raise RuntimeError(
            f"SEEDCore has no callable "
            f"command named '{cmd_name}'"
        )

    track(
        "PY-SEED",
        "CLI_COMMAND_EXECUTE",
        priority="MED",
        note=(
            f"{cmd_name} "
            f"args={args} "
            f"kwargs={kwargs}"
        ),
    )

    return func(
        *args,
        **kwargs,
    )


# ==========================================================
# ASYNC CLI COMMAND
# ==========================================================

async def cli_command_async(
    cmd_name: str,
    *args,
    **kwargs,
):

    ctx = PySeedContext.get()

    if ctx.shutdown:

        raise RuntimeError(
            "PySeedBridge is shutting down"
        )

    core = (
        ctx.seed_core
    )

    if core is None:

        raise RuntimeError(
            "SEEDCore not initialized"
        )

    func = getattr(
        core,
        cmd_name,
        None,
    )

    if not callable(func):

        raise RuntimeError(
            f"SEEDCore has no callable "
            f"command '{cmd_name}'"
        )

    result = func(
        *args,
        **kwargs,
    )

    if inspect.isawaitable(
        result
    ):

        return await result

    return result


# ==========================================================
# SAFE NATIVE CALL
# ==========================================================

def safe_call(
    func_name,
    *args,
    retries=3,
    **kwargs,
):

    ctx = PySeedContext.get()

    if ctx.shutdown:

        raise RuntimeError(
            "PySeedBridge is shutting down"
        )

    bindings = (
        ctx.bindings
    )

    # ------------------------------------------------------
    # Late resolve.
    # ------------------------------------------------------

    if bindings is None:

        try:

            bindings = (
                get_py_seed()
            )

        except Exception as exc:

            raise RuntimeError(
                f"Bindings not initialized "
                f"for function '{func_name}': "
                f"{exc}"
            ) from exc

    if not func_name:

        raise ValueError(
            "func_name is required"
        )

    func = getattr(
        bindings,
        func_name,
        None,
    )

    if not callable(func):

        raise AttributeError(
            f"Native py_seed bindings "
            f"do not expose callable "
            f"'{func_name}'"
        )

    attempts = max(
        int(retries),
        1,
    )

    last_err = None

    for attempt in range(
        1,
        attempts + 1,
    ):

        ctx.call_count += 1

        ctx.last_call = (
            time.time()
        )

        try:

            result = func(
                *args,
                **kwargs,
            )

            track(
                "PY-SEED",
                "CALL_SUCCESS",
                priority="LOW",
                note=(
                    f"{func_name} "
                    f"attempt={attempt}"
                ),
            )

            return result

        except Exception as exc:

            last_err = exc
            ctx.failure_count += 1
            ctx.last_error = str(
                exc
            )

            track(
                "PY-SEED",
                "CALL_FAIL",
                priority="HIGH",
                note=(
                    f"{func_name} "
                    f"attempt={attempt} "
                    f"err={exc}"
                ),
            )

            if attempt >= attempts:
                break

            # --------------------------------------------------
            # Resource-aware retry.
            # --------------------------------------------------

            state = _governor_state(
                ctx
            )

            if state == "block":

                delay = 0.5

            elif state == "warning":

                delay = 0.25

            elif state == "pressure":

                delay = 0.10

            else:

                delay = 0.02

            time.sleep(
                delay
            )

    raise RuntimeError(
        f"Function '{func_name}' "
        f"failed after {attempts} "
        f"attempts: {last_err}"
    ) from last_err


# ==========================================================
# BUILD ITEM CREATION
# ==========================================================

def _make_build_item(
    target,
    config=None,
    source_files=None,
):

    track_id = (
        _generate_track_id(
            "PY-SEED-BUILD"
        )
    )

    channel_id = (
        _generate_channel_id(
            "B"
        )
    )

    return {

        "target": target,

        "config": deepcopy(
            config or {}
        ),

        "source_files": deepcopy(
            source_files or []
        ),

        "channel_id": channel_id,

        "_channel_id": channel_id,

        "track_id": track_id,

        "timestamp": time.time(),

        "source": "py_seed",

        "status": "queued",

        "governor_state": None,

    }


# ==========================================================
# SUBMIT BUILD
# ==========================================================

def submit_build(
    target,
    config=None,
    source_files=None,
):

    ctx = PySeedContext.get()

    if ctx.shutdown:

        raise RuntimeError(
            "Cannot submit build while "
            "PySeedBridge is shutting down"
        )

    if not target:

        raise ValueError(
            "Build target is required"
        )

    item = _make_build_item(
        target,
        config=config,
        source_files=source_files,
    )

    state = _governor_state(
        ctx
    )

    item[
        "governor_state"
    ] = state

    if (
        ctx.limp_mode
        or state in (
            "pressure",
            "warning",
            "block",
        )
    ):

        track(
            "PY-SEED",
            "BUILD_SUBMIT_GOVERNED",
            priority="MED",
            note=(
                f"target={target} "
                f"state={state}"
            ),
        )

    with ctx.build_queue_lock:

        ctx.build_queue.append(
            item
        )

        queue_depth = len(
            ctx.build_queue
        )

    track(
        "PY-SEED",
        "BUILD_SUBMIT",
        priority="MED",
        note=(
            f"target={target} "
            f"channel={item['channel_id']} "
            f"track={item['track_id']} "
            f"queue_depth={queue_depth}"
        ),
    )

    _publish_event(
        ctx,
        "BUILD_QUEUE_UPDATE",
        {
            "target": target,
            "config": item[
                "config"
            ],
            "source_files": item[
                "source_files"
            ],
            "channel_id": item[
                "channel_id"
            ],
            "track_id": item[
                "track_id"
            ],
            "queue_depth": queue_depth,
            "governor_state": state,
        },
        source="py_seed",
        channel="build_manager",
        priority=5,
        track_id=item[
            "track_id"
        ],
    )

    return item[
        "channel_id"
    ]


# ==========================================================
# POP BUILD ITEM
# ==========================================================

def _pop_build_item(
    ctx: PySeedContext,
):

    with ctx.build_queue_lock:

        if not ctx.build_queue:

            return None

        return (
            ctx.build_queue.popleft()
        )


# ==========================================================
# BUILD MANAGER DISPATCH
# ==========================================================

def _compile_build_item(
    ctx: PySeedContext,
    item: Dict[str, Any],
):

    target = item[
        "target"
    ]

    track_id = item[
        "track_id"
    ]

    # ------------------------------------------------------
    # Prefer the existing BuildManager if wired.
    # ------------------------------------------------------

    manager = (
        ctx.build_manager
    )

    if manager is not None:

        candidates = (
            "compile_project",
            "build",
            "submit_build",
            "compile",
        )

        for method_name in candidates:

            method = getattr(
                manager,
                method_name,
                None,
            )

            if callable(method):

                try:

                    return method(
                        target,
                        config=item[
                            "config"
                        ],
                        files=item[
                            "source_files"
                        ],
                    )

                except TypeError:

                    try:

                        return method(
                            target
                        )

                    except TypeError:
                        continue

    # ------------------------------------------------------
    # Fallback to native py_seed.
    # ------------------------------------------------------

    return safe_call(
        "compile_project",
        target,
        config=item[
            "config"
        ],
        files=item[
            "source_files"
        ],
    )


# ==========================================================
# PROCESS ONE BUILD
# ==========================================================

def _process_one_build(
    ctx: PySeedContext,
    item: Dict[str, Any],
):

    target = item[
        "target"
    ]

    track_id = item[
        "track_id"
    ]

    channel_id = item[
        "channel_id"
    ]

    state = _governor_state(
        ctx
    )

    item[
        "governor_state"
    ] = state

    # ------------------------------------------------------
    # Do not process background builds under a hard block.
    # Put the work back in the queue.
    # ------------------------------------------------------

    if not _background_allowed(
        ctx
    ):

        item[
            "status"
        ] = "deferred"

        with ctx.build_queue_lock:

            ctx.build_queue.append(
                item
            )

        track(
            "PY-SEED",
            "BUILD_DEFERRED",
            priority="MED",
            note=(
                f"target={target} "
                f"state={state} "
                f"track={track_id}"
            ),
        )

        return False

    item[
        "status"
    ] = "running"

    _publish_event(
        ctx,
        "BUILD_STARTED",
        {
            "target": target,
            "channel_id": channel_id,
            "track_id": track_id,
            "governor_state": state,
        },
        source="py_seed",
        channel="build_manager",
        priority=7,
        track_id=track_id,
    )

    try:

        result = (
            _compile_build_item(
                ctx,
                item,
            )
        )

        item[
            "status"
        ] = "success"

        item[
            "completed_at"
        ] = time.time()

        track(
            "PY-SEED",
            "BUILD_COMPLETE",
            priority="MED",
            note=(
                f"{target} "
                f"channel={channel_id} "
                f"track={track_id}"
            ),
        )

        _publish_event(
            ctx,
            "BUILD_COMPLETE",
            {
                "target": target,
                "status": "success",
                "result": result,
                "channel_id": channel_id,
                "track_id": track_id,
            },
            source="py_seed",
            channel="build_manager",
            priority=10,
            track_id=track_id,
        )

        return True

    except Exception as exc:

        item[
            "status"
        ] = "error"

        item[
            "error"
        ] = str(exc)

        item[
            "completed_at"
        ] = time.time()

        ctx.last_error = str(
            exc
        )

        track(
            "PY-SEED",
            "BUILD_ERROR",
            priority="HIGH",
            note=(
                f"{target} "
                f"track={track_id} "
                f"err={exc}"
            ),
        )

        _publish_event(
            ctx,
            "BUILD_COMPLETE",
            {
                "target": target,
                "status": "error",
                "error": str(exc),
                "channel_id": channel_id,
                "track_id": track_id,
            },
            source="py_seed",
            channel="build_manager",
            priority=10,
            track_id=track_id,
        )

        return False


# ==========================================================
# PROCESS BUILD QUEUE
#
# Synchronous compatibility API.
# It is guarded so two callers cannot process the same queue.
# ==========================================================

def process_build_queue():

    ctx = PySeedContext.get()

    if ctx.shutdown:

        return 0

    # ------------------------------------------------------
    # Only one synchronous processor at a time.
    # ------------------------------------------------------

    with ctx._lock:

        if getattr(
            ctx,
            "_processing_builds",
            False,
        ):

            return 0

        ctx._processing_builds = True

    processed = 0

    try:

        while not ctx.shutdown:

            item = _pop_build_item(
                ctx
            )

            if item is None:
                break

            _process_one_build(
                ctx,
                item,
            )

            processed += 1

            # --------------------------------------------------
            # Yield between builds.
            # --------------------------------------------------

            time.sleep(0)

        return processed

    finally:

        with ctx._lock:

            ctx._processing_builds = False


# ==========================================================
# ASYNC BUILD SUBMISSION
# ==========================================================

async def submit_build_async(
    target,
    config=None,
    source_files=None,
):

    channel_id = submit_build(
        target,
        config=config,
        source_files=source_files,
    )

    ctx = PySeedContext.get()

    # ------------------------------------------------------
    # If a BuildManager is already processing the queue,
    # do not create another worker.
    # ------------------------------------------------------

    _ensure_build_worker(
        ctx
    )

    await asyncio.sleep(
        0
    )

    return channel_id


# ==========================================================
# BUILD WORKER
#
# One worker only.
# No thread-per-build behavior.
# ==========================================================

def _build_worker_loop(
    ctx: PySeedContext,
):

    track(
        "PY-SEED",
        "BUILD_WORKER_ONLINE",
        priority="MED",
    )

    try:

        while not ctx.build_shutdown.is_set():

            # --------------------------------------------------
            # Wait briefly rather than spinning.
            # --------------------------------------------------

            if not ctx.build_queue:

                ctx.build_shutdown.wait(
                    0.5
                )

                continue

            if ctx.shutdown:

                break

            item = _pop_build_item(
                ctx
            )

            if item is None:
                continue

            success = (
                _process_one_build(
                    ctx,
                    item,
                )
            )

            # --------------------------------------------------
            # If deferred, avoid hot looping.
            # --------------------------------------------------

            if not success:

                state = _governor_state(
                    ctx
                )

                if state in (
                    "warning",
                    "block",
                ):

                    ctx.build_shutdown.wait(
                        1.0
                    )

    except Exception as exc:

        ctx.last_error = str(
            exc
        )

        track(
            "PY-SEED",
            "BUILD_WORKER_ERROR",
            priority="HIGH",
            note=str(exc),
        )

    finally:

        with ctx._lock:

            ctx.build_worker_running = False
            ctx.build_worker_thread = None

        track(
            "PY-SEED",
            "BUILD_WORKER_OFFLINE",
            priority="MED",
        )


# ==========================================================
# ENSURE BUILD WORKER
# ==========================================================

def _ensure_build_worker(
    ctx: PySeedContext,
):

    with ctx._lock:

        if ctx.shutdown:
            return False

        if (
            ctx.build_worker_running
            and ctx.build_worker_thread is not None
            and ctx.build_worker_thread.is_alive()
        ):

            return True

        ctx.build_shutdown.clear()

        ctx.build_worker_running = True

        ctx.build_worker_thread = (
            threading.Thread(
                target=_build_worker_loop,
                args=(ctx,),
                name="SEED-PySeed-BuildWorker",
                daemon=True,
            )
        )

        ctx.build_worker_thread.start()

    return True


# ==========================================================
# ASYNC LOOP SUPPORT
#
# This is compatibility support only.
#
# SEED's primary runtime loop should remain owned by the
# system boot/orchestrator.
# ==========================================================

def start_async_loop():

    ctx = PySeedContext.get()

    with ctx._lock:

        if ctx.shutdown:

            raise RuntimeError(
                "PySeedBridge is shutting down"
            )

        if (
            ctx.event_loop is not None
            and ctx.event_loop.is_running()
        ):

            return ctx.event_loop

        # --------------------------------------------------
        # If an externally owned loop exists, do not start
        # another one.
        # --------------------------------------------------

        if (
            ctx.event_loop is not None
            and not ctx.loop_owned
        ):

            try:

                running = (
                    ctx.event_loop.is_running()
                )

                if running:
                    return ctx.event_loop

            except Exception:
                pass

        # --------------------------------------------------
        # Create a private compatibility loop only when
        # explicitly requested.
        # --------------------------------------------------

        loop = (
            ctx.event_loop
        )

        if loop is None:

            loop = (
                asyncio.new_event_loop()
            )

            ctx.event_loop = loop

        ctx.loop_owned = True

    def loop_worker():

        try:

            asyncio.set_event_loop(
                loop
            )

            loop.run_forever()

        except Exception as exc:

            ctx.last_error = str(
                exc
            )

            track(
                "PY-SEED",
                "ASYNC_LOOP_ERROR",
                priority="HIGH",
                note=str(exc),
            )

        finally:

            try:

                asyncio.set_event_loop(
                    None
                )

            except Exception:
                pass

            track(
                "PY-SEED",
                "ASYNC_LOOP_OFFLINE",
                priority="MED",
            )

    thread = threading.Thread(
        target=loop_worker,
        name="SEED-PySeed-AsyncLoop",
        daemon=True,
    )

    ctx.loop_thread = thread

    thread.start()

    track(
        "PY-SEED",
        "ASYNC_LOOP_STARTED",
        priority="MED",
    )

    return loop


# ==========================================================
# SUBMIT COROUTINE TO EXISTING LOOP
# ==========================================================

def submit_async(
    coroutine,
):

    ctx = PySeedContext.get()

    loop = (
        ctx.event_loop
    )

    if loop is None:

        raise RuntimeError(
            "No SEED event loop is registered"
        )

    if loop.is_running():

        return asyncio.run_coroutine_threadsafe(
            coroutine,
            loop,
        )

    raise RuntimeError(
        "Registered SEED event loop "
        "is not running"
    )


# ==========================================================
# STATUS
# ==========================================================

def status():

    ctx = PySeedContext.get()

    with ctx._lock:

        with ctx.build_queue_lock:

            queue_depth = len(
                ctx.build_queue
            )

        return {

            "module": "py_seed",

            "version": "2.0.0",

            "initialized": (
                ctx.initialized
            ),

            "shutdown": (
                ctx.shutdown
            ),

            "bindings": (
                ctx.bindings is not None
            ),

            "binding_source": (
                ctx.binding_source
            ),

            "seed_core": (
                ctx.seed_core is not None
            ),

            "event_bus": (
                ctx.event_bus is not None
            ),

            "build_manager": (
                ctx.build_manager is not None
            ),

            "qbit_dialer": (
                ctx.qbit_dialer is not None
            ),

            "qbit_queue": (
                ctx.qbit_queue is not None
            ),

            "heartbeat": (
                ctx.heartbeat is not None
            ),

            "constraint_guardian": (
                ctx.constraint_guardian is not None
            ),

            "limp_controller": (
                ctx.limp_controller is not None
            ),

            "time_travel_engine": (
                ctx.time_travel_engine is not None
            ),

            "governor_state": (
                _governor_state(ctx)
            ),

            "background_allowed": (
                _background_allowed(ctx)
            ),

            "limp_mode": (
                ctx.limp_mode
            ),

            "build_queue_depth": (
                queue_depth
            ),

            "build_worker_running": (
                ctx.build_worker_running
            ),

            "event_loop_running": (
                ctx.event_loop is not None
                and ctx.event_loop.is_running()
            ),

            "call_count": (
                ctx.call_count
            ),

            "failure_count": (
                ctx.failure_count
            ),

            "last_call": (
                ctx.last_call
            ),

            "last_post": (
                ctx.last_post
            ),

            "last_error": (
                ctx.last_error
            ),
        }


# ==========================================================
# HEALTH CHECK
# ==========================================================

def health_check():

    ctx = PySeedContext.get()

    result = status()

    result[
        "healthy"
    ] = bool(
        ctx.initialized
        and not ctx.shutdown
    )

    # ------------------------------------------------------
    # Binding health is reported separately.
    #
    # The bridge can be boot-safe without native bindings.
    # ------------------------------------------------------

    result[
        "bindings_ready"
    ] = (
        ctx.bindings is not None
    )

    result[
        "runtime_ready"
    ] = bool(
        ctx.seed_core is not None
        or ctx.event_bus is not None
    )

    return result


# ==========================================================
# SET LIMP MODE
# ==========================================================

def set_limp_mode(
    active: bool,
    reason: Optional[str] = None,
):

    ctx = PySeedContext.get()

    with ctx._lock:

        ctx.limp_mode = bool(
            active
        )

    track(
        "PY-SEED",
        (
            "LIMP_MODE_ENTER"
            if active
            else "LIMP_MODE_EXIT"
        ),
        priority="HIGH" if active else "MED",
        note=(
            reason
            or ""
        ),
    )

    _publish_event(
        ctx,
        (
            "PY_SEED_LIMP_ENTER"
            if active
            else "PY_SEED_LIMP_EXIT"
        ),
        {
            "active": bool(
                active
            ),
            "reason": reason,
            "governor_state": (
                _governor_state(ctx)
            ),
        },
        source="py_seed",
        channel="PY_SEED",
        priority=8 if active else 5,
    )


# ==========================================================
# BUILD QUEUE SNAPSHOT
# ==========================================================

def get_build_queue():

    ctx = PySeedContext.get()

    with ctx.build_queue_lock:

        return deepcopy(
            list(
                ctx.build_queue
            )
        )


# ==========================================================
# CLEAR BUILD QUEUE
#
# Deliberately explicit; never called automatically by
# shutdown/recovery.
# ==========================================================

def clear_build_queue():

    ctx = PySeedContext.get()

    with ctx.build_queue_lock:

        count = len(
            ctx.build_queue
        )

        ctx.build_queue.clear()

    track(
        "PY-SEED",
        "BUILD_QUEUE_CLEARED",
        priority="MED",
        note=f"count={count}",
    )

    return count


# ==========================================================
# SHUTDOWN
#
# IMPORTANT:
#   Shutdown is idempotent.
#   It does NOT destroy EventBus/Qbit/Heartbeat.
#   It only stops resources owned by this bridge.
# ==========================================================

def shutdown(
    timeout: float = 2.0,
):

    ctx = PySeedContext.get()

    with ctx._lock:

        if ctx.shutdown:

            return True

        ctx.shutdown = True

    track(
        "PY-SEED",
        "SHUTDOWN_BEGIN",
        priority="MED",
    )

    # ------------------------------------------------------
    # Stop build worker.
    # ------------------------------------------------------

    try:

        ctx.build_shutdown.set()

        worker = (
            ctx.build_worker_thread
        )

        if (
            worker is not None
            and worker.is_alive()
            and worker is not threading.current_thread()
        ):

            worker.join(
                timeout=max(
                    float(timeout),
                    0.1,
                )
            )

    except Exception as exc:

        logger.debug(
            "[PySeedBridge] "
            f"Build worker shutdown: {exc}"
        )

    # ------------------------------------------------------
    # Stop ONLY a loop owned by this bridge.
    #
    # Never stop SEED's external loop.
    # ------------------------------------------------------

    try:

        loop = (
            ctx.event_loop
        )

        if (
            ctx.loop_owned
            and loop is not None
            and loop.is_running()
        ):

            loop.call_soon_threadsafe(
                loop.stop
            )

            thread = (
                ctx.loop_thread
            )

            if (
                thread is not None
                and thread.is_alive()
                and thread is not threading.current_thread()
            ):

                thread.join(
                    timeout=max(
                        float(timeout),
                        0.1,
                    )
                )

    except Exception as exc:

        logger.debug(
            "[PySeedBridge] "
            f"Async loop shutdown: {exc}"
        )

    with ctx._lock:

        ctx.build_worker_running = False

        ctx.loop_thread = None

        if ctx.loop_owned:

            ctx.event_loop = None

        ctx.loop_owned = False

    track(
        "PY-SEED",
        "SHUTDOWN_COMPLETE",
        priority="MED",
    )

    return True


# ==========================================================
# RESET
#
# Intended for controlled development/testing only.
# Does not automatically destroy native bindings.
# ==========================================================

def reset(
    clear_queue: bool = False,
):

    ctx = PySeedContext.get()

    shutdown()

    with ctx._lock:

        ctx.initialized = False
        ctx.shutdown = False

        ctx.last_error = None
        ctx.last_call = None
        ctx.last_post = None

        ctx.call_count = 0
        ctx.failure_count = 0

        ctx.limp_mode = False

        if clear_queue:

            with ctx.build_queue_lock:

                ctx.build_queue.clear()

    track(
        "PY-SEED",
        "RESET_COMPLETE",
        priority="MED",
    )

    return ctx


# ==========================================================
# MODULE API
# ==========================================================

__all__ = [

    # Core
    "PySeedContext",
    "get_context",
    "initialize",
    "link_runtime",

    # Bindings
    "get_py_seed",
    "register_bindings",

    # Commands
    "cli_command",
    "cli_command_async",

    # Native calls
    "safe_call",

    # Build
    "submit_build",
    "submit_build_async",
    "process_build_queue",
    "get_build_queue",
    "clear_build_queue",

    # Async
    "start_async_loop",
    "submit_async",

    # Governance
    "set_limp_mode",

    # Diagnostics
    "status",
    "health_check",

    # Lifecycle
    "shutdown",
    "reset",
]


# ==========================================================
# END OF FILE
#
# SEED AI OS — PY-SEED BRIDGE 2.0.0
#
# Architectural rule:
#
#   py_seed ADAPTS.
#   py_seed DOES NOT GOVERN.
#   py_seed DOES NOT COMMAND THE HEARTBEAT.
#   py_seed DOES NOT REPLACE QbitDialer.
#   py_seed DOES NOT CREATE ANOTHER Qbit QUEUE.
#
# It connects the Python runtime to native/build services
# while preserving SEED's existing control architecture.
# ==========================================================