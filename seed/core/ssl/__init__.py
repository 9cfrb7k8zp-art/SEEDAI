# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\ssl\__init__.py
#
# VERSION: 2.0.0
#
# SEED AI OS — CORE SSL PACKAGE
#
# PURPOSE
# -------
# Package boundary for SEED secure-connection / SSL management.
#
# CURRENT COMPONENT
# -----------------
#     auto_ssl_manager.py
#
# ROLE
# ----
# Provides SSL-management component discovery, package metadata,
# SRegistry registration, validation, and runtime status.
#
# IMPORTANT OWNERSHIP RULE
# ------------------------
# This package initializer DOES NOT:
#
#   - create AutoSSLManager
#   - start SSL services
#   - create network connections
#   - create threads
#   - create timers
#   - create runtime loops
#   - create EventBus
#   - create Qbit
#   - create QbitDialer
#   - execute commands
#   - replace authoritative runtime objects
#
# The authoritative SEED boot/runtime path owns construction and
# lifecycle of the actual SSL manager.
#
# =====================================================================

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Optional


# =====================================================================
# LOGGER
# =====================================================================

logger = logging.getLogger("SEED.core.ssl")


# =====================================================================
# PACKAGE METADATA
# =====================================================================

__version__ = "2.0.0"

PACKAGE_NAME = "ssl"
PACKAGE_ROLE = "security_transport"

PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_FILE = Path(__file__).resolve()

PACKAGE_IMPORT = "seed.core.ssl"


# =====================================================================
# COMPONENT METADATA
# =====================================================================

AUTO_SSL_MANAGER_FILE = (
    PACKAGE_ROOT / "auto_ssl_manager.py"
)

AUTO_SSL_MANAGER_IMPORT = (
    "seed.core.ssl.auto_ssl_manager"
)


SSL_COMPONENTS = {
    "AutoSSLManager": {
        "name": "AutoSSLManager",
        "file": AUTO_SSL_MANAGER_FILE,
        "import": AUTO_SSL_MANAGER_IMPORT,
        "role": "ssl_management",
    },
}


# =====================================================================
# COMPONENT CACHE
#
# CLASS REFERENCE ONLY.
#
# No AutoSSLManager instance is created here.
# =====================================================================

_AutoSSLManager: Optional[Any] = None
_module_loaded = False


# =====================================================================
# EXPLICIT MODULE REGISTRATION
#
# Compatibility entry point.
#
# This allows the authoritative runtime or component loader to supply
# the actual class without this package constructing it.
# =====================================================================

def register_module(
    module_cls: Any,
) -> Any:

    global _AutoSSLManager
    global _module_loaded

    if module_cls is None:

        logger.warning(
            "[SEED-SSL] Refused empty module registration"
        )

        return None

    _AutoSSLManager = module_cls
    _module_loaded = True

    logger.info(
        "[SEED-SSL] Registered module | %s",
        getattr(
            module_cls,
            "__name__",
            type(module_cls).__name__,
        ),
    )

    return module_cls


# =====================================================================
# COMPONENT DISCOVERY
#
# Discovery imports the module only when explicitly requested.
#
# Discovery DOES NOT instantiate AutoSSLManager.
# =====================================================================

def discover_modules() -> dict:

    global _AutoSSLManager
    global _module_loaded

    result = {}

    metadata = SSL_COMPONENTS[
        "AutoSSLManager"
    ]

    available = False
    module = None
    component = None

    # -------------------------------------------------------------
    # Already explicitly registered?
    # -------------------------------------------------------------

    if _AutoSSLManager is not None:

        component = _AutoSSLManager
        available = True

    # -------------------------------------------------------------
    # Otherwise discover the existing module.
    # -------------------------------------------------------------

    else:

        try:

            module = importlib.import_module(
                AUTO_SSL_MANAGER_IMPORT
            )

            component = module

            if component is not None:

                _AutoSSLManager = component
                _module_loaded = True
                available = True

        except Exception as exc:

            logger.debug(
                "[SEED-SSL] AutoSSLManager discovery failed | "
                "error=%s",
                exc,
                exc_info=True,
            )

    result[
        "AutoSSLManager"
    ] = {
        "name": metadata["name"],
        "file": str(metadata["file"]),
        "import": metadata["import"],
        "role": metadata["role"],
        "available": available,
        "registered": (
            _AutoSSLManager is not None
        ),
        "instantiated": False,
    }

    return result


# =====================================================================
# COMPONENT ACCESS
# =====================================================================

def get_component(
    name: str = "AutoSSLManager",
    default: Any = None,
) -> Any:

    if name != "AutoSSLManager":
        return default

    if _AutoSSLManager is None:

        discover_modules()

    if _AutoSSLManager is None:
        return default

    return _AutoSSLManager


def get_auto_ssl_manager(
    default: Any = None,
) -> Any:

    return get_component(
        "AutoSSLManager",
        default,
    )


# =====================================================================
# COMPONENT AVAILABILITY
# =====================================================================

def component_available(
    name: str = "AutoSSLManager",
) -> bool:

    return (
        get_component(
            name,
            None,
        )
        is not None
    )


# =====================================================================
# CAPABILITIES
# =====================================================================

_SSL_CAPABILITIES = (
    "python_package",
    "security_transport",
    "ssl_management",
    "secure_connection_support",
    "component_discovery",
    "registry_compatible",
    "status_reporting",
    "runtime_safe_import",
)


def get_capabilities() -> list[str]:

    return list(
        _SSL_CAPABILITIES
    )


# =====================================================================
# SREGISTRY METADATA
# =====================================================================

def get_registry_metadata() -> dict:

    return {
        "name": PACKAGE_NAME,
        "package": PACKAGE_IMPORT,
        "version": __version__,
        "role": PACKAGE_ROLE,
        "group": "seed.core",
        "state": "READY",
        "path": str(PACKAGE_ROOT),
        "package_file": str(PACKAGE_FILE),

        "authoritative_owner":
            "SEED runtime",

        "registry_owned":
            False,

        "capabilities":
            get_capabilities(),

        "components":
            discover_modules(),
    }


# =====================================================================
# SREGISTRY CONNECTION
#
# SRegistry is authoritative.
#
# This package does not create or replace SRegistry.
# =====================================================================

try:

    from SRegistry import register_node

except Exception:

    register_node = None

    logger.debug(
        "[SEED-SSL] SRegistry registration interface unavailable",
        exc_info=True,
    )


def register_seed_node() -> bool:

    if not callable(register_node):

        logger.debug(
            "[SEED-SSL] SRegistry registration skipped"
        )

        return False

    metadata = get_registry_metadata()

    try:

        result = register_node(
            name=PACKAGE_NAME,
            path=PACKAGE_ROOT,
            parent=PACKAGE_ROOT.parent,
            group="seed.core",
            role=PACKAGE_ROLE,
            state="READY",
            capabilities=get_capabilities(),
            metadata=metadata,
        )

        return result is not False

    except Exception as exc:

        logger.error(
            "[SEED-SSL] SRegistry registration failed | "
            "error=%s",
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# PACKAGE VALIDATION
# =====================================================================

def validate_package() -> bool:

    if not PACKAGE_ROOT.exists():
        return False

    if not PACKAGE_FILE.exists():
        return False

    if not AUTO_SSL_MANAGER_FILE.exists():
        return False

    return True


# =====================================================================
# PACKAGE STATUS
# =====================================================================

def get_status() -> dict:

    components = discover_modules()

    available = sum(
        1
        for item in components.values()
        if item["available"]
    )

    total = len(components)

    valid = validate_package()

    return {

        "package":
            PACKAGE_IMPORT,

        "name":
            PACKAGE_NAME,

        "role":
            PACKAGE_ROLE,

        "version":
            __version__,

        "loaded":
            True,

        "valid":
            valid,

        "state":
            "READY"
            if valid
            else "DEGRADED",

        "components":
            components,

        "component_count":
            total,

        "available_components":
            available,

        "capabilities":
            get_capabilities(),

        "registry":
            {
                "compatible":
                    callable(register_node),

                "metadata":
                    get_registry_metadata(),
            },

        "ownership":
            {
                "owns_ssl_manager":
                    False,

                "owns_runtime":
                    False,

                "owns_qbit":
                    False,

                "owns_qbit_dialer":
                    False,

                "owns_command_pipeline":
                    False,

                "owns_event_bus":
                    False,

                "owns_runtime_loops":
                    False,
            },
    }


# =====================================================================
# DIAGNOSTIC
# =====================================================================

def diagnose() -> dict:

    status = get_status()

    return {

        "package":
            PACKAGE_IMPORT,

        "version":
            __version__,

        "valid":
            status["valid"],

        "state":
            status["state"],

        "components":
            status["components"],

        "registry_available":
            status[
                "registry"
            ]["compatible"],

        "capabilities":
            status["capabilities"],
    }


# =====================================================================
# PUBLIC API
# =====================================================================

__all__ = (

    # -------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------

    "__version__",
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",
    "PACKAGE_IMPORT",

    # -------------------------------------------------------------
    # Components
    # -------------------------------------------------------------

    "SSL_COMPONENTS",
    "AutoSSLManager",
    "register_module",
    "discover_modules",
    "get_component",
    "get_auto_ssl_manager",
    "component_available",

    # -------------------------------------------------------------
    # Capabilities
    # -------------------------------------------------------------

    "get_capabilities",

    # -------------------------------------------------------------
    # Registry
    # -------------------------------------------------------------

    "get_registry_metadata",
    "register_seed_node",

    # -------------------------------------------------------------
    # Validation / status
    # -------------------------------------------------------------

    "validate_package",
    "get_status",
    "diagnose",
)


# =====================================================================
# COMPATIBILITY EXPORT
#
# IMPORTANT:
# Do not instantiate anything.
#
# AutoSSLManager is initially None until explicit discovery or
# registration occurs.
# =====================================================================

AutoSSLManager = None


# =====================================================================
# PACKAGE LOAD DIAGNOSTIC
#
# Importing seed.core.ssl MUST remain side-effect safe.
# =====================================================================

logger.debug(
    "[SEED-SSL] package loaded | "
    "version=%s | components=%d",
    __version__,
    len(SSL_COMPONENTS),
)