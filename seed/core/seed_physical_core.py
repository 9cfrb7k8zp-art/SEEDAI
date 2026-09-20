# ==========================================================
# FILE: seed_physical_core.py
# MODULE: SEED AI OS — Full Physical Autonomy Core (TrackID v2.2 | Qbit-Ready)
# VERSION: 1.8
# AUTHOR: Carlos A. Clarke
# UPDATED: 2026-01-03
# ==========================================================

import time
import math
import threading
import logging
import uuid
from typing import Optional, Tuple
from datetime import datetime

from seed.core.track_system import TrackSystem

logger = logging.getLogger("SEEDPhysicalCore")
logger.setLevel(logging.INFO)

# ==========================================================
# TRACK ID (DETERMINISTIC v2.2)
# ==========================================================
_track_seq = 0
_track_lock = threading.Lock()

def gen_track_id(prefix: str = "PHY") -> str:
    global _track_seq
    with _track_lock:
        _track_seq += 1
        seq = _track_seq
    ts = int(time.time() * 1000)
    return f"{prefix}:{ts}:{seq}"

# ==========================================================
# HARDWARE ABSTRACTION LAYER
# ==========================================================
class HardwareHAL:
    def __init__(self, simulate: bool = True):
        self.simulate = simulate

    def apply(self, channels: dict):
        if self.simulate:
            logger.debug(f"[HAL SIM] {channels}")
            return
        # REAL HARDWARE OUTPUT (INTENTIONAL NO-OP PLACEHOLDER)

# ==========================================================
# SENSOR FUSION
# ==========================================================
class SensorFusion:
    """
    Fuses IMU, Vision, EM, Thermal, Power.
    Last-write-wins, deterministic.
    """
    def __init__(self):
        self.state = {
            "x": 0.0,
            "y": 0.0,
            "heading": 0.0,
            "velocity": 0.0,
            "em_stability": 1.0,
            "temperature": 25.0,
            "power_draw": 0.0,
        }

    def update(self, sensors: dict) -> dict:
        for k in self.state:
            if k in sensors:
                self.state[k] = sensors[k]
        return self.state

# ==========================================================
# NAVIGATION
# ==========================================================
class Navigator:
    def __init__(self):
        self.goal: Optional[Tuple[float, float]] = None

    def set_goal(self, x: float, y: float):
        self.goal = (x, y)

    def compute_intent(self, state: dict) -> Tuple[str, float]:
        if not self.goal:
            return "idle", 0.15
        dx = self.goal[0] - state["x"]
        dy = self.goal[1] - state["y"]
        dist = math.hypot(dx, dy)
        if dist < 0.25:
            return "hold", 0.9
        confidence = min(1.0, dist / 3.0)
        return "forward", confidence

# ==========================================================
# ACTUATOR CORE
# ==========================================================
class ActuatorCore:
    LIMITS = {
        "EM_1": (0.0, 1.0),
        "EM_2": (0.0, 1.0),
        "Motor_Left": (0.0, 1.0),
        "Motor_Right": (0.0, 1.0),
        "LED": (0.0, 1.0),
    }
    MAX_DELTA = 0.1
    MAX_TEMP = 85.0
    MAX_POWER = 2.2

    def __init__(self, hal: HardwareHAL):
        self.hal = hal
        self.channels = {k: 0.0 for k in self.LIMITS}
        self._last = self.channels.copy()

    def apply(self, intent: str, confidence: float, fusion: dict) -> dict:
        target = {k: 0.0 for k in self.channels}
        if intent == "forward":
            target["Motor_Left"] = confidence
            target["Motor_Right"] = confidence
        elif intent == "hold":
            target["EM_1"] = 0.4
            target["EM_2"] = 0.4
        elif intent == "idle":
            target["LED"] = 0.1

        # Thermal & Power Safety
        if fusion["temperature"] > self.MAX_TEMP:
            self._shutdown("OVERHEAT")
            return self.channels
        total = sum(target.values())
        if total > self.MAX_POWER:
            scale = self.MAX_POWER / total
            for k in target:
                target[k] *= scale
            logger.warning(f"[ActuatorCore] Power scaled x{scale:.2f}")

        # Clamp + Slew
        for k, v in target.items():
            lo, hi = self.LIMITS[k]
            v = max(lo, min(v, hi))
            prev = self._last[k]
            if abs(v - prev) > self.MAX_DELTA:
                v = prev + self.MAX_DELTA * (1 if v > prev else -1)
            self.channels[k] = v

        self._last = self.channels.copy()
        self.hal.apply(self.channels)
        return self.channels

    def _shutdown(self, reason: str):
        for k in self.channels:
            self.channels[k] = 0.0
        self.hal.apply(self.channels)
        logger.error(f"[ActuatorCore] SHUTDOWN ({reason})")

# ==========================================================
# AUTONOMOUS POLICY
# ==========================================================
class AutonomousPolicy:
    def decide(self, fusion: dict) -> Tuple[Optional[str], Optional[float]]:
        if fusion["em_stability"] < 0.6:
            return "hold", max(0.3, fusion["em_stability"])
        return None, None

# ==========================================================
# FULL PHYSICAL CORE — QBIT READY
# ==========================================================
class SEEDPhysicalCore:
    TICK_RATE = 0.05  # 20Hz

    def __init__(self, fat_layer=None, hud=None, simulate: bool = True, sparkplug=None):
        self.fat_layer = fat_layer
        self.hud = hud
        self.sparkplug = sparkplug
        self.hal = HardwareHAL(simulate=simulate)
        self.sensors = SensorFusion()
        self.navigator = Navigator()
        self.policy = AutonomousPolicy()
        self.actuator = ActuatorCore(self.hal)

        self._state = "INIT"
        self._running = False

    def set_goal(self, x: float, y: float):
        self.navigator.set_goal(x, y)

    def ingest_sensors(self, data: dict) -> dict:
        track_id = gen_track_id("SENSOR")
        data["track_id"] = track_id
        return self.sensors.update(data)

    def start(self):
        if self._running:
            return
        self._running = True
        self._state = "RUNNING"
        threading.Thread(target=self._loop, daemon=True).start()
        logger.info("[SEEDPhysicalCore] STARTED")

    def stop(self):
        self._running = False
        self._state = "STOPPED"
        logger.warning("[SEEDPhysicalCore] STOPPED")

    # -----------------------------------------------------
    # MAIN LOOP (Qbit + Dev Line)
    # -----------------------------------------------------
    def _loop(self):
        next_tick = time.time()
        while self._running:
            track_id = gen_track_id("TICK")
            fusion = self.sensors.state.copy()

            # Policy
            intent, conf = self.policy.decide(fusion)

            # SparkPlug override
            if intent is None and self.sparkplug:
                try:
                    override = self.sparkplug.query_override(fusion, track_id=track_id)
                    if override:
                        intent, conf = override
                except Exception:
                    pass

            # Navigation fallback
            if intent is None:
                intent, conf = self.navigator.compute_intent(fusion)

            # Actuation
            channels = self.actuator.apply(intent, conf, fusion)

            # Developer line & Qbit payload
            dev_line = f"PHY-{uuid.uuid4().hex[:6]}"
            numeric_payload = sum(int(v*100) for v in channels.values()) + sum(int(fusion.get(k,0)*100) for k in fusion)
            channel_labels = {
                "dev_line": dev_line,
                "channel_id": f"SEED:PHYSICAL:TICK:{track_id[-6:]}",
                "intent": intent,
                "confidence": conf,
            }

            # HUD push
            if self.hud:
                try:
                    self.hud.push({
                        "type": "physical_tick",
                        "track_id": track_id,
                        "intent": intent,
                        "confidence": conf,
                        "fusion": fusion.copy(),
                        "channels": channels.copy(),
                        "channel_labels": channel_labels,
                        "numeric_payload": numeric_payload,
                    })
                except Exception:
                    pass

            # FAT log
            if self.fat_layer:
                try:
                    self.fat_layer.append_log({
                        **fusion,
                        "intent": intent,
                        "confidence": conf,
                        "channels": channels,
                        "track_id": track_id,
                        "dev_line": dev_line,
                        "numeric_payload": numeric_payload,
                    }, source="physical", label="tick")
                except Exception:
                    pass

            # Qbit dispatch
            try:
                TrackSystem.emit(
                    channel="PHYSICAL",
                    state=intent,
                    stage="tick",
                    payload=numeric_payload,
                    input_type="PHYSICAL_STATE",
                    output_type="QBIT",
                    priority="MED",
                    metadata={"dev_line": dev_line, "channel_labels": channel_labels},
                )
            except Exception as e:
                logger.error(f"[SEEDPhysicalCore] Qbit dispatch failed: {e}")

            logger.debug(
                "[SEEDPhysicalCore][%s] %s | %s",
                track_id,
                intent,
                ", ".join(f"{k}:{v:.2f}" for k, v in channels.items()),
            )

            # Tick scheduling
            next_tick += self.TICK_RATE
            sleep = next_tick - time.time()
            if sleep > 0:
                time.sleep(sleep)
            else:
                next_tick = time.time()

# ==========================================================
# END FILE — SEEDPhysicalCore v1.8
# ==========================================================
