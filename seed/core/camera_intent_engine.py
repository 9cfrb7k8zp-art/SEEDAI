# ==========================================================
# FILE: camera_intent_engine.py
# PATH: SEED_ROOT/seed/core/camera_intent_engine.py
# CAMERA INTENT ENGINE – Level 1 Interpretation Layer
# VERSION: 1.2 (Track ID system + async-safe EventBus)
# UPDATED: 2025-12-28
# ==========================================================

import time
import math
import logging
from collections import deque
import uuid
import asyncio

logger = logging.getLogger("CameraIntentEngine")


def gen_track_id(prefix="CAM_INTENT"):
    """Generate a unique Track ID for each intent packet"""
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


class CameraIntentEngine:
    """
    LEVEL 1 – INTENT EXTRACTION

    Responsibilities:
      - Consume camera qbit packets (light / motion)
      - Detect intent primitives:
            * presence
            * motion_direction
            * motion_intensity
            * attention_change
      - Smooth noisy signals
      - Emit intent packets upward (Level 2+)
      - Track ID added for traceability
    """

    def __init__(
        self,
        event_bus=None,
        history_size=10,
        motion_threshold=0.02,
        attention_threshold=0.15,
    ):
        self.event_bus = event_bus
        self.motion_threshold = motion_threshold
        self.attention_threshold = attention_threshold

        # rolling buffers per camera
        self.motion_history = {}
        self.light_history = {}
        self.history_size = history_size

        # optional asyncio loop for async emits
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None

    # --------------------------------------------------
    # Public ingest API
    # --------------------------------------------------
    def ingest(self, packet: dict):
        """
        Entry point for camera qbit packets.
        Expected packet keys:
            channel, type, camera_id, value, confidence, vector, timestamp
        """
        try:
            qtype = packet.get("type")
            cam_id = packet.get("camera_id")
            ts = packet.get("timestamp", time.time())

            if not cam_id or not qtype:
                return

            if qtype == "motion":
                self._handle_motion(cam_id, packet, ts)
            elif qtype == "light":
                self._handle_light(cam_id, packet, ts)

        except Exception as e:
            logger.warning(f"[CameraIntentEngine] ingest failed: {e}")

    # --------------------------------------------------
    # MOTION → INTENT
    # --------------------------------------------------
    def _handle_motion(self, cam_id, packet, ts):
        history = self.motion_history.setdefault(
            cam_id, deque(maxlen=self.history_size)
        )

        magnitude = float(packet.get("value", 0.0))
        confidence = float(packet.get("confidence", 0.0))
        vector = packet.get("vector")

        history.append(magnitude)
        avg_motion = sum(history) / max(1, len(history))

        if avg_motion < self.motion_threshold:
            return

        direction = None
        if vector:
            dx = vector.get("dx", 0.0)
            dy = vector.get("dy", 0.0)
            direction = math.degrees(math.atan2(dy, dx))

        intent = {
            "track_id": gen_track_id("MOTION"),
            "intent": "motion_detected",
            "camera": cam_id,
            "magnitude": avg_motion,
            "direction": direction,
            "confidence": confidence,
            "timestamp": ts,
        }

        self._emit_intent(intent)

    # --------------------------------------------------
    # LIGHT → ATTENTION INTENT
    # --------------------------------------------------
    def _handle_light(self, cam_id, packet, ts):
        history = self.light_history.setdefault(
            cam_id, deque(maxlen=self.history_size)
        )

        level = float(packet.get("value", 0.0))
        confidence = float(packet.get("confidence", 0.0))

        history.append(level)

        if len(history) < 2:
            return

        delta = abs(history[-1] - history[-2])
        delta_norm = delta / max(1.0, history[-2])

        if delta_norm < self.attention_threshold:
            return

        intent = {
            "track_id": gen_track_id("ATTN"),
            "intent": "attention_change",
            "camera": cam_id,
            "delta": delta_norm,
            "confidence": confidence,
            "timestamp": ts,
        }

        self._emit_intent(intent)

    # --------------------------------------------------
    # EMIT INTENT – async-safe
    # --------------------------------------------------
    def _emit_intent(self, intent_packet: dict):
        """
        Emit Level 1 intent packet upward with track ID
        """
        logger.info(
            f"[CameraIntent] TrackID={intent_packet.get('track_id')} "
            f"{intent_packet['intent']} cam={intent_packet.get('camera')} "
            f"conf={intent_packet.get('confidence', 0):.2f}"
        )

        if self.event_bus:
            try:
                if self.loop:
                    # run async emit in existing loop
                    asyncio.run_coroutine_threadsafe(
                        self._async_emit(intent_packet),
                        self.loop
                    )
                else:
                    # fallback to synchronous emit
                    self.event_bus.emit("CAMERA_INTENT", data=intent_packet)
            except Exception as e:
                logger.warning(f"[CameraIntentEngine] Event emit failed: {e}")

    async def _async_emit(self, intent_packet: dict):
        try:
            result = self.event_bus.emit("CAMERA_INTENT", data=intent_packet)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.warning(f"[CameraIntentEngine] Async emit failed: {e}")
