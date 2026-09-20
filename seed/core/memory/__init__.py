# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\memory\__init__.py
#
# SEED MEMORY PACKAGE
#
# PURPOSE
# -------
# Package boundary for SEED memory components.
#
# CURRENT COMPONENT
# -----------------
# qbit_memory_graph.py
#
# RULES
# -----
# - Import-safe package initialization
# - Do not start runtime loops
# - Do not create Qbit objects
# - Do not create queues
# - Do not create EventBus instances
# - Do not force runtime wiring during import
# - Expose existing memory components when available
# - Preserve compatibility with the authoritative runtime
# =====================================================================

from __future__ import annotations

import importlib
import logging


logger = logging.getLogger(
    "SEED.core.memory"
)


# ---------------------------------------------------------------------
# PACKAGE METADATA
# ---------------------------------------------------------------------

PACKAGE_NAME = "seed.core.memory"
PACKAGE_ROLE = "memory"
PACKAGE_STATE = "AVAILABLE"


# ---------------------------------------------------------------------
# COMPONENT REGISTRY
#
# This is a package-local discovery map only.
#
# It does NOT replace SRegistry.
# SRegistry remains the authoritative system registry.
# ---------------------------------------------------------------------

_COMPONENTS: dict[str, object] = {}


# ---------------------------------------------------------------------
# SAFE COMPONENT LOADER
# ---------------------------------------------------------------------

def _load_component(
    module_name: str,
    exports: tuple[str, ...],
) -> None:
    """
    Load an existing memory module without forcing runtime startup.

    Missing optional symbols do not prevent the package itself from
    importing.
    """

    try:

        module = importlib.import_module(
            f"{__name__}.{module_name}"
        )

    except Exception as exc:

        logger.debug(
            "[MEMORY] Component unavailable: %s | %s",
            module_name,
            exc,
        )

        return

    for symbol in exports:

        value = getattr(
            module,
            symbol,
            None,
        )

        if value is None:
            continue

        globals()[symbol] = value

        _COMPONENTS[symbol] = value

        logger.debug(
            "[MEMORY] Component exposed: %s.%s",
            module_name,
            symbol,
        )


# ---------------------------------------------------------------------
# QBIT MEMORY GRAPH
#
# qbit_memory_graph.py is part of this package.
#
# We expose its public symbols if they exist.
# We do NOT assume a particular class/function name that may not match
# the actual implementation.
# ---------------------------------------------------------------------

_load_component(
    "qbit_memory_graph",
    (
        "QbitMemoryGraph",
        "QBITMemoryGraph",
        "QbitMemory",
        "QbitMemoryNode",
        "MemoryGraph",
        "MemoryNode",
        "QbitMemoryGraphManager",
    ),
)


# ---------------------------------------------------------------------
# EXPLICIT PACKAGE DISCOVERY
# ---------------------------------------------------------------------

def discover_components() -> dict:
    """
    Return the memory components currently exposed by this package.

    This is package-local discovery information.

    The authoritative system-wide registry remains SRegistry.
    """

    return {
        "package": PACKAGE_NAME,
        "role": PACKAGE_ROLE,
        "state": PACKAGE_STATE,
        "components": sorted(
            _COMPONENTS.keys()
        ),
    }


def get_component(
    name: str,
):
    """
    Return an exposed memory component by name.

    Returns None when the requested component is not available.
    """

    if not name:
        return None

    return _COMPONENTS.get(
        name
    )


# ---------------------------------------------------------------------
# PACKAGE EXPORTS
# ---------------------------------------------------------------------

__all__ = [
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_STATE",
    "discover_components",
    "get_component",
]

__all__.extend(
    sorted(
        _COMPONENTS.keys()
    )
)


logger.debug(
    "[MEMORY] Package loaded | components=%s",
    sorted(
        _COMPONENTS.keys()
    ),
)