# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\executor\__init__.py
#
# SEED CORE — EXECUTOR PACKAGE
#
# PURPOSE:
#   Package boundary for SEED execution / Qbit executor systems.
#
# ARCHITECTURE:
#
#       DISCOVERY
#           |
#           v
#       SRegistry
#           |
#           v
#       seed.core.executor
#           |
#           +----> qbit_executor.py
#           |
#           v
#       Qbit / Command Execution Runtime
#
# IMPORTANT:
#
#   This package DOES:
#       - expose the authoritative executor class
#       - register the package/node with SRegistry
#       - expose package metadata
#       - provide safe availability inspection
#
#   This package DOES NOT:
#       - construct executor instances
#       - construct Qbit
#       - construct QbitDialer
#       - construct queues
#       - construct EventBus
#       - start execution loops
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


logger = logging.getLogger("SEEDExecutor")


# =====================================================================
# PACKAGE VERSION
# =====================================================================

__version__ = "1.0.0"


# =====================================================================
# PACKAGE PATH
# =====================================================================

PACKAGE_PATH = Path(__file__).resolve().parent


# =====================================================================
# AUTHORITATIVE QBIT EXECUTOR
# =====================================================================
#
# Import only.
#
# No executor instance is created here.
# =====================================================================

try:

    from .qbit_executor import QbitExecutor

except Exception as exc:

    QbitExecutor = None

    logger.error(
        "[Executor] QbitExecutor import failed: %s",
        exc,
        exc_info=True,
    )


# =====================================================================
# SREGISTRY REGISTRATION
# =====================================================================

def _register_with_sregistry() -> bool:

    try:

        from SRegistry import register_node

    except Exception:

        try:

            from seed.SRegistry import register_node

        except Exception as exc:

            logger.debug(
                "[Executor] SRegistry unavailable during package "
                "registration: %s",
                exc,
            )

            return False

    try:

        capabilities = [
            "executor",
            "qbit_executor",
            "command_execution",
        ]

        register_node(
            name="executor",
            path=PACKAGE_PATH,
            parent=PACKAGE_PATH.parent,
            group="core",
            role="executor",
            update_domain="core.executor",
            state=(
                "AVAILABLE"
                if QbitExecutor is not None
                else "DEGRADED"
            ),
            capabilities=capabilities,
            metadata={
                "package": "seed.core.executor",
                "module": "qbit_executor",
                "executor_available": (
                    QbitExecutor is not None
                ),
                "dynamic_discovery": True,
                "runtime_owner": (
                    "main3.py / SEEDKernelRuntime"
                ),
            },
        )

        logger.info(
            "[REGISTRY] Executor package registered | "
            "executor=%s",
            QbitExecutor is not None,
        )

        return True

    except Exception as exc:

        logger.error(
            "[Executor] Registry registration failed: %s",
            exc,
            exc_info=True,
        )

        return False


# =====================================================================
# PACKAGE AVAILABILITY
# =====================================================================

def executor_available() -> bool:

    return QbitExecutor is not None


# =====================================================================
# COMPONENT LOOKUP
# =====================================================================

def get_qbit_executor_class() -> Any:

    return QbitExecutor


# =====================================================================
# PACKAGE STATUS
# =====================================================================

def executor_status() -> dict:

    return {
        "package": "seed.core.executor",
        "path": str(PACKAGE_PATH),
        "available": (
            QbitExecutor is not None
        ),
        "components": {
            "QbitExecutor": (
                QbitExecutor is not None
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
    "QbitExecutor",
    "__version__",
    "PACKAGE_PATH",

    "executor_available",
    "get_qbit_executor_class",
    "executor_status",
]


# =====================================================================
# PACKAGE LOAD DIAGNOSTIC
# =====================================================================

logger.debug(
    "[Executor] package loaded | "
    "registered=%s | "
    "QbitExecutor=%s",
    _registry_registered,
    QbitExecutor is not None,
)