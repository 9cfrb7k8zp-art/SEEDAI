# ============================================================================
# File: runtime.py
# Path: SEED_ROOT\runtime.py
# Notes:
# SEED CORE RUNTIME
# =================
# 
# This module defines the SINGLE source of truth for
# core system-wide runtime objects.
#
# Nothing in SEED may create its own:
# - EventBus
# - Scheduler
# - Identity anchor
#
# All core systems must IMPORT from here.
#
# If this file breaks, SEED does not boot.
#
# ==========================================================================


from seed.core.event_bus import SEEDEventBus

# --------------------------------------------------
# CORE EVENT BUS (SYSTEM NERVOUS SYSTEM)
# --------------------------------------------------

EVENT_BUS: SEEDEventBus = SEEDEventBus

# --------------------------------------------------
# RUNTIME STATE REGISTRY (OPTIONAL EXTENSION POINT)
# --------------------------------------------------

RUNTIME_STATE = {
    "booted": False,
    "version": "SEED-ALPHA",
}

def mark_boot_complete():
    RUNTIME_STATE["booted"] = True
