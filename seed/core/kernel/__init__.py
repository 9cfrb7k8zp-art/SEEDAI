# =====================================================================
# FILE: __init__.py
# PATH: C:\SEED_ROOT\seed\core\kernel\__init__.py
#
# SEED CORE KERNEL PACKAGE
#
# CURRENT PACKAGE COMPONENT
# -------------------------
#   qbit_bus.py
#
# PURPOSE
# -------
# Package boundary for the SEED kernel.
#
# qbit_bus.py is a kernel-level Qbit communication component and is
# therefore identified here as part of the Kernel -> Qbit data boundary.
#
# IMPORTANT
# ---------
# This __init__.py:
#
#   - exposes Kernel package metadata
#   - registers the Kernel package with SRegistry
#   - identifies qbit_bus.py to the registry
#   - preserves the existing qbit_bus implementation
#   - does NOT instantiate QbitBus
#   - does NOT create Qbit objects
#   - does NOT create queues
#   - does NOT create EventBus instances
#   - does NOT start runtime loops
#   - does NOT construct QbitDialer
#
# The authoritative boot/runtime path remains responsible for creating
# and wiring the live Kernel/Qbit components.
# =====================================================================

from __future__ import annotations

from pathlib import Path


# ---------------------------------------------------------------------
# PACKAGE METADATA
# ---------------------------------------------------------------------

PACKAGE_NAME = "kernel"
PACKAGE_ROLE = "kernel"

PACKAGE_ROOT = Path(
    __file__
).resolve().parent

PACKAGE_FILE = Path(
    __file__
).resolve()


# ---------------------------------------------------------------------
# EXISTING KERNEL COMPONENT
# ---------------------------------------------------------------------

QBIT_BUS_FILE = (
    PACKAGE_ROOT / "qbit_bus.py"
)


# ---------------------------------------------------------------------
# SREGISTRY CONNECTION
#
# Registration is metadata only.
#
# We intentionally do NOT import qbit_bus here. Importing it from the
# package boundary could execute its dependency graph during registry
# discovery and create circular-import problems.
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
            "kernel",
            "qbit",
            "qbit_bus",
            "kernel_qbit_boundary",
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
                "qbit_bus": str(
                    QBIT_BUS_FILE
                ),
            },
            "qbit_boundary": {
                "direction":
                    "kernel_to_qbit",
                "component":
                    "qbit_bus",
                "runtime_owner":
                    "authoritative_boot",
            },
            "runtime_owner":
                "authoritative_boot",
        },
    )


# ---------------------------------------------------------------------
# COMPONENT METADATA
# ---------------------------------------------------------------------

def get_qbit_bus_info() -> dict:

    return {
        "name": "qbit_bus",
        "path": str(
            QBIT_BUS_FILE
        ),
        "exists": QBIT_BUS_FILE.is_file(),
        "package": PACKAGE_NAME,
        "boundary": "kernel_to_qbit",
        "runtime_owner":
            "authoritative_boot",
    }


# ---------------------------------------------------------------------
# PACKAGE STATUS
# ---------------------------------------------------------------------

def get_package_status() -> dict:

    return {
        "package": PACKAGE_NAME,
        "role": PACKAGE_ROLE,
        "root": str(
            PACKAGE_ROOT
        ),
        "qbit_bus":
            get_qbit_bus_info(),
    }


# ---------------------------------------------------------------------
# PUBLIC EXPORTS
#
# We intentionally do NOT expose classes from qbit_bus.py here.
#
# The existing qbit_bus implementation remains untouched.
# The authoritative runtime can import the actual class from
# seed.core.kernel.qbit_bus when it is ready to construct/wire it.
# ---------------------------------------------------------------------

__all__ = (
    "PACKAGE_NAME",
    "PACKAGE_ROLE",
    "PACKAGE_ROOT",
    "PACKAGE_FILE",
    "QBIT_BUS_FILE",
    "register_seed_node",
    "get_qbit_bus_info",
    "get_package_status",
)