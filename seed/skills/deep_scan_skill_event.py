# ==========================================================
# FILE: deep_scan_skill_event.py
# PATH: SEED_ROOT/seed/skills/deep_scan_skill_event.py
# VERSION: 3.0 (TrackSystem + HUD + Qbit + EventBus | Async Safe)
# UPDATED: 2026-01-01
# ==========================================================
# PURPOSE:
#   Event-driven deep scan skill
#   - Full TrackSystem integration
#   - HUD overlay aware
#   - Qbit emission + EventBus reporting
#   - Async inbox/outbox handling
#   - Boot-safe and tolerant
# ==========================================================

import asyncio
import logging
import time
from copy import deepcopy
from collections import deque
import uuid
from typing import Optional, Dict, Any

from seed.skills.skill_base import SkillBase

try:
    from seed.core.track_system import TrackSystem
    from seed.core.track_id_manager import TrackIDManager
    from seed.core.qbit_dialer import QbitDialer
except ImportError:
    TrackSystem = None
    TrackIDManager = None
    QbitDialer = None

logger = logging.getLogger("DeepScanSkillEvent")
logger.setLevel(logging.INFO)


class DeepScanSkillEvent(SkillBase):

    SKILL_TRACK_PROFILE = {
        "module": "DeepScan",
        "role": "analysis",
        "intent": "deep_scan",
        "emits": ["SCAN_RESULT", "SCAN_EVENT"],
        "accepts": ["SCAN_REQUEST", "RAW_EVENT"]
    }

    def __init__(
        self,
        actuator_engine = ActuatorEngine,
        sparkplug = Sparkplug,
        scan_interval = 0.05,
        push_throttle = 0.1,
        track_manager = TrackIDManager,
    ):
        super().__init__(
            name="DeepScanSkillEvent",
            throttle_interval=scan_interval,
            actuator_engine=actuator_engine,
            sparkplug=sparkplug
        )

        # Queues
        self.inbox = deque()
        self.outbox = deque()

        # State
        self.running = False
        self.last_push_time = 0.0
        self.latest_result: Optional[Dict[str, Any]] = None
        self.push_throttle = push_throttle

        # TrackID / TrackSystem integration
        self.track_manager: TrackIDManager = track_manager or TrackIDManager(
            main_id="SKILL",
            channels=["DEEP_SCAN_EVENT"]
        )
        self.track_id: str = self.track_manager.new(
            channel="DEEP_SCAN_EVENT",
            skill_name="DeepScanSkillEvent"
        )

        logger.info(
            "[DeepScanSkillEvent] Initialized | track_id=%s | profile=%s",
            self.track_id,
            self.SKILL_TRACK_PROFILE
        )

    # --------------------------------------------------
    # INBOX
    # --------------------------------------------------
    def enqueue(self, payload: dict, source="unknown", parent_track_id=None) -> str:
        track_id = self.track_manager.new(
            channel="DEEP_SCAN_EVENT",
            skill_name="DeepScanSkillEvent",
            parent_id=parent_track_id
        )
        self.inbox.append({
            "payload": deepcopy(payload),
            "source": source,
            "track_id": track_id,
            "hud_id": f"SS-HUD-{uuid.uuid4().hex[:8]}",
            "ts": time.time()
        })
        logger.debug("[DeepScanSkillEvent] Payload enqueued | track_id=%s from %s", track_id, source)
        return track_id

    # --------------------------------------------------
    # PROCESS ONE ITEM
    # --------------------------------------------------
    async def execute_async(self, event=None) -> Optional[Dict[str, Any]]:
        if not self.inbox:
            return None

        item = self.inbox.popleft()
        payload = item.get("payload", {})
        track_id = item.get("track_id", self.track_id)
        hud_id = item.get("hud_id")

        if not isinstance(payload, dict):
            logger.warning("[DeepScanSkillEvent] Malformed payload dropped | track_id=%s", track_id)
            return None

        # Begin TrackSystem context if available
        if TrackSystem:
            try:
                TrackSystem.begin(
                    channel="DEEP_SCAN_EVENT",
                    skill="DeepScanSkillEvent",
                    parent_id=payload.get("parent_track_id"),
                    hud_id=hud_id,
                    priority="HIGH"
                )
            except Exception as e:
                logger.warning("[DeepScanSkillEvent] TrackSystem begin failed: %s", e)

        param = payload.get("param", 0)
        scan_result = {
            "track_id": track_id,
            "parent_track_id": payload.get("parent_track_id"),
            "source": item.get("source"),
            "param": param,
            "status": "processed",
            "timestamp": time.time(),
            "hud_id": hud_id
        }

        # Store result locally
        self.latest_result = deepcopy(scan_result)
        self.outbox.append(scan_result)

        # Throttled logging
        now = time.time()
        if now - self.last_push_time >= self.push_throttle:
            logger.info("[DeepScanSkillEvent] Scan result → track_id=%s | HUD=%s", track_id, hud_id)
            self.last_push_time = now

        # Optional actuator signal
        self.send_actuator_command(
            dominant_intent="analyze",
            intent_scores={"deep_scan": 0.9},
            resonance=0.6
        )

        # End TrackSystem context if available
        if TrackSystem:
            try:
                TrackSystem.end()
            except Exception:
                pass

        return scan_result

    # --------------------------------------------------
    # OUTBOX DISPATCH
    # --------------------------------------------------
    async def flush_outbox(self):
        while self.outbox:
            result = self.outbox.popleft()

            # SparkPlug
            if self.sparkplug:
                try:
                    self.sparkplug.send("SCAN_RESULT", result)
                except Exception as e:
                    logger.warning("[DeepScanSkillEvent] SparkPlug send failed: %s", e)

            # EventBus (SkillBase may provide event bus)
            if hasattr(self, 'event_bus') and self.event_bus:
                try:
                    self.event_bus.publish("SCAN_RESULT", payload=result)
                except Exception as e:
                    logger.warning("[DeepScanSkillEvent] EventBus publish failed: %s", e)

            # Qbit propagation (if available)
            if hasattr(self, 'qbit_dialer') and self.qbit_dialer:
                try:
                    self.qbit_dialer.send_track(
                        track_id=result["track_id"],
                        skill_name="DeepScanSkillEvent",
                        payload=result,
                        hud_id=result["hud_id"]
                    )
                except Exception as e:
                    logger.warning("[DeepScanSkillEvent] Qbit send failed: %s", e)

    # --------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------
    async def run_loop(self):
        self.running = True
        logger.info("[DeepScanSkillEvent] run_loop started")

        while self.running:
            try:
                await self.execute_async()
                await self.flush_outbox()
            except Exception as e:
                logger.error("[DeepScanSkillEvent] Loop error: %s", e)

            await asyncio.sleep(self.throttle_interval)

    # --------------------------------------------------
    # SPARKPLUG ENTRY
    # --------------------------------------------------
    async def run(self):
        logger.info("[DeepScanSkillEvent] run() called")
        await self.run_loop()

    # --------------------------------------------------
    # CONTROL
    # --------------------------------------------------
    def stop(self):
        self.running = False
        logger.info("[DeepScanSkillEvent] Stopped")
