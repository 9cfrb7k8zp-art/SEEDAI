# =====================================================================
# FILE: __init__.py
# PATH: seed/core/Apps/__init__.py
#
# SEED Apps Package
# - Custom folder managed by SEED-AI for Designer modules
# - Holds dynamic Apps for SEED self-reflection and feedback
# - Supports timers, cycles, and autonomous improvement loops
# - No auto-instantiation on import — safe for boot
# =====================================================================

import logging

logger = logging.getLogger("SEED.core.Apps")

# Package namespace — populated by discovery/registration
__all__ = []

# Placeholder dictionary to hold actual App classes or instances
REGISTERED_APPS = {}

def register_app(name, app_cls):
    REGISTERED_APPS[name] = app_cls
    __all__.append(name)
    logger.info(f"[SEED-APPS] Registered App: {name}")

def discover_apps():
    logger.debug("[SEED-APPS] App discovery deferred")
