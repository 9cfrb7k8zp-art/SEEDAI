# ==========================================================
# FILE: camera_integration.py
# PATH: SEED_ROOT/seed/skills/camera_integration.py
# VERSION: 1.1
# CATEGORY: Skill Integration
# PURPOSE: Integrate camera detection with CameraSkill & SparkPlugLoader
#          Fully supports Track ID system for HUD, analytics, and debugging
# UPDATED: 2025-12-28
# ==========================================================

import asyncio
import logging
import time
import uuid
from seed.skills.camera_event_handler import CameraSkill

logger = logging.getLogger("CameraIntegration")


class CameraIntegration:
    def __init__(self, sparkplug_loader, event_bus):
        self.loader = sparkplug_loader
        self.event_bus = event_bus
        self.camera_skill = CameraSkill(event_bus=self.event_bus)
        # Register the skill with SparkPlugLoader
        self.loader.register_skill(self.camera_skill, priority="high")

    # --------------------------------------------------
    # Generate a unique Track ID
    # --------------------------------------------------
    def _generate_track_id(self, prefix="CAM"):
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    # --------------------------------------------------
    # Push camera light detection
    # --------------------------------------------------
    async def push_light(self, camera_id: str, confidence: float, health: float, frame_data=None):
        track_id = self._generate_track_id("LIGHT")
        payload = {
            "camera_id": camera_id,
            "channel": "light",
            "confidence": confidence,
            "health": health,
            "frame_data": frame_data,
            "timestamp": time.time(),
            "track_id": track_id
        }
        logger.debug(f"[TRACK] CAM:LIGHT | PUSH | ID={track_id} | PRIORITY=MED | NOTE={confidence:.3f}")
        await self.loader.execute_skill(self.camera_skill.name, payload)
        if self.event_bus:
            self.event_bus.emit("CAMERA_LIGHT_PUSH", payload)

    # --------------------------------------------------
    # Push camera motion detection
    # --------------------------------------------------
    async def push_motion(self, camera_id: str, confidence: float, health: float, frame_data=None):
        track_id = self._generate_track_id("MOTION")
        payload = {
            "camera_id": camera_id,
            "channel": "motion",
            "confidence": confidence,
            "health": health,
            "frame_data": frame_data,
            "timestamp": time.time(),
            "track_id": track_id
        }
        logger.debug(f"[TRACK] CAM:MOTION | PUSH | ID={track_id} | PRIORITY=MED | NOTE={confidence:.3f}")
        await self.loader.execute_skill(self.camera_skill.name, payload)
        if self.event_bus:
            self.event_bus.emit("CAMERA_MOTION_PUSH", payload)

    # --------------------------------------------------
    # Process a detected frame (from camera loop)
    # --------------------------------------------------
    async def process_frame(self, camera_id, light_conf, motion_conf, health=1.0, frame_data=None):
        # Prioritize light events first
        await self.push_light(camera_id, light_conf, health, frame_data=frame_data)
        # Then motion
        await self.push_motion(camera_id, motion_conf, health, frame_data=frame_data)
