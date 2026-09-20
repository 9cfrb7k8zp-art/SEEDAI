# ==========================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\dialers\__init__.py
#
# SEED CORE — DIALERS PACKAGE
#
# AUTHORITATIVE RUNTIME FILE:
#   qbit_dialer.py
#
# PURPOSE:
#   Expose the authoritative QbitDialer class AND provide a
#   dynamic discovery/connection boundary for the authoritative
#   runtime.
#
# ARCHITECTURE:
#
#       DISCOVERY
#           |
#           v
#       SRegistry
#           |
#           v
#       DIALERS PACKAGE
#           |
#           v
#       QbitDialer
#           |
#           v
#       QbitQueueLoop
#           |
#           v
#       Qbit / Cognitive Runtime
#
# IMPORTANT:
#
#   Discovery finds what exists.
#   SRegistry describes what exists.
#   This package connects QbitDialer to what already exists.
#
# THIS FILE DOES NOT:
#   - create QbitDialer instances
#   - create Qbit objects
#   - create QbitQueueLoop
#   - create EventBus
#   - create Heartbeat
#   - create queues
#   - create replacement runtime objects
#   - silently replace authoritative dependencies
#
# Runtime construction remains owned by the authoritative boot
# path (main3.py / SEED kernel runtime).
#
# VERSION:
#   1.2.0
#
# BUILD:
#   AUTHORITATIVE-QBIT-DIALER-DYNAMIC-DISCOVERY
# ==========================================================

from __future__ import annotations

import logging
import inspect
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger("SEEDDialers")


# ==========================================================
# PACKAGE VERSION
# ==========================================================

__version__ = "1.2.0"


# ==========================================================
# AUTHORITATIVE QBIT DIALER EXPORT
# ==========================================================
#
# There is ONE authoritative dialer implementation:
#
#     seed.core.dialers.qbit_dialer.QbitDialer
#
# This package imports that implementation.
#
# It NEVER constructs the runtime object.
# ==========================================================

try:

    from .qbit_dialer import QbitDialer

except Exception as exc:

    QbitDialer = None

    logger.error(
        "[DIALERS] Authoritative QbitDialer import failed: %s",
        exc,
        exc_info=True,
    )


# ==========================================================
# SREGISTRY DISCOVERY BRIDGE
# ==========================================================
#
# SRegistry is authoritative for discovered runtime nodes.
#
# This package deliberately imports only the registry API.
#
# No private registry is created here.
# No duplicate registry state is maintained here.
# ==========================================================

try:

    from SRegistry import (
        SEED_KERNEL_REGISTRY,
        get_node,
        get_nodes_by_capability,
        get_registry_view,
        snapshot_registry,
    )

    _SREGISTRY_AVAILABLE = True

except Exception as exc:

    SEED_KERNEL_REGISTRY = None
    get_node = None
    get_nodes_by_capability = None
    get_registry_view = None
    snapshot_registry = None

    _SREGISTRY_AVAILABLE = False

    logger.warning(
        "[DIALERS] SRegistry discovery bridge unavailable: %s",
        exc,
    )


# ==========================================================
# DIALER AVAILABILITY
# ==========================================================

def dialer_available() -> bool:

    return QbitDialer is not None


def registry_available() -> bool:

    return _SREGISTRY_AVAILABLE


# ==========================================================
# AUTHORITATIVE DIALER LOOKUP
# ==========================================================

def get_qbit_dialer_class():

    return QbitDialer


# ==========================================================
# DYNAMIC DISCOVERY
# ==========================================================
#
# These functions DO NOT construct anything.
#
# They ask SRegistry what is currently registered.
#
# This allows newly discovered nodes/modules/services to become
# visible without adding their names to this package.
# ==========================================================

def discover_nodes() -> list[dict]:

    """
    Return the currently discovered nodes from SRegistry.

    SRegistry remains the source of truth.
    """

    if not _SREGISTRY_AVAILABLE:
        return []

    try:

        tree = SEED_KERNEL_REGISTRY.get("tree", {})

        return [
            dict(node)
            for node in tree.values()
            if isinstance(node, dict)
        ]

    except Exception as exc:

        logger.error(
            "[DISCOVERY] Node discovery failed: %s",
            exc,
            exc_info=True,
        )

        return []


def discover_modules() -> list[dict]:

    """
    Return dynamically registered modules.

    No hard-coded module list exists here.
    """

    if not _SREGISTRY_AVAILABLE:
        return []

    try:

        modules = SEED_KERNEL_REGISTRY.get(
            "modules",
            {},
        )

        return [
            dict(module)
            for module in modules.values()
            if isinstance(module, dict)
        ]

    except Exception as exc:

        logger.error(
            "[DISCOVERY] Module discovery failed: %s",
            exc,
            exc_info=True,
        )

        return []


def discover_services() -> list[dict]:

    """
    Return dynamically registered services.
    """

    if not _SREGISTRY_AVAILABLE:
        return []

    try:

        services = SEED_KERNEL_REGISTRY.get(
            "services",
            {},
        )

        return [
            dict(service)
            for service in services.values()
            if isinstance(service, dict)
        ]

    except Exception as exc:

        logger.error(
            "[DISCOVERY] Service discovery failed: %s",
            exc,
            exc_info=True,
        )

        return []


def discover_by_capability(
    capability: str,
) -> list[dict]:

    """
    Dynamically locate nodes advertising a capability.

    Example:

        discover_by_capability("qbit_queue")
        discover_by_capability("event_bus")
        discover_by_capability("qbit")
    """

    if not capability:
        return []

    if not _SREGISTRY_AVAILABLE:
        return []

    if not callable(get_nodes_by_capability):
        return []

    try:

        return get_nodes_by_capability(
            capability,
        )

    except Exception as exc:

        logger.error(
            "[DISCOVERY] Capability lookup failed: %s | %s",
            capability,
            exc,
            exc_info=True,
        )

        return []


def discover_registry() -> dict:

    """
    Return the authoritative SRegistry runtime view.
    """

    if not _SREGISTRY_AVAILABLE:
        return {
            "available": False,
            "source": "SRegistry",
        }

    try:

        if callable(get_registry_view):

            view = get_registry_view()

            if isinstance(view, dict):

                return view

    except Exception as exc:

        logger.error(
            "[DISCOVERY] Registry view failed: %s",
            exc,
            exc_info=True,
        )

    return {
        "available": False,
        "source": "SRegistry",
    }


# ==========================================================
# AUTHORITATIVE DIALER IDENTITY VALIDATION
# ==========================================================

def is_qbit_dialer(
    instance,
) -> bool:

    if instance is None:
        return False

    if QbitDialer is None:
        return False

    try:

        return isinstance(
            instance,
            QbitDialer,
        )

    except Exception:

        return False


# ==========================================================
# RUNTIME DEPENDENCY INSPECTION
# ==========================================================

def queue_identity_matches(
    dialer,
    authoritative_queue,
) -> bool:

    if dialer is None:
        return False

    if authoritative_queue is None:
        return False

    queue = getattr(
        dialer,
        "qbit_queue",
        None,
    )

    if queue is authoritative_queue:
        return True

    loop = getattr(
        dialer,
        "qbit_loop",
        None,
    )

    return loop is authoritative_queue


def qbit_identity_matches(
    dialer,
    authoritative_qbit,
) -> bool:

    if dialer is None:
        return False

    if authoritative_qbit is None:
        return False

    return (
        getattr(
            dialer,
            "qbit",
            None,
        )
        is authoritative_qbit
    )


def event_bus_identity_matches(
    dialer,
    authoritative_event_bus,
) -> bool:

    if dialer is None:
        return False

    if authoritative_event_bus is None:
        return False

    return (
        getattr(
            dialer,
            "event_bus",
            None,
        )
        is authoritative_event_bus
    )


# ==========================================================
# DYNAMIC DEPENDENCY EXTRACTION
# ==========================================================
#
# The registry can tell us WHERE a discovered object lives,
# but registry metadata may use different keys depending on the
# discovery source.
#
# These helpers normalize that metadata without creating anything.
# ==========================================================

def _resolve_reference(
    value: Any,
) -> Any:

    """
    Resolve a registry reference without constructing an object.

    Supported forms:
      - direct object reference
      - callable returning an existing object
      - object exposing .instance
      - object exposing .ref

    No constructor is invoked.
    """

    if value is None:
        return None

    # Direct runtime object.
    if not inspect.isclass(value) and not inspect.isfunction(value):
        return value

    # A callable reference is deliberately NOT executed here.
    #
    # Discovery must not accidentally construct runtime objects.
    return None


def _find_registered_reference(
    record: Optional[dict],
) -> Any:

    if not isinstance(record, dict):
        return None

    for key in (
        "ref",
        "instance",
        "object",
        "runtime",
        "handle",
    ):

        if key not in record:
            continue

        value = _resolve_reference(
            record.get(key)
        )

        if value is not None:
            return value

    return None


def discover_runtime_references() -> dict:

    """
    Inspect SRegistry for already-registered runtime references.

    This is discovery only.

    Nothing is instantiated.
    Nothing is replaced.
    """

    result = {
        "qbit": None,
        "qbit_queue": None,
        "qbit_loop": None,
        "event_bus": None,
        "heartbeat": None,
        "dialer": None,
        "nodes": [],
        "modules": [],
        "services": [],
    }

    nodes = discover_nodes()
    modules = discover_modules()
    services = discover_services()

    result["nodes"] = nodes
    result["modules"] = modules
    result["services"] = services

    records = (
        nodes
        + modules
        + services
    )

    for record in records:

        if not isinstance(record, dict):
            continue

        name = str(
            record.get("name", "")
        ).lower()

        role = str(
            record.get("role", "")
        ).lower()

        module_type = str(
            record.get("type", "")
        ).lower()

        capabilities = {
            str(cap).lower()
            for cap in record.get(
                "capabilities",
                [],
            )
            if cap is not None
        }

        reference = _find_registered_reference(
            record
        )

        if reference is None:
            continue

        # ------------------------------------------------------
        # Qbit
        # ------------------------------------------------------

        if (
            "qbit" in capabilities
            or name in {
                "qbit",
                "qbitkernel",
                "qbit_runtime",
            }
            or role == "qbit"
            or module_type == "qbit"
        ):

            result["qbit"] = reference

        # ------------------------------------------------------
        # Queue
        # ------------------------------------------------------

        if (
            "qbit_queue" in capabilities
            or "queue" in capabilities
            or "qbitqueueloop" in name
            or "qbit_queue" in name
            or "queue" in role
        ):

            result["qbit_queue"] = reference

        # ------------------------------------------------------
        # Qbit loop
        # ------------------------------------------------------

        if (
            "qbit_loop" in capabilities
            or "processing_loop" in capabilities
            or "qbitqueueloop" in name
        ):

            result["qbit_loop"] = reference

        # ------------------------------------------------------
        # Event bus
        # ------------------------------------------------------

        if (
            "event_bus" in capabilities
            or "eventbus" in name
            or name.endswith("event_bus")
        ):

            result["event_bus"] = reference

        # ------------------------------------------------------
        # Heartbeat
        # ------------------------------------------------------

        if (
            "heartbeat" in capabilities
            or "heartbeat" in name
            or role == "heartbeat"
        ):

            result["heartbeat"] = reference

        # ------------------------------------------------------
        # Existing dialer
        # ------------------------------------------------------

        if (
            "qbit_dialer" in capabilities
            or name == "qbitdialer"
            or role == "dialer"
            or module_type == "dialer"
        ):

            if is_qbit_dialer(reference):

                result["dialer"] = reference

    return result


# ==========================================================
# DYNAMIC DIALER CONNECTION
# ==========================================================
#
# THIS IS THE IMPORTANT ADDITION.
#
# QbitDialer is NOT constructed here.
#
# The function accepts an already-created authoritative dialer
# and connects only dependencies that already exist.
#
# Existing matching identities are preserved.
#
# No replacement objects are created.
# ==========================================================

def connect_authoritative_runtime(
    dialer,
    *,
    qbit=None,
    qbit_queue=None,
    qbit_loop=None,
    event_bus=None,
    heartbeat=None,
    discover: bool = True,
) -> dict:

    """
    Dynamically connect an existing authoritative QbitDialer
    to existing runtime objects.

    Priority:

        explicit authoritative object
                |
                v
        discovered registry object

    No object is constructed.

    Returns a connection report.
    """

    report = {
        "available": QbitDialer is not None,
        "is_qbit_dialer": is_qbit_dialer(dialer),
        "discovery_used": False,
        "connections": {},
        "errors": [],
    }

    if not is_qbit_dialer(dialer):

        report["errors"].append(
            "Provided object is not authoritative QbitDialer"
        )

        return report

    discovered = {}

    if discover:

        try:

            discovered = (
                discover_runtime_references()
            )

            report["discovery_used"] = True

        except Exception as exc:

            report["errors"].append(
                f"Discovery failed: {exc}"
            )

    # ----------------------------------------------------------
    # Explicit runtime objects win.
    #
    # Otherwise use discovered registry references.
    # ----------------------------------------------------------

    resolved_qbit = (
        qbit
        if qbit is not None
        else discovered.get("qbit")
    )

    resolved_queue = (
        qbit_queue
        if qbit_queue is not None
        else discovered.get("qbit_queue")
    )

    resolved_loop = (
        qbit_loop
        if qbit_loop is not None
        else discovered.get("qbit_loop")
    )

    resolved_event_bus = (
        event_bus
        if event_bus is not None
        else discovered.get("event_bus")
    )

    resolved_heartbeat = (
        heartbeat
        if heartbeat is not None
        else discovered.get("heartbeat")
    )

    # ----------------------------------------------------------
    # QBIT
    # ----------------------------------------------------------

    if resolved_qbit is not None:

        current = getattr(
            dialer,
            "qbit",
            None,
        )

        if current is None:

            try:

                setattr(
                    dialer,
                    "qbit",
                    resolved_qbit,
                )

                report["connections"]["qbit"] = (
                    getattr(
                        dialer,
                        "qbit",
                        None,
                    )
                    is resolved_qbit
                )

            except Exception as exc:

                report["errors"].append(
                    f"qbit connection failed: {exc}"
                )

        else:

            report["connections"]["qbit"] = (
                current is resolved_qbit
            )

    else:

        report["connections"]["qbit"] = False

    # ----------------------------------------------------------
    # QBIT QUEUE
    # ----------------------------------------------------------

    if resolved_queue is not None:

        current = getattr(
            dialer,
            "qbit_queue",
            None,
        )

        if current is None:

            try:

                setattr(
                    dialer,
                    "qbit_queue",
                    resolved_queue,
                )

                report["connections"]["qbit_queue"] = (
                    getattr(
                        dialer,
                        "qbit_queue",
                        None,
                    )
                    is resolved_queue
                )

            except Exception as exc:

                report["errors"].append(
                    f"qbit_queue connection failed: {exc}"
                )

        else:

            report["connections"]["qbit_queue"] = (
                current is resolved_queue
            )

    else:

        report["connections"]["qbit_queue"] = False

    # ----------------------------------------------------------
    # QBIT LOOP
    # ----------------------------------------------------------

    if resolved_loop is not None:

        current = getattr(
            dialer,
            "qbit_loop",
            None,
        )

        if current is None:

            try:

                setattr(
                    dialer,
                    "qbit_loop",
                    resolved_loop,
                )

                report["connections"]["qbit_loop"] = (
                    getattr(
                        dialer,
                        "qbit_loop",
                        None,
                    )
                    is resolved_loop
                )

            except Exception as exc:

                report["errors"].append(
                    f"qbit_loop connection failed: {exc}"
                )

        else:

            report["connections"]["qbit_loop"] = (
                current is resolved_loop
            )

    else:

        report["connections"]["qbit_loop"] = False

    # ----------------------------------------------------------
    # EVENT BUS
    # ----------------------------------------------------------

    if resolved_event_bus is not None:

        current = getattr(
            dialer,
            "event_bus",
            None,
        )

        if current is None:

            try:

                setattr(
                    dialer,
                    "event_bus",
                    resolved_event_bus,
                )

                report["connections"]["event_bus"] = (
                    getattr(
                        dialer,
                        "event_bus",
                        None,
                    )
                    is resolved_event_bus
                )

            except Exception as exc:

                report["errors"].append(
                    f"event_bus connection failed: {exc}"
                )

        else:

            report["connections"]["event_bus"] = (
                current is resolved_event_bus
            )

    else:

        report["connections"]["event_bus"] = False

    # ----------------------------------------------------------
    # HEARTBEAT
    #
    # Heartbeat remains an input source.
    # QbitDialer does not construct or own it.
    # ----------------------------------------------------------

    if resolved_heartbeat is not None:

        current = getattr(
            dialer,
            "heartbeat",
            None,
        )

        if current is None:

            try:

                setattr(
                    dialer,
                    "heartbeat",
                    resolved_heartbeat,
                )

                report["connections"]["heartbeat"] = (
                    getattr(
                        dialer,
                        "heartbeat",
                        None,
                    )
                    is resolved_heartbeat
                )

            except Exception as exc:

                report["errors"].append(
                    f"heartbeat connection failed: {exc}"
                )

        else:

            report["connections"]["heartbeat"] = (
                current is resolved_heartbeat
            )

    else:

        report["connections"]["heartbeat"] = False

    report["connected"] = any(
        report["connections"].values()
    )

    report["fully_connected"] = all(
        value
        for key, value
        in report["connections"].items()
        if key in {
            "qbit",
            "qbit_queue",
            "event_bus",
        }
    )

    return report


# ==========================================================
# DISCOVER + CONNECT
# ==========================================================
#
# Convenience boundary for boot/runtime.
#
# The caller supplies the authoritative dialer.
#
# Discovery finds the rest.
#
# Nothing is constructed.
# ==========================================================

def discover_and_connect(
    dialer,
    *,
    qbit=None,
    qbit_queue=None,
    qbit_loop=None,
    event_bus=None,
    heartbeat=None,
) -> dict:

    if not is_qbit_dialer(dialer):

        return {
            "success": False,
            "error": (
                "discover_and_connect requires "
                "the authoritative QbitDialer instance"
            ),
        }

    report = connect_authoritative_runtime(
        dialer,
        qbit=qbit,
        qbit_queue=qbit_queue,
        qbit_loop=qbit_loop,
        event_bus=event_bus,
        heartbeat=heartbeat,
        discover=True,
    )

    report["success"] = (
        report.get("is_qbit_dialer", False)
        and not report.get("errors")
    )

    return report


# ==========================================================
# DIALER CONNECTION STATUS
# ==========================================================

def dialer_status(
    dialer,
    *,
    authoritative_queue=None,
    authoritative_qbit=None,
    authoritative_event_bus=None,
) -> dict:

    if dialer is None:

        return {
            "available": False,
            "is_qbit_dialer": False,
            "queue_connected": False,
            "qbit_connected": False,
            "event_bus_connected": False,
        }

    return {
        "available": QbitDialer is not None,
        "is_qbit_dialer": is_qbit_dialer(dialer),

        "queue_connected": (
            queue_identity_matches(
                dialer,
                authoritative_queue,
            )
            if authoritative_queue is not None
            else (
                getattr(
                    dialer,
                    "qbit_queue",
                    None,
                )
                is not None
                or getattr(
                    dialer,
                    "qbit_loop",
                    None,
                )
                is not None
            )
        ),

        "qbit_connected": (
            qbit_identity_matches(
                dialer,
                authoritative_qbit,
            )
            if authoritative_qbit is not None
            else getattr(
                dialer,
                "qbit",
                None,
            )
            is not None
        ),

        "event_bus_connected": (
            event_bus_identity_matches(
                dialer,
                authoritative_event_bus,
            )
            if authoritative_event_bus is not None
            else getattr(
                dialer,
                "event_bus",
                None,
            )
            is not None
        ),

        "heartbeat_connected": (
            getattr(
                dialer,
                "heartbeat",
                None,
            )
            is not None
        ),

        "registry_available": registry_available(),
    }


# ==========================================================
# RUNTIME DISCOVERY STATUS
# ==========================================================

def runtime_discovery_status() -> dict:

    """
    Diagnostic view of what SRegistry currently knows.

    This does not alter runtime state.
    """

    discovered = discover_runtime_references()

    return {
        "registry_available": registry_available(),
        "dialer_available": dialer_available(),

        "nodes_discovered": len(
            discovered.get("nodes", [])
        ),

        "modules_discovered": len(
            discovered.get("modules", [])
        ),

        "services_discovered": len(
            discovered.get("services", [])
        ),

        "qbit_discovered": (
            discovered.get("qbit") is not None
        ),

        "qbit_queue_discovered": (
            discovered.get("qbit_queue") is not None
        ),

        "qbit_loop_discovered": (
            discovered.get("qbit_loop") is not None
        ),

        "event_bus_discovered": (
            discovered.get("event_bus") is not None
        ),

        "heartbeat_discovered": (
            discovered.get("heartbeat") is not None
        ),

        "dialer_discovered": (
            discovered.get("dialer") is not None
        ),
    }


# ==========================================================
# PUBLIC API
# ==========================================================

__all__ = [

    # ------------------------------------------------------
    # Authoritative implementation
    # ------------------------------------------------------

    "QbitDialer",

    # ------------------------------------------------------
    # Package metadata
    # ------------------------------------------------------

    "__version__",

    # ------------------------------------------------------
    # Availability / lookup
    # ------------------------------------------------------

    "dialer_available",
    "registry_available",
    "get_qbit_dialer_class",
    "is_qbit_dialer",

    # ------------------------------------------------------
    # Dynamic discovery
    # ------------------------------------------------------

    "discover_nodes",
    "discover_modules",
    "discover_services",
    "discover_by_capability",
    "discover_registry",
    "discover_runtime_references",

    # ------------------------------------------------------
    # Dynamic connection
    # ------------------------------------------------------

    "connect_authoritative_runtime",
    "discover_and_connect",

    # ------------------------------------------------------
    # Runtime identity checks
    # ------------------------------------------------------

    "queue_identity_matches",
    "qbit_identity_matches",
    "event_bus_identity_matches",

    # ------------------------------------------------------
    # Runtime inspection
    # ------------------------------------------------------

    "dialer_status",
    "runtime_discovery_status",
]


# ==========================================================
# PACKAGE LOAD LOG
# ==========================================================

logger.debug(
    "[Dialers] package loaded | "
    "QbitDialer=%s | "
    "SRegistry=%s",
    QbitDialer is not None,
    _SREGISTRY_AVAILABLE,
)