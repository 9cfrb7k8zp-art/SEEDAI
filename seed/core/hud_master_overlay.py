# ==========================================================
# FILE: hud_master_overlay.py
# PATH: SEED_ROOT/seed/core/hud_master_overlay.py
# HUDMasterOverlay v3.3 — TrackID-safe camera overlays + multi-channel HUD + motion + health
# AUTHOR: Carlos A. Clarke
# NOTES:
# - Safe dict/copy operations
# - Track ID: MS-HUD-O
# - Channel ID: S-C
# - HUD ID: S-HUD-1
# - Camera input handled via push, no direct OpenCV capture
# ==========================================================

import time
import tracemalloc
from collections import deque
from threading import Lock
import logging
import cv2
import numpy as np

logger = logging.getLogger("HUDMasterOverlay")

# --------------------------------------------------
# SAFE MODEM
# --------------------------------------------------
class Modem:
    def __init__(self):
        self.tx_log = deque(maxlen=200)
        self.rx_log = deque(maxlen=200)

# --------------------------------------------------
# AI CORE
# --------------------------------------------------
class SEEDAICore:
    def __init__(self):
        self.learning_state = {}

    def compute_modem_signal(self, base):
        total = (base * 0.4) + (base * 0.35) + (base * 0.25)
        self.learning_state["last_modem_signal"] = total
        return total

# --------------------------------------------------
# QBIT NORMALIZER
# --------------------------------------------------
class QbitNormalizer:
    def __init__(self, window=50, delta_threshold=0.02, min_interval=0.05):
        self.window = window
        self.delta_threshold = delta_threshold
        self.min_interval = min_interval
        self.history = deque(maxlen=window)
        self.last_value = None
        self.last_emit = 0.0

    def process(self, raw_value):
        if raw_value is None:
            return None
        now = time.time()
        self.history.append(raw_value)
        min_v = min(self.history)
        max_v = max(self.history)
        normalized = 0.0 if max_v - min_v == 0 else (raw_value - min_v) / (max_v - min_v)
        delta = abs(normalized - (self.last_value or 0.0))
        if delta < self.delta_threshold or now - self.last_emit < self.min_interval:
            return None
        confidence = min(1.0, delta * 2.0)
        self.last_value = normalized
        self.last_emit = now
        return {"value": round(normalized, 4), "confidence": round(confidence, 3), "delta": round(delta, 4)}

# --------------------------------------------------
# QBIT AGGREGATOR
# --------------------------------------------------
class QbitAggregator:
    def __init__(self, device_manager=None, modem=None, ai_core=None):
        self.device_manager = device_manager
        self.modem = modem or Modem()
        self.ai_core = ai_core
        tracemalloc.start()

    def modem_signal(self, push=None):
        if push is not None:
            self.modem.tx_log.append(push)
        base = sum(self.modem.tx_log) + sum(self.modem.rx_log)
        return base + (self.ai_core.compute_modem_signal(base) if self.ai_core else 0)

    def memory_signal(self):
        try:
            snap = tracemalloc.take_snapshot()
            return sum(stat.size for stat in snap.statistics("lineno")) / (1024 * 1024)
        except Exception:
            return 0.0

    def compute(self, push=None):
        return self.modem_signal(push) + self.memory_signal()

# --------------------------------------------------
# HUD INPUT CONSOLE
# --------------------------------------------------
class HUDInputConsole:
    def __init__(self, hud):
        self.hud = hud
        self.history = deque(maxlen=200)
        self.lock = Lock()

    def submit(self, command: str):
        ts = time.time() - self.hud.start_time
        self.history.append((ts, command))
        return self._exec(command)

    def _exec(self, cmd):
        parts = cmd.split()
        try:
            if parts[0] == "set" and parts[1] == "qbit":
                ch = int(parts[2])
                val = float(parts[3])
                self.hud.qbit_factors[ch] = val
                return {"qbit_factor": {ch: val}}
        except Exception as e:
            return {"error": str(e)}
        return {"error": "unknown"}

# --------------------------------------------------
# MASTER HUD OVERLAY
# --------------------------------------------------
class HUDMasterOverlay:
    TRACK_ID = "MS-HUD-O"
    CHANNEL_ID = "S-C"
    HUD_ID = "S-HUD-1"

    def __init__(self, device_manager=None, ai_core=None, event_bus=None, channels=(3, 6, 9), max_points=300, width=1024, height=768):
        self.device_manager = device_manager
        self.ai_core = ai_core
        self.channels = list(channels)
        self.event_bus = event_bus

        self.aggregator = QbitAggregator(device_manager, ai_core=ai_core)
        self.qbit_factors = {ch: 1.0 for ch in self.channels}
        self.qbit_normalizers = {ch: QbitNormalizer() for ch in self.channels}
        self.channel_log = {ch: deque(maxlen=max_points) for ch in self.channels}
        self.normalized_log = deque(maxlen=max_points)

        self.start_time = time.time()
        self.console = HUDInputConsole(self)

        self.thought_pressure = 0.0
        self.latest_memory_snapshot = []

        self.width = width
        self.height = height
        self.lock = Lock()

        # Camera overlay (push only)
        self.camera_frames = {}   # cam_id -> latest frame
        self.camera_vectors = {}  # cam_id -> motion vector
        self.camera_health = {}    # cam_id -> health

        # Subscribe to Qbit events safely
        if self.event_bus:
            self.event_bus.on("ANALYTICS_UPDATED", self._on_qbit_event)

    # ---------------------------
    # EventBus dict-safe accessor
    # ---------------------------
    def to_dict(self):
        return {
            "track_id": self.TRACK_ID,
            "hud_id": self.HUD_ID,
            "channels": self.channels,
            "channel_id": self.CHANNEL_ID,
            "qbit_factors": self.qbit_factors,
            "camera_health": self.camera_health,
            "thought_pressure": self.thought_pressure,
        }

    # ---------------------------
    # Qbit event handler
    # ---------------------------
    def _on_qbit_event(self, event):
        try:
            payload = getattr(event, "payload", None) or event
            if not isinstance(payload, dict):
                payload = {"data": payload}
            data = payload.get("qbit_data") or payload.get("data")
            if isinstance(data, dict):
                self.push(data)
        except Exception as e:
            logger.warning(f"[HUDMasterOverlay] Failed to handle event: {e}")

    # ---------------------------
    # Submit command
    # ---------------------------
    def submit_command(self, command: str):
        result = self.console.submit(command)
        logger.info(f"[HUD CMD] {command} → {result}")
        return result

    # ---------------------------
    # Push data into HUD overlay (track-safe)
    # ---------------------------
    def push(self, entry):
        if not isinstance(entry, dict):
            logger.warning(f"[HUD] push received unrecognized format: {entry}")
            return
        entry = entry.copy()
        entry.setdefault("type", "unknown")
        entry["track_id"] = self.TRACK_ID
        entry["hud_id"] = self.HUD_ID
        entry["channel_id"] = self.CHANNEL_ID

        self.update(entry)
        self._draw_camera_overlay(entry)

    # ---------------------------
    # Update channel & Qbit logs
    # ---------------------------
    def update(self, push_data=None):
        ts = time.time() - self.start_time
        raw_value = push_data.get("value") if push_data else None
        raw = self.aggregator.compute(raw_value)

        for ch in self.channels:
            scaled = raw * self.qbit_factors[ch]
            norm = self.qbit_normalizers[ch].process(scaled)
            if norm is None:
                continue

            packet = {
                "timestamp": ts,
                "track_id": self.TRACK_ID,
                "hud_id": self.HUD_ID,
                "channel": ch,
                "channel_id": self.CHANNEL_ID,
                "value": norm["value"],
                "confidence": norm["confidence"],
                "delta": norm["delta"],
                "type": push_data.get("type", "unknown") if push_data else "unknown",
                "fusion": push_data.get("fusion") if push_data else None
            }

            self.channel_log[ch].append(packet)
            self.normalized_log.append(packet)
            self.thought_pressure += packet["confidence"]

            if self.event_bus:
                try:
                    self.event_bus.emit("ANALYTICS_UPDATED", {"qbit_data": packet})
                except Exception as e:
                    logger.warning(f"[HUDMasterOverlay] Event emit failed: {e}")

    # ---------------------------
    # Draw camera overlay (safe)
    # ---------------------------
    def _draw_camera_overlay(self, data):
        cam_id = data.get("camera_id", "CAM_0")
        frame = data.get("frame")
        vector = data.get("vector", {})
        health = data.get("health", 1.0)

        if frame is not None:
            self.camera_frames[cam_id] = frame
        if vector:
            self.camera_vectors[cam_id] = vector
        self.camera_health[cam_id] = health

        try:
            with self.lock:
                canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                num_cams = len(self.camera_frames)
                if num_cams == 0:
                    return

                cam_w = self.width // max(1, num_cams)
                cam_h = self.height

                for idx, (cid, cam_frame) in enumerate(self.camera_frames.items()):
                    x0 = idx * cam_w
                    y0 = 0
                    x1 = x0 + cam_w - 5
                    y1 = cam_h - 5

                    if cam_frame is not None:
                        resized = cv2.resize(cam_frame, (cam_w, cam_h))
                        canvas[y0:y1, x0:x1] = resized

                    vector = self.camera_vectors.get(cid, {})
                    center_x = x0 + cam_w // 2
                    center_y = y0 + cam_h // 2
                    dx = int(vector.get("dx", 0) * 50)
                    dy = int(vector.get("dy", 0) * 50)
                    cv2.arrowedLine(canvas, (center_x, center_y), (center_x + dx, center_y + dy), (255,255,255), 2, tipLength=0.3)

                    hval = self.camera_health.get(cid, 1.0)
                    color = (0,255,0) if hval >= 0.7 else (0,255,255) if hval >= 0.3 else (0,0,255)
                    cv2.rectangle(canvas, (x0,y0), (x1,y1), color, 2)
                    cv2.putText(canvas, f"{cid} H:{hval:.2f}", (x0+5, y0+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

                cv2.imshow("SEED HUD", canvas)
                cv2.waitKey(1)
        except Exception as e:
            logger.warning(f"[HUDMasterOverlay] Camera overlay draw failed: {e}")

    # ---------------------------
    # Access last N entries
    # ---------------------------
    def get_state(self):
        return list(self.normalized_log)[-10:]

    # ---------------------------
    # Update memory snapshot
    # ---------------------------
    def update_memory(self, entry=None):
        self.latest_memory_snapshot = self.get_state()
        return self.latest_memory_snapshot
