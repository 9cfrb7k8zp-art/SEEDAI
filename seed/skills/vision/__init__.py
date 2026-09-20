# =====================================================================
# FILE: __init__.py
# PATH: seed/skills/vision/__init__.py
#
# SEED Vision Skills Package
# - Safe package marker
# - No side effects on import
# - Explicit registration only
# =====================================================================

import logging

logger = logging.getLogger("SEED.skills.vision")

SKILL_NAMESPACE = "vision"

__all__ = []


def register(registry=None):
    logger.debug("[SEED-VISION] register() invoked")
