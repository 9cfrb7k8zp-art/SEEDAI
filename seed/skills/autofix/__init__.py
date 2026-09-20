# ==========================================================
# FILE: __init__.py
# PATH: seed/skills/autofix/__init__.py
#
# NOTES:
# - Marks autofix as a skill namespace
# - FixSkill modules are auto-discovered
# - Adds smarter labeling, dynamic file categorization
# - Sorts skills by label: User-'U', System-'S', SEEDCore AI-'SC'
# - Does NOT contain processing logic
# ==========================================================

import os
import importlib
import logging

logger = logging.getLogger("AutoFixNamespace")
logger.setLevel(logging.INFO)

# Base skill modules
__all__ = [
    "base_fix_skill",
    "typo_self_fix",
    "attribute_guard_fix",
    "import_repair_fix",
]

# --------------------------------------------------
# Smart labeling / file organizer
# --------------------------------------------------
def get_skill_label(module_name: str) -> str:
    """
    Returns a label based on naming conventions:
    - User-created: starts with 'user_' -> 'U'
    - System core: starts with 'system_' -> 'S'
    - SEEDCore AI: starts with 'seedcore_' -> 'SC'
    """
    lname = module_name.lower()
    if lname.startswith("user_"):
        return "U"
    elif lname.startswith("system_"):
        return "S"
    elif lname.startswith("seedcore_") or lname in ["base_fix_skill", "typo_self_fix", "attribute_guard_fix", "import_repair_fix"]:
        return "SC"
    return "U"  # default to User

# --------------------------------------------------
# Dynamic module discovery & sorted list
# --------------------------------------------------
def discover_skills(base_path=None):
    """
    Discover and sort FixSkill modules dynamically.
    Returns a list of (module_name, label) tuples.
    """
    base_path = base_path or os.path.dirname(__file__)
    skills = []

    for fname in os.listdir(base_path):
        if fname.endswith(".py") and not fname.startswith("_"):
            mod_name = fname[:-3]
            try:
                importlib.import_module(f".{mod_name}", package="seed.skills.autofix")
                label = get_skill_label(mod_name)
                skills.append((mod_name, label))
            except Exception as e:
                logger.warning(f"[AutoFix] Failed to import {mod_name}: {e}")

    # Sort: SC > S > U, then alphabetically
    label_priority = {"SC": 0, "S": 1, "U": 2}
    skills.sort(key=lambda x: (label_priority.get(x[1], 99), x[0]))
    return skills

# --------------------------------------------------
# Runtime accessible lists
# --------------------------------------------------
# List of tuples: (module_name, label)
discovered_skills = discover_skills()

# Separate lists per label
user_skills = [m for m, l in discovered_skills if l == "U"]
system_skills = [m for m, l in discovered_skills if l == "S"]
seedcore_skills = [m for m, l in discovered_skills if l == "SC"]

logger.info(f"[AutoFix] Discovered skills: {discovered_skills}")
logger.info(f"[AutoFix] User Skills: {user_skills}")
logger.info(f"[AutoFix] System Skills: {system_skills}")
logger.info(f"[AutoFix] SEEDCore AI Skills: {seedcore_skills}")
