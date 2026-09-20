# =============================================================================
# SEED-AI :: AFM CORE REGISTRATION
# File: __init__.py
# Path: C:\SEED_ROOT\seed\core\afm\__init__.py
# Version: 1.0.0
#
# ROLE:
#   Kernel-level declaration for AFM (Automatic Framework Module).
#   This file performs NO compilation, NO scanning, NO execution.
#
# DESIGN RULES:
#   - Silent by default (no print, no logging, no exceptions unless fatal)
#   - Path-aware and relocatable
#   - Idempotent registration (safe on multiple imports)
#   - Zero dependency creation
#
# AFM RESPONSIBILITY:
#   - One-time compilation handled elsewhere (afm_compiler_full.py)
#   - This file ONLY declares existence + authority boundary
# =============================================================================

from pathlib import Path

try:
    from SRegistry import register_node
except ImportError as e:
    # Kernel-level failure: registry must exist.
    # Raise once, cleanly, no cascade.
    raise RuntimeError(
        "SEED kernel registry (SRegistry) missing. "
        "AFM cannot register without core registry."
    ) from e


# -------------------------------------------------------------------------
# PATH RESOLUTION (NO ASSUMPTIONS)
# -------------------------------------------------------------------------

THIS_PATH = Path(__file__).resolve().parent
CORE_PATH = THIS_PATH.parent  # seed/core
SEED_PATH = CORE_PATH.parent  # seed

# -------------------------------------------------------------------------
# KERNEL-SAFE REGISTRATION
# -------------------------------------------------------------------------

register_node(
    name="seed.core.afm",
    path=THIS_PATH,
    parent=CORE_PATH,
    group="core",
    role="kernel-subsystem",
    update_domain="afm-runtime",
    metadata={
        "compile_mode": "one-time",
        "mutation_allowed": False,
        "execution_allowed": False,
        "dependency_policy": "sealed",
        "source_root_expected": "C:\\AFM",
    },
)

# -------------------------------------------------------------------------
# EXPLICIT PUBLIC SURFACE
# -------------------------------------------------------------------------
# Nothing is auto-imported.
# Compiler and tools must be explicitly requested by SEEDCore.

__all__ = [
    "THIS_PATH",
]
