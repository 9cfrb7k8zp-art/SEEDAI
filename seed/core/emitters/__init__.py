# ==========================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\emitters\__init__.py
#
# SEED CORE — EMITTERS PACKAGE
#
# PURPOSE:
#   Package-level discovery, registration, exports, and
#   compatibility helpers for the existing SEED emitter /
#   Qbit processing runtime.
#
# ARCHITECTURE:
#
#       SRegistry
#           |
#           v
#       seed.core discovery
#           |
#           +----> emitters package node
#           |
#           +----> emitter component metadata
#           |
#           v
#       authoritative runtime objects
#
# AUTHORITATIVE RUNTIME CHAIN:
#
#       EventBus
#          |
#          v
#        Qbit
#          |
#          v
#     QbitQueueLoop
#          |
#          v
#      QbitDialer
#
# IMPORTANT:
#
#   THIS FILE DOES NOT CONSTRUCT RUNTIME OBJECTS.
#
#   It does NOT create:
#
#       Qbit
#       QbitQueueLoop
#       EventBus
#       QbitDialer
#       Heartbeat
#       Watchdog
#       ReplayEngine
#
#   Runtime ownership remains with:
#
#       main3.py
#       SEEDKernelRuntime
#
# DISCOVERY MODEL:
#
#   seed.core discovers this package.
#
#   seed.core may then call:
#
#       register_package_node()
#
#   That function safely connects this package to SRegistry.
#
#   SRegistry is NOT imported automatically during package import.
#   This prevents circular boot dependencies.
#
# DYNAMIC CONNECTION:
#
#   Package
#       |
#       v
#   discovery metadata
#       |
#       v
#   SRegistry.register_node()
#       |
#       v
#   authoritative registry
#
# VERSION:
#   9.0.0
#
# BUILD:
#   DYNAMIC-DISCOVERY-REGISTRY-CONNECTED-EMITTERS
# ==========================================================

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger("SEEDEmitters")


# ==========================================================
# PACKAGE VERSION
# ==========================================================

__version__ = "9.0.0"


# ==========================================================
# PACKAGE IDENTITY
# ==========================================================
#
# Static package identity is NOT runtime subsystem ownership.
#
# It simply gives discovery a stable node description.
# ==========================================================

PACKAGE_NAME = "emitters"

PACKAGE_PATH = Path(__file__).resolve().parent

PACKAGE_MODULE = "seed.core.emitters"

PACKAGE_ROLE = "runtime-support"

PACKAGE_UPDATE_DOMAIN = "core.emitters"


# ==========================================================
# DISCOVERY STATE
# ==========================================================
#
# These values describe whether this package has been connected
# to the authoritative registry.
#
# No runtime object is created here.
# ==========================================================

_DISCOVERY_REGISTERED = False

_DISCOVERY_REGISTRY = None


# ==========================================================
# AUTHORITATIVE QBIT QUEUE LOOP
# ==========================================================
#
# Existing runtime component.
#
# Import the implementation for package exposure only.
#
# NEVER construct it here.
# ==========================================================

try:

    from .qbit_queue_loop import QbitQueueLoop

except Exception as exc:

    QbitQueueLoop = None

    logger.debug(
        "[Emitters] QbitQueueLoop unavailable: %s",
        exc,
        exc_info=True,
    )


# Compatibility name used by older callers.

QbitQueue = QbitQueueLoop


# ==========================================================
# EMIT WRAPPER
# ==========================================================

try:

    from .emit_wrapper import (
        EmitWrapper,
        EmitStub,
    )

except Exception as exc:

    EmitWrapper = None
    EmitStub = None

    logger.debug(
        "[Emitters] EmitWrapper unavailable: %s",
        exc,
        exc_info=True,
    )


# ==========================================================
# QBIT REPLAY ENGINE
# ==========================================================

try:

    from .qbit_replay_engine import (
        QbitReplayEngine,
    )

except Exception as exc:

    QbitReplayEngine = None

    logger.debug(
        "[Emitters] QbitReplayEngine unavailable: %s",
        exc,
        exc_info=True,
    )


# ==========================================================
# QBIT WATCHDOG
# ==========================================================

try:

    from .qbit_watchdog import (
        QbitWatchdog,
        start_watchdog,
    )

except Exception as exc:

    QbitWatchdog = None
    start_watchdog = None

    logger.debug(
        "[Emitters] QbitWatchdog unavailable: %s",
        exc,
        exc_info=True,
    )


# ==========================================================
# HEARTBEAT EMITTER
# ==========================================================

try:

    from .heartbeatemitter import (
        HeartbeatEmitter,
    )

except Exception as exc:

    HeartbeatEmitter = None

    logger.debug(
        "[Emitters] HeartbeatEmitter unavailable: %s",
        exc,
        exc_info=True,
    )


# ==========================================================
# AUTHORITATIVE COMPONENT MAP
# ==========================================================
#
# Metadata only.
#
# Values are classes/functions already imported above.
# Nothing is instantiated.
# ==========================================================

EMITTER_COMPONENTS = {
    "QbitQueueLoop": QbitQueueLoop,
    "QbitQueue": QbitQueueLoop,

    "EmitWrapper": EmitWrapper,
    "EmitStub": EmitStub,

    "QbitReplayEngine": QbitReplayEngine,

    "QbitWatchdog": QbitWatchdog,
    "start_watchdog": start_watchdog,

    "HeartbeatEmitter": HeartbeatEmitter,
}


# ==========================================================
# DISCOVERY COMPONENT MAP
# ==========================================================
#
# This is deliberately metadata.
#
# It lets SRegistry know what this package exposes without
# forcing SRegistry to import or construct runtime objects.
# ==========================================================

def get_discovery_metadata() -> dict:

    available_components = [
        name
        for name, component
        in EMITTER_COMPONENTS.items()
        if component is not None
    ]

    return {
        "name": PACKAGE_NAME,
        "module": PACKAGE_MODULE,
        "path": str(PACKAGE_PATH),
        "role": PACKAGE_ROLE,
        "update_domain": PACKAGE_UPDATE_DOMAIN,

        "state": "DISCOVERED",

        "capabilities": [
            "qbit_queue",
            "qbit_processing",
            "emit",
            "runtime_wiring",
            "runtime_diagnostics",
            "dynamic_discovery",
        ],

        "components": available_components,

        "metadata": {
            "package": PACKAGE_MODULE,
            "version": __version__,
            "authoritative_runtime": True,
            "constructs_runtime_objects": False,
            "owns_runtime": False,
            "dynamic_discovery": True,
            "registry_connectable": True,
        },
    }


# ==========================================================
# REGISTRY CONNECTOR
# ==========================================================
#
# IMPORTANT:
#
# This function is intentionally explicit.
#
# It is NOT called automatically while this package imports.
#
# That prevents:
#
#   SRegistry
#       ->
#   seed.core
#       ->
#   emitters
#       ->
#   SRegistry
#
# circular initialization.
#
# seed.core discovery owns the timing.
# ==========================================================

def register_package_node(
    registry: Any = None,
) -> bool:

    global _DISCOVERY_REGISTERED
    global _DISCOVERY_REGISTRY

    # ------------------------------------------------------
    # Resolve registry lazily.
    # ------------------------------------------------------

    if registry is None:

        try:

            import SRegistry as registry_module

            registry = registry_module

        except Exception as exc:

            logger.debug(
                "[Emitters] SRegistry unavailable during discovery: %s",
                exc,
                exc_info=True,
            )

            return False

    # ------------------------------------------------------
    # Obtain authoritative registration function.
    # ------------------------------------------------------

    register_node = getattr(
        registry,
        "register_node",
        None,
    )

    if not callable(register_node):

        logger.error(
            "[Emitters] Registry does not expose register_node()"
        )

        return False

    metadata = get_discovery_metadata()

    try:

        register_node(
            name=PACKAGE_MODULE,
            path=PACKAGE_PATH,
            parent=PACKAGE_PATH.parent,
            group="seed.core",
            role=metadata["role"],
            update_domain=metadata["update_domain"],
            state=metadata["state"],
            capabilities=metadata["capabilities"],
            metadata=metadata["metadata"],
        )

        _DISCOVERY_REGISTERED = True
        _DISCOVERY_REGISTRY = registry

        logger.info(
            "[DISCOVERY] Registered package node: %s",
            PACKAGE_MODULE,
        )

        return True

    except Exception as exc:

        logger.error(
            "[DISCOVERY] Failed to register package node %s: %s",
            PACKAGE_MODULE,
            exc,
            exc_info=True,
        )

        return False


# ==========================================================
# REGISTRY CONNECTION STATUS
# ==========================================================

def registry_connection_status() -> dict:

    return {
        "package": PACKAGE_MODULE,
        "path": str(PACKAGE_PATH),
        "registered": _DISCOVERY_REGISTERED,
        "registry_connected": _DISCOVERY_REGISTRY is not None,
        "registry_type": (
            type(_DISCOVERY_REGISTRY).__name__
            if _DISCOVERY_REGISTRY is not None
            else None
        ),
    }


# ==========================================================
# COMPONENT LOOKUP
# ==========================================================

def get_emitter_component(
    name: str,
    default: Any = None,
) -> Any:

    return EMITTER_COMPONENTS.get(
        name,
        default,
    )


# ==========================================================
# COMPONENT AVAILABILITY
# ==========================================================

def emitter_component_available(
    name: str,
) -> bool:

    return (
        EMITTER_COMPONENTS.get(name)
        is not None
    )


# ==========================================================
# REQUIRED RUNTIME VALIDATION
# ==========================================================

def validate_emitter_runtime() -> bool:

    if QbitQueueLoop is None:

        logger.error(
            "[Emitters] REQUIRED component unavailable | "
            "QbitQueueLoop"
        )

        return False

    return True


# ==========================================================
# QUEUE LOOP LOOKUP
# ==========================================================

def get_queue_loop(
    owner: Any,
) -> Any:

    if owner is None:
        return None

    # Authoritative current name.

    queue_loop = getattr(
        owner,
        "qbit_queue_loop",
        None,
    )

    if queue_loop is not None:
        return queue_loop

    # Compatibility.

    queue_loop = getattr(
        owner,
        "qbit_queue",
        None,
    )

    if queue_loop is not None:
        return queue_loop

    return getattr(
        owner,
        "qbit_loop",
        None,
    )


# ==========================================================
# QUEUE IDENTITY
# ==========================================================

def queue_identity_matches(
    owner: Any,
    authoritative_queue: Any,
) -> bool:

    if owner is None:
        return False

    if authoritative_queue is None:
        return False

    return (
        get_queue_loop(owner)
        is authoritative_queue
    )


# ==========================================================
# QBIT LOOKUP
# ==========================================================

def get_qbit(
    owner: Any,
) -> Any:

    if owner is None:
        return None

    return getattr(
        owner,
        "qbit",
        None,
    )


# ==========================================================
# QBIT IDENTITY
# ==========================================================

def qbit_identity_matches(
    owner: Any,
    authoritative_qbit: Any,
) -> bool:

    if owner is None:
        return False

    if authoritative_qbit is None:
        return False

    return (
        get_qbit(owner)
        is authoritative_qbit
    )


# ==========================================================
# EVENT BUS LOOKUP
# ==========================================================

def get_event_bus(
    owner: Any,
) -> Any:

    if owner is None:
        return None

    return getattr(
        owner,
        "event_bus",
        None,
    )


# ==========================================================
# EVENT BUS IDENTITY
# ==========================================================

def event_bus_identity_matches(
    owner: Any,
    authoritative_event_bus: Any,
) -> bool:

    if owner is None:
        return False

    if authoritative_event_bus is None:
        return False

    return (
        get_event_bus(owner)
        is authoritative_event_bus
    )


# ==========================================================
# QBIT DIALER LOOKUP
# ==========================================================

def get_qbit_dialer(
    owner: Any,
) -> Any:

    if owner is None:
        return None

    dialer = getattr(
        owner,
        "qbit_dialer",
        None,
    )

    if dialer is not None:
        return dialer

    return getattr(
        owner,
        "dialer",
        None,
    )


# ==========================================================
# QBIT DIALER IDENTITY
# ==========================================================

def dialer_identity_matches(
    owner: Any,
    authoritative_dialer: Any,
) -> bool:

    if owner is None:
        return False

    if authoritative_dialer is None:
        return False

    return (
        get_qbit_dialer(owner)
        is authoritative_dialer
    )


# ==========================================================
# RUNTIME ATTACHMENT
# ==========================================================
#
# Existing-object attachment only.
#
# No object creation.
# No replacement.
# No runtime ownership transfer.
# ==========================================================

def attach_runtime_components(
    owner: Any,
    *,
    event_bus: Any = None,
    qbit: Any = None,
    qbit_queue_loop: Any = None,
    qbit_dialer: Any = None,
) -> bool:

    if owner is None:
        return False

    attached = False

    if event_bus is not None:

        try:

            owner.event_bus = event_bus
            attached = True

        except Exception:

            logger.debug(
                "[Emitters] EventBus attachment failed",
                exc_info=True,
            )

    if qbit is not None:

        try:

            owner.qbit = qbit
            attached = True

        except Exception:

            logger.debug(
                "[Emitters] Qbit attachment failed",
                exc_info=True,
            )

    if qbit_queue_loop is not None:

        try:

            owner.qbit_queue_loop = (
                qbit_queue_loop
            )

            attached = True

        except Exception:

            logger.debug(
                "[Emitters] QbitQueueLoop attachment failed",
                exc_info=True,
            )

    if qbit_dialer is not None:

        try:

            owner.qbit_dialer = (
                qbit_dialer
            )

            attached = True

        except Exception:

            logger.debug(
                "[Emitters] QbitDialer attachment failed",
                exc_info=True,
            )

    return attached


# ==========================================================
# QUEUE LOOP ATTACHMENT
# ==========================================================

def attach_queue_loop(
    owner: Any,
    qbit_queue_loop: Any,
) -> bool:

    if owner is None:
        return False

    if qbit_queue_loop is None:
        return False

    try:

        owner.qbit_queue_loop = (
            qbit_queue_loop
        )

        return True

    except Exception as exc:

        logger.debug(
            "[Emitters] QueueLoop attachment failed: %s",
            exc,
            exc_info=True,
        )

        return False


# ==========================================================
# QBIT ATTACHMENT
# ==========================================================

def attach_qbit(
    owner: Any,
    qbit: Any,
) -> bool:

    if owner is None:
        return False

    if qbit is None:
        return False

    try:

        owner.qbit = qbit

        return True

    except Exception as exc:

        logger.debug(
            "[Emitters] Qbit attachment failed: %s",
            exc,
            exc_info=True,
        )

        return False


# ==========================================================
# DIALER ATTACHMENT
# ==========================================================

def attach_qbit_dialer(
    owner: Any,
    qbit_dialer: Any,
) -> bool:

    if owner is None:
        return False

    if qbit_dialer is None:
        return False

    try:

        owner.qbit_dialer = (
            qbit_dialer
        )

        return True

    except Exception as exc:

        logger.debug(
            "[Emitters] QbitDialer attachment failed: %s",
            exc,
            exc_info=True,
        )

        return False


# ==========================================================
# QUEUE WIRING VALIDATION
# ==========================================================

def validate_queue_wiring(
    *,
    queue_loop: Any = None,
    qbit_dialer: Any = None,
    qbit: Any = None,
) -> dict:

    queue_present = (
        queue_loop is not None
    )

    dialer_present = (
        qbit_dialer is not None
    )

    qbit_present = (
        qbit is not None
    )

    dialer_queue = (
        get_queue_loop(qbit_dialer)
        if dialer_present
        else None
    )

    dialer_qbit = (
        get_qbit(qbit_dialer)
        if dialer_present
        else None
    )

    return {

        "queue_present":
            queue_present,

        "dialer_present":
            dialer_present,

        "qbit_present":
            qbit_present,

        "dialer_queue_attached":
            dialer_queue is not None,

        "dialer_queue_identity":
            (
                dialer_queue is queue_loop
                if queue_present
                else False
            ),

        "dialer_qbit_attached":
            dialer_qbit is not None,

        "dialer_qbit_identity":
            (
                dialer_qbit is qbit
                if qbit_present
                else False
            ),

        "queue_wiring_ok":
            (
                queue_present
                and dialer_present
                and dialer_queue is queue_loop
            ),

        "qbit_wiring_ok":
            (
                qbit_present
                and dialer_present
                and dialer_qbit is qbit
            ),
    }


# ==========================================================
# PACKAGE STATUS
# ==========================================================

def emitter_status() -> dict:

    return {
        name: component is not None
        for name, component
        in EMITTER_COMPONENTS.items()
    }


# ==========================================================
# RUNTIME CONTRACT STATUS
# ==========================================================

def emitter_runtime_status(
    *,
    queue_loop: Any = None,
    qbit: Any = None,
    qbit_dialer: Any = None,
) -> dict:

    wiring = validate_queue_wiring(
        queue_loop=queue_loop,
        qbit=qbit,
        qbit_dialer=qbit_dialer,
    )

    return {

        "package":
            emitter_status(),

        "discovery":
            registry_connection_status(),

        "required_runtime":
            QbitQueueLoop is not None,

        "queue_wiring":
            wiring,
    }


# ==========================================================
# DISCOVERY SNAPSHOT
# ==========================================================
#
# Useful to seed.core, DevHUD, runtime diagnostics, and
# future automatic discovery.
#
# No runtime objects are created.
# ==========================================================

def discovery_snapshot() -> dict:

    return {

        "package":
            get_discovery_metadata(),

        "registry":
            registry_connection_status(),

        "components":
            emitter_status(),

        "runtime":
            {
                "queue_loop_available":
                    QbitQueueLoop is not None,

                "qbit_replay_available":
                    QbitReplayEngine is not None,

                "watchdog_available":
                    QbitWatchdog is not None,

                "heartbeat_emitter_available":
                    HeartbeatEmitter is not None,
            },
    }


# ==========================================================
# PUBLIC API
# ==========================================================

__all__ = [

    # ------------------------------------------------------
    # Primary queue
    # ------------------------------------------------------

    "QbitQueueLoop",
    "QbitQueue",

    # ------------------------------------------------------
    # Existing emitters
    # ------------------------------------------------------

    "EmitWrapper",
    "EmitStub",

    # ------------------------------------------------------
    # Replay
    # ------------------------------------------------------

    "QbitReplayEngine",

    # ------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------

    "QbitWatchdog",
    "start_watchdog",

    # ------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------

    "HeartbeatEmitter",

    # ------------------------------------------------------
    # Package discovery
    # ------------------------------------------------------

    "PACKAGE_NAME",
    "PACKAGE_PATH",
    "PACKAGE_MODULE",
    "PACKAGE_ROLE",
    "PACKAGE_UPDATE_DOMAIN",

    "get_discovery_metadata",
    "register_package_node",
    "registry_connection_status",
    "discovery_snapshot",

    # ------------------------------------------------------
    # Component registry metadata
    # ------------------------------------------------------

    "EMITTER_COMPONENTS",

    # ------------------------------------------------------
    # Lookup / validation
    # ------------------------------------------------------

    "get_emitter_component",
    "emitter_component_available",
    "validate_emitter_runtime",
    "emitter_status",
    "emitter_runtime_status",

    # ------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------

    "get_queue_loop",
    "queue_identity_matches",

    "get_qbit",
    "qbit_identity_matches",

    "get_event_bus",
    "event_bus_identity_matches",

    "get_qbit_dialer",
    "dialer_identity_matches",

    # ------------------------------------------------------
    # Attachment helpers
    # ------------------------------------------------------

    "attach_runtime_components",
    "attach_queue_loop",
    "attach_qbit",
    "attach_qbit_dialer",

    # ------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------

    "validate_queue_wiring",

    # ------------------------------------------------------
    # Version
    # ------------------------------------------------------

    "__version__",
]


# ==========================================================
# PACKAGE LOAD DIAGNOSTIC
# ==========================================================

logger.debug(
    "[Emitters] package loaded | "
    "QbitQueueLoop=%s | "
    "EmitWrapper=%s | "
    "Replay=%s | "
    "Watchdog=%s | "
    "HeartbeatEmitter=%s | "
    "Discovery=%s",
    QbitQueueLoop is not None,
    EmitWrapper is not None,
    QbitReplayEngine is not None,
    QbitWatchdog is not None,
    HeartbeatEmitter is not None,
    _DISCOVERY_REGISTERED,
)