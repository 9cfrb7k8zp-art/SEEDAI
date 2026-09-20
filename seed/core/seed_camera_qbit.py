# ==========================================================
# FILE: seed_camera_qbit.py
# PATH: SEED_ROOT/seed/core/seed_camera_qbit.py
#
# SEED AI OS — Camera Qbit Integration
# VERSION: 6.1.0 (QBIT-CLEAN | NUMERIC-ONLY | EVENTBUS-PRIMARY)
# UPDATED: 2026-01-05
# ==========================================================

import cv2
import asyncio
import logging
import threading
import time
import platform
from dataclasses import dataclass, field
from uuid import uuid4
from typing import Any, Callable, Dict, List, Optional
from collections import deque

import numpy as np
import psutil

from seed.core.tracked_data import TrackedData
from seed.core.channel_id import ChannelID

logger = logging.getLogger("SEEDCameraQbit")
logger.setLevel(logging.INFO)

# ==========================================================
# Helpers
# ==========================================================
def gen_track_id(prefix="CAM"):
    return f"{prefix}-{uuid4().hex[:8]}"

def numericize(value):
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        return {k: numericize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [numericize(v) for v in value]
    return 0.0

# ==========================================================
# Optional YOLO
# ==========================================================
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("[CameraQbit] YOLO not installed")

# ==========================================================
# Camera Info
# ==========================================================
@dataclass
class CameraInfo:
    cam_id: str
    source_index: int
    capture: Optional[cv2.VideoCapture] = None
    last_frame_time: float = field(default_factory=time.time)
    last_push_time: float = 0.0
    connected: bool = True
    failure_count: int = 0

# ==========================================================
# Camera Skill Engine
# ==========================================================
class CameraSkillEngine:
    def __init__(self):
        self.bg = cv2.createBackgroundSubtractorMOG2()
        self.detector = None
        self.gpu_enabled = False

    def enable_gpu(self):
        if YOLO_AVAILABLE and not self.detector:
            try:
                self.detector = YOLO("yolov8n.pt").to("cuda")
                self.gpu_enabled = True
                logger.info("[CameraSkillEngine] GPU enabled")
            except Exception as e:
                logger.warning(f"[CameraSkillEngine] GPU init failed: {e}")

    def process(self, frame: np.ndarray) -> Dict[str, float]:
        fg = self.bg.apply(frame)
        return {
            "avg_intensity": float(frame.mean()),
            "std": float(frame.std()),
            "motion": float(fg.mean()),
        }

# ==========================================================
# SEED Camera Qbit
# ==========================================================
class SEEDCameraQbit:
    """
    Camera → EventBus → QbitDialer bridge
    Sensor-only. Numeric-only output.
    """

    def __init__(
        self,
        storage_root: str = "./SEED_ROOT",
        event_bus=None,
        qbit_dialer=None,
        max_cameras: int = 4,
        poll_interval: float = 0.05,
        push_interval: float = 0.25,
    ):
        self.storage_root = storage_root
        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer

        self.max_cameras = max_cameras
        self.poll_interval = poll_interval
        self.push_interval = push_interval

        self.cameras: Dict[int, CameraInfo] = {}
        self.frame_buffer = deque(maxlen=64)

        self.skill_engine = CameraSkillEngine()

        self._running = False
        self.os_boot_complete = False
        self.os_stable = False
        self._last_camera_discovery = 0.0
        self.camera_discovery_interval = 30.0

        self._thread = threading.Thread(
            target=self._camera_loop,
            daemon=True,
            name="SEEDCameraQbitLoop",
        )

        ChannelID.register(
            "CAMERA",
            controller="SENSOR",
            metadata={"numeric_only": True}
        )

        self._register_boot_autostart()
        logger.info("[CameraQbit] Initialized")

    # ======================================================
    # Boot
    # ======================================================
    def _register_boot_autostart(self):
        try:
            system = platform.system().lower()
            logger.info(f"[CameraQbit] Boot target: {system}")
        except Exception as e:
            logger.warning(f"[CameraQbit] Boot registration failed: {e}")

    def mark_boot_complete(self):
        self.os_boot_complete = True

    def mark_os_stable(self):
        if not self.os_stable:
            self.os_stable = True
            self.skill_engine.enable_gpu()

    # ======================================================
    # Control
    # ======================================================
    def start(self):
        if not self._thread.is_alive():
            self._running = True
            self._thread.start()
            logger.info("[CameraQbit] Camera thread started")

    def stop(self):
        self._running = False
        for cam in self.cameras.values():
            try:
                if cam.capture:
                    cam.capture.release()
            except Exception:
                pass
        logger.info("[CameraQbit] Stopped")

    # ======================================================
    # Camera Loop
    # ======================================================
    def _camera_loop(self):
        logger.info("[CameraQbit] Waiting for OS boot")
        while not self.os_boot_complete:
            time.sleep(1)

        logger.info("[CameraQbit] Boot complete")

        while self._running:
            now = time.time()
            if now - self._last_camera_discovery >= self.camera_discovery_interval:
                self._discover_cameras()
                self._last_camera_discovery = now

            for cam in list(self.cameras.values()):
                if not cam.capture or not cam.connected:
                    continue

                ret, frame = cam.capture.read()
                if not ret:
                    cam.connected = False
                    cam.failure_count += 1
                    continue

                meta = self.skill_engine.process(frame)

                vector = {
                    "camera": cam.cam_id,
                    "timestamp": float(now),
                    "features": meta,
                }

                numeric_vector = numericize(vector)
                self.frame_buffer.append(numeric_vector)

                self._emit_event(numeric_vector)

                if now - cam.last_push_time >= self.push_interval:
                    cam.last_push_time = now

            time.sleep(self.poll_interval)

    # ======================================================
    # Discovery
    # ======================================================
    def _discover_cameras(self):
        for i in range(self.max_cameras):
            if i in self.cameras:
                continue

            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                self.cameras[i] = CameraInfo(
                    cam_id=f"CAM_{i}",
                    source_index=i,
                    capture=cap,
                )
                logger.info(f"[CameraQbit] Camera {i} connected")

    # ======================================================
    # Event Emission (ONLY PATH TO QBIT)
    # ======================================================
    def _emit_event(self, numeric_vector: Dict[str, Any]):
        if not self.event_bus:
            return

        td = TrackedData(
            payload=numeric_vector,
            data=numeric_vector,
            channel="CAMERA",
            source_id="SEEDCameraQbit",
            track_id=gen_track_id(),
        )

        publish = getattr(self.event_bus, "publish", None)
        emit = getattr(self.event_bus, "emit", None)
        try:
            if callable(publish):
                publish("CAMERA_FRAME", payload=td)
            elif callable(emit):
                emit("CAMERA_FRAME", td)
        except Exception as exc:
            logger.debug("[CameraQbit] EventBus frame emission skipped | error=%s", exc)

        dialer = self.qbit_dialer
        push_data = getattr(dialer, "push_data", None) if dialer is not None else None
        if callable(push_data):
            try:
                frame = dict(numeric_vector)
                frame["vision"] = True
                frame["source"] = "SEEDCameraQbit"
                loop = getattr(dialer, "loop", None)
                if loop is not None and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        push_data(frame=frame, track_id=td.track_id),
                        loop,
                    )
            except Exception as exc:
                logger.debug("[CameraQbit] QbitDialer frame bridge skipped | error=%s", exc)

    # ======================================================
    # Status
    # ======================================================
    def get_status(self) -> Dict[str, Any]:
        return {
            "running": float(self._running),
            "camera_count": float(len(self.cameras)),
            "buffer_size": float(len(self.frame_buffer)),
            "cpu": float(psutil.cpu_percent()),
            "mem": float(psutil.virtual_memory().percent),
            "boot": float(self.os_boot_complete),
            "stable": float(self.os_stable),
        }
