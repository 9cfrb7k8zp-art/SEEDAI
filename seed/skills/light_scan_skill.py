# ========================================================== 
# FILE: light_scan_skill.py
# PATH: SEED_ROOT/seed/skills/light_scan_skill.py
# VERSION: 2.3.0 – Full TrackID + LogLight + ChaosEngine integration
# UPDATED: 2026-01-01
# ==========================================================

import logging
import time
import asyncio
from typing import Optional

from seed.skills.skill_base import SkillBase
from seed.core.event_bus import ChannelID
from seed.skills.sparkplug import CHANNELS  # consistent channel mapping
from seed.core.track_id_manager import TrackIDManager
from seed.skills.log_light_skill import LightLogger  # direct logging integration
from seed.core.chaos_engine import ChaosEngine  # optional dynamic chaos scoring
from COM.quantum_object import QuantumObject


logger = logging.getLogger("LightScanSkill")
logger.setLevel(logging.INFO)

# ----------------------------------------------------------
# SparkPlug Discovery Metadata
# ----------------------------------------------------------
SKILL_NAME = "light_scan_skill"
SKILL_VERSION = "2.3.0"
SKILL_DESCRIPTION = "Processes CameraQbit light_qbit data for HUD + analytics with TrackID, logging, and ChaosEngine"
SKILL_AUTOLOAD = True

# ----------------------------------------------------------
# LightScanSkill Class
# ----------------------------------------------------------
class LightScanSkill(SkillBase):
    _subscribed_global = False

    def __init__(
        self,
        event_bus=None,
        qbit_dialer=1.0,
        scan_interval=0.08,
        track_manager: TrackIDManager = None,
        chaos_engine: Optional[ChaosEngine] = None,
        parent_track_id: str = None,
        **kwargs,
    ):
        super().__init__(name=SKILL_NAME, **kwargs)
        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer
        self.scan_interval = scan_interval
        self.agent_manager = kwargs.get("agent_manager")
        self.last_scan_time = 0.0
        self.current_mode = "default"

        # TrackID manager & skill track
        self.track_manager = track_manager or TrackIDManager(main_id="SKILL", channels=["LIGHT_SCAN"])
        self.track_id = self.track_manager.new(
            channel="LIGHT_SCAN",
            skill_name=SKILL_NAME,
            parent_id=parent_track_id
        )

        # Optional ChaosEngine integration
        self.chaos_engine = chaos_engine

        if self.agent_manager:
            logger.info("[LightScanSkill] AgentManager injected")

        if self.event_bus and not LightScanSkill._subscribed_global:
            self.event_bus.on("LIGHT_SCAN_MODE", self._handle_mode_update)
            LightScanSkill._subscribed_global = True
            logger.info("[LightScanSkill] Subscribed to LIGHT_SCAN_MODE events (global)")


    # ------------------------------------------------------
    # Handle mode updates
    # ------------------------------------------------------
    def _handle_mode_update(self, payload: dict):
        try:
            self.current_mode = payload.get("mode", "default")
            logger.info(f"[LightScanSkill] Mode updated → {self.current_mode}")
        except Exception as e:
            logger.exception(f"[LightScanSkill] Mode update failed: {e}")

    # ------------------------------------------------------
    # SkillBase entry point
    # ------------------------------------------------------
    async def execute(self, payload: dict, parent_track_id: str = None):
        if not payload:
            return
        self.process_light_data(
            camera_id=payload.get("camera_id", "CAM_UNKNOWN"),
            light_qbit=payload.get("light_qbit", {}),
            objects=payload.get("objects", []),
            timestamp=payload.get("timestamp", time.time()),
            frame_data=payload.get("frame", None),
            parent_track_id=parent_track_id
        )

    # ------------------------------------------------------
    # Core light processing logic
    # ------------------------------------------------------
    def process_light_data(self, camera_id, light_qbit, objects, timestamp, frame_data=None, parent_track_id=None):
        try:
            now = time.time()
            if now - self.last_scan_time < self.scan_interval:
                return
            self.last_scan_time = now

            # Basic intensity for HUD/logging
            avg_intensity = float(light_qbit.get("avg_intensity", 0.0))
            motion_level = float(light_qbit.get("motion_level", 0.0))
            amp = light_qbit.get("amp", 0.0)
            freq = light_qbit.get("freq", 0.0)
            phase = light_qbit.get("phase", 0.0)

            # Generate TrackID for this processing
            track_id = self.track_manager.new(
                channel="LIGHT_SCAN",
                skill_name=SKILL_NAME,
                parent_id=parent_track_id or self.track_id
            )

            # ALERT threshold logging
            if avg_intensity > 200 or motion_level > 50:
                logger.info(
                    f"[LightScanSkill] ALERT camera={camera_id} "
                    f"intensity={avg_intensity:.2f} motion={motion_level:.2f} track_id={track_id}"
                )

            # Emit event / HUD update
            self._emit_update(
                camera_id=camera_id,
                avg_intensity=avg_intensity,
                motion_level=motion_level,
                amp=amp,
                freq=freq,
                phase=phase,
                objects=len(objects),
                timestamp=timestamp,
                mode=self.current_mode,
                track_id=track_id,
                frame_data=frame_data
            )

            # Push to QbitDialer with TrackID
            if self.qbit_dialer and hasattr(self.qbit_dialer, "inject"):
                payload_with_track = dict(light_qbit)
                payload_with_track["track_id"] = track_id
                self.qbit_dialer.inject("analytics." + camera_id, payload_with_track)

            # -------------------------
            # Log via log_light_skill
            # -------------------------
            if self.event_bus:
                asyncio.run(log_light_skill(
                    {
                        "camera_id": camera_id,
                        "avg_intensity": avg_intensity,
                        "motion_level": motion_level,
                        "objects_detected": len(objects),
                        "mode": self.current_mode,
                        "timestamp": timestamp,
                        "track_id": track_id
                    },
                    event_bus=self.event_bus,
                    qbit_dialer=self.qbit_dialer
                ))

            # -------------------------
            # ChaosEngine integration
            # -------------------------
            if self.chaos_engine:
                self.chaos_engine.submit(
                    task_name="light_scan_entropy",
                    payload={
                        "camera_id": camera_id,
                        "intensity": avg_intensity,
                        "motion": motion_level,
                        "track_id": track_id
                    },
                    priority=0.5,
                    allow_mutation=True,
                    source="LightScanSkill"
                )

        except Exception as e:
            logger.exception(f"[LightScanSkill] Processing failure: {e}")

    # ------------------------------------------------------
    # Async-safe EventBus emit
    # ------------------------------------------------------
    def _emit_update(
        self,
        camera_id,
        avg_intensity,
        motion_level,
        amp,
        freq,
        phase,
        objects,
        timestamp,
        mode,
        track_id,
        frame_data=None
    ):
        if not self.event_bus:
            return

        qbit_adj = avg_intensity * self.qbit_dialer
        if mode == "high_sensitivity":
            qbit_adj *= 1.5
        elif mode == "low_power":
            qbit_adj *= 0.7

        channels = {f"channel_{ch}": qbit_adj for ch in CHANNELS}
        channels["channel_overlay"] = sum(channels.values()) / max(len(channels), 1)

        payload = {
            "camera_id": camera_id,
            "avg_intensity": avg_intensity,
            "motion_level": motion_level,
            "amp": amp,
            "freq": freq,
            "phase": phase,
            "objects_detected": objects,
            "timestamp": timestamp,
            "mode": mode,
            "channels": channels,
            "frame_data": frame_data,
            "source": "LightScanSkill",
            "track_id": track_id
        }

        async def _emit():
            result = self.event_bus.emit("LIGHT_SCAN_UPDATE", payload)
            if asyncio.iscoroutine(result):
                await result

        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(_emit(), loop)
        except RuntimeError:
            asyncio.run(_emit())

# ----------------------------------------------------------
# Loader / SparkPlug entrypoint
# ----------------------------------------------------------
def run(payload: Optional[dict] = None, event_bus=None, qbit_dialer=1.0, scan_interval=0.08, chaos_engine=None, **kwargs):
    skill = LightScanSkill(
        event_bus=event_bus,
        qbit_dialer=qbit_dialer,
        scan_interval=scan_interval,
        chaos_engine=chaos_engine,
        **kwargs
    )
    if payload:
        asyncio.run(skill.execute(payload))
    logger.info("[LightScanSkill] Loaded successfully")
    return skill

# ==========================================================
# END OF FILE
# ==========================================================
