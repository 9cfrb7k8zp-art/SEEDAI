# ==========================================================
# FILE: skills_runtime.py
# PATH: SEED_ROOT/seed/skills/skills_runtime.py
# VERSION: 1.0.1
# PURPOSE: Bounded skill discovery and authoritative runtime binding
# ==========================================================

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent
EXCLUDED_DIRS = {"__pycache__", "_archive", "inbox", "outbox", "autofix", "vision", "Quantum_Linux"}


def discover_skills(max_files: int = 250) -> Dict[str, Any]:
    result: Dict[str, Any] = {"skills": [], "errors": [], "count": 0}
    for path in sorted(ROOT.rglob("*.py")):
        if len(result["skills"]) >= max_files or any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            names = [n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
            result["skills"].append({"name": path.stem, "path": str(path), "symbols": names})
        except Exception as exc:
            result["errors"].append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    result["count"] = len(result["skills"])
    return result


def bind_runtime(skill: Any, **runtime):
    """Bind only authorities accepted by the skill's adapter; never create them."""
    binder = getattr(skill, "bind_runtime", None)
    if not callable(binder):
        return skill
    try:
        return binder(**runtime)
    except TypeError:
        allowed = {
            k: runtime[k]
            for k in (
                "event_bus",
                "actuator_engine",
                "sparkplug",
                "qbit_dialer",
                "track_system",
                "registry",
                "channel_manager",
                "channel_id",
                "nodes",
                "oracle",
            )
            if k in runtime
        }
        return binder(**allowed)
