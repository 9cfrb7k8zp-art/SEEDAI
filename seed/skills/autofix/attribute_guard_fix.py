# ==========================================================
# FILE: attribute_guard_fix.py
# PATH: seed/skills/autofix/attribute_guard_fix.py
#
# NOTES:
# - Prevents AttributeError crashes
# - Wraps unsafe attribute calls with hasattr()
# - TrackID-aware logging
# - DOES NOT invent methods
# ==========================================================

import re
import logging
from .base_fix_skill import FixSkill as BaseFixSkill

logger = logging.getLogger("AutoFix.AttributeGuard")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


class FixSkill(BaseFixSkill):
    name = "attribute_guard_fix"
    priority = 2
    description = "Guards unsafe attribute access"

    # Matches: self.attr(...) but not already guarded
    _pattern = re.compile(r"^(\s*)(self\.\w+)\((.*?)\)\s*$")

    def match(self, content: str) -> bool:
        return "AttributeError" in content or "self._" in content

    def apply(self, content: str, track_id=None) -> str:
        lines = content.splitlines()
        fixed = []

        for line in lines:
            m = self._pattern.match(line)
            if m:
                indent, call, args = m.groups()
                attr_name = call.split(".")[1]

                # Avoid double-wrapping if line is already guarded
                if "hasattr" not in line:
                    guarded = (
                        f"{indent}if hasattr(self, '{attr_name}'):\n"
                        f"{indent}    {call}({args})"
                    )
                    logger.info(f"[{self.name}] Guarded call: {call} | TrackID={track_id}")
                    fixed.append(guarded)
                    continue

            fixed.append(line)

        return "\n".join(fixed)
