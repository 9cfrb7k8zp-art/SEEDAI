# ==========================================================
# FILE: typo_self_fix_dictionary.py
# PATH: seed/skills/autofix/typo_self_fix_dictionary.py
#
# VERSION: 1.0 – Full Human Error Mitigation + Traceback Linking
# UPDATED: 2025-12-31
# NOTES:
# - Wide dictionary of common Python syntax & human errors
# - Can trace broken imports and method/property references
# - TrackID-aware, supports Limp Mode and BuildManager
# - Integrates with AutoFix / SparkPlug pipelines
# ==========================================================

import re
import os
import logging
import traceback
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("AutoFix.Dictionary")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class TypoSelfDictionary:

    def __init__(self, seed_root="./SEED_ROOT"):
        self.seed_root = Path(seed_root or r"C:\SEED_ROOT\seed")
        self.self_typos = [
            r"\bsekf\b",
            r"\bsefl\b",
            r"\bslef\b",
            r"\bselff\b",
        ]
        self.syntax_typos = {
            r"\bdefn\b": "def",
            r"\bretun\b": "return",
            r"\bclas\b": "class",
            r"\bimprot\b": "import",
            r"\bprnit\b": "print",
            r"\bforr\b": "for",
            r"\biff\b": "if",
            r"\belsee\b": "else",
            r"\belif\b": "elif",
            r"\bwhilee\b": "while",
            r"\btru\b": "True",
            r"\bfals\b": "False",
            r"\bnon\b": "None",
        }

        self.colon_pattern = re.compile(r"(def .+\)|class .+)(\s*)$")
        self.indent_pattern = re.compile(r"^\s+[^ \t]")

    # -----------------------------
    # Detect issues in content
    # -----------------------------
    def detect_issues(self, content: str) -> List[str]:
        issues = []

        for p in self.self_typos:
            if re.search(p, content):
                issues.append(f"self typo: {p}")

        for pattern, _ in self.syntax_typos.items():
            if re.search(pattern, content):
                issues.append(f"syntax typo: {pattern}")

        if re.search(self.colon_pattern, content, flags=re.MULTILINE):
            issues.append("missing colon")

        if re.search(self.indent_pattern, content, flags=re.MULTILINE):
            issues.append("indentation issue")

        return issues

    # -----------------------------
    # Apply fixes to content
    # -----------------------------
    def apply_fixes(
        self,
        content: str,
        track_id: Optional[str] = None,
        limp_mode: bool = False,
        build_manager=None,
    ) -> str:
        fixes_applied = 0

        # Fix self typos
        for p in self.self_typos:
            matches = re.findall(p, content)
            if matches:
                content = re.sub(p, "self", content)
                fixes_applied += len(matches)
                logger.info(f"[Dictionary] Fixed {len(matches)} 'self' typos | TrackID={track_id}")

        # Fix syntax typos
        for pattern, replacement in self.syntax_typos.items():
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                fixes_applied += len(matches)
                logger.info(f"[Dictionary] Fixed {len(matches)} keyword typos: '{pattern}' -> '{replacement}' | TrackID={track_id}")

        # Add missing colons
        def colon_fix(match):
            return f"{match.group(1)}:"

        colon_matches = re.findall(self.colon_pattern, content, flags=re.MULTILINE)
        if colon_matches:
            content = re.sub(self.colon_pattern, colon_fix, content, flags=re.MULTILINE)
            fixes_applied += len(colon_matches)
            logger.info(f"[Dictionary] Added {len(colon_matches)} missing colons | TrackID={track_id}")

        # Normalize indentation
        lines = content.splitlines()
        content = "\n".join([line.expandtabs(4) for line in lines])

        # Limp Mode - conservative application
        if limp_mode:
            logger.info(f"[Dictionary] Limp mode active | TrackID={track_id}")
            logger.info(f"[Dictionary] Detected {fixes_applied} issues, applying cautiously in limp mode.")

        # BuildManager integration
        if build_manager:
            build_manager.queue_task(
                task_name="typo_self_fix_dictionary",
                description="AutoFix human errors & syntax issues",
                track_id=track_id,
                limp_mode=limp_mode,
                fixes_applied=fixes_applied,
            )
            logger.info(f"[Dictionary] Queued in BuildManager | TrackID={track_id}")

        return content

    # -----------------------------
    # Follow import paths and detect broken links
    # -----------------------------
    def find_broken_imports(self, content: str) -> List[str]:
        broken = []
        imports = re.findall(r"import (\S+)|from (\S+) import", content)
        for group in imports:
            module = group[0] or group[1]
            try:
                path = self.seed_root / module.replace(".", "/")
                if not path.exists() and not any((path.with_suffix(".py")).exists() for path in [path]):
                    broken.append(module)
            except Exception as e:
                logger.warning(f"[Dictionary] Could not resolve import {module}: {e}")
        return broken

    # -----------------------------
    # Traceback analysis for broken references
    # -----------------------------
    def analyze_traceback(self, tb: str) -> List[str]:
        broken_files = []
        lines = tb.splitlines()
        for line in lines:
            match = re.search(r'File "(.+\.py)"', line)
            if match:
                file_path = match.group(1)
                if not Path(file_path).exists():
                    broken_files.append(file_path)
        return broken_files

    # -----------------------------
    # Recursively follow imports to check all linked files
    # -----------------------------
    def recursive_import_check(self, file_path: str, visited=None) -> List[str]:
        if visited is None:
            visited = set()
        broken = []

        if file_path in visited:
            return broken
        visited.add(file_path)

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"[Dictionary] Cannot open {file_path}: {e}")
            broken.append(file_path)
            return broken

        # Check imports
        imports = re.findall(r"import (\S+)|from (\S+) import", content)
        for group in imports:
            module = group[0] or group[1]
            module_path = self.seed_root / module.replace(".", "/")
            py_file = module_path.with_suffix(".py")
            if not module_path.exists() and not py_file.exists():
                broken.append(module)
            else:
                next_path = py_file if py_file.exists() else module_path
                broken.extend(self.recursive_import_check(str(next_path), visited))

        return list(set(broken))
