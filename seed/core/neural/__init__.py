# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\neural\__init__.py
#
# SEED NEURAL PACKAGE
#
# PURPOSE
# -------
# Package boundary for SEED neural components.
#
# CURRENT COMPONENT
# -----------------
# neural_bridge.py
#
# ARCHITECTURE
# ------------
#
#     Neural Nodes
#          |
#          v
#     neural_bridge.py
#          |
#          v
#     SEED runtime / registry / processing pipeline
#
# The bridge provides the adapter boundary.
#
# IMPORTANT
# ---------
# This __init__.py:
#
#   - exposes existing neural components
#   - does not create neural nodes
#   - does not create EventBus
#   - does not create Qbit objects
#   - does not create queues
#   - does not start loops
#   - does not perform runtime startup
#   - does not replace SRegistry
#
# Runtime ownership remains with the authoritative boot path.
# =====================================================================

from __future__ import annotations

import importlib
import logging


logger = logging.getLogger(
    "SEED.core.neural"
)


# ---------------------------------------------------------------------
# PACKAGE METADATA
# ---------------------------------------------------------------------

PACKAGE_NAME = "seed.core.neural"
PACKAGE_ROLE = "neural"
PACKAGE_STATE = "AVAILABLE"


# ---------------------------------------------------------------------
# PACKAGE COMPONENTS
#
# Package-local exposure only.
# SRegistry remains the authoritative system registry.
# ---------------------------------------------------------------------

_COMPONENTS: dict[str, object] = {}


# ---------------------------------------------------------------------
# SAFE COMPONENT LOADER
# ---------------------------------------------------------------------

def _load_component(
    module_name: str,
    candidate_exports: tuple[str, ...],
) -> None:
    """
    Safely expose existing symbols from a neural package module.

    This does not instantiate anything or start runtime services.
    """

    try:

        module = importlib.import_module(
            f"{__name__}.{module_name}"
        )

    except Exception as exc:

        logger.debug(
            "[NEURAL] Component unavailable: %s | %s",
            module_name,
            exc,
        )

        return

    for symbol in candidate_exports:

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
            "[NEURAL] Exposed: %s.%s",
            module_name,
            symbol,
        )


# ---------------------------------------------------------------------
# NEURAL BRIDGE
#
# Existing file:
#
#     seed/core/neural/neural_bridge.py
#
# We expose its existing public bridge symbols when present.
#
# We intentionally do not assume that the bridge has only one class
# name. The actual module remains authoritative for its implementation.
# ---------------------------------------------------------------------

_load_component(
    "neural_bridge",
    (
        "NeuralBridge",
        "SEEDNeuralBridge",
        "NeuralNodeBridge",
        "NeuralNetworkBridge",
        "NeuralBridgeManager",
    ),
)


# ---------------------------------------------------------------------
# COMPONENT DISCOVERY
# ---------------------------------------------------------------------

def discover_components() -> dict:
    """
    Return the neural components currently exposed by this package.
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
    Return an exposed neural component.

    Returns None when the component is not available.
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
    "[NEURAL] Package loaded | components=%s",
    sorted(
        _COMPONENTS.keys()
    ),
)

# ==========================================================
# NODE NETWORK EXPORTS
# ==========================================================
# Expose the existing node bridge classes without constructing them.
try:
    from .node_registry import Node_Registry
    _COMPONENTS["Node_Registry"] = Node_Registry
    globals()["Node_Registry"] = Node_Registry
except Exception as exc:
    logger.debug("[NEURAL] Node_Registry unavailable: %s", exc)

try:
    from .node_manager import Node_Manager, NodeManager
    _COMPONENTS["Node_Manager"] = Node_Manager
    _COMPONENTS["NodeManager"] = NodeManager
    globals()["Node_Manager"] = Node_Manager
    globals()["NodeManager"] = NodeManager
except Exception as exc:
    logger.debug("[NEURAL] NodeManager unavailable: %s", exc)

for _symbol in ("Node_Registry", "Node_Manager", "NodeManager"):
    if _symbol in globals() and _symbol not in __all__:
        __all__.append(_symbol)

logger.debug(
    "[NEURAL] Node network exposed | components=%s",
    sorted(_COMPONENTS.keys()),
)
