# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\supervisors\__init__.py
#
# SEED SUPERVISORS PACKAGE
#
# PURPOSE:
#   Package boundary and SRegistry registration point for the SEED
#   supervisor subsystem.
#
# CURRENT COMPONENTS:
#   - qbit_load_balancer.py
#   - qbit_watchdog.py
#
# ARCHITECTURE:
#
#   SRegistry
#       |
#       v
#   seed.supervisors
#       |
#       +--> qbit_load_balancer
#       |
#       +--> qbit_watchdog
#       |
#       v
#   authoritative SEED runtime
#
# IMPORTANT:
#   This package initializer:
#
#   - identifies the supervisors package
#   - registers package metadata with SRegistry
#   - exposes package discovery/status information
#   - does NOT instantiate supervisors
#   - does NOT create Qbit
#   - does NOT create QbitDialer
#   - does NOT create queues
#   - does NOT create EventBus
#   - does NOT start watchdog loops
#   - does NOT start load-balancer loops
#   - does NOT start threads
#   - does NOT own the authoritative runtime
#
# Runtime construction and lifecycle remain with the authoritative
# SEED boot/runtime path.
# =====================================================================

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any


# =====================================================================
# LOGGER
# =====================================================================

logger = logging.getLogger(
    "SEED.supervisors"
)


# =====================================================================
# PACKAGE METADATA
# =====================================================================

__version__ = "1.0.0"

PACKAGE_NAME = "seed.supervisors"
PACKAGE_ROLE = "kernel-supervisors"

PACKAGE_ROOT = Path(
    __file__
).resolve().parent

PACKAGE_FILE = Path(
    __file__
).resolve()


# =====================================================================
# COMPONENT PATHS
# =====================================================================

QBIT_LOAD_BALANCER_FILE = (
    PACKAGE_ROOT / "qbit_load_balancer.py"
)

QBIT_WATCHDOG_FILE = (
    PACKAGE_ROOT / "qbit_watchdog.py"
)


# =====================================================================
# COMPONENT MAP
#
# Metadata only.
#
# The actual supervisor classes are intentionally NOT imported here.
# This keeps package discovery from constructing dependency graphs
# unnecessarily.
# =====================================================================

SUPERVISOR_COMPONENTS = {
    "qbit_load_balancer": str(
        QBIT_LOAD_BALANCER_FILE
    ),
    "qbit_watchdog": str(
        QBIT_WATCHDOG_FILE
    ),
}


# =====================================================================
# CAPABILITIES
# =====================================================================

SUPERVISOR_CAPABILITIES = (
    "python_package",
    "kernel_supervisors",
    "qbit_load_balancing",
    "qbit_watchdog",
    "runtime_supervision",
    "runtime_monitoring",
    "registry_discovery",
)


def get_capabilities() -> list[str]:
    """
    Return the capabilities declared by the supervisors package.

    Metadata only. No runtime objects are created.
    """

    return list(
        SUPERVISOR_CAPABILITIES
    )


# =====================================================================
# SREGISTRY REGISTRATION
#
# SRegistry remains authoritative.
#
# The package registers its existence and metadata.
# It does NOT register live supervisor instances.
# =====================================================================

def register_seed_node() -> bool:
    """
    Register seed.supervisors with SRegistry.

    Safe package-boundary registration:
      - no supervisor construction
      - no runtime startup
      - no loops
      - no Qbit creation
      - no QbitDialer creation
    """

    try:

        from SRegistry import register_node

    except Exception as exc:

        logger.debug(
            "[SEED-SUPERVISORS] SRegistry unavailable "
            "during package registration | error=%s",
            exc,
        )

        return False

    try:

        register_node(
            name=PACKAGE_NAME,
            path=PACKAGE_ROOT,
            parent=PACKAGE_ROOT.parent,
            group="runtime",
            role=PACKAGE_ROLE,
            update_domain="core-supervisors",
            state="REGISTERED",
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
                "components": dict(
                    SUPERVISOR_COMPONENTS
                ),
                "runtime_owner":
                    "authoritative_boot",
                "owns_runtime":
                    False,
                "owns_qbit":
                    False,
                "owns_qbit_dialer":
                    False,
                "owns_event_bus":
                    False,
            },
        )

        logger.debug(
            "[SEED-SUPERVISORS] SRegistry registration complete"
        )

        return True

    except Exception as exc:

        logger.warning(
            "[SEED-SUPERVISORS] SRegistry registration "
            "failed | error=%s",
            exc,
        )

        return False


# =====================================================================
# DISCOVERY
# =====================================================================

def discover_modules() -> dict[str, Any]:
    """
    Return the supervisor package discovery map.

    Discovery does not instantiate modules.
    """

    return {
        "package": PACKAGE_NAME,
        "version": __version__,
        "root": str(
            PACKAGE_ROOT
        ),
        "components": dict(
            SUPERVISOR_COMPONENTS
        ),
        "capabilities": get_capabilities(),
    }


def component_available(
    name: str,
) -> bool:
    """
    Check whether a declared supervisor component exists
    on disk.
    """

    component_path = (
        SUPERVISOR_COMPONENTS.get(name)
    )

    if component_path is None:
        return False

    return Path(
        component_path
    ).is_file()


# =====================================================================
# PACKAGE STATUS
# =====================================================================

def get_status() -> dict[str, Any]:
    """
    Return package-level supervisor status.

    This reports package/component availability only.
    It does not claim that supervisor runtime instances are ONLINE.
    """

    components = {
        name: component_available(name)
        for name in SUPERVISOR_COMPONENTS
    }

    available = sum(
        1
        for value in components.values()
        if value
    )

    total = len(components)

    if total == 0:
        state = "EMPTY"

    elif available == total:
        state = "READY"

    elif available > 0:
        state = "PARTIAL"

    else:
        state = "UNAVAILABLE"

    return {
        "package": PACKAGE_NAME,
        "version": __version__,
        "state": state,
        "loaded": True,
        "package_root": str(
            PACKAGE_ROOT
        ),
        "components": components,
        "component_count": total,
        "available_components": available,
        "capabilities": get_capabilities(),
        "runtime_owner": "authoritative_boot",
        "owns_runtime": False,
        "owns_qbit": False,
        "owns_qbit_dialer": False,
        "owns_event_bus": False,
    }


# =====================================================================
# REGISTRY METADATA
# =====================================================================

def get_registry_metadata() -> dict[str, Any]:
    """
    Return the canonical metadata representation used by SRegistry
    and discovery systems.
    """

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
        "group": "runtime",
        "role": PACKAGE_ROLE,
        "update_domain": "core-supervisors",
        "state": get_status()["state"],
        "capabilities": get_capabilities(),
        "components": dict(
            SUPERVISOR_COMPONENTS
        ),
        "runtime_owner":
            "authoritative_boot",
        "registry_owned":
            True,
    }


# =====================================================================
# PUBLIC API
# =====================================================================

__all__ = (
    # ---------------------------------------------------------------
    # Metadata
    # ---------------------------------------------------------------

    "__version__",
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",

    # ---------------------------------------------------------------
    # Components
    # ---------------------------------------------------------------

    "QBIT_LOAD_BALANCER_FILE",
    "QBIT_WATCHDOG_FILE",
    "SUPERVISOR_COMPONENTS",

    # ---------------------------------------------------------------
    # Registry / discovery
    # ---------------------------------------------------------------

    "register_seed_node",
    "discover_modules",
    "get_registry_metadata",

    # ---------------------------------------------------------------
    # Status / capabilities
    # ---------------------------------------------------------------

    "get_capabilities",
    "component_available",
    "get_status",
)


# =====================================================================
# PACKAGE REGISTRATION
#
# Register package identity with SRegistry.
#
# Nothing else starts here.
# =====================================================================

register_seed_node()


# =====================================================================
# PACKAGE LOAD DIAGNOSTIC
# =====================================================================

logger.debug(
    "[SEED-SUPERVISORS] package loaded | "
    "version=%s | components=%d",
    __version__,
    len(
        SUPERVISOR_COMPONENTS
    ),
)