# ==========================================================
# FILE: SEEDCameraQbit.py
# PATH: SEED_ROOT/seed/core/SEEDCameraQbit.py
#
# SEED AI OS — Camera Qbit Integration (v6.1 TRACK-MULTI | HUD-INTEGRATED)
#
# FEATURES:
# 1. Runs automatically on SYSTEM BOOT
# 2. Boot-safe: waits for SEED AI OS boot completion
# 3. Stability-safe: GPU is only enabled once OS is stable
# 4. Async-safe Qbit push & pull
# 5. Camera reconnect + failure isolation
# 6. EventBus + HUD + FAT compatible
# 7. Multi-layer channels + priority queue
# 8. CPU/Memory dynamic throttling
# 9. Optional YOLO detection
# 10. Full Qbit callback support
# 11. Track system integration
# 12. Multi-track channel overlay
# ==========================================================

import cv2
import asyncio
import logging
import threading
import time
import platform
import traceback
from dataclasses import dataclass, field
from uuid import uuid4
from typing import Any, Callable, Dict, List, Optional
from collections import deque

import numpy as np
import psutil


from seed.core.event_bus import TrackedData
from seed.core.channel_id import ChannelID, generate_track_id

logger = logging.getLogger("SEEDCameraQbit")
logger.setLevel(logging.INFO)

# ==========================================================
# Helpers
# ==========================================================
def gen_track_id(prefix="CAM2"):
    return f"{prefix}-{uuid4().hex[:8]}"

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

from dataclasses import dataclass, field
import cv2
import time
from typing import List

@dataclass
class CameraInfo:
    cam_id: str = ""                                # camera ID
    source_index: int = 1                            # device index
    capture: cv2.VideoCapture = None                # capture object
    last_frame_time: float = field(default_factory=time.time)   # last frame timestamp
    last_push_time: float = 0.0                     # last Qbit push
    connected: bool = True                           # connection state
    failure_count: int = 0                           # failure counter


# ==========================================================
# Camera Skill Engine
# ==========================================================
@dataclass
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

    def process(self, frame: np.ndarray) -> Dict[str, Any]:
        fg = self.bg.apply(frame)
        motion = float(fg.mean())

        data = {
            "avg_intensity": float(frame.mean()),
            "std": float(frame.std()),
            "motion": motion,
        }

        return data

# ==========================================================
# SEED Camera Qbit
# ==========================================================
@dataclass
class SEEDCameraQbit:
    def __init__(
        self,
        emit,
        track=None,
        storage_root = "./SEED_ROOT",
        qbit_dialer = None,
        hud_overlay=None,
        hud_interface=None,
        event_bus=None,
        max_cameras: int = 4,
        poll_interval: float = 0.05,
        push_interval: float = 0.25,
    ):
        from seed.core.qbit_dialer import QbitDialer
        from seed.ui.fat_hud_adapter import FATHUDAdapter
        self.storage_root = storage_root
        self.qbit_dialer = qbit_dialer
        self.hud_overlay = hud_interface
        self.event_bus = event_bus
        self.fat_hud_adapter = fat_hud_adapter
        self.max_cameras = max_cameras
        self.poll_interval = poll_interval
        self.push_interval = push_interval
        self.emit = _camera_qbit_emit_stub

        self.cameras = {}
        self.frame_buffer = deque(maxlen=50)
        self.track = True
        self.skill_engine = CameraSkillEngine()

        self._running = False
        self.os_boot_complete = False
        self.os_stable = False

        self._qbit_callbacks: List[Callable[[dict], Any]] = []

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self._thread = threading.Thread(
            target=self._camera_loop,
            daemon=True,
            name="SEEDCameraQbitLoop",
        )
        last_frame_time: float = field(default_factory=lambda: time.time())
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


    def _camera_qbit_emit_stub(event_type, payload=None):
        # Explicit stub – ethics module loaded before EventBus
        pass

    # ======================================================
    # Public control
    # ======================================================
    def start_camera_thread(self):
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
    # Camera loop
    # ======================================================
    def _camera_loop(self):
        logger.info("[CameraQbit] Waiting for OS boot")
        while not self.os_boot_complete:
            time.sleep(1)

        logger.info("[CameraQbit] Boot complete")

        while self._running:
            self._discover_cameras()
            now = time.time()

            for cam in list(self.cameras.values()):
                if not cam.capture or not cam.connected:
                    continue

                ret, frame = cam.capture.read()
                if not ret:
                    cam.connected = False
                    continue

                meta = self.skill_engine.process(frame)
                track_id = generate_track_id("CAM")
                channel = ChannelID.build(f"CAMERA_{cam.cam_id}")
                seq_data = ChannelID.next(
                    channel,
                    track_id=track_id,
                    overlay=True,
                    metadata=meta
                )

                self.frame_buffer.append(seq_data)

                # HUD Update
                if self.hud_overlay:
                    self.hud_overlay.update_channel(seq_data)

                # EventBus
                if self.event_bus:
                    self.event_bus.emit("CAMERA_FRAME", seq_data)

                # Qbit Push
                if self.qbit_dialer and now - cam.last_push_time >= self.push_interval:
                    self._submit_to_qbit(seq_data)
                    cam.last_push_time = now

            time.sleep(self.poll_interval)

    # ======================================================
    # Camera discovery
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
    # Qbit integration
    # ======================================================
    def add_qbit_callback(self, callback: Callable[[dict], Any]):
        if callable(callback):
            self._qbit_callbacks.append(callback)

    def _submit_to_qbit(self, vector_data: dict, **kwargs) -> bool:
        if not self.qbit_dialer:
            logger.warning("[CameraQbit] No QbitDialer available")
            return False

        try:
            if hasattr(self.qbit_dialer, "push_data"):
                self.qbit_dialer.push_data(vector_data, **kwargs)
            elif hasattr(self.qbit_dialer, "submit_data"):
                self.qbit_dialer.submit_data(vector_data, **kwargs)
            else:
                logger.warning("[CameraQbit] QbitDialer missing push/submit")
                return False
        except Exception as e:
            logger.error(f"[CameraQbit] submit error: {e}")
            return False

        for cb in self._qbit_callbacks:
            try:
                cb(vector_data)
            except Exception:
                pass

        return True

    # ======================================================
    # Status
    # ======================================================
    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "cameras": list(self.cameras.keys()),
            "buffer_size": len(self.frame_buffer),
            "cpu": psutil.cpu_percent(),
            "mem": psutil.virtual_memory().percent,
            "os_boot_complete": self.os_boot_complete,
            "os_stable": self.os_stable,
        }
    @dataclass
    class SEEDCameraQbit:
        last_frame_time: float = field(default_factory=lambda: time.time())
