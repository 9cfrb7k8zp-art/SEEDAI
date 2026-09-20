# ==========================================================
# FILE: hud_autofix_runner.py
# PATH: seed/skills/autofix/hud_autofix_runner.py
# VERSION: 1.0 (HUD + TrackID + SparkPlug)
# UPDATED: 2026-01-02
# ==========================================================

import asyncio
import logging
from seed.ui.hud_channel import HUDChannel
from seed.skills.autofix.base_fix_skill import AutoFixPipeline, FixSkill, ExampleFixUppercase, ExampleFixRemoveWhitespace
from seed.skills.module_registry import ModuleRegistry, handle_skill_done
from seed.skills.sparkplug import SparkPlug

logger = logging.getLogger("HUD-AutoFixRunner")
logger.setLevel(logging.INFO)

# ==========================================================
# HUD-integrated AutoFixPipeline
# ==========================================================
class HUDAutoFixRunner:
    def __init__(self, hud: HUDChannel, sparkplug: SparkPlug = None, autofix_folder: str = None):
        self.hud = hud
        self.sparkplug = sparkplug or SparkPlug(skills_root="./skills", event_bus=None)
        self.pipeline = AutoFixPipeline(
            skills=[ExampleFixUppercase(), ExampleFixRemoveWhitespace()],
            sparkplug=self.sparkplug,
            autofix_folder=autofix_folder
        )

    async def run_async(self, content: str, track_id: str = None) -> str:
        track_id = track_id or handle_skill_done(module_id="HUDAutoFixRunner")
        self.hud.publish(
            event="AUTOFIX_START",
            payload={"content": content},
            track_id=track_id,
            priority=1,
            source="HUDAutoFixRunner"
        )

        result = await self.pipeline.run_async(content, track_id=track_id)

        self.hud.publish(
            event="AUTOFIX_COMPLETE",
            payload={
                "original": content,
                "fixed": result,
                "skills_applied": list(self.pipeline.get_track_history().keys())
            },
            track_id=track_id,
            priority=1,
            source="HUDAutoFixRunner"
        )
        return result

    def run(self, content: str, track_id: str = None) -> str:
        return asyncio.run(self.run_async(content, track_id=track_id))


# ==========================================================
# Demo / Test
# ==========================================================
if __name__ == "__main__":
    hud = HUDChannel(name="AUTOFIX")
    runner = HUDAutoFixRunner(hud=hud)

    demo_text = "This   is  a HUD Demo \n\nString"

    print("=== BEFORE ===")
    print(demo_text)

    fixed_text = runner.run(demo_text, track_id="TRACK-HUD-DEMO")
    print("\n=== AFTER HUD-AUTOFIX ===")
    print(fixed_text)
