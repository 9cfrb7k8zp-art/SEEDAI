# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\handlers\__init__.py
#
# SEED CORE HANDLERS PACKAGE
#
# CURRENT PACKAGE FILES
# ---------------------
#   system_handlers.py
#
# PURPOSE
# -------
# Package boundary for SEED system handlers.
#
# This package:
#   - registers the handlers node with SRegistry
#   - exposes package/component metadata
#   - does NOT instantiate handlers
#   - does NOT create EventBus objects
#   - does NOT create queues
#   - does NOT create runtime loops
#   - does NOT import QbitDialer
#
# Runtime ownership remains with the authoritative boot path.
# =====================================================================

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------
# PACKAGE METADATA
# ---------------------------------------------------------------------

PACKAGE_NAME = "handlers"
PACKAGE_ROLE = "handlers"

PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_FILE = Path(__file__).resolve()


# ---------------------------------------------------------------------
# HANDLER COMPONENT
# ---------------------------------------------------------------------

SYSTEM_HANDLERS_FILE = (
    PACKAGE_ROOT / "system_handlers.py"
)


# ---------------------------------------------------------------------
# SREGISTRY CONNECTION
#
# Registration is metadata only.
# No handler runtime is constructed during package import.
# ---------------------------------------------------------------------

try:

    from SRegistry import register_node

except Exception:

    register_node = None


def register_seed_node() -> None:
    """
    Register the handlers package with the authoritative SRegistry.

    This registers the package and identifies its handler component.
    Actual handler construction and runtime dependency wiring are
    performed by the authoritative boot/runtime path.
    """

    if not callable(register_node):
        return

    register_node(
        name=PACKAGE_NAME,
        path=PACKAGE_ROOT,
        parent=PACKAGE_ROOT.parent,
        group="seed.core",
        role=PACKAGE_ROLE,
        state="REGISTERED",
        capabilities=[
            "python_package",
            "system_handlers",
            "handlers",
        ],
        metadata={
            "package": True,
            "package_name": PACKAGE_NAME,
            "package_root": str(
                PACKAGE_ROOT
            ),
            "package_file": str(
                PACKAGE_FILE
            ),
            "components": {
                "system_handlers": str(
                    SYSTEM_HANDLERS_FILE
                ),
            },
            "runtime_owner":
                "authoritative_boot",
        },
    )


# ---------------------------------------------------------------------
# PUBLIC EXPORTS
#
# Do not import system_handlers here.
# Keeping the runtime module lazy prevents package discovery from
# executing its dependency graph.
# ---------------------------------------------------------------------

__all__ = (
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",
    "SYSTEM_HANDLERS_FILE",
    "register_seed_node",
)