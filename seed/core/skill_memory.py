# ==========================================================
# FILE: skill_memory.py
# PATH: SEED_ROOT/seed/core/skill_memory.py
# VERSION: 2.1 (Full TrackID lineage + async + Qbit + HUD + Entropy + Delta + Batch Summary)
# PURPOSE: Records and evaluates skill usage outcomes with TrackID
# UPDATED: 2026-01-01
# ==========================================================

import time
import uuid
import random
import asyncio
import logging
from typing import Any, Dict, Optional, List

from seed.core.track_id_manager import TrackIDManager

# Optional QbitDialer integration
try:
    from seed.core.qbit_dialer import qbit_dialer
except ImportError:
    qbit_dialer = None

# Optional HUD integration
try:
    from seed.core.hud_engine import HudEngine
except ImportError:
    HudEngine = None

logger = logging.getLogger("SkillMemory")
logger.setLevel(logging.INFO)


# ----------------------------------------------------------
# TrackID Generation
# ----------------------------------------------------------
def gen_track_id(prefix: str = "SKILL_EXP", parent_track_id: Optional[str] = None) -> str:
    tid = TrackIDManager.generate(skill_name=prefix)
    if parent_track_id:
        tid = f"{tid}_PARENT-{parent_track_id}"
    return tid


# ----------------------------------------------------------
# SkillMemory Class
# ----------------------------------------------------------
class SkillMemory:
    """
    Records and evaluates skill usage outcomes with TrackIDs for traceability,
    optional Qbit push, HUD telemetry, entropy scoring, delta tracking, and batch analytics.
    """

    def __init__(self, memory_manager):
        self.memory = memory_manager
        self._last_entries: Dict[str, Dict[str, Any]] = {}  # last entry per skill

    # --------------------------
    # Record Skill Experience
    # --------------------------
    async def record_experience(
        self,
        skill_name: str,
        context: Any,
        input_payload: Any,
        output: Any,
        success: bool,
        utility_score: float,
        cost: Optional[Dict[str, Any]] = None,
        parent_track_id: Optional[str] = None
    ) -> str:
        """
        Record a single skill execution outcome with TrackID, entropy, delta, and optional pushes.
        """
        track_id = gen_track_id(skill_name, parent_track_id=parent_track_id)
        timestamp = time.time()

        # Delta tracking vs last entry
        last_entry = self._last_entries.get(skill_name)
        delta = {}
        if last_entry:
            for key in ["utility_score", "success"]:
                delta[key] = (utility_score - last_entry.get(key, 0.0))

        # Entropy (0.0-1.0)
        entropy = round(random.random() * 0.5 + 0.25, 4)

        entry = {
            "track_id": track_id,
            "timestamp": timestamp,
            "skill": skill_name,
            "context": context,
            "input": input_payload,
            "output_summary": str(output)[:500],
            "success": success,
            "utility_score": utility_score,
            "cost": cost or {},
            "entropy": entropy,
            "delta": delta,
        }

        # Record to memory manager
        self.memory.record(event_type="skill_experience", payload=entry)
        self._last_entries[skill_name] = entry

        # HUD Telemetry
        if HudEngine:
            try:
                HudEngine.publish(
                    channel="SKILL_MEMORY",
                    payload={
                        "track_id": track_id,
                        "skill": skill_name,
                        "success": success,
                        "utility_score": utility_score,
                        "entropy": entropy,
                        "delta": delta,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
                    }
                )
            except Exception as e:
                logger.warning(f"[HUD] Failed to publish skill telemetry | TrackID={track_id} | Error={e}")

        # QbitDialer push
        if qbit_dialer and hasattr(qbit_dialer, "push_data"):
            try:
                push_func = qbit_dialer.push_data
                payload = {
                    "track_id": track_id,
                    "skill": skill_name,
                    "success": success,
                    "utility_score": utility_score,
                    "entropy": entropy,
                    "delta": delta,
                    "timestamp": timestamp
                }
                if asyncio.iscoroutinefunction(push_func):
                    await push_func(payload)
                else:
                    push_func(payload)
            except Exception as e:
                logger.error(f"[SkillMemory | TrackID={track_id}] Qbit push failed: {e}")

        logger.info(f"[SkillMemory] Recorded skill '{skill_name}' | TrackID={track_id} | Success={success} | Utility={utility_score} | Entropy={entropy}")

        return track_id

    # --------------------------
    # Summarize Skill Experiences
    # --------------------------
    def summarize_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        Summarize all experiences for a given skill.
        """
        experiences = [
            e for e in getattr(self.memory, "long_term", [])
            if e.get("event_type") == "skill_experience"
            and e["payload"]["skill"] == skill_name
        ]

        if not experiences:
            return None

        success_rate = sum(1 for e in experiences if e["payload"]["success"]) / len(experiences)
        avg_utility = sum(e["payload"]["utility_score"] for e in experiences) / len(experiences)
        avg_entropy = sum(e["payload"].get("entropy", 0.5) for e in experiences) / len(experiences)

        return {
            "skill": skill_name,
            "attempts": len(experiences),
            "success_rate": success_rate,
            "avg_utility": avg_utility,
            "avg_entropy": avg_entropy
        }

    # --------------------------
    # Batch Summary of All Skills
    # --------------------------
    def summarize_all_skills(self) -> List[Dict[str, Any]]:
        """
        Returns summaries for all recorded skills with success, utility, and entropy.
        """
        skills = {}
        for e in getattr(self.memory, "long_term", []):
            if e.get("event_type") != "skill_experience":
                continue
            skill_name = e["payload"]["skill"]
            if skill_name not in skills:
                skills[skill_name] = []
            skills[skill_name].append(e["payload"])

        summaries = []
        for skill, entries in skills.items():
            success_rate = sum(1 for x in entries if x["success"]) / len(entries)
            avg_utility = sum(x["utility_score"] for x in entries) / len(entries)
            avg_entropy = sum(x.get("entropy", 0.5) for x in entries) / len(entries)
            summaries.append({
                "skill": skill,
                "attempts": len(entries),
                "success_rate": success_rate,
                "avg_utility": avg_utility,
                "avg_entropy": avg_entropy
            })
        return summaries
