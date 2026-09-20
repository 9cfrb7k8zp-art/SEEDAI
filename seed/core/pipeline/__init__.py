# =====================================================================
# FILE: __init__.py
# PATH: seed/core/pipeline/__init__.py
#
# SEED PIPELINE PACKAGE
#
# CURRENT COMPONENT
# -----------------
# SEEDPipeline.py
#
# PURPOSE
# -------
# Package boundary for the existing SEED pipeline implementation.
#
# IMPORTANT
# ---------
# This package initializer:
#
#   - exposes the existing pipeline implementation
#   - does not start the pipeline
#   - does not create queues
#   - does not create EventBus
#   - does not create Qbit objects
#   - does not create runtime loops
#   - does not replace SRegistry
#
# Runtime execution remains owned by the authoritative boot path.
# =====================================================================

from __future__ import annotations

import importlib
import logging


logger = logging.getLogger(
    "SEED.core.pipeline"
)


# ---------------------------------------------------------------------
# PACKAGE METADATA
# ---------------------------------------------------------------------

PACKAGE_NAME = "seed.core.pipeline"
PACKAGE_ROLE = "pipeline"
PACKAGE_STATE = "AVAILABLE"


# ---------------------------------------------------------------------
# PIPELINE COMPONENT
# ---------------------------------------------------------------------

SEEDPipeline = None


# ---------------------------------------------------------------------
# CONNECT EXISTING PIPELINE IMPLEMENTATION
#
# The implementation already exists in:
#
#     seed/core/pipeline/SEEDPipeline.py
#
# We expose it here without executing it.
# ---------------------------------------------------------------------

try:

    _pipeline_module = importlib.import_module(
        f"{__name__}.SEEDPipeline"
    )

    # Prefer the canonical class name.
    SEEDPipeline = getattr(
        _pipeline_module,
        "SEEDPipeline",
        None,
    )

    if SEEDPipeline is not None:

        logger.debug(
            "[SEED-PIPELINE] Existing SEEDPipeline connected"
        )

    else:

        logger.debug(
            "[SEED-PIPELINE] SEEDPipeline.py loaded "
            "but canonical SEEDPipeline symbol was not found"
        )

except Exception as exc:

    logger.debug(
        "[SEED-PIPELINE] Pipeline implementation "
        "not available during package import: %s",
        exc,
    )


# ---------------------------------------------------------------------
# EXPLICIT REGISTRATION
#
# Kept for compatibility with code that already uses the old package
# registration mechanism.
# ---------------------------------------------------------------------

def register_pipeline(
    pipeline_cls,
) -> None:

    global SEEDPipeline

    if pipeline_cls is None:
        return

    SEEDPipeline = pipeline_cls

    logger.info(
        "[SEED-PIPELINE] Pipeline registered: %s",
        getattr(
            pipeline_cls,
            "__name__",
            repr(pipeline_cls),
        ),
    )


# ---------------------------------------------------------------------
# PIPELINE DISCOVERY
# ---------------------------------------------------------------------

def discover_pipeline():

    if SEEDPipeline is None:

        return {
            "available": False,
            "package": PACKAGE_NAME,
            "implementation": (
                "SEEDPipeline.py"
            ),
        }

    return {
        "available": True,
        "package": PACKAGE_NAME,
        "implementation": (
            "SEEDPipeline.py"
        ),
        "class": getattr(
            SEEDPipeline,
            "__name__",
            str(SEEDPipeline),
        ),
    }


# ---------------------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------------------

__all__ = [
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_STATE",
    "SEEDPipeline",
    "register_pipeline",
    "discover_pipeline",
]