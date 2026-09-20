# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\__init__.py
#
# SEED AI OS — CORE PACKAGE / KERNEL COORDINATION BOUNDARY
#
# VERSION: 5.0.0
#
# PURPOSE
# -------
# Core is the package-level coordination and discovery boundary for
# SEED's core subsystem.
#
# Core:
#
#   - registers itself with SRegistry
#   - exposes package/component metadata
#   - discovers core packages without importing/starting them
#   - maintains the existing module registry
#   - tracks module health / active / activated state
#   - tracks boot cycles and lifecycle state
#   - provides read/write runtime-state boundaries
#   - provides Qbit / QbitDialer connection boundaries
#   - provides command-pipeline connection boundaries
#   - provides EventBus connection boundaries
#   - provides Neural Node Network connection boundaries
#   - provides TrackID / ChannelID context
#   - provides node status/control boundaries
#   - provides package diagnostics for DevHUD / runtime / registry
#
# OWNERSHIP
# ---------
# Core DOES NOT own:
#
#   - Qbit
#   - QbitDialer
#   - QbitQueueLoop
#   - command execution
#   - EventBus
#   - Heartbeat
#   - Neural Node runtime
#   - TrackSystem
#   - TrackID manager
#   - ChannelID manager
#   - SRegistry
#   - authoritative runtime loop
#
# The authoritative runtime supplies references/callbacks.
#
# IMPORTANT
# ---------
# Importing this package MUST NOT:
#
#   - construct Qbit
#   - construct QbitDialer
#   - construct queues
#   - construct EventBus
#   - construct neural nodes
#   - create an asyncio event loop
#   - start a health thread
#   - start runtime loops
#   - execute commands
#   - connect external services
#
# Explicit runtime calls may activate monitoring/control after boot.
#
# ARCHITECTURE
# ------------
#
#                         SRegistry
#                             |
#                             v
#                     +---------------+
#                     |  seed.core    |
#                     | package       |
#                     +---------------+
#                       /    |    \
#                      /     |     \
#               discovery   status   metadata
#                    |        |
#                    v        v
#              core packages  runtime
#                                |
#             +------------------+------------------+
#             |                  |                  |
#             v                  v                  v
#          QbitDialer         EventBus        Neural Nodes
#             |
#             v
#       Command Pipeline
#
# TrackID / ChannelID provide identity/context.
#
# Core coordinates.
# The authoritative runtime executes.
# =====================================================================

from __future__ import annotations

import inspect
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


# =====================================================================
# 0. PACKAGE LOGGER
# =====================================================================

logger = logging.getLogger("SEEDCoreKernelInit")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[SEED-Core-KERNEL] %(asctime)s | "
            "%(levelname)s | %(message)s"
        )
    )
    logger.addHandler(handler)

logger.setLevel(logging.INFO)


# =====================================================================
# 1. PACKAGE IDENTITY
# =====================================================================

__version__ = "5.0.0"

PACKAGE_NAME = "seed.core"
PACKAGE_ROLE = "core-kernel-coordination"

SEED_ROOT = Path("C:/SEED_ROOT")
SEED_CORE_PATH = SEED_ROOT / "seed" / "core"

PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_FILE = Path(__file__).resolve()


# =====================================================================
# 2. RUNTIME STATE PATHS
#
# Preserve the existing state locations.
# =====================================================================

RUNTIME_STATE_DIR = (
    SEED_ROOT / "seed" / "qbit_states"
)

SYSTEM_STATE_FILE = (
    SEED_ROOT / "seed" / "runtime_state.json"
)

STATUS_FILE = (
    SEED_CORE_PATH / "core_status.json"
)

MODULE_STATE_FILE = (
    SEED_CORE_PATH / "module_states.json"
)

DISCOVERY_STATE_FILE = (
    SEED_CORE_PATH / "core_discovery.json"
)


# =====================================================================
# 3. DIRECTORY PREPARATION
#
# This is filesystem preparation only.
# No modules are imported or started.
# =====================================================================

try:

    RUNTIME_STATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SEED_CORE_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

except Exception as exc:

    logger.warning(
        "[SEED-CORE] State directory preparation failed: %s",
        exc,
    )


# =====================================================================
# 4. RUNTIME CONNECTION STATE
#
# REFERENCES ONLY.
#
# These are supplied by the authoritative runtime.
# =====================================================================

_runtime_lock = threading.RLock()

_qbit: Any = None
_qbit_dialer: Any = None

_command_handler: Optional[Callable] = None
_control_handler: Optional[Callable] = None

_event_bus: Any = None
_event_handler: Optional[Callable] = None

_neural_network: Any = None
_neural_node_handler: Optional[Callable] = None

_health_monitor: Any = None
_track_id_manager: Any = None
_channel_id_manager: Any = None

_sregistry: Any = None

_runtime: Any = None

_runtime_ready = False
_runtime_active = False


# =====================================================================
# 5. MODULE REGISTRY
#
# Preserve the original registry concept.
#
# The registry contains REFERENCES and metadata.
#
# It does not construct modules.
# =====================================================================

_module_registry: dict[str, dict[str, Any]] = {}


# =====================================================================
# 6. CORE CAPABILITIES
# =====================================================================

_CORE_CAPABILITIES = (
    "core_package",
    "sregistry_registration",
    "package_discovery",
    "component_discovery",
    "module_registry",
    "module_status",
    "module_health",
    "module_activation",
    "module_deactivation",
    "module_start",
    "module_stop",
    "runtime_state_read",
    "runtime_state_write",
    "qbit_connection",
    "qbit_dialer_connection",
    "command_pipeline_connection",
    "event_bus_connection",
    "neural_node_network_connection",
    "track_id_context",
    "channel_id_context",
    "node_control_boundary",
    "node_status_boundary",
    "runtime_diagnostics",
)


def get_capabilities() -> list[str]:

    return list(
        _CORE_CAPABILITIES
    )


# =====================================================================
# 7. TIME HELPERS
# =====================================================================

def _utc_now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


def _timestamp() -> float:

    return time.time()


# =====================================================================
# 8. SAFE OBJECT NAME
# =====================================================================

def _safe_name(
    value: Any,
) -> Optional[str]:

    if value is None:
        return None

    try:

        return getattr(
            value,
            "__qualname__",
            getattr(
                value,
                "__name__",
                type(value).__name__,
            ),
        )

    except Exception:

        return type(value).__name__


# =====================================================================
# 9. KERNEL CONTEXT
# =====================================================================

def load_kernel_context() -> dict:

    try:

        if SYSTEM_STATE_FILE.exists():

            with SYSTEM_STATE_FILE.open(
                "r",
                encoding="utf-8",
            ) as f:

                data = json.load(f)

                if isinstance(
                    data,
                    dict,
                ):
                    return data

        logger.warning(
            "[SEED-KERNEL] Kernel context missing: %s",
            SYSTEM_STATE_FILE,
        )

        return {
            "_unknown_kernel_state": True,
        }

    except Exception as exc:

        logger.error(
            "[SEED-KERNEL] Failed to load kernel context: %s",
            exc,
        )

        return {
            "_load_error": str(exc),
        }


# =====================================================================
# 10. RUNTIME STATE WRITE
# =====================================================================

def save_runtime_state(
    track_id: str,
    data: dict,
) -> bool:

    if not track_id:
        return False

    if not isinstance(
        data,
        dict,
    ):
        return False

    try:

        RUNTIME_STATE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        target = (
            RUNTIME_STATE_DIR
            / f"{track_id}.json"
        )

        with target.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                default=str,
            )

        return True

    except Exception as exc:

        logger.warning(
            "[SEED-KERNEL] Failed to save runtime state "
            "%s: %s",
            track_id,
            exc,
        )

        return False


# =====================================================================
# 11. RUNTIME STATE READ
# =====================================================================

def load_runtime_state(
    track_id: str,
) -> Optional[dict]:

    if not track_id:
        return None

    target = (
        RUNTIME_STATE_DIR
        / f"{track_id}.json"
    )

    try:

        if not target.exists():
            return None

        with target.open(
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

        return (
            data
            if isinstance(data, dict)
            else None
        )

    except Exception as exc:

        logger.warning(
            "[SEED-KERNEL] Failed to read runtime state "
            "%s: %s",
            track_id,
            exc,
        )

        return None


# =====================================================================
# 12. TRACK / CHANNEL CONTEXT
# =====================================================================

def _read_context_value(
    manager: Any,
    names: tuple[str, ...],
) -> Any:

    if manager is None:
        return None

    for name in names:

        try:

            value = getattr(
                manager,
                name,
                None,
            )

            if callable(value):

                result = value()

                if inspect.isawaitable(
                    result
                ):
                    continue

                return result

            if value is not None:
                return value

        except Exception:
            continue

    return None


def get_tracking_context() -> dict:

    with _runtime_lock:

        track_manager = (
            _track_id_manager
        )

        channel_manager = (
            _channel_id_manager
        )

    track_id = _read_context_value(
        track_manager,
        (
            "current_track_id",
            "get_current_track_id",
            "track_id",
            "current_id",
        ),
    )

    channel_id = _read_context_value(
        channel_manager,
        (
            "current_channel_id",
            "get_current_channel_id",
            "channel_id",
            "current_id",
        ),
    )

    return {
        "track_id": track_id,
        "channel_id": channel_id,
        "track_id_manager": (
            track_manager is not None
        ),
        "channel_id_manager": (
            channel_manager is not None
        ),
    }


# =====================================================================
# 13. MODULE REGISTRATION
#
# PRESERVED:
#
#   register_module(name, module_obj, auto_start=False)
#
# Nothing is constructed here.
# =====================================================================

def register_module(
    name: str,
    module_obj: Any,
    auto_start: bool = False,
    *,
    role: Optional[str] = None,
    capabilities: Optional[list[str]] = None,
    metadata: Optional[dict] = None,
) -> dict:

    if not name:
        raise ValueError(
            "module name is required"
        )

    with _runtime_lock:

        existing = _module_registry.get(
            name
        )

        if existing is not None:

            # Preserve the authoritative existing instance.
            if (
                existing.get("instance")
                is not module_obj
                and module_obj is not None
            ):

                logger.warning(
                    "[SEED-KERNEL] Module %s already registered; "
                    "existing instance preserved.",
                    name,
                )

            return existing

        record = {
            "name": name,
            "instance": module_obj,
            "health": (
                module_obj is not None
            ),
            "active": bool(
                auto_start
            ),
            "activated": False,
            "state": (
                "ACTIVE"
                if auto_start
                else "REGISTERED"
            ),
            "last_cycle": _timestamp(),
            "cycle_interval": 0.5,
            "boot_cycle": 0,
            "last_boot": None,
            "last_start": None,
            "last_stop": None,
            "last_error": None,
            "role": role,
            "capabilities": list(
                capabilities or []
            ),
            "metadata": dict(
                metadata or {}
            ),
        }

        _module_registry[name] = record

    logger.info(
        "[SEED-KERNEL] Module registered: %s",
        name,
    )

    return record


# =====================================================================
# 14. MODULE LOOKUP
# =====================================================================

def get_module(
    name: str,
) -> Optional[dict]:

    with _runtime_lock:

        return _module_registry.get(
            name
        )


def get_module_instance(
    name: str,
) -> Any:

    record = get_module(
        name
    )

    if not record:
        return None

    return record.get(
        "instance"
    )


def list_modules() -> list[str]:

    with _runtime_lock:

        return list(
            _module_registry.keys()
        )


# =====================================================================
# 15. MODULE HEALTH CYCLE
#
# This performs ONE health observation.
#
# It does not create a health-monitor thread.
# =====================================================================

def module_health_cycle(
    name: str,
) -> bool:

    with _runtime_lock:

        mod = _module_registry.get(
            name
        )

    if mod is None:
        return False

    instance = mod.get(
        "instance"
    )

    healthy = (
        instance is not None
    )

    if instance is not None:

        for method_name in (
            "health_check",
            "check_health",
            "is_healthy",
            "get_health",
        ):

            try:

                method = getattr(
                    instance,
                    method_name,
                    None,
                )

                if callable(method):

                    result = method()

                    if inspect.isawaitable(
                        result
                    ):
                        continue

                    healthy = bool(
                        result
                    )

                    break

            except Exception as exc:

                mod["last_error"] = str(
                    exc
                )

                healthy = False

    with _runtime_lock:

        mod["last_cycle"] = _timestamp()
        mod["health"] = healthy
        mod["HealthMonitor"] = healthy

        if not healthy:
            mod["state"] = "DEGRADED"

        elif mod.get("active"):
            mod["state"] = "ACTIVE"

        else:
            mod["state"] = "READY"

    return healthy


# =====================================================================
# 16. MODULE BOOT
#
# Lifecycle bookkeeping + optional existing lifecycle interface.
#
# It does not instantiate anything.
# =====================================================================

def module_boot(
    name: str,
) -> bool:

    with _runtime_lock:

        mod = _module_registry.get(
            name
        )

    if mod is None:
        return False

    instance = mod.get(
        "instance"
    )

    try:

        lifecycle = None

        for method_name in (
            "boot",
            "initialize",
            "on_boot",
        ):

            method = getattr(
                instance,
                method_name,
                None,
            )

            if callable(method):

                lifecycle = method()
                break

        if inspect.isawaitable(
            lifecycle
        ):
            logger.warning(
                "[SEED-KERNEL] Async boot method on %s "
                "requires authoritative async runtime.",
                name,
            )

            return False

        with _runtime_lock:

            mod["boot_cycle"] += 1
            mod["last_boot"] = _timestamp()
            mod["activated"] = True
            mod["active"] = True
            mod["state"] = "ACTIVE"
            mod["last_error"] = None

        logger.info(
            "[SEED-KERNEL] Module %s booted | cycle=%s",
            name,
            mod["boot_cycle"],
        )

        return True

    except Exception as exc:

        with _runtime_lock:

            mod["last_error"] = str(
                exc
            )
            mod["state"] = "ERROR"

        logger.error(
            "[SEED-KERNEL] Module %s boot failed: %s",
            name,
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# 17. MODULE START
# =====================================================================

def module_start(
    name: str,
) -> bool:

    mod = get_module(
        name
    )

    if mod is None:
        return False

    instance = mod.get(
        "instance"
    )

    try:

        method = None

        for method_name in (
            "start",
            "run",
            "activate",
            "enable",
        ):

            candidate = getattr(
                instance,
                method_name,
                None,
            )

            if callable(candidate):
                method = candidate
                break

        if method is not None:

            result = method()

            if inspect.isawaitable(
                result
            ):
                logger.warning(
                    "[SEED-KERNEL] Async start for %s "
                    "requires authoritative async runtime.",
                    name,
                )

                return False

            if result is False:
                return False

        with _runtime_lock:

            mod["active"] = True
            mod["activated"] = True
            mod["state"] = "ACTIVE"
            mod["last_start"] = _timestamp()
            mod["last_error"] = None

        return True

    except Exception as exc:

        with _runtime_lock:

            mod["last_error"] = str(
                exc
            )
            mod["state"] = "ERROR"

        logger.error(
            "[SEED-KERNEL] Module %s start failed: %s",
            name,
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# 18. MODULE STOP
# =====================================================================

def module_stop(
    name: str,
) -> bool:

    mod = get_module(
        name
    )

    if mod is None:
        return False

    instance = mod.get(
        "instance"
    )

    try:

        method = None

        for method_name in (
            "stop",
            "shutdown",
            "deactivate",
            "disable",
        ):

            candidate = getattr(
                instance,
                method_name,
                None,
            )

            if callable(candidate):
                method = candidate
                break

        if method is not None:

            result = method()

            if inspect.isawaitable(
                result
            ):
                logger.warning(
                    "[SEED-KERNEL] Async stop for %s "
                    "requires authoritative async runtime.",
                    name,
                )

                return False

            if result is False:
                return False

        with _runtime_lock:

            mod["active"] = False
            mod["state"] = "STOPPED"
            mod["last_stop"] = _timestamp()

        return True

    except Exception as exc:

        with _runtime_lock:

            mod["last_error"] = str(
                exc
            )
            mod["state"] = "ERROR"

        logger.error(
            "[SEED-KERNEL] Module %s stop failed: %s",
            name,
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# 19. MODULE ACTIVATE / DEACTIVATE
# =====================================================================

def activate_module(
    name: str,
) -> bool:

    return module_start(
        name
    )


def deactivate_module(
    name: str,
) -> bool:

    return module_stop(
        name
    )


# =====================================================================
# 20. RUNTIME CONNECTION ATTACHMENT
# =====================================================================

def attach_qbit(
    qbit: Any,
) -> Any:

    global _qbit

    with _runtime_lock:
        _qbit = qbit

    logger.info(
        "[SEED-CORE] Qbit connected | type=%s",
        type(qbit).__name__,
    )

    return qbit


def attach_qbit_dialer(
    qbit_dialer: Any,
) -> Any:

    global _qbit_dialer

    with _runtime_lock:
        _qbit_dialer = qbit_dialer

    logger.info(
        "[SEED-CORE] QbitDialer connected | type=%s",
        type(qbit_dialer).__name__,
    )

    return qbit_dialer


def attach_command_handler(
    handler: Optional[Callable],
) -> None:

    global _command_handler

    with _runtime_lock:
        _command_handler = handler

    logger.info(
        "[SEED-CORE] Command boundary %s",
        "connected" if handler else "detached",
    )


def attach_control_handler(
    handler: Optional[Callable],
) -> None:

    global _control_handler

    with _runtime_lock:
        _control_handler = handler

    logger.info(
        "[SEED-CORE] Control boundary %s",
        "connected" if handler else "detached",
    )


def attach_event_bus(
    event_bus: Any,
) -> Any:

    global _event_bus

    with _runtime_lock:
        _event_bus = event_bus

    logger.info(
        "[SEED-CORE] EventBus connected | type=%s",
        type(event_bus).__name__,
    )

    return event_bus


def attach_event_handler(
    handler: Optional[Callable],
) -> None:

    global _event_handler

    with _runtime_lock:
        _event_handler = handler


def attach_neural_network(
    network: Any,
) -> Any:

    global _neural_network

    with _runtime_lock:
        _neural_network = network

    logger.info(
        "[SEED-CORE] Neural Node Network connected | type=%s",
        type(network).__name__,
    )

    return network


def attach_neural_node_handler(
    handler: Optional[Callable],
) -> None:

    global _neural_node_handler

    with _runtime_lock:
        _neural_node_handler = handler


def attach_health_monitor(
    monitor: Any,
) -> Any:

    global _health_monitor

    with _runtime_lock:
        _health_monitor = monitor

    logger.info(
        "[SEED-CORE] HealthMonitor connected | type=%s",
        type(monitor).__name__,
    )

    return monitor


def attach_track_id_manager(
    manager: Any,
) -> Any:

    global _track_id_manager

    with _runtime_lock:
        _track_id_manager = manager

    return manager


def attach_channel_id_manager(
    manager: Any,
) -> Any:

    global _channel_id_manager

    with _runtime_lock:
        _channel_id_manager = manager

    return manager


def attach_sregistry(
    registry: Any,
) -> Any:

    global _sregistry

    with _runtime_lock:
        _sregistry = registry

    return registry


def attach_runtime(
    runtime: Any,
) -> Any:

    global _runtime
    global _runtime_ready
    global _runtime_active

    with _runtime_lock:

        _runtime = runtime
        _runtime_ready = runtime is not None

    return runtime


# =====================================================================
# 21. MASTER RUNTIME BINDING
# =====================================================================

def bind_runtime(
    *,
    qbit: Any = None,
    qbit_dialer: Any = None,
    command_handler: Optional[Callable] = None,
    control_handler: Optional[Callable] = None,
    event_bus: Any = None,
    event_handler: Optional[Callable] = None,
    neural_network: Any = None,
    neural_node_handler: Optional[Callable] = None,
    health_monitor: Any = None,
    track_id_manager: Any = None,
    channel_id_manager: Any = None,
    sregistry: Any = None,
    runtime: Any = None,
) -> dict:

    if qbit is not None:
        attach_qbit(qbit)

    if qbit_dialer is not None:
        attach_qbit_dialer(qbit_dialer)

    if command_handler is not None:
        attach_command_handler(
            command_handler
        )

    if control_handler is not None:
        attach_control_handler(
            control_handler
        )

    if event_bus is not None:
        attach_event_bus(
            event_bus
        )

    if event_handler is not None:
        attach_event_handler(
            event_handler
        )

    if neural_network is not None:
        attach_neural_network(
            neural_network
        )

    if neural_node_handler is not None:
        attach_neural_node_handler(
            neural_node_handler
        )

    if health_monitor is not None:
        attach_health_monitor(
            health_monitor
        )

    if track_id_manager is not None:
        attach_track_id_manager(
            track_id_manager
        )

    if channel_id_manager is not None:
        attach_channel_id_manager(
            channel_id_manager
        )

    if sregistry is not None:
        attach_sregistry(
            sregistry
        )

    if runtime is not None:
        attach_runtime(
            runtime
        )

    return get_runtime_connections()


# =====================================================================
# 22. RUNTIME CONNECTION STATUS
# =====================================================================

def get_runtime_connections() -> dict:

    with _runtime_lock:

        return {
            "qbit": _qbit is not None,
            "qbit_dialer": (
                _qbit_dialer is not None
            ),
            "command_handler": (
                _command_handler is not None
            ),
            "control_handler": (
                _control_handler is not None
            ),
            "event_bus": (
                _event_bus is not None
            ),
            "event_handler": (
                _event_handler is not None
            ),
            "neural_network": (
                _neural_network is not None
            ),
            "neural_node_handler": (
                _neural_node_handler is not None
            ),
            "health_monitor": (
                _health_monitor is not None
            ),
            "track_id_manager": (
                _track_id_manager is not None
            ),
            "channel_id_manager": (
                _channel_id_manager is not None
            ),
            "sregistry": (
                _sregistry is not None
            ),
            "runtime": (
                _runtime is not None
            ),
        }


# =====================================================================
# 23. COMMAND PIPELINE
#
# QbitDialer remains the preferred authoritative command path.
#
# Core does NOT execute the command itself.
# =====================================================================

def submit_command(
    command: Any,
) -> bool:

    with _runtime_lock:

        dialer = _qbit_dialer
        handler = _command_handler

    # -------------------------------------------------------------
    # QbitDialer is preferred.
    # -------------------------------------------------------------

    if dialer is not None:

        for method_name in (
            "submit_command",
            "receive_command",
            "handle_command",
            "process_command",
            "dispatch_command",
            "enqueue_command",
        ):

            method = getattr(
                dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    command
                )

                if inspect.isawaitable(
                    result
                ):
                    logger.warning(
                        "[SEED-CORE] Async QbitDialer command "
                        "requires authoritative async runtime."
                    )
                    return False

                return result is not False

            except Exception as exc:

                logger.error(
                    "[SEED-CORE] QbitDialer command handoff "
                    "failed via %s: %s",
                    method_name,
                    exc,
                    exc_info=True,
                )

                return False

    # -------------------------------------------------------------
    # Fallback to the authoritative command callback.
    # -------------------------------------------------------------

    if callable(handler):

        try:

            result = handler(
                command
            )

            if inspect.isawaitable(
                result
            ):
                logger.warning(
                    "[SEED-CORE] Async command handler requires "
                    "authoritative async runtime."
                )
                return False

            return result is not False

        except Exception as exc:

            logger.error(
                "[SEED-CORE] Command handoff failed: %s",
                exc,
                exc_info=True,
            )

            return False

    logger.debug(
        "[SEED-CORE] Command skipped: "
        "QbitDialer/command boundary unavailable"
    )

    return False


# =====================================================================
# 24. CONTROL PIPELINE
#
# Used for:
#
#   ON
#   OFF
#   START
#   STOP
#   ACTIVATE
#   DEACTIVATE
#
# Core provides the boundary.
# The authoritative command/control layer determines semantics.
# =====================================================================

def control(
    action: str,
    target: Any = None,
    *,
    payload: Any = None,
) -> bool:

    request = {
        "action": str(
            action
        ).upper(),
        "target": target,
        "payload": payload,
        "timestamp": _utc_now(),
        "source": PACKAGE_NAME,
        "tracking": get_tracking_context(),
    }

    with _runtime_lock:

        handler = _control_handler

    if callable(handler):

        try:

            result = handler(
                request
            )

            if inspect.isawaitable(
                result
            ):
                logger.warning(
                    "[SEED-CORE] Async control handler requires "
                    "authoritative async runtime."
                )
                return False

            return result is not False

        except Exception as exc:

            logger.error(
                "[SEED-CORE] Control handoff failed: %s",
                exc,
                exc_info=True,
            )

            return False

    # -------------------------------------------------------------
    # If the target is a registered local module, lifecycle
    # bookkeeping may be performed directly.
    #
    # This is NOT command execution.
    # -------------------------------------------------------------

    if isinstance(
        target,
        str,
    ):

        action_upper = request[
            "action"
        ]

        if action_upper in {
            "START",
            "RUN",
            "ON",
            "ACTIVATE",
        }:

            return module_start(
                target
            )

        if action_upper in {
            "STOP",
            "OFF",
            "DEACTIVATE",
        }:

            return module_stop(
                target
            )

    return False


# =====================================================================
# 25. EVENT BUS HANDOFF
# =====================================================================

def emit_event(
    event: str,
    payload: Any = None,
) -> bool:

    envelope = {
        "source": PACKAGE_NAME,
        "event": event,
        "timestamp": _utc_now(),
        "payload": payload,
        "tracking": get_tracking_context(),
    }

    with _runtime_lock:

        event_bus = _event_bus
        handler = _event_handler

    # -------------------------------------------------------------
    # Existing EventBus object.
    # -------------------------------------------------------------

    if event_bus is not None:

        for method_name in (
            "emit",
            "publish",
            "dispatch",
            "send",
            "post",
        ):

            method = getattr(
                event_bus,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    event,
                    envelope,
                )

                if inspect.isawaitable(
                    result
                ):
                    logger.warning(
                        "[SEED-CORE] Async EventBus operation "
                        "requires authoritative async runtime."
                    )
                    return False

                return result is not False

            except TypeError:

                try:

                    result = method(
                        envelope
                    )

                    if inspect.isawaitable(
                        result
                    ):
                        return False

                    return result is not False

                except Exception:
                    continue

            except Exception as exc:

                logger.error(
                    "[SEED-CORE] EventBus handoff failed: %s",
                    exc,
                    exc_info=True,
                )

                return False

    # -------------------------------------------------------------
    # Existing event callback.
    # -------------------------------------------------------------

    if callable(handler):

        try:

            result = handler(
                envelope
            )

            if inspect.isawaitable(
                result
            ):
                return False

            return result is not False

        except Exception as exc:

            logger.error(
                "[SEED-CORE] Event handler failed: %s",
                exc,
                exc_info=True,
            )

    return False


# =====================================================================
# 26. QBIT HANDOFF
#
# QbitDialer remains preferred.
# =====================================================================

def emit_to_qbit(
    payload: Any,
) -> bool:

    with _runtime_lock:

        dialer = _qbit_dialer
        qbit = _qbit

    target = (
        dialer
        if dialer is not None
        else qbit
    )

    if target is None:
        return False

    envelope = {
        "source": PACKAGE_NAME,
        "event": "CORE_QBIT_DATA",
        "timestamp": _utc_now(),
        "payload": payload,
        "tracking": get_tracking_context(),
    }

    for method_name in (
        "receive_core_data",
        "receive_relay_data",
        "handle_core_data",
        "handle_relay_data",
        "receive_data",
        "ingest",
        "submit",
        "enqueue",
    ):

        method = getattr(
            target,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:

            result = method(
                envelope
            )

            if inspect.isawaitable(
                result
            ):
                return False

            return result is not False

        except Exception as exc:

            logger.error(
                "[SEED-CORE] Qbit handoff failed via %s: %s",
                method_name,
                exc,
                exc_info=True,
            )

            return False

    return False


# =====================================================================
# 27. NEURAL NODE NETWORK
# =====================================================================

def emit_to_neural_network(
    event: str,
    payload: Any = None,
) -> bool:

    envelope = {
        "source": PACKAGE_NAME,
        "event": event,
        "timestamp": _utc_now(),
        "payload": payload,
        "tracking": get_tracking_context(),
    }

    with _runtime_lock:

        network = _neural_network
        handler = _neural_node_handler

    if network is not None:

        for method_name in (
            "emit",
            "publish",
            "dispatch",
            "route",
            "send",
            "receive",
            "process",
        ):

            method = getattr(
                network,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    event,
                    envelope,
                )

                if inspect.isawaitable(
                    result
                ):
                    return False

                return result is not False

            except TypeError:

                try:

                    result = method(
                        envelope
                    )

                    if inspect.isawaitable(
                        result
                    ):
                        return False

                    return result is not False

                except Exception:
                    continue

            except Exception as exc:

                logger.error(
                    "[SEED-CORE] Neural network handoff "
                    "failed: %s",
                    exc,
                    exc_info=True,
                )

                return False

    if callable(handler):

        try:

            result = handler(
                envelope
            )

            if inspect.isawaitable(
                result
            ):
                return False

            return result is not False

        except Exception as exc:

            logger.error(
                "[SEED-CORE] Neural node handler failed: %s",
                exc,
                exc_info=True,
            )

    return False


# =====================================================================
# 28. NODE STATUS
# =====================================================================

def get_node_status(
    name: str,
) -> dict:

    module = get_module(
        name
    )

    if module is not None:

        return {
            "name": name,
            "exists": True,
            "state": module.get(
                "state"
            ),
            "health": module.get(
                "health",
                False,
            ),
            "active": module.get(
                "active",
                False,
            ),
            "activated": module.get(
                "activated",
                False,
            ),
            "boot_cycle": module.get(
                "boot_cycle",
                0,
            ),
            "last_boot": module.get(
                "last_boot"
            ),
            "last_cycle": module.get(
                "last_cycle"
            ),
            "last_start": module.get(
                "last_start"
            ),
            "last_stop": module.get(
                "last_stop"
            ),
            "last_error": module.get(
                "last_error"
            ),
        }

    return {
        "name": name,
        "exists": False,
        "state": "UNKNOWN",
        "health": False,
        "active": False,
        "activated": False,
    }


# =====================================================================
# 29. NODE CONTROL
# =====================================================================

def control_node(
    name: str,
    action: str,
    *,
    payload: Any = None,
) -> bool:

    return control(
        action,
        name,
        payload=payload,
    )


# =====================================================================
# 30. PACKAGE DISCOVERY
#
# Discovery is filesystem metadata discovery.
#
# It does NOT import discovered modules.
# It does NOT instantiate anything.
# =====================================================================

def discover_packages(
    root: Optional[Path] = None,
) -> list[dict]:

    discovery_root = (
        Path(root)
        if root is not None
        else PACKAGE_ROOT
    )

    results: list[dict] = []

    try:

        for child in sorted(
            discovery_root.iterdir(),
            key=lambda p: p.name.lower(),
        ):

            if not child.is_dir():
                continue

            if child.name.startswith(
                "_"
            ):
                continue

            init_file = (
                child / "__init__.py"
            )

            if not init_file.exists():
                continue

            results.append(
                {
                    "name": child.name,
                    "package": (
                        f"{PACKAGE_NAME}.{child.name}"
                    ),
                    "path": str(child),
                    "init_file": str(
                        init_file
                    ),
                    "registered": False,
                    "loaded": False,
                    "runtime_owned": False,
                }
            )

    except Exception as exc:

        logger.warning(
            "[SEED-CORE] Package discovery failed: %s",
            exc,
        )

    return results


# =====================================================================
# 31. COMPONENT DISCOVERY
#
# Finds Python files without importing them.
# =====================================================================

def discover_components(
    root: Optional[Path] = None,
) -> list[dict]:

    discovery_root = (
        Path(root)
        if root is not None
        else PACKAGE_ROOT
    )

    results: list[dict] = []

    try:

        for py_file in sorted(
            discovery_root.rglob("*.py"),
            key=lambda p: str(p).lower(),
        ):

            if py_file.name == "__init__.py":
                continue

            if "__pycache__" in py_file.parts:
                continue

            try:

                relative = (
                    py_file.relative_to(
                        discovery_root
                    )
                )

            except ValueError:

                continue

            results.append(
                {
                    "name": py_file.stem,
                    "file": str(py_file),
                    "relative": str(
                        relative
                    ),
                    "package": (
                        ".".join(
                            relative.with_suffix(
                                ""
                            ).parts
                        )
                    ),
                    "loaded": False,
                }
            )

    except Exception as exc:

        logger.warning(
            "[SEED-CORE] Component discovery failed: %s",
            exc,
        )

    return results


# =====================================================================
# 32. SAVE DISCOVERY
# =====================================================================

def save_discovery_state() -> bool:

    data = {
        "package": PACKAGE_NAME,
        "version": __version__,
        "timestamp": _utc_now(),
        "packages": discover_packages(),
        "components": discover_components(),
    }

    try:

        with DISCOVERY_STATE_FILE.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                default=str,
            )

        return True

    except Exception as exc:

        logger.warning(
            "[SEED-CORE] Failed to save discovery state: %s",
            exc,
        )

        return False


# =====================================================================
# 33. MODULE REGISTRY SNAPSHOT
#
# Never serialize live object instances.
# =====================================================================

def get_module_snapshot() -> dict:

    snapshot = {}

    with _runtime_lock:

        for name, record in (
            _module_registry.items()
        ):

            snapshot[name] = {
                "name": name,
                "type": (
                    type(
                        record.get(
                            "instance"
                        )
                    ).__name__
                    if record.get(
                        "instance"
                    ) is not None
                    else None
                ),
                "health": record.get(
                    "health",
                    False,
                ),
                "active": record.get(
                    "active",
                    False,
                ),
                "activated": record.get(
                    "activated",
                    False,
                ),
                "state": record.get(
                    "state",
                    "UNKNOWN",
                ),
                "last_cycle": record.get(
                    "last_cycle"
                ),
                "cycle_interval": record.get(
                    "cycle_interval"
                ),
                "boot_cycle": record.get(
                    "boot_cycle",
                    0,
                ),
                "last_boot": record.get(
                    "last_boot"
                ),
                "last_start": record.get(
                    "last_start"
                ),
                "last_stop": record.get(
                    "last_stop"
                ),
                "last_error": record.get(
                    "last_error"
                ),
                "role": record.get(
                    "role"
                ),
                "capabilities": list(
                    record.get(
                        "capabilities",
                        [],
                    )
                ),
                "metadata": dict(
                    record.get(
                        "metadata",
                        {},
                    )
                ),
            }

    return snapshot


# =====================================================================
# 34. SREGISTRY METADATA
# =====================================================================

def get_registry_metadata() -> dict:

    return {
        "name": PACKAGE_NAME,
        "package": PACKAGE_NAME,
        "version": __version__,
        "path": str(
            PACKAGE_ROOT
        ),
        "parent": str(
            PACKAGE_ROOT.parent
        ),
        "group": "seed",
        "role": PACKAGE_ROLE,
        "update_domain": "core",
        "state": (
            "ACTIVE"
            if _runtime_active
            else "READY"
        ),
        "authoritative_owner": (
            "SEEDKernelRuntime"
        ),
        "registry_owned": False,
        "capabilities": get_capabilities(),
        "runtime_connections":
            get_runtime_connections(),
        "modules":
            get_module_snapshot(),
    }


# =====================================================================
# 35. SREGISTRY REGISTRATION
#
# Registry registration is package metadata registration.
#
# It does NOT instantiate core modules.
# =====================================================================

def register_seed_node() -> bool:

    global _sregistry

    try:

        from SRegistry import register_node

    except Exception as exc:

        logger.debug(
            "[SEED-CORE] SRegistry unavailable during "
            "package registration: %s",
            exc,
        )

        return False

    metadata = get_registry_metadata()

    try:

        result = register_node(
            name=PACKAGE_NAME,
            path=PACKAGE_ROOT,
            parent=PACKAGE_ROOT.parent,
            group="seed",
            role=PACKAGE_ROLE,
            update_domain="core",
            state=metadata[
                "state"
            ],
            capabilities=get_capabilities(),
            metadata={
                "package": True,
                "package_name": PACKAGE_NAME,
                "package_root": str(
                    PACKAGE_ROOT
                ),
                "package_file": str(
                    PACKAGE_FILE
                ),
                "components": {
                    item["name"]: item[
                        "file"
                    ]
                    for item in discover_components()
                },
                "subpackages": {
                    item["name"]: item[
                        "path"
                    ]
                    for item in discover_packages()
                },
                "runtime_owner":
                    "SEEDKernelRuntime",
                "runtime_connections":
                    get_runtime_connections(),
            },
        )

        _sregistry = True

        logger.info(
            "[SEED-CORE] Registered with SRegistry"
        )

        return (
            result is not False
        )

    except Exception as exc:

        logger.warning(
            "[SEED-CORE] SRegistry registration failed: %s",
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# 36. REGISTRY UPDATE
# =====================================================================

def update_registry_node(
    *,
    state: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> bool:

    registry = _sregistry

    if registry is None:

        try:
            from SRegistry import register_node
        except Exception:
            return False

        try:

            data = get_registry_metadata()

            if state is not None:
                data["state"] = state

            if metadata:
                data.update(
                    metadata
                )

            result = register_node(
                name=PACKAGE_NAME,
                path=PACKAGE_ROOT,
                parent=PACKAGE_ROOT.parent,
                group="seed",
                role=PACKAGE_ROLE,
                update_domain="core",
                state=data.get(
                    "state",
                    "READY",
                ),
                capabilities=get_capabilities(),
                metadata=data,
            )

            return result is not False

        except Exception:
            return False

    for method_name in (
        "update_node",
        "update",
        "register_node",
    ):

        method = getattr(
            registry,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:

            result = method(
                name=PACKAGE_NAME,
                state=state,
                metadata=metadata or {},
            )

            if inspect.isawaitable(
                result
            ):
                return False

            return result is not False

        except TypeError:
            continue

        except Exception as exc:

            logger.debug(
                "[SEED-CORE] Registry update failed: %s",
                exc,
            )

            return False

    return False


# =====================================================================
# 37. STATUS
# =====================================================================

def get_status() -> dict:

    with _runtime_lock:

        runtime_active = (
            _runtime_active
        )

    connections = (
        get_runtime_connections()
    )

    modules = (
        get_module_snapshot()
    )

    healthy_modules = sum(
        1
        for item in modules.values()
        if item.get(
            "health"
        )
    )

    active_modules = sum(
        1
        for item in modules.values()
        if item.get(
            "active"
        )
    )

    return {
        "package": PACKAGE_NAME,
        "version": __version__,
        "loaded": True,
        "state": (
            "ACTIVE"
            if runtime_active
            else "READY"
        ),
        "runtime_ready":
            _runtime_ready,
        "runtime_active":
            runtime_active,
        "connections":
            connections,
        "connection_count":
            sum(
                1
                for value in connections.values()
                if value
            ),
        "module_count":
            len(modules),
        "healthy_modules":
            healthy_modules,
        "active_modules":
            active_modules,
        "modules":
            modules,
        "tracking":
            get_tracking_context(),
        "discovery": {
            "packages":
                len(
                    discover_packages()
                ),
            "components":
                len(
                    discover_components()
                ),
        },
        "capabilities":
            get_capabilities(),
        "registry":
            get_registry_metadata(),
    }


# =====================================================================
# 38. DIAGNOSTICS
# =====================================================================

def diagnose() -> dict:

    status = get_status()

    problems = []

    if not status[
        "runtime_ready"
    ]:
        problems.append(
            "runtime_not_connected"
        )

    if not status[
        "connections"
    ][
        "qbit_dialer"
    ]:
        problems.append(
            "qbit_dialer_not_connected"
        )

    if not status[
        "connections"
    ][
        "event_bus"
    ]:
        problems.append(
            "event_bus_not_connected"
        )

    if not status[
        "connections"
    ][
        "neural_network"
    ]:
        problems.append(
            "neural_network_not_connected"
        )

    unhealthy = [
        name
        for name, item
        in status[
            "modules"
        ].items()
        if not item.get(
            "health",
            False,
        )
    ]

    if unhealthy:

        problems.append(
            "unhealthy_modules"
        )

    return {
        "package":
            PACKAGE_NAME,
        "version":
            __version__,
        "healthy":
            len(problems) == 0,
        "problems":
            problems,
        "status":
            status,
    }


# =====================================================================
# 39. HEALTH MONITOR TICK
#
# One explicit health pass.
#
# No background thread is created here.
# =====================================================================

def health_tick() -> dict:

    results = {}

    for name in list_modules():

        results[name] = (
            module_health_cycle(
                name
            )
        )

    status = get_status()

    try:

        with STATUS_FILE.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                status,
                f,
                indent=2,
                default=str,
            )

    except Exception as exc:

        logger.debug(
            "[SEED-CORE] Status write failed: %s",
            exc,
        )

    try:

        with MODULE_STATE_FILE.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                get_module_snapshot(),
                f,
                indent=2,
                default=str,
            )

    except Exception as exc:

        logger.debug(
            "[SEED-CORE] Module state write failed: %s",
            exc,
        )

    return results


# =====================================================================
# 40. EXPLICIT HEALTH MONITOR START
#
# The authoritative runtime may call this.
#
# Core does not automatically create the thread during import.
# =====================================================================

_health_thread: Optional[
    threading.Thread
] = None

_health_stop_event = (
    threading.Event()
)


def start_health_monitor(
    interval: float = 0.5,
) -> bool:

    global _health_thread

    if interval <= 0:
        interval = 0.5

    with _runtime_lock:

        if (
            _health_thread is not None
            and _health_thread.is_alive()
        ):
            return True

        _health_stop_event.clear()

        def _loop():

            while not _health_stop_event.is_set():

                try:

                    health_tick()

                except Exception as exc:

                    logger.warning(
                        "[SEED-CORE] Health tick failed: %s",
                        exc,
                    )

                _health_stop_event.wait(
                    interval
                )

        _health_thread = threading.Thread(
            target=_loop,
            name="SEED-Core-HealthMonitor",
            daemon=True,
        )

        _health_thread.start()

    logger.info(
        "[SEED-CORE] Health monitor started"
    )

    return True


# =====================================================================
# 41. EXPLICIT HEALTH MONITOR STOP
# =====================================================================

def stop_health_monitor() -> bool:

    global _health_thread

    _health_stop_event.set()

    with _runtime_lock:

        thread = _health_thread

    if thread is not None:

        if thread.is_alive():

            thread.join(
                timeout=2.0
            )

    with _runtime_lock:

        _health_thread = None

    logger.info(
        "[SEED-CORE] Health monitor stopped"
    )

    return True


# =====================================================================
# 42. DIALER STATE REFRESH
#
# PRESERVED FUNCTION.
#
# The JSON state is handed to the existing QbitDialer object.
# =====================================================================

def refresh_dialer_from_json() -> bool:

    qd = get_module(
        "QbitDialer"
    )

    if not qd:
        return False

    dialer = qd.get(
        "instance"
    )

    if dialer is None:
        return False

    try:

        files = list(
            RUNTIME_STATE_DIR.glob(
                "*.json"
            )
        )

        if not files:
            return False

        latest = max(
            files,
            key=lambda f: f.stat().st_mtime,
        )

        with latest.open(
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

        upstream = data.get(
            "upstream_track",
            {},
        )

        qbit = getattr(
            dialer,
            "qbit",
            None,
        )

        if qbit is not None:

            track = getattr(
                qbit,
                "upstream_track",
                None,
            )

            if hasattr(
                track,
                "update",
            ):

                track.update(
                    upstream
                )

                return True

        # Compatibility with dialers that expose
        # their own state ingestion boundary.

        for method_name in (
            "refresh_state",
            "load_runtime_state",
            "ingest_runtime_state",
        ):

            method = getattr(
                dialer,
                method_name,
                None,
            )

            if callable(method):

                result = method(
                    data
                )

                if inspect.isawaitable(
                    result
                ):
                    return False

                return result is not False

    except Exception as exc:

        logger.warning(
            "[SEED-KERNEL] Could not refresh QbitDialer "
            "from JSON: %s",
            exc,
        )

    return False


# =====================================================================
# 43. RUNTIME ACTIVATION
#
# This changes Core's coordination state only.
# It does not start Qbit, EventBus, neural nodes, etc.
# =====================================================================

def activate_core_runtime() -> bool:

    global _runtime_active

    with _runtime_lock:

        _runtime_active = True

    update_registry_node(
        state="ACTIVE"
    )

    return True


def deactivate_core_runtime() -> bool:

    global _runtime_active

    with _runtime_lock:

        _runtime_active = False

    update_registry_node(
        state="READY"
    )

    return True


# =====================================================================
# 44. FULL CORE SNAPSHOT
# =====================================================================

def snapshot() -> dict:

    return {
        "package": PACKAGE_NAME,
        "version": __version__,
        "timestamp": _utc_now(),
        "status": get_status(),
        "diagnostics": diagnose(),
        "tracking": get_tracking_context(),
        "discovery": {
            "packages":
                discover_packages(),
            "components":
                discover_components(),
        },
    }


# =====================================================================
# 45. PUBLIC API
# =====================================================================

__all__ = [

    # ---------------------------------------------------------------
    # Identity
    # ---------------------------------------------------------------

    "__version__",
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",
    "SEED_CORE_PATH",

    # ---------------------------------------------------------------
    # Existing state paths
    # ---------------------------------------------------------------

    "RUNTIME_STATE_DIR",
    "SYSTEM_STATE_FILE",
    "STATUS_FILE",
    "MODULE_STATE_FILE",
    "DISCOVERY_STATE_FILE",

    # ---------------------------------------------------------------
    # Existing kernel state API
    # ---------------------------------------------------------------

    "load_kernel_context",
    "save_runtime_state",
    "load_runtime_state",

    # ---------------------------------------------------------------
    # Module registry
    # ---------------------------------------------------------------

    "_module_registry",
    "register_module",
    "get_module",
    "get_module_instance",
    "list_modules",
    "get_module_snapshot",

    # ---------------------------------------------------------------
    # Module lifecycle
    # ---------------------------------------------------------------

    "module_health_cycle",
    "module_boot",
    "module_start",
    "module_stop",
    "activate_module",
    "deactivate_module",

    # ---------------------------------------------------------------
    # Runtime binding
    # ---------------------------------------------------------------

    "bind_runtime",
    "attach_runtime",
    "attach_qbit",
    "attach_qbit_dialer",
    "attach_command_handler",
    "attach_control_handler",
    "attach_event_bus",
    "attach_event_handler",
    "attach_neural_network",
    "attach_neural_node_handler",
    "attach_health_monitor",
    "attach_track_id_manager",
    "attach_channel_id_manager",
    "attach_sregistry",

    # ---------------------------------------------------------------
    # Runtime access
    # ---------------------------------------------------------------

    "get_runtime_connections",
    "get_tracking_context",

    # ---------------------------------------------------------------
    # Qbit / command / control
    # ---------------------------------------------------------------

    "emit_to_qbit",
    "submit_command",
    "control",
    "control_node",

    # ---------------------------------------------------------------
    # EventBus / neural network
    # ---------------------------------------------------------------

    "emit_event",
    "emit_to_neural_network",

    # ---------------------------------------------------------------
    # Node status
    # ---------------------------------------------------------------

    "get_node_status",

    # ---------------------------------------------------------------
    # Discovery
    # ---------------------------------------------------------------

    "discover_packages",
    "discover_components",
    "save_discovery_state",

    # ---------------------------------------------------------------
    # Registry
    # ---------------------------------------------------------------

    "get_capabilities",
    "get_registry_metadata",
    "register_seed_node",
    "update_registry_node",

    # ---------------------------------------------------------------
    # Status / diagnostics
    # ---------------------------------------------------------------

    "get_status",
    "diagnose",
    "snapshot",

    # ---------------------------------------------------------------
    # Health
    # ---------------------------------------------------------------

    "health_tick",
    "start_health_monitor",
    "stop_health_monitor",

    # ---------------------------------------------------------------
    # Existing QbitDialer state refresh
    # ---------------------------------------------------------------

    "refresh_dialer_from_json",

    # ---------------------------------------------------------------
    # Core runtime state
    # ---------------------------------------------------------------

    "activate_core_runtime",
    "deactivate_core_runtime",
]


# =====================================================================
# 46. PACKAGE LOAD DIAGNOSTIC
#
# IMPORTANT:
#
# This is diagnostic only.
#
# NO:
#   Qbit construction
#   QbitDialer construction
#   EventBus construction
#   Neural construction
#   queue construction
#   loop creation
#   health thread
#   command execution
#
# SRegistry registration is explicit through register_seed_node().
# =====================================================================

logger.debug(
    "[SEED-CORE] package loaded | "
    "version=%s | capabilities=%d | modules=%d",
    __version__,
    len(
        _CORE_CAPABILITIES
    ),
    len(
        _module_registry
    ),
)