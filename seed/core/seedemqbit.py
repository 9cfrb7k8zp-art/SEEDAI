# ==========================================================
# FILE: seedemqbit.py
# PATH: SEED_ROOT/seed/core/seedemqbit.py
# SEEDEMQbit – Camera Qbit Ingest (Thread-Safe, Async-Safe)
# Track ID integrated for full traceability
# ==========================================================

import cv2
import time
import threading
import logging
import numpy as np
import asyncio
import uuid

from seed.core.hud_adapter import HUDPushAdapter  # <--- patch integration
from seed.core.sparkplug_loader import TrackContext

logger = logging.getLogger("SEEDEMQbit")


# ==========================================================
# Track ID helper
# ==========================================================
def gen_track_id(prefix="QBIT"):
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


class SEEDEMQbit:
    SUPPORTED_QBITS = ["light_qbit", "motion_qbit"]

    def __init__(self, qbit_dialer, event_bus=None, hud_interface=None, fat_layer=None):
        self.qbit_dialer = qbit_dialer
        self.event_bus = event_bus
        self.fat_layer = fat_layer

        self.hud = HUDPushAdapter(hud_interface) if hud_interface else None

        self.running = False
        self.thread = None
        self.cameras = {}
        self._qbit_callbacks = []  # list of registered callbacks
        self._prev_frames = {}     # for motion detection

        self._detect_cameras()

    # -----------------------------
    # Callback management
    # -----------------------------
    def set_qbit_callback(self, callback):
        self._qbit_callbacks = [callback]

    def add_qbit_callback(self, callback):
        if callback not in self._qbit_callbacks:
            self._qbit_callbacks.append(callback)

    # -----------------------------
    # Camera detection
    # -----------------------------
    def _detect_cameras(self, max_devices=4):
        for i in range(max_devices):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                cam_id = f"CAM_{i}"
                self.cameras[cam_id] = cap
                logger.info(f"[SEEDEMQbit] Found camera: {cam_id}")
            else:
                cap.release()

    # -----------------------------
    # Start / stop loop
    # -----------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(
            target=self._camera_loop_thread,
            name="SEEDEMQbit-CameraThread",
            daemon=True,
        )
        self.thread.start()
        logger.info("[SEEDEMQbit] Camera tracking loop started")

    def stop(self):
        self.running = False
        for cap in self.cameras.values():
            try:
                cap.release()
            except Exception:
                pass
        logger.info("[SEEDEMQbit] Camera tracking stopped")

    # -----------------------------
    # Camera loop
    # -----------------------------
    def _camera_loop_thread(self):
        while self.running:
            for cam_id, cap in list(self.cameras.items()):
                try:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        continue
                    self._process_frame(cam_id, frame)
                except Exception as e:
                    logger.warning(f"[SEEDEMQbit] Camera error ({cam_id}): {e}")
            time.sleep(0.03)  # ~30 FPS

    # -----------------------------
    # Process frame into Qbits
    # -----------------------------
    def _process_frame(self, cam_id, frame):
        timestamp = time.time()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ---- Light Qbit ----
        mean_intensity = float(np.mean(gray))
        light_qbit = {
            "type": "light_qbit",
            "camera_id": cam_id,
            "timestamp": timestamp,
            "freq": mean_intensity % 120.0,
            "amp": 1.0,
            "phase": 0.0,
            "_track_id": gen_track_id("LIGHT")
        }

        # ---- Motion Qbit ----
        motion_val = 0.0
        if cam_id in self._prev_frames:
            prev_gray = self._prev_frames[cam_id]
            motion_val = float(np.sum(cv2.absdiff(prev_gray, gray))) / gray.size
        self._prev_frames[cam_id] = gray
        motion_qbit = {
            "type": "motion_qbit",
            "camera_id": cam_id,
            "timestamp": timestamp,
            "motion": motion_val,
            "_track_id": gen_track_id("MOTION")
        }

        # Emit both Qbits
        for qbit in [light_qbit, motion_qbit]:
            self._emit_qbit(cam_id, qbit)

    # -----------------------------
    # Emit a single Qbit to all systems
    # -----------------------------
    def _emit_qbit(self, cam_id, qbit_data):
        # Push TrackContext for this Qbit
        track_id, parent_id = TrackContext.push(cam_id)
        qbit_data["_parent_track_id"] = parent_id or None

        fat_entry = {
            "type": qbit_data["type"],
            "source": cam_id,
            "label": f"{qbit_data['type']}_frame",
            "data": qbit_data,
            "timestamp": time.time(),
            "_track_id": qbit_data.get("_track_id"),
        }

        # FAT log
        if self.fat_layer:
            try:
                self.fat_layer.append_log(qbit_data, source="camera", label=qbit_data["type"])
            except Exception as e:
                logger.warning(f"[SEEDEMQbit] FAT append failed: {e}")

        # HUD push (safe)
        if self.hud:
            try:
                self.hud.push({"type": qbit_data["type"], "data": fat_entry})
            except Exception as e:
                logger.warning(f"[SEEDEMQbit] HUD push failed: {e}")

        # Event bus
        if self.event_bus:
            try:
                self.event_bus.emit("ANALYTICS_UPDATED", data={"qbit_data": qbit_data, "source": cam_id})
            except Exception as e:
                logger.warning(f"[SEEDEMQbit] Event bus publish failed: {e}")

        # Qbit dialer + callbacks
        try:
            if hasattr(self.qbit_dialer, "inject"):
                self.qbit_dialer.inject(qbit_data["type"], qbit_data.get("freq", qbit_data.get("motion", 0.0)))

            for cb in self._qbit_callbacks:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(qbit_data))
                else:
                    cb(qbit_data)
        except Exception as e:
            logger.warning(f"[SEEDEMQbit] Qbit ingest/callback failed: {e}")

        TrackContext.pop()
