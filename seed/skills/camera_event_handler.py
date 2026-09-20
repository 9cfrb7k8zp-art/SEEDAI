# ==========================================================
# FILE: camera_event_handler.py
# PATH: SEED_ROOT/seed/skills/camera_event_handler.py
# VERSION: 1.0 (Camera Skill + Async-safe EventBus integration)
# CATEGORY: Skill
# PURPOSE: Handle camera events and push to EventBus safely
# UPDATED: 2025-12-27
# ==========================================================

import asyncio
import threading
import logging
import time

logger = logging.getLogger("CameraSkill")


class CameraSkill:
    name = "camera_skill"

    def __init__(self, event_bus=None):
        self.event_bus = event_bus

    # --------------------------------------------------
    # SEED Skill async entry point
    # --------------------------------------------------
    async def execute_async(self, payload):
        """
        Executes the skill with the provided payload.
        Payload example:
            {
                "camera_id": "CAM_0",
                "channel": "light",
                "confidence": 0.987,
                "health": 1.0
            }
        """
        camera_id = payload.get("camera_id", "CAM_UNKNOWN")
        channel = payload.get("channel", "unknown")
        confidence = payload.get("confidence", 0.0)
        health = payload.get("health", 1.0)
        timestamp = payload.get("timestamp", time.time())

        event_payload = {
            "camera_id": camera_id,
            "channel": f"{camera_id}.{channel}",
            "confidence": confidence,
            "health": health,
            "timestamp": timestamp
        }

        await self._safe_emit(f"{camera_id}.{channel}", event_payload)

    # --------------------------------------------------
    # Async-safe EventBus emit
    # --------------------------------------------------
    async def _safe_emit(self, event_name, payload):
        if not self.event_bus:
            logger.warning(f"[CameraSkill] No EventBus assigned. Cannot emit '{event_name}'")
            return

        try:
            loop = asyncio.get_running_loop()
            if asyncio.iscoroutinefunction(self.event_bus.emit):
                # async emit
                asyncio.create_task(self.event_bus.emit(event_name, payload))
            else:
                # sync emit → thread
                threading.Thread(target=lambda: self.event_bus.emit(event_name, payload), daemon=True).start()
        except RuntimeError:
            # loop not running → fallback to thread
            threading.Thread(target=lambda: self.event_bus.emit(event_name, payload), daemon=True).start()
        except Exception as e:
            logger.warning(f"[CameraSkill] Failed safe emit '{event_name}': {e}")

    # --------------------------------------------------
    # Helper: push light event
    # --------------------------------------------------
    async def push_light(self, camera_id: str, confidence: float, health: float):
        payload = {
            "camera_id": camera_id,
            "channel": "light",
            "confidence": confidence,
            "health": health,
            "timestamp": time.time()
        }
        await self._safe_emit(f"{camera_id}.light", payload)

    # --------------------------------------------------
    # Helper: push motion event
    # --------------------------------------------------
    async def push_motion(self, camera_id: str, confidence: float, health: float):
        payload = {
            "camera_id": camera_id,
            "channel": "motion",
            "confidence": confidence,
            "health": health,
            "timestamp": time.time()
        }
        await self._safe_emit(f"{camera_id}.motion", payload)
