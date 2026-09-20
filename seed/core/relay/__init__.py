# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\relay\__init__.py
#
# SEED CORE RELAY PACKAGE
#
# VERSION: 5.0.0
#
# PURPOSE
# -------
# Package boundary and registry-discovery interface for the SEED Relay
# subsystem.
#
# Relay is a controlled connection boundary between SEED core systems
# and external services.
#
# THIS PACKAGE FILE:
#
#   - identifies the Relay package
#   - exposes package/component metadata
#   - registers Relay with SRegistry
#   - exposes discovery information
#   - exposes package status
#   - exposes runtime connection state
#   - provides runtime binding points
#   - provides controlled handoff interfaces
#   - remains compatible with QbitDialer and the command pipeline
#   - preserves TrackID / ChannelID context
#   - provides node/update metadata
#
# THIS PACKAGE FILE DOES NOT:
#
#   - create Qbit
#   - create QbitDialer
#   - create queues
#   - create EventBus
#   - create command loops
#   - create runtime loops
#   - create threads
#   - create timers
#   - execute commands during import
#   - connect external services during import
#   - own SRegistry
#   - own the authoritative runtime
#
# OWNERSHIP
# ---------
#
# SRegistry:
#     discovery / registration authority
#
# Authoritative SEED runtime:
#     runtime construction and dependency wiring
#
# QbitDialer:
#     authoritative Qbit command/control boundary
#
# Command pipeline:
#     authoritative command execution path
#
# Relay:
#     boundary / adapter / handoff subsystem
#
# =====================================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional


# =====================================================================
# 1. LOGGER
# =====================================================================

logger = logging.getLogger(
    "SEED.core.relay"
)


# =====================================================================
# 2. PACKAGE METADATA
#
# Keep the package metadata pattern consistent with other SEED
# package __init__.py files.
# =====================================================================

PACKAGE_NAME = "relay"
PACKAGE_ROLE = "boundary"

PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_FILE = Path(__file__).resolve()

PACKAGE_GROUP = "seed.core"
PACKAGE_VERSION = "5.0.0"

PACKAGE_STATE = "REGISTERED"

PACKAGE_DESCRIPTION = (
    "SEED controlled relay boundary for internal "
    "cognition, command, task, node, and external "
    "service communication."
)


# =====================================================================
# 3. RELAY COMPONENT MAP
#
# Metadata only.
#
# No runtime component is constructed here.
# =====================================================================

RELAY_COMPONENTS = {
    "relay_core": (
        PACKAGE_ROOT / "relay_core.py"
    ),
    "relay_protocol": (
        PACKAGE_ROOT / "relay_protocol.py"
    ),
    "relay_policy": (
        PACKAGE_ROOT / "relay_policy.py"
    ),
    "relay_resource_gate": (
        PACKAGE_ROOT / "relay_resource_gate.py"
    ),
    "relay_queue": (
        PACKAGE_ROOT / "relay_queue.py"
    ),
    "relay_audit": (
        PACKAGE_ROOT / "relay_audit.py"
    ),
    "relay_github": (
        PACKAGE_ROOT / "relay_github.py"
    ),
    "relay_auth": (
        PACKAGE_ROOT / "relay_auth.py"
    ),
    "relay_emergency_stop": (
        PACKAGE_ROOT / "relay_emergency_stop.py"
    ),
    "relay_gateway": (
        PACKAGE_ROOT / "relay_gateway.py"
    ),
    "relay_mission_bridge": (
        PACKAGE_ROOT / "relay_mission_bridge.py"
    ),
    "relay_operations": (
        PACKAGE_ROOT / "relay_operations.py"
    ),
    "relay_rate_limiter": (
        PACKAGE_ROOT / "relay_rate_limiter.py"
    ),
    "relay_router": (
        PACKAGE_ROOT / "relay_router.py"
    ),
    "relay_watchdog": (
        PACKAGE_ROOT / "relay_watchdog.py"
    ),
}


# =====================================================================
# 4. CAPABILITIES
#
# SRegistry/discovery metadata.
#
# These describe what Relay supports.
# They do not create or start anything.
# =====================================================================

RELAY_CAPABILITIES = (
    "python_package",
    "relay_boundary",
    "external_service_boundary",
    "qbit_handoff",
    "qbit_dialer_handoff",
    "command_handoff",
    "control_update_handoff",
    "event_handoff",
    "track_id_context",
    "channel_id_context",
    "node_compatible",
    "registry_compatible",
    "runtime_binding",
    "async_dispatch",
    "status_reporting",
    "discovery",
    "diagnostics",
)


# =====================================================================
# 5. AUTHORITATIVE SREGISTRY REGISTRATION
#
# Registration is PACKAGE DISCOVERY / METADATA.
#
# It does not construct Relay.
# It does not start Relay.
# It does not connect QbitDialer.
# It does not create a command pipeline.
#
# This follows the same package-level pattern used by the other SEED
# __init__.py files.
# =====================================================================

try:

    from SRegistry import register_node

except Exception:

    register_node = None


def get_registry_metadata() -> dict:

    return {
        "name": PACKAGE_NAME,
        "package": "seed.core.relay",
        "version": PACKAGE_VERSION,
        "role": PACKAGE_ROLE,
        "group": PACKAGE_GROUP,
        "state": PACKAGE_STATE,
        "description": PACKAGE_DESCRIPTION,

        "path": str(
            PACKAGE_ROOT
        ),

        "package_file": str(
            PACKAGE_FILE
        ),

        "parent": str(
            PACKAGE_ROOT.parent
        ),

        "capabilities": list(
            RELAY_CAPABILITIES
        ),

        "components": {
            name: str(path)
            for name, path
            in RELAY_COMPONENTS.items()
        },

        "runtime_owner": (
            "authoritative_boot"
        ),

        "registry_owner": (
            "SRegistry"
        ),

        "owns_runtime": False,
        "owns_qbit": False,
        "owns_qbit_dialer": False,
        "owns_command_loop": False,
        "owns_qbit_queue": False,
        "owns_event_bus": False,
        "owns_runtime_loop": False,
        "owns_track_id": False,
        "owns_channel_id": False,
    }


def register_seed_node() -> bool:

    if not callable(
        register_node
    ):
        logger.debug(
            "[RELAY] SRegistry registration unavailable"
        )
        return False

    metadata = get_registry_metadata()

    try:

        result = register_node(
            name=PACKAGE_NAME,
            path=PACKAGE_ROOT,
            parent=PACKAGE_ROOT.parent,
            group=PACKAGE_GROUP,
            role=PACKAGE_ROLE,
            state=PACKAGE_STATE,
            capabilities=list(
                RELAY_CAPABILITIES
            ),
            metadata=metadata,
        )

        logger.debug(
            "[RELAY] Package registered with SRegistry"
        )

        return result is not False

    except Exception as exc:

        logger.error(
            "[RELAY] SRegistry registration failed: %s",
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# 6. REAL RELAY COMPONENT EXPORTS
#
# These are the existing implementations.
#
# Importing the classes exposes them.
# It does not instantiate them.
# =====================================================================

from .relay_core import SEEDRelay

from .relay_protocol import (
    RelayRequest,
    RelayResponse,
    RelayStatus,
    RelayOperation,
)

from .relay_policy import RelayPolicy
from .relay_resource_gate import RelayResourceGate
from .relay_queue import RelayQueue
from .relay_audit import RelayAudit
from .relay_github import RelayGitHub
from .relay_auth import RelayAuth, RelayIdentity
from .relay_emergency_stop import RelayEmergencyStop
from .relay_gateway import RelayGateway
from .relay_mission_bridge import RelayMissionBridge
from .relay_operations import RelayOperationSpec, RelayOperations, OperationClass
from .relay_rate_limiter import RelayRateLimiter
from .relay_router import RelayRouter
from .relay_watchdog import RelayWatchdog
from .relay_auth import RelayAuth, RelayIdentity
from .relay_emergency_stop import RelayEmergencyStop
from .relay_gateway import RelayGateway
from .relay_mission_bridge import RelayMissionBridge
from .relay_operations import RelayOperationSpec, RelayOperations, OperationClass
from .relay_rate_limiter import RelayRateLimiter
from .relay_router import RelayRouter
from .relay_watchdog import RelayWatchdog


# =====================================================================
# 7. RUNTIME REFERENCES
#
# REFERENCES ONLY.
#
# These are supplied by the authoritative boot/runtime path.
# =====================================================================

_runtime_lock = threading.RLock()

_qbit: Any = None
_qbit_dialer: Any = None

_command_handler: Optional[Callable] = None
_control_update_handler: Optional[Callable] = None
_event_handler: Optional[Callable] = None

_track_id_manager: Any = None
_channel_id_manager: Any = None

_sregistry: Any = None


# =====================================================================
# 8. TIME / SAFE VALUE HELPERS
# =====================================================================

def _utc_now() -> str:

    return (
        datetime.utcnow()
        .isoformat()
    )


def _safe_name(
    value: Any,
) -> Optional[str]:

    if value is None:
        return None

    return getattr(
        value,
        "__qualname__",
        getattr(
            value,
            "__name__",
            type(value).__name__,
        ),
    )


# =====================================================================
# 9. CAPABILITY ACCESS
# =====================================================================

def get_capabilities() -> list[str]:

    return list(
        RELAY_CAPABILITIES
    )


# =====================================================================
# 10. RUNTIME BINDING
#
# The authoritative boot path supplies these references.
#
# Relay waits for them.
#
# It does not construct them.
# =====================================================================

def bind_runtime(
    *,
    qbit: Any = None,
    qbit_dialer: Any = None,
    command_handler: Optional[Callable] = None,
    control_update_handler: Optional[Callable] = None,
    event_handler: Optional[Callable] = None,
    track_id_manager: Any = None,
    channel_id_manager: Any = None,
    sregistry: Any = None,
) -> dict:

    if qbit is not None:
        attach_qbit(qbit)

    if qbit_dialer is not None:
        attach_qbit_dialer(
            qbit_dialer
        )

    if command_handler is not None:
        attach_command_handler(
            command_handler
        )

    if control_update_handler is not None:
        attach_control_update(
            control_update_handler
        )

    if event_handler is not None:
        attach_event_handler(
            event_handler
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

    logger.info(
        "[RELAY] Runtime bindings updated"
    )

    return get_runtime_connections()


# =====================================================================
# 11. ATTACHMENT HELPERS
# =====================================================================

def attach_qbit(
    qbit: Any,
) -> Any:

    global _qbit

    with _runtime_lock:
        _qbit = qbit

    logger.info(
        "[RELAY] Qbit attached | type=%s",
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
        "[RELAY] QbitDialer attached | type=%s",
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
        "[RELAY] Command handler %s",
        "attached"
        if handler
        else "detached",
    )


def attach_control_update(
    handler: Optional[Callable],
) -> None:

    global _control_update_handler

    with _runtime_lock:
        _control_update_handler = handler

    logger.info(
        "[RELAY] Control-update handler %s",
        "attached"
        if handler
        else "detached",
    )


def attach_event_handler(
    handler: Optional[Callable],
) -> None:

    global _event_handler

    with _runtime_lock:
        _event_handler = handler

    logger.info(
        "[RELAY] Event handler %s",
        "attached"
        if handler
        else "detached",
    )


def attach_track_id_manager(
    manager: Any,
) -> Any:

    global _track_id_manager

    with _runtime_lock:
        _track_id_manager = manager

    logger.info(
        "[RELAY] TrackID manager attached | type=%s",
        type(manager).__name__,
    )

    return manager


def attach_channel_id_manager(
    manager: Any,
) -> Any:

    global _channel_id_manager

    with _runtime_lock:
        _channel_id_manager = manager

    logger.info(
        "[RELAY] ChannelID manager attached | type=%s",
        type(manager).__name__,
    )

    return manager


def attach_sregistry(
    registry: Any,
) -> Any:

    global _sregistry

    with _runtime_lock:
        _sregistry = registry

    logger.info(
        "[RELAY] SRegistry attached | type=%s",
        type(registry).__name__,
    )

    return registry


# =====================================================================
# 12. DETACHMENT
# =====================================================================

def detach_qbit() -> None:

    global _qbit

    with _runtime_lock:
        _qbit = None

    logger.info(
        "[RELAY] Qbit detached"
    )


def detach_qbit_dialer() -> None:

    global _qbit_dialer

    with _runtime_lock:
        _qbit_dialer = None

    logger.info(
        "[RELAY] QbitDialer detached"
    )


def detach_sregistry() -> None:

    global _sregistry

    with _runtime_lock:
        _sregistry = None

    logger.info(
        "[RELAY] SRegistry detached"
    )


def detach_all_runtime() -> None:

    global _qbit
    global _qbit_dialer
    global _command_handler
    global _control_update_handler
    global _event_handler
    global _track_id_manager
    global _channel_id_manager
    global _sregistry

    with _runtime_lock:

        _qbit = None
        _qbit_dialer = None
        _command_handler = None
        _control_update_handler = None
        _event_handler = None
        _track_id_manager = None
        _channel_id_manager = None
        _sregistry = None

    logger.info(
        "[RELAY] Runtime bindings detached"
    )


# =====================================================================
# 13. ACCESSORS
# =====================================================================

def get_qbit():
    return _qbit


def get_qbit_dialer():
    return _qbit_dialer


def get_command_handler():
    return _command_handler


def get_control_update_handler():
    return _control_update_handler


def get_event_handler():
    return _event_handler


def get_track_id_manager():
    return _track_id_manager


def get_channel_id_manager():
    return _channel_id_manager


def get_sregistry():
    return _sregistry


# =====================================================================
# 14. RUNTIME CONNECTION STATUS
# =====================================================================

def get_runtime_connections() -> dict:

    with _runtime_lock:

        return {
            "qbit":
                _qbit is not None,

            "qbit_dialer":
                _qbit_dialer is not None,

            "command_handler":
                _command_handler is not None,

            "control_update_handler":
                _control_update_handler is not None,

            "event_handler":
                _event_handler is not None,

            "track_id_manager":
                _track_id_manager is not None,

            "channel_id_manager":
                _channel_id_manager is not None,

            "sregistry":
                _sregistry is not None,
        }


# =====================================================================
# 15. IDENTITY / TRACKING CONTEXT
#
# Relay does not own identity.
#
# It reads current identity from the supplied managers.
# =====================================================================

def _read_identity(
    manager: Any,
    *,
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

                if not inspect.isawaitable(
                    result
                ):
                    return result

            elif value is not None:

                return value

        except Exception:

            continue

    return None


def get_tracking_context() -> dict:

    track_id = _read_identity(
        _track_id_manager,
        names=(
            "current_track_id",
            "get_current_track_id",
            "track_id",
            "current_id",
        ),
    )

    channel_id = _read_identity(
        _channel_id_manager,
        names=(
            "current_channel_id",
            "get_current_channel_id",
            "channel_id",
            "current_id",
        ),
    )

    return {
        "track_id": track_id,
        "channel_id": channel_id,

        "track_id_manager":
            _track_id_manager is not None,

        "channel_id_manager":
            _channel_id_manager is not None,
    }


# =====================================================================
# 16. EVENT ENVELOPE
#
# Relay adds context.
#
# It does NOT reinterpret the command.
# =====================================================================

def _build_event(
    event: str,
    payload: Any = None,
) -> dict:

    tracking = get_tracking_context()

    envelope = {
        "source":
            "SEED.core.relay",

        "package":
            PACKAGE_NAME,

        "event":
            event,

        "timestamp":
            _utc_now(),

        "payload":
            payload,

        "track_id":
            tracking.get(
                "track_id"
            ),

        "channel_id":
            tracking.get(
                "channel_id"
            ),
    }

    return envelope


# =====================================================================
# 17. SAFE ASYNC DISPATCH
#
# Relay never creates an event loop.
# =====================================================================

def _dispatch_result(
    result: Any,
    *,
    context: str,
) -> bool:

    if result is False:
        return False

    if not inspect.isawaitable(
        result
    ):
        return True

    try:

        loop = asyncio.get_running_loop()

    except RuntimeError:

        close = getattr(
            result,
            "close",
            None,
        )

        if callable(close):

            try:
                close()
            except Exception:
                pass

        logger.debug(
            "[RELAY] Async dispatch rejected | "
            "no running runtime loop | context=%s",
            context,
        )

        return False

    try:

        loop.create_task(
            result
        )

        return True

    except Exception as exc:

        logger.error(
            "[RELAY] Async dispatch failed | "
            "context=%s | error=%s",
            context,
            exc,
            exc_info=True,
        )

        close = getattr(
            result,
            "close",
            None,
        )

        if callable(close):

            try:
                close()
            except Exception:
                pass

        return False


def _call_handler(
    handler: Optional[Callable],
    payload: Any,
    *,
    context: str,
) -> bool:

    if not callable(handler):
        return False

    try:

        result = handler(
            payload
        )

        return _dispatch_result(
            result,
            context=context,
        )

    except Exception as exc:

        logger.error(
            "[RELAY] Boundary dispatch failed | "
            "context=%s | error=%s",
            context,
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# 18. QBIT / QBITDIALER HANDOFF
#
# QbitDialer is preferred because it is the authoritative Qbit
# command/control boundary.
#
# Relay does not create or operate the Qbit queue.
# Relay does not start a Qbit loop.
# Relay does not become another command loop.
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

        logger.debug(
            "[RELAY] Qbit handoff waiting | "
            "QbitDialer/Qbit not attached"
        )

        return False

    envelope = _build_event(
        "RELAY_DATA",
        payload,
    )

    method_names = (
        "receive_relay_data",
        "handle_relay_data",
        "receive_data",
        "ingest",
        "submit",
        "enqueue",
    )

    for method_name in method_names:

        method = getattr(
            target,
            method_name,
            None,
        )

        if not callable(method):
            continue

        result = _call_handler(
            method,
            envelope,
            context=f"qbit.{method_name}",
        )

        if result:

            logger.debug(
                "[RELAY] Qbit handoff delivered | "
                "target=%s | interface=%s",
                type(target).__name__,
                method_name,
            )

            return True

        return False

    logger.debug(
        "[RELAY] Qbit target exposes no compatible "
        "Relay handoff interface | target=%s",
        type(target).__name__,
    )

    return False


# =====================================================================
# 19. COMMAND PIPELINE HANDOFF
#
# Relay DOES NOT execute commands.
#
# Relay passes the command to the authoritative command boundary.
#
# QbitDialer / command pipeline decide what happens next.
# =====================================================================

def emit_command(
    command: Any,
) -> bool:

    with _runtime_lock:
        handler = _command_handler

    if handler is None:

        logger.debug(
            "[RELAY] Command handoff waiting | "
            "authoritative command handler not attached"
        )

        return False

    envelope = _build_event(
        "RELAY_COMMAND",
        command,
    )

    return _call_handler(
        handler,
        envelope,
        context="command_pipeline",
    )


# =====================================================================
# 20. CONTROL UPDATE HANDOFF
#
# Separate from command execution.
#
# The authoritative runtime defines the semantics.
# =====================================================================

def emit_control_update(
    update: Any,
) -> bool:

    with _runtime_lock:
        handler = _control_update_handler

    if handler is None:

        logger.debug(
            "[RELAY] Control-update handoff waiting"
        )

        return False

    envelope = _build_event(
        "RELAY_CONTROL_UPDATE",
        update,
    )

    return _call_handler(
        handler,
        envelope,
        context="control_update",
    )


# =====================================================================
# 21. GENERIC EVENT HANDOFF
# =====================================================================

def emit_event(
    event: str,
    payload: Any = None,
) -> bool:

    with _runtime_lock:
        handler = _event_handler

    if handler is None:

        logger.debug(
            "[RELAY] Event handoff waiting | event=%s",
            event,
        )

        return False

    envelope = _build_event(
        event,
        payload,
    )

    return _call_handler(
        handler,
        envelope,
        context=f"event.{event}",
    )


# =====================================================================
# 22. PACKAGE DISCOVERY
#
# Gives SRegistry / runtime / DevHUD a complete package description.
# =====================================================================

def discover() -> dict:

    return {
        "name": PACKAGE_NAME,
        "package": "seed.core.relay",
        "version": PACKAGE_VERSION,
        "role": PACKAGE_ROLE,
        "group": PACKAGE_GROUP,
        "state": PACKAGE_STATE,
        "description": PACKAGE_DESCRIPTION,

        "path": str(
            PACKAGE_ROOT
        ),

        "components": {
            name: str(path)
            for name, path
            in RELAY_COMPONENTS.items()
        },

        "capabilities":
            get_capabilities(),

        "registry":
            get_registry_metadata(),

        "runtime_connections":
            get_runtime_connections(),

        "tracking":
            get_tracking_context(),
    }


# =====================================================================
# 23. STATUS
#
# This is intentionally richer than a simple "loaded=True".
# =====================================================================

def get_status() -> dict:

    connections = (
        get_runtime_connections()
    )

    connected = sum(
        1
        for value
        in connections.values()
        if value
    )

    total = len(
        connections
    )

    return {
        "package":
            "SEED.core.relay",

        "name":
            PACKAGE_NAME,

        "version":
            PACKAGE_VERSION,

        "loaded":
            True,

        "state":
            PACKAGE_STATE,

        "role":
            PACKAGE_ROLE,

        "group":
            PACKAGE_GROUP,

        "capabilities":
            get_capabilities(),

        "runtime_connections":
            connections,

        "tracking":
            get_tracking_context(),

        "connection_count":
            connected,

        "connection_total":
            total,

        "connection_percentage":
            (
                round(
                    connected
                    / total
                    * 100.0,
                    1,
                )
                if total
                else 0.0
            ),

        "ownership":
            {
                "qbit": False,
                "qbit_dialer": False,
                "command_loop": False,
                "qbit_queue": False,
                "event_bus": False,
                "runtime_loop": False,
                "track_id": False,
                "channel_id": False,
                "sregistry": False,
            },

        "runtime_owner":
            "authoritative_boot",

        "registry_owner":
            "SRegistry",
    }


# =====================================================================
# 24. DIAGNOSTICS
# =====================================================================

def diagnose_connections() -> dict:

    connections = (
        get_runtime_connections()
    )

    missing = [
        name
        for name, connected
        in connections.items()
        if not connected
    ]

    connected = [
        name
        for name, connected
        in connections.items()
        if connected
    ]

    return {
        "package":
            "SEED.core.relay",

        "version":
            PACKAGE_VERSION,

        "ready":
            bool(
                _qbit_dialer is not None
                or _qbit is not None
            ),

        "connected":
            connected,

        "missing":
            missing,

        "connection_count":
            len(connected),

        "connection_total":
            len(connections),

        "connections":
            connections,

        "tracking":
            get_tracking_context(),

        "capabilities":
            get_capabilities(),
    }


# =====================================================================
# 25. PUBLIC API
# =====================================================================

__all__ = (

    # --------------------------------------------------------------
    # Package metadata
    # --------------------------------------------------------------

    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",
    "PACKAGE_GROUP",
    "PACKAGE_VERSION",
    "PACKAGE_STATE",
    "PACKAGE_DESCRIPTION",
    "RELAY_COMPONENTS",
    "RELAY_CAPABILITIES",

    "__version__",

    # --------------------------------------------------------------
    # Registry / discovery
    # --------------------------------------------------------------

    "register_seed_node",
    "get_registry_metadata",
    "discover",

    # --------------------------------------------------------------
    # Real Relay components
    # --------------------------------------------------------------

    "SEEDRelay",
    "RelayRequest",
    "RelayResponse",
    "RelayStatus",
    "RelayOperation",
    "RelayPolicy",
    "RelayResourceGate",
    "RelayQueue",
    "RelayAudit",
    "RelayGitHub",
    "RelayAuth",
    "RelayIdentity",
    "RelayEmergencyStop",
    "RelayGateway",
    "RelayMissionBridge",
    "RelayOperationSpec",
    "RelayOperations",
    "OperationClass",
    "RelayRateLimiter",
    "RelayRouter",
    "RelayWatchdog",
    "RelayAuth",
    "RelayIdentity",
    "RelayEmergencyStop",
    "RelayGateway",
    "RelayMissionBridge",
    "RelayOperationSpec",
    "RelayOperations",
    "OperationClass",
    "RelayRateLimiter",
    "RelayRouter",
    "RelayWatchdog",

    # --------------------------------------------------------------
    # Runtime binding
    # --------------------------------------------------------------

    "bind_runtime",

    "attach_qbit",
    "attach_qbit_dialer",
    "attach_command_handler",
    "attach_control_update",
    "attach_event_handler",
    "attach_track_id_manager",
    "attach_channel_id_manager",
    "attach_sregistry",

    # --------------------------------------------------------------
    # Runtime detach
    # --------------------------------------------------------------

    "detach_qbit",
    "detach_qbit_dialer",
    "detach_sregistry",
    "detach_all_runtime",

    # --------------------------------------------------------------
    # Runtime access
    # --------------------------------------------------------------

    "get_qbit",
    "get_qbit_dialer",
    "get_command_handler",
    "get_control_update_handler",
    "get_event_handler",
    "get_track_id_manager",
    "get_channel_id_manager",
    "get_sregistry",

    # --------------------------------------------------------------
    # Runtime state
    # --------------------------------------------------------------

    "get_runtime_connections",
    "get_tracking_context",
    "get_capabilities",
    "get_status",
    "diagnose_connections",

    # --------------------------------------------------------------
    # Handoffs
    # --------------------------------------------------------------

    "emit_to_qbit",
    "emit_command",
    "emit_control_update",
    "emit_event",
)


# =====================================================================
# 26. VERSION ALIAS
# =====================================================================

__version__ = PACKAGE_VERSION


# =====================================================================
# 27. IMPORT DIAGNOSTIC
#
# IMPORTANT:
#
# Registration is metadata/discovery.
# No runtime is started here.
# =====================================================================

logger.debug(
    "[SEED-RELAY] package loaded | "
    "version=%s | registry=%s | capabilities=%d",
    PACKAGE_VERSION,
    callable(register_node),
    len(RELAY_CAPABILITIES),
)