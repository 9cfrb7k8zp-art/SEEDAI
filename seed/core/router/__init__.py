# ==========================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\router\__init__.py
#
# VERSION: 2.0.0
#
# SEED AI OS — CORE ROUTER PACKAGE
#
# PURPOSE:
#   Package boundary for the existing SEED Qbit routing
#   component.
#
# ARCHITECTURE:
#
#       Qbit
#         |
#         v
#   QbitQueueLoop
#         |
#         v
#      QbitRouter
#         |
#         v
#    QbitExecutor
#
# AUTHORITY:
#   QbitRouter = route resolution only.
#
# PACKAGE RESPONSIBILITIES:
#   - package discovery
#   - SRegistry registration
#   - component metadata
#   - component lookup
#   - runtime contract validation
#   - runtime status reporting
#   - existing router export
#
# DOES NOT:
#   - execute commands
#   - process Qbits
#   - create Qbits
#   - create QueueLoop
#   - create QbitRouter instances
#   - own EventBus
#   - own heartbeat
#   - own QbitDialer
#   - own TrackSystem
#   - modify TrackID
#   - replace runtime objects
#   - create runtime loops
#
# RUNTIME OWNERSHIP:
#   main3.py
#   SEEDKernelRuntime
#
# REGISTRY OWNERSHIP:
#   SRegistry
#
# IMPORTANT:
#   Importing this package must remain passive.
#
#   The initializer exposes the real QbitRouter implementation,
#   registers package metadata with SRegistry when available,
#   and waits for the authoritative runtime to construct/connect
#   the actual router instance.
# ==========================================================

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger(
    "SEED.core.router"
)


# ==========================================================
# PACKAGE METADATA
# ==========================================================

PACKAGE_NAME = "router"
PACKAGE_ROLE = "routing"
PACKAGE_GROUP = "seed.core"

PACKAGE_ROOT = Path(
    __file__
).resolve().parent

PACKAGE_FILE = Path(
    __file__
).resolve()

PACKAGE_VERSION = "2.0.0"

PACKAGE_STATE = "REGISTERED"

PACKAGE_DESCRIPTION = (
    "SEED core Qbit routing package. "
    "Provides route resolution through the existing "
    "QbitRouter implementation."
)


# ==========================================================
# VERSION
# ==========================================================

__version__ = PACKAGE_VERSION


# ==========================================================
# SREGISTRY CONNECTION
#
# Registration is package metadata only.
#
# No router instance is constructed.
# No runtime is started.
# ==========================================================

try:

    from SRegistry import register_node

except Exception:

    register_node = None

    logger.debug(
        "[Router] SRegistry registration interface unavailable",
        exc_info=True,
    )


# ==========================================================
# AUTHORITATIVE ROUTER EXPORT
#
# This remains the existing router implementation.
#
# We do NOT replace or wrap QbitRouter.
# ==========================================================

try:

    from .qbit_router import QbitRouter

except Exception:

    QbitRouter = None

    logger.debug(
        "[Router] QbitRouter unavailable",
        exc_info=True,
    )


# ==========================================================
# COMPONENT MAP
#
# Metadata only.
#
# No router instance is created here.
# ==========================================================

ROUTER_COMPONENTS = {
    "QbitRouter": QbitRouter,
}


# ==========================================================
# CAPABILITIES
#
# Used by SRegistry / discovery / runtime diagnostics.
# ==========================================================

ROUTER_CAPABILITIES = (
    "python_package",
    "qbit_routing",
    "route_resolution",
    "route_registration",
    "runtime_validation",
    "status_reporting",
    "discovery",
    "registry_compatible",
)


# ==========================================================
# REGISTRY METADATA
# ==========================================================

def get_registry_metadata() -> dict:
    """
    Return package metadata suitable for SRegistry.

    This function is read-only metadata generation.

    It does not construct or start QbitRouter.
    """

    return {
        "name": PACKAGE_NAME,
        "package": "seed.core.router",
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
            ROUTER_CAPABILITIES
        ),

        "components": {
            "QbitRouter": (
                str(
                    PACKAGE_ROOT
                    / "qbit_router.py"
                )
            ),
        },

        "runtime_owner": (
            "SEEDKernelRuntime"
        ),

        "registry_owner": (
            "SRegistry"
        ),

        "owns_qbit": False,
        "owns_qbit_queue": False,
        "owns_queue_loop": False,
        "owns_qbit_dialer": False,
        "owns_event_bus": False,
        "owns_heartbeat": False,
        "owns_track_system": False,
        "owns_runtime_loop": False,
        "owns_router_instance": False,
    }


# ==========================================================
# SREGISTRY PACKAGE REGISTRATION
# ==========================================================
#
# Same package-level registration pattern used by the other
# SEED core package initializers.
#
# Registration:
#   YES
#
# Router construction:
#   NO
#
# Runtime startup:
#   NO
# ==========================================================

def register_seed_node() -> bool:
    """
    Register the Router package with SRegistry.

    Registration describes the package and its component.
    The authoritative runtime remains responsible for creating
    and wiring the live QbitRouter instance.
    """

    if not callable(
        register_node
    ):

        logger.debug(
            "[Router] SRegistry registration unavailable"
        )

        return False

    metadata = (
        get_registry_metadata()
    )

    try:

        result = register_node(
            name=PACKAGE_NAME,
            path=PACKAGE_ROOT,
            parent=PACKAGE_ROOT.parent,
            group=PACKAGE_GROUP,
            role=PACKAGE_ROLE,
            state=PACKAGE_STATE,
            capabilities=list(
                ROUTER_CAPABILITIES
            ),
            metadata=metadata,
        )

        logger.debug(
            "[Router] Package registered with SRegistry"
        )

        return result is not False

    except Exception as exc:

        logger.error(
            "[Router] SRegistry registration failed: %s",
            exc,
            exc_info=True,
        )

        return False


# ==========================================================
# COMPONENT LOOKUP
# ==========================================================

def get_router_component(
    name: str = "QbitRouter",
    default: Any = None,
) -> Any:

    return ROUTER_COMPONENTS.get(
        name,
        default,
    )


# ==========================================================
# COMPONENT AVAILABILITY
# ==========================================================

def router_component_available(
    name: str = "QbitRouter",
) -> bool:

    return (
        ROUTER_COMPONENTS.get(
            name
        )
        is not None
    )


# ==========================================================
# PACKAGE VALIDATION
# ==========================================================

def validate_router_runtime() -> bool:
    """
    Validate that the real QbitRouter implementation can be
    imported.

    This validates package/component availability only.

    It does NOT claim that a router instance is ONLINE.
    """

    if QbitRouter is None:

        logger.error(
            "[Router] REQUIRED component unavailable | "
            "QbitRouter"
        )

        return False

    return True


# ==========================================================
# ROUTER IDENTITY
# ==========================================================

def router_identity_matches(
    router: Any,
) -> bool:
    """
    Confirm that an existing runtime object is an instance
    of the authoritative QbitRouter class.

    No replacement occurs.
    """

    if router is None:
        return False

    if QbitRouter is None:
        return False

    try:

        return isinstance(
            router,
            QbitRouter,
        )

    except Exception:

        return False


# ==========================================================
# ROUTER CONTRACT
# ==========================================================

def router_contract_valid(
    router: Any,
) -> bool:
    """
    Validate the existing QbitRouter interface.

    The current runtime requires register().
    """

    if router is None:
        return False

    register = getattr(
        router,
        "register",
        None,
    )

    return callable(
        register
    )


# ==========================================================
# OPTIONAL ROUTE INSPECTION
#
# Read-only helpers.
#
# These do not modify router state.
# ==========================================================

def get_router_routes(
    router: Any,
) -> Any:
    """
    Return route information when the existing router exposes
    a readable route table.

    No assumptions are made about a new routing API.
    """

    if router is None:
        return None

    for name in (
        "routes",
        "_routes",
        "route_table",
        "_route_table",
    ):

        try:

            value = getattr(
                router,
                name,
                None,
            )

            if value is not None:

                if isinstance(
                    value,
                    dict,
                ):
                    return dict(value)

                return value

        except Exception:

            continue

    return None


def get_router_route_count(
    router: Any,
) -> Optional[int]:
    """
    Return the known route count when the existing router
    exposes a readable route collection.
    """

    routes = get_router_routes(
        router
    )

    if routes is None:
        return None

    try:
        return len(routes)

    except Exception:
        return None


# ==========================================================
# ROUTER STATUS
# ==========================================================

def router_status(
    router: Optional[Any] = None,
) -> dict:
    """
    Return package and optional live-router status.

    A missing router instance is NOT treated as a package failure.
    The authoritative runtime owns router construction.
    """

    component_available = (
        QbitRouter is not None
    )

    status = {
        "package":
            "seed.core.router",

        "name":
            PACKAGE_NAME,

        "version":
            PACKAGE_VERSION,

        "role":
            PACKAGE_ROLE,

        "state":
            PACKAGE_STATE,

        "QbitRouter":
            component_available,

        "package_valid":
            component_available,

        "runtime_owner":
            "SEEDKernelRuntime",

        "registry_owner":
            "SRegistry",
    }

    if router is None:

        status.update({
            "router_instance":
                False,

            "router_identity":
                False,

            "router_contract":
                False,

            "router_online":
                False,

            "route_count":
                None,
        })

        return status

    identity = (
        router_identity_matches(
            router
        )
    )

    contract = (
        router_contract_valid(
            router
        )
    )

    status.update({
        "router_instance":
            True,

        "router_identity":
            identity,

        "router_contract":
            contract,

        "router_online":
            bool(
                identity
                and contract
            ),

        "router_type":
            type(router).__name__,

        "route_count":
            get_router_route_count(
                router
            ),
    })

    return status


# ==========================================================
# DISCOVERY
# ==========================================================

def discover(
    router: Optional[Any] = None,
) -> dict:
    """
    Return complete Router package discovery information.

    Safe for registry, boot diagnostics, DevHUD, and runtime
    inspection.
    """

    return {
        "name":
            PACKAGE_NAME,

        "package":
            "seed.core.router",

        "version":
            PACKAGE_VERSION,

        "role":
            PACKAGE_ROLE,

        "group":
            PACKAGE_GROUP,

        "state":
            PACKAGE_STATE,

        "description":
            PACKAGE_DESCRIPTION,

        "path":
            str(PACKAGE_ROOT),

        "components":
            get_registry_metadata()[
                "components"
            ],

        "capabilities":
            list(
                ROUTER_CAPABILITIES
            ),

        "registry":
            get_registry_metadata(),

        "status":
            router_status(
                router
            ),
    }


# ==========================================================
# PACKAGE STATUS
# ==========================================================

def get_status(
    router: Optional[Any] = None,
) -> dict:
    """
    Public package status interface.
    """

    status = router_status(
        router
    )

    status.update({
        "loaded":
            True,

        "capabilities":
            list(
                ROUTER_CAPABILITIES
            ),

        "ownership": {
            "qbit":
                False,

            "qbit_queue":
                False,

            "queue_loop":
                False,

            "qbit_dialer":
                False,

            "event_bus":
                False,

            "heartbeat":
                False,

            "track_system":
                False,

            "runtime_loop":
                False,

            "router_instance":
                False,

            "sregistry":
                False,
        },

        "runtime_owner":
            "SEEDKernelRuntime",

        "registry_owner":
            "SRegistry",
    })

    if router is not None:

        status[
            "ownership"
        ][
            "router_instance"
        ] = True

    return status


# ==========================================================
# DIAGNOSTICS
# ==========================================================

def diagnose(
    router: Optional[Any] = None,
) -> dict:
    """
    Return concise diagnostic information for runtime/DevHUD.
    """

    package_valid = (
        QbitRouter is not None
    )

    instance_present = (
        router is not None
    )

    identity_valid = (
        router_identity_matches(
            router
        )
        if router is not None
        else False
    )

    contract_valid = (
        router_contract_valid(
            router
        )
        if router is not None
        else False
    )

    return {
        "package":
            "seed.core.router",

        "version":
            PACKAGE_VERSION,

        "package_valid":
            package_valid,

        "instance_present":
            instance_present,

        "identity_valid":
            identity_valid,

        "contract_valid":
            contract_valid,

        "runtime_ready":
            bool(
                package_valid
                and identity_valid
                and contract_valid
            ),

        "route_count":
            (
                get_router_route_count(
                    router
                )
                if router is not None
                else None
            ),

        "capabilities":
            list(
                ROUTER_CAPABILITIES
            ),
    }


# ==========================================================
# PUBLIC API
# ==========================================================

__all__ = [

    # ------------------------------------------------------
    # Package metadata
    # ------------------------------------------------------

    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_GROUP",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",
    "PACKAGE_VERSION",
    "PACKAGE_STATE",
    "PACKAGE_DESCRIPTION",

    "__version__",

    # ------------------------------------------------------
    # Router
    # ------------------------------------------------------

    "QbitRouter",

    "ROUTER_COMPONENTS",
    "ROUTER_CAPABILITIES",

    # ------------------------------------------------------
    # SRegistry / discovery
    # ------------------------------------------------------

    "register_seed_node",
    "get_registry_metadata",
    "discover",

    # ------------------------------------------------------
    # Component lookup
    # ------------------------------------------------------

    "get_router_component",
    "router_component_available",

    # ------------------------------------------------------
    # Validation
    # ------------------------------------------------------

    "validate_router_runtime",
    "router_identity_matches",
    "router_contract_valid",

    # ------------------------------------------------------
    # Read-only route inspection
    # ------------------------------------------------------

    "get_router_routes",
    "get_router_route_count",

    # ------------------------------------------------------
    # Status / diagnostics
    # ------------------------------------------------------

    "router_status",
    "get_status",
    "diagnose",
]


# ==========================================================
# PACKAGE LOAD DIAGNOSTIC
#
# PASSIVE.
#
# No router construction.
# No queue.
# No loop.
# No command execution.
# ==========================================================

logger.debug(
    "[Router] package loaded | "
    "version=%s | QbitRouter=%s | SRegistry=%s",
    PACKAGE_VERSION,
    QbitRouter is not None,
    callable(register_node),
)