# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\bios\__init__.py
#
# SEED BIOS PACKAGE
#
# PURPOSE
#   Low-level development and system-access package for SEED.
#
#   BIOS components:
#
#       bios_control_handoff.py  -> BIOSControlHandoff
#       bios_file_tool.py        -> BIOSFileTool
#       bios_module_loader.py    -> BIOSModuleLoader
#       bios_tool_registry.py    -> BIOSToolRegistry
#
# ARCHITECTURE
#
#       DISCOVERY
#           |
#           v
#       SRegistry
#           |
#           v
#       seed.core.bios
#           |
#           +--> BIOSControlHandoff
#           +--> BIOSFileTool
#           +--> BIOSModuleLoader
#           +--> BIOSToolRegistry
#
# IMPORTANT
#
#   This package DOES NOT:
#
#       - construct runtime objects during import
#       - create Qbit
#       - create QbitDialer
#       - create EventBus
#       - create queues
#       - create a second registry
#       - become a second boot orchestrator
#
#   Discovery and registration are separate from construction and
#   activation.
#
#   The package may describe and register what exists without making
#   it active.
#
# GROWTH MODEL
#
#   A new BIOS module placed in this directory can be discovered and
#   registered without manually adding another hard-coded subsystem
#   entry to SRegistry.
#
#   Actual runtime ownership remains with the authoritative kernel.
#
# ACCESS MODEL
#
#   BIOSFileTool / BIOSModuleLoader are the eventual controlled
#   mechanisms through which SEED can inspect, modify, load, and grow
#   its own development environment.
#
#   This __init__.py only exposes and describes those capabilities.
#
# VERSION:
#   2.0.0
#
# BUILD:
#   DYNAMIC-DISCOVERY / SREGISTRY-INTEGRATED / GROWTH-READY
# =====================================================================

from __future__ import annotations

import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger("SEED.core.bios")


# =====================================================================
# PACKAGE METADATA
# =====================================================================

__version__ = "2.0.0"

PACKAGE_NAME = "seed.core.bios"

PACKAGE_PATH = Path(__file__).resolve().parent

PACKAGE_STATE = "DISCOVERED"


# =====================================================================
# AUTHORITATIVE COMPONENT REFERENCES
#
# These references are deliberately empty until the actual runtime
# component is imported/registered.
#
# Importing this package NEVER constructs an object.
# =====================================================================

BIOSControlHandoff = None
BIOSFileTool = None
BIOSModuleLoader = None
BIOSToolRegistry = None


# =====================================================================
# COMPONENT DEFINITIONS
#
# Metadata only.
#
# This gives Discovery a description of what the package contains
# without creating the runtime objects.
# =====================================================================

BIOS_COMPONENT_DEFINITIONS = {
    "BIOSControlHandoff": {
        "module": "bios_control_handoff",
        "symbol": "BIOSControlHandoff",
        "role": "control_handoff",
        "capabilities": [
            "control_handoff",
            "runtime_boundary",
        ],
    },

    "BIOSFileTool": {
        "module": "bios_file_tool",
        "symbol": "BIOSFileTool",
        "role": "file_access",
        "capabilities": [
            "file_read",
            "file_write",
            "filesystem_access",
        ],
    },

    "BIOSModuleLoader": {
        "module": "bios_module_loader",
        "symbol": "BIOSModuleLoader",
        "role": "module_loader",
        "capabilities": [
            "module_discovery",
            "module_loading",
            "dynamic_growth",
        ],
    },

    "BIOSToolRegistry": {
        "module": "bios_tool_registry",
        "symbol": "BIOSToolRegistry",
        "role": "tool_registry",
        "capabilities": [
            "tool_registration",
            "tool_discovery",
        ],
    },
}


# =====================================================================
# INTERNAL REGISTRATION STATE
# =====================================================================

_DISCOVERED_COMPONENTS: dict[str, Any] = {}

_REGISTRY_REGISTERED = False


# =====================================================================
# SAFE COMPONENT IMPORT
#
# Discovery may inspect a component without constructing it.
# =====================================================================

def _load_component(
    name: str,
) -> Any:

    definition = BIOS_COMPONENT_DEFINITIONS.get(name)

    if definition is None:
        return None

    module_name = definition["module"]
    symbol_name = definition["symbol"]

    try:

        module = importlib.import_module(
            f"{PACKAGE_NAME}.{module_name}"
        )

        component = getattr(
            module,
            symbol_name,
            None,
        )

        if component is None:

            logger.warning(
                "[BIOS] Component symbol missing | %s.%s",
                module_name,
                symbol_name,
            )

            return None

        _DISCOVERED_COMPONENTS[name] = component

        return component

    except Exception as exc:

        logger.warning(
            "[BIOS] Component discovery failed | %s | %s",
            name,
            exc,
        )

        return None


# =====================================================================
# DISCOVER
#
# Discovery is intentionally separate from construction.
#
# This function finds what is physically present in the package.
# It does not instantiate anything.
# =====================================================================

def discover_components() -> dict[str, Any]:

    discovered = {}

    for name in BIOS_COMPONENT_DEFINITIONS:

        component = _load_component(name)

        if component is not None:
            discovered[name] = component

    logger.info(
        "[BIOS] Discovery complete | %d component(s)",
        len(discovered),
    )

    return dict(discovered)


# =====================================================================
# REGISTER WITH SREGISTRY
#
# This connects BIOS to the authoritative registry without importing
# Qbit or QbitDialer.
#
# Registration describes the component.
# It does NOT activate the component.
# =====================================================================

def register_with_sregistry() -> bool:

    global _REGISTRY_REGISTERED

    try:

        from SRegistry import register_node

    except Exception as exc:

        logger.debug(
            "[BIOS] SRegistry unavailable during registration | %s",
            exc,
        )

        return False

    try:

        register_node(
            name=PACKAGE_NAME,
            path=PACKAGE_PATH,
            role="core_package",
            group="core",
            update_domain="bios",
            state="REGISTERED",
            capabilities=[
                "bios",
                "system_access",
                "file_access",
                "module_loading",
                "dynamic_growth",
            ],
            metadata={
                "package": PACKAGE_NAME,
                "version": __version__,
                "package_state": PACKAGE_STATE,
                "runtime_constructed": False,
                "runtime_active": False,
                "components": list(
                    BIOS_COMPONENT_DEFINITIONS.keys()
                ),
            },
        )

        for name, definition in BIOS_COMPONENT_DEFINITIONS.items():

            component_path = (
                PACKAGE_PATH
                / f"{definition['module']}.py"
            )

            register_node(
                name=f"{PACKAGE_NAME}.{name}",
                path=component_path,
                parent=PACKAGE_PATH,
                role=definition["role"],
                group="bios",
                update_domain="bios",
                state=(
                    "DISCOVERED"
                    if name in _DISCOVERED_COMPONENTS
                    else "DECLARED"
                ),
                capabilities=list(
                    definition["capabilities"]
                ),
                metadata={
                    "package": PACKAGE_NAME,
                    "symbol": definition["symbol"],
                    "module": definition["module"],
                    "constructed": False,
                    "active": False,
                },
            )

        _REGISTRY_REGISTERED = True

        logger.info(
            "[BIOS] Registered with SRegistry | %s",
            PACKAGE_NAME,
        )

        return True

    except Exception as exc:

        logger.error(
            "[BIOS] SRegistry registration failed | %s",
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# COMPONENT REGISTRATION
#
# Preserves the existing public register_tools() behavior.
#
# Runtime code can explicitly supply already-created components.
# Nothing is constructed here.
# =====================================================================

def register_tools(
    control_handoff=None,
    file_tool=None,
    module_loader=None,
    tool_registry=None,
):

    global BIOSControlHandoff
    global BIOSFileTool
    global BIOSModuleLoader
    global BIOSToolRegistry

    if control_handoff is not None:
        BIOSControlHandoff = control_handoff

    if file_tool is not None:
        BIOSFileTool = file_tool

    if module_loader is not None:
        BIOSModuleLoader = module_loader

    if tool_registry is not None:
        BIOSToolRegistry = tool_registry

    logger.info(
        "[SEED-BIOS] Tools registered | "
        "ControlHandoff=%s | "
        "FileTool=%s | "
        "ModuleLoader=%s | "
        "ToolRegistry=%s",
        BIOSControlHandoff is not None,
        BIOSFileTool is not None,
        BIOSModuleLoader is not None,
        BIOSToolRegistry is not None,
    )

    return bios_status()


# =====================================================================
# COMPONENT LOOKUP
# =====================================================================

def get_bios_component(
    name: str,
    default: Any = None,
) -> Any:

    if not name:
        return default

    return globals().get(
        name,
        _DISCOVERED_COMPONENTS.get(
            name,
            default,
        ),
    )


# =====================================================================
# COMPONENT AVAILABILITY
# =====================================================================

def bios_component_available(
    name: str,
) -> bool:

    return (
        get_bios_component(name) is not None
    )


# =====================================================================
# BIOS STATUS
#
# Read-only diagnostic information.
# =====================================================================

def bios_status() -> dict:

    return {
        "package": PACKAGE_NAME,
        "version": __version__,
        "path": str(PACKAGE_PATH),
        "state": PACKAGE_STATE,

        "sregistry_registered":
            _REGISTRY_REGISTERED,

        "components": {
            name: {
                "available":
                    get_bios_component(name) is not None,

                "module":
                    definition["module"],

                "symbol":
                    definition["symbol"],

                "role":
                    definition["role"],

                "capabilities":
                    list(definition["capabilities"]),
            }

            for name, definition
            in BIOS_COMPONENT_DEFINITIONS.items()
        },
    }


# =====================================================================
# DISCOVERY / REGISTRATION ENTRY POINT
#
# Safe to call repeatedly.
#
# It does NOT construct runtime objects.
# =====================================================================

def discover_and_register() -> dict:

    discover_components()
    register_with_sregistry()

    return bios_status()


# =====================================================================
# PUBLIC API
# =====================================================================

__all__ = [

    # ------------------------------------------------------
    # Package metadata
    # ------------------------------------------------------

    "__version__",
    "PACKAGE_NAME",
    "PACKAGE_PATH",

    # ------------------------------------------------------
    # BIOS components
    # ------------------------------------------------------

    "BIOSControlHandoff",
    "BIOSFileTool",
    "BIOSModuleLoader",
    "BIOSToolRegistry",

    # ------------------------------------------------------
    # Existing registration API
    # ------------------------------------------------------

    "register_tools",

    # ------------------------------------------------------
    # Dynamic discovery
    # ------------------------------------------------------

    "discover_components",
    "discover_and_register",
    "register_with_sregistry",

    # ------------------------------------------------------
    # Lookup / diagnostics
    # ------------------------------------------------------

    "get_bios_component",
    "bios_component_available",
    "bios_status",

    # ------------------------------------------------------
    # Metadata
    # ------------------------------------------------------

    "BIOS_COMPONENT_DEFINITIONS",
]


# =====================================================================
# PACKAGE LOAD
#
# IMPORTANT:
#
# We perform discovery/registration metadata only.
# No runtime object is constructed.
#
# This makes the package visible to the system map while leaving
# activation under the authoritative runtime.
# =====================================================================

logger.debug(
    "[BIOS] package loaded | path=%s",
    PACKAGE_PATH,
)