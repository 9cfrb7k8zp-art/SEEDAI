# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\compiler\__init__.py
#
# SEED CORE COMPILER PACKAGE
#
# PURPOSE
# -------
# Package boundary for the SEED Qbit compiler.
#
# ARCHITECTURE
# ------------
# This __init__.py:
#
#   - exposes the compiler package
#   - registers package metadata with SRegistry
#   - does NOT instantiate the compiler
#   - does NOT create Qbit objects
#   - does NOT create queues
#   - does NOT create runtime loops
#   - does NOT create EventBus instances
#   - does NOT import QbitDialer
#
# Runtime ownership remains with the authoritative boot path.
# =====================================================================

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------
# PACKAGE METADATA
# ---------------------------------------------------------------------

PACKAGE_NAME = "compiler"
PACKAGE_ROLE = "compiler"

PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_FILE = Path(__file__).resolve()

QBIT_COMPILER_FILE = (
    PACKAGE_ROOT / "qbit_compiler.py"
)


# ---------------------------------------------------------------------
# SREGISTRY CONNECTION
#
# Registration is metadata only.
# No runtime compiler instance is created here.
# ---------------------------------------------------------------------

try:

    from SRegistry import register_node

except Exception:

    register_node = None


def register_seed_node() -> None:

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
            "qbit_compiler",
            "compiler",
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
            "compiler_file": str(
                QBIT_COMPILER_FILE
            ),
            "runtime_owner":
                "authoritative_boot",
        },
    )


# ---------------------------------------------------------------------
# PUBLIC PACKAGE EXPORTS
#
# Export metadata/registration only.
#
# Do NOT import qbit_compiler here.
# This prevents package import from pulling the compiler's runtime
# dependency graph into SRegistry/bootstrap.
# ---------------------------------------------------------------------

__all__ = (
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",
    "QBIT_COMPILER_FILE",
    "register_seed_node",
)