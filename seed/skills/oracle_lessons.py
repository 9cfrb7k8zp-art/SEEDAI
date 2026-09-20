# ==========================================================
# FILE: oracle_lessons.py
# PATH: SEED_ROOT/seed/skills/oracle_lessons.py
# VERSION: 1.0.0
# PURPOSE: Oracle lesson plans for SEED keyboard + Seed Mouse practice
# SAFETY: lesson generation only; no OS input injection or autonomous control
# ==========================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from seed.skills.skill_base import SkillBase


class OracleLessonSkill(SkillBase):
    """Produces bounded, repeatable lessons that SEED can study and practice."""

    def __init__(self, oracle=None, writer=None, qbit_dialer=None, **kwargs):
        super().__init__(name="OracleLessonSkill", **kwargs)
        self.oracle = oracle
        self.writer = writer
        self.qbit_dialer = qbit_dialer

    def bind_oracle(self, oracle):
        self.oracle = oracle
        return self

    def bind_writer(self, writer):
        self.writer = writer
        return self

    def make_lesson(self, topic: str = "keyboard", level: str = "beginner") -> Dict[str, Any]:
        topic_l = topic.lower()
        if "mouse" in topic_l or "seed mouse" in topic_l:
            steps = [
                {"step": 1, "skill": "move", "practice": "move pointer to a visible target"},
                {"step": 2, "skill": "left_click", "practice": "single-click a target"},
                {"step": 3, "skill": "double_click", "practice": "double-click a file target"},
                {"step": 4, "skill": "right_click", "practice": "open a context menu"},
                {"step": 5, "skill": "drag", "practice": "drag a selection between two targets"},
                {"step": 6, "skill": "scroll", "practice": "scroll up and down and return to the target"},
            ]
        else:
            steps = [
                {"step": 1, "skill": "typing", "practice": "type: SEED AI"},
                {"step": 2, "skill": "selection", "practice": "SHIFT + arrow keys"},
                {"step": 3, "skill": "copy_paste", "practice": "CTRL+C then CTRL+V"},
                {"step": 4, "skill": "save", "practice": "CTRL+S"},
                {"step": 5, "skill": "navigation", "practice": "TAB and SHIFT+TAB"},
                {"step": 6, "skill": "editing", "practice": "HOME, END, BACKSPACE, DELETE"},
            ]
        return {"source": "Oracle", "topic": topic, "level": level,
                "objective": "learn the interaction as a repeatable SEED skill",
                "steps": steps, "execution": "user_controlled"}

    async def execute(self, payload: Dict[str, Any], track_id: str):
        return self.make_lesson(payload.get("topic", "keyboard"), payload.get("level", "beginner"))

    def save_lesson(self, lesson: Dict[str, Any], filename: str = "oracle_lesson.json") -> Path:
        if self.writer is not None:
            return self.writer.write_file(filename, json.dumps(lesson, indent=2))
        path = Path(__file__).resolve().parent / "outbox" / filename
        path.write_text(json.dumps(lesson, indent=2), encoding="utf-8")
        return path
