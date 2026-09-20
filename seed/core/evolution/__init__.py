# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\evolution\__init__.py
#
# SEED CORE — EVOLUTION PACKAGE
#
# PURPOSE:
#   Package boundary for SEED evolutionary / Qbit evolution systems.
#
# ARCHITECTURE:
#
#       DISCOVERY
#           |
#           v
#       SRegistry
#           |
#           v
#       seed.core.evolution
#           |
#           +----> qbit_evolution_engine.py
#           |
#           v
#       Runtime / Qbit pipeline
#
# IMPORTANT:
#
#   This package DOES:
#       - expose the authoritative evolution class
#       - register the package/node with SRegistry
#       - expose package metadata
#       - provide safe availability inspection
#
#   This package DOES NOT:
#       - construct the evolution engine
#       - construct Qbit
#       - construct QbitDialer
#       - construct queues
#       - construct EventBus
#       - start runtime loops
#       - own runtime lifecycle
#
# RUNTIME OWNERSHIP:
#
#       main3.py / SEEDKernelRuntime
#
# REGISTRY:
#
#       SRegistry is authoritative for discovery state.
#
# VERSION:
#       1.0.0
#
# BUILD:
#       DYNAMIC-CORE-DISCOVERY
# =====================================================================

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger("SEEDEvolution")


# =====================================================================
# PACKAGE VERSION
# =====================================================================

__version__ = "1.0.0"


# =====================================================================
# PACKAGE PATH
# =====================================================================

PACKAGE_PATH = Path(__file__).resolve().parent


# =====================================================================
# AUTHORITATIVE EVOLUTION ENGINE
# =====================================================================
#
# Import only.
#
# No instance is created here.
# =====================================================================

try:

    from .qbit_evolution_engine import QbitEvolutionEngine

except Exception as exc:

    QbitEvolutionEngine = None

    logger.error(
        "[Evolution] QbitEvolutionEngine import failed: %s",
        exc,
        exc_info=True,
    )


# =====================================================================
# SREGISTRY REGISTRATION
# =====================================================================
#
# Registration is deliberately isolated from the engine import.
#
# If SRegistry is unavailable during an unusual early import,
# the package remains import-safe.
#
# No runtime object is created.
# =====================================================================

def _register_with_sregistry() -> bool:

    try:

        from SRegistry import register_node

    except Exception:

        try:

            from seed.SRegistry import register_node

        except Exception as exc:

            logger.debug(
                "[Evolution] SRegistry unavailable during package "
                "registration: %s",
                exc,
            )

            return False

    try:

        capabilities = [
            "evolution",
            "qbit_evolution",
        ]

        if QbitEvolutionEngine is not None:
            capabilities.append(
                "qbit_evolution_engine"
            )

        register_node(
            name="evolution",
            path=PACKAGE_PATH,
            parent=PACKAGE_PATH.parent,
            group="core",
            role="evolution",
            update_domain="core.evolution",
            state=(
                "AVAILABLE"
                if QbitEvolutionEngine is not None
                else "DEGRADED"
            ),
            capabilities=capabilities,
            metadata={
                "package": "seed.core.evolution",
                "module": "qbit_evolution_engine",
                "engine_available": (
                    QbitEvolutionEngine is not None
                ),
                "dynamic_discovery": True,
                "runtime_owner": (
                    "main3.py / SEEDKernelRuntime"
                ),
            },
        )

        logger.info(
            "[REGISTRY] Evolution package registered | "
            "engine=%s",
            QbitEvolutionEngine is not None,
        )

        return True

    except Exception as exc:

        logger.error(
            "[Evolution] Registry registration failed: %s",
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# PACKAGE AVAILABILITY
# =====================================================================

def evolution_available() -> bool:

    return QbitEvolutionEngine is not None


# =====================================================================
# COMPONENT LOOKUP
# =====================================================================

def get_evolution_engine_class() -> Any:

    return QbitEvolutionEngine


# =====================================================================
# PACKAGE STATUS
# =====================================================================

def evolution_status() -> dict:

    return {
        "package": "seed.core.evolution",
        "path": str(PACKAGE_PATH),
        "available": (
            QbitEvolutionEngine is not None
        ),
        "components": {
            "QbitEvolutionEngine": (
                QbitEvolutionEngine is not None
            ),
        },
        "dynamic_discovery": True,
        "registry": "SRegistry",
    }


# =====================================================================
# DISCOVER / REGISTER PACKAGE
# =====================================================================

_registry_registered = _register_with_sregistry()


# =====================================================================
# PUBLIC API
# =====================================================================

__all__ = [
    "QbitEvolutionEngine",
    "__version__",
    "PACKAGE_PATH",

    "evolution_available",
    "get_evolution_engine_class",
    "evolution_status",
]


# =====================================================================
# PACKAGE LOAD DIAGNOSTIC
# =====================================================================

logger.debug(
    "[Evolution] package loaded | "
    "registered=%s | "
    "QbitEvolutionEngine=%s",
    _registry_registered,
    QbitEvolutionEngine is not None,
)