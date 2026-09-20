# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\qbit\__init__.py
#
# SEED QBIT PACKAGE
#
# ARCHITECTURAL NOTE
# ------------------
# Qbit was moved from seed/core into seed/core/qbit/.
#
# Existing components:
#
#     qbit.py
#     qbit_encoder.py
#
# Qbit owns its encoder at this package level.
#
# IMPORTANT
# ---------
# This package initializer exposes the existing Qbit implementation.
# It does not create queues, start loops, create EventBus instances,
# or instantiate runtime Qbit objects.
#
# Runtime ownership remains with the authoritative boot path.
# =====================================================================

from __future__ import annotations

import logging


logger = logging.getLogger(
    "SEED.core.qbit"
)


# ---------------------------------------------------------------------
# PACKAGE METADATA
# ---------------------------------------------------------------------

PACKAGE_NAME = "seed.core.qbit"
PACKAGE_ROLE = "qbit"
PACKAGE_STATE = "AVAILABLE"


# ---------------------------------------------------------------------
# QBIT
#
# Existing authoritative implementation:
#
#     seed/core/qbit/qbit.py
# ---------------------------------------------------------------------

from .qbit import Qbit


# ---------------------------------------------------------------------
# QBIT ENCODER
#
# Existing encoder belongs to the Qbit package.
#
# We expose the encoder module without assuming a class name that we
# have not inspected yet.
#
# This keeps the package boundary intact without inventing an API.
# ---------------------------------------------------------------------

try:
    from . import qbit_encoder
except Exception as exc:

    qbit_encoder = None

    logger.debug(
        "[QBIT] qbit_encoder unavailable during package import: %s",
        exc,
    )


# ---------------------------------------------------------------------
# PACKAGE DISCOVERY
# ---------------------------------------------------------------------

def discover_components() -> dict:

    return {
        "package": PACKAGE_NAME,
        "role": PACKAGE_ROLE,
        "state": PACKAGE_STATE,
        "qbit": Qbit is not None,
        "encoder": qbit_encoder is not None,
    }


# ---------------------------------------------------------------------
# EXPORTS
# ---------------------------------------------------------------------

__all__ = [
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_STATE",
    "Qbit",
    "qbit_encoder",
    "discover_components",
]


logger.debug(
    "[QBIT] Package loaded | Qbit=%s | encoder=%s",
    Qbit is not None,
    qbit_encoder is not None,
)