# ==========================================================
# FILE: log_light_skill.py
# PATH: SEED_ROOT/seed/skills/log_light_skill.py
# VERSION: 1.3 (Track-native | Async-safe | HUD-compatible)
# UPDATED: 2026-01-02
#
# Skill: log_light_skill
# Logs light scan events from LightScanSkill with SEED Track IDs
# ==========================================================

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

from seed.core.track_context import TrackContext
from seed.core.tracked_data import TrackedData

logger = logging.getLogger("HUDLightLogger")
logger.setLevel(logging.INFO)

# ==========================================================
# Core async skill
# ==========================================================
async def LightLogger (event_payload: Dict[str, Any]) -> Dict[str, Any]:
    # --------------------------
    # Bind track context (HUD-visible)
    # --------------------------
    with TrackContext.bind(domain="S", channel="hud.light"):
        track_id = TrackedData.generate_track_id(
            category="LightScan",
            domain="S",
            stream_type="IN",
            parent_id=TrackContext.current(),
            channels="hud.light",
            emit_hud=True
        )

        try:
            camera_id = event_payload.get("camera_id", "CAM_UNKNOWN")
            intensity = float(event_payload.get("avg_intensity", 0.0))
            motion = float(event_payload.get("motion_level", 0.0))
            objects_detected = int(event_payload.get("objects_detected", 0))
            mode = event_payload.get("mode", "default")
            timestamp = event_payload.get("timestamp") or datetime.utcnow().isoformat()

            logger.info(
                "[log_light_skill] "
                f"track_id={track_id} "
                f"camera={camera_id} "
                f"intensity={intensity:.2f} "
                f"motion={motion:.2f} "
                f"objects={objects_detected} "
                f"mode={mode} "
                f"time={timestamp}"
            )

            # Attach track_id back to payload (non-destructive)
            event_payload = dict(event_payload)
            event_payload["track_id"] = track_id

            return {
                "status": "logged",
                "track_id": track_id,
                "payload": event_payload
            }

        except Exception as e:
            logger.exception(
                f"[log_light_skill] track_id={track_id} FAILED: {e}"
            )
            return {
                "status": "error",
                "track_id": track_id,
                "message": str(e)
            }

# ==========================================================
# Skill loader entry (SparkPlug / EventBus safe)
# ==========================================================
def run(event_payload=None):
    if event_payload is None:
        return log_light_skill

    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(log_light_skill(event_payload))
    except RuntimeError:
        # No loop → safe one-shot execution
        return asyncio.run(log_light_skill(event_payload))

# ==========================================================
# EXPORTS
# ==========================================================
__all__ = [
    "log_light_skill",
    "run"
]

# ==========================================================
# END OF FILE
# ==========================================================
