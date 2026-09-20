# ==========================================================
# FILE: typo_self_fix.py
# PATH: seed/skills/autofix/typo_self_fix.py
#
# NOTES:
# - Repairs common 'self' typos
# - Detects broken imports and missing files
# - Checks for file/function name conflicts
# - High confidence, high priority
# - TrackID-aware for telemetry
# - Links to BuildManager and limp mode for safe execution
# ==========================================================

import re
import logging
from pathlib import Path
from difflib import get_close_matches
from .base_fix_skill import FixSkill

logger = logging.getLogger("AutoFix.TypoSelf")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class FixSkill(FixSkill):
    name = "typo_self_fix"
    priority = 1
    description = "Fixes common 'self' typos, broken imports, and file/function conflicts"

    _patterns = [
        r"\bsekf\b",
        r"\bsefl\b",
        r"\bslef\b",
        r"\bselff\b",
    ]

    def __init__(self, seed_root: str = "C:/SEED_ROOT/seed", build_manager=None, limp_mode: bool = False):
        self.seed_root = Path(seed_root)
        self.build_manager = build_manager
        self.limp_mode = limp_mode

    # -----------------------------
    # Match function
    # -----------------------------
    def match(self, content: str) -> bool:
        return any(re.search(p, content) for p in self._patterns)

    # -----------------------------
    # Apply function
    # -----------------------------
    def apply(self, content: str, track_id=None) -> str:
        # Step 1: Fix self typos
        for p in self._patterns:
            matches = re.findall(p, content)
            if matches:
                content = re.sub(p, "self", content)
                logger.info(f"[{self.name}] Corrected {len(matches)} typos of pattern '{p}' | TrackID={track_id}")

        # Step 2: Detect broken imports
        broken_imports = self.recursive_import_check(content)
        if broken_imports:
            for b in broken_imports:
                logger.warning(f"[{self.name}] Broken import detected: {b} | TrackID={track_id}")
                # Optional: attempt auto-fix if limp_mode is off
                if not self.limp_mode:
                    suggestion = self.suggest_close_match(b)
                    if suggestion:
                        content = re.sub(rf'\b{b}\b', suggestion, content)
                        logger.info(f"[{self.name}] Auto-corrected import {b} → {suggestion} | TrackID={track_id}")

        # Step 3: Check file/function name conflicts
        conflicts = self.detect_name_conflicts(content)
        if conflicts:
            for conflict in conflicts:
                logger.warning(f"[{self.name}] File/Function conflict detected: {conflict} | TrackID={track_id}")
                if not self.limp_mode:
                    suggestion = self.suggest_close_match(conflict)
                    if suggestion:
                        content = re.sub(rf'\b{conflict}\b', suggestion, content)
                        logger.info(f"[{self.name}] Auto-corrected conflict {conflict} → {suggestion} | TrackID={track_id}")

        return content

    # -----------------------------
    # Recursive import check
    # -----------------------------
    def recursive_import_check(self, content: str, visited_files=None) -> list:
        if visited_files is None:
            visited_files = set()
        broken = []

        imports = re.findall(r'^\s*(?:import (\S+)|from (\S+) import)', content, re.MULTILINE)
        for grp in imports:
            module = grp[0] or grp[1]
            module_path = self.seed_root / module.replace(".", "/")
            py_file = module_path.with_suffix(".py")
            if not module_path.exists() and not py_file.exists():
                broken.append(module)
            elif py_file.exists() and py_file not in visited_files:
                visited_files.add(py_file)
                try:
                    with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                        sub_content = f.read()
                    broken.extend(self.recursive_import_check(sub_content, visited_files))
                except Exception:
                    broken.append(str(py_file))

        return list(set(broken))

    # -----------------------------
    # Detect file/function conflicts
    # -----------------------------
    def detect_name_conflicts(self, content: str) -> list:
        conflicts = []
        function_names = re.findall(r'def (\w+)\(', content)
        file_names = [p.stem for p in self.seed_root.glob("**/*.py")]

        for fn in function_names:
            if fn in file_names:
                conflicts.append(fn)
        return conflicts

    # -----------------------------
    # Suggest closest match for typos
    # -----------------------------
    def suggest_close_match(self, name: str) -> str:
        file_names = [p.stem for p in self.seed_root.glob("**/*.py")]
        matches = get_close_matches(name, file_names, n=1, cutoff=0.7)
        return matches[0] if matches else None
