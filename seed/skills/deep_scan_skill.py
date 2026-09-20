# ==========================================================
# FILE: deep_scan_skill.py
# PATH: SEED_ROOT/seed/skills/deep_scan_skill.py
# VERSION: 3.0 (TrackSystem + HUD + Qbit + EventBus | Async Safe)
# UPDATED: 2026-01-01
# ==========================================================
# PURPOSE:
#   Deep scanning / diagnostic skill
#   - TrackSystem unified (parent/child context)
#   - HUD overlay aware
#   - EventBus & Qbit integration
#   - Async safe & throttled logging
#   - Boot-safe and tolerant
# ==========================================================

import asyncio
import logging
import time
from copy import deepcopy
from collections import deque
from typing import Optional, Dict, Any

logger = logging.getLogger("DeepScanSkill")
logger.setLevel(logging.INFO)

# ==========================================================
# CORE INTEGRATION
# ==========================================================
try:
    from seed.core.track_system import TrackSystem
    from seed.core.qbit_dialer import QbitDialer
except ImportError:
    TrackSystem = None
    QbitDialer = None

# ==========================================================
# DEEP SCAN SKILL
# ==========================================================
class DeepScanSkill:
    SKILL_NAME = "DeepScanSkill"
    SKILL_VERSION = "3.0.0"
    SKILL_TYPE = "diagnostic"

    # ------------------------------------------------------
    # Initialization
    # ------------------------------------------------------
    def __init__(self, *args, **kwargs):
        # Metadata
        self.name = kwargs.get("name", self.SKILL_NAME)

        # Dependencies
        self.qbit_dialer: Optional[QbitDialer] = kwargs.get("qbit_dialer")
        self.event_bus = kwargs.get("event_bus")
        self.analytics_engine = kwargs.get("analytics_engine")
        self.actuator_engine = kwargs.get("actuator_engine")
        self.sparkplug = kwargs.get("sparkplug")

        # Runtime settings
        self.scan_interval = float(kwargs.get("scan_interval", 0.05))
        self.push_throttle = float(kwargs.get("push_throttle", 0.15))

        # Runtime state
        self.running = False
        self.last_push_time = 0.0
        self.latest_result: Optional[Dict[str, Any]] = None
        self._history = deque(maxlen=500)  # extended history

        logger.info(
            "[DeepScanSkill] Initialized | name=%s actuator=%s sparkplug=%s event_bus=%s qbit=%s",
            self.name,
            bool(self.actuator_engine),
            bool(self.sparkplug),
            bool(self.event_bus),
            bool(self.qbit_dialer),
        )

    # ------------------------------------------------------
    # Execute one scan action
    # ------------------------------------------------------
    async def execute(self, payload: Optional[Dict[str, Any]] = None, **context) -> Optional[Dict[str, Any]]:
        payload = payload or {}
        parent_track_id = context.get("parent_track_id")
        hud_id = context.get("hud_id") or f"SS-HUD-{uuid.uuid4().hex[:8]}"

        # Begin a new TrackSystem context if available
        track_id = None
        if TrackSystem:
            try:
                track_id = TrackSystem.begin(
                    channel="DEEP_SCAN",
                    skill=self.name,
                    parent_id=parent_track_id,
                    hud_id=hud_id,
                    priority="HIGH",
                )
            except Exception as e:
                logger.warning(f"[DeepScanSkill] TrackSystem begin failed: {e}")

        # Prepare result
        param = payload.get("param", 0)
        result = {
            "skill": self.name,
            "param": param,
            "timestamp": time.time(),
            "status": "processed",
            "track_id": track_id,
            "parent_track_id": parent_track_id,
            "hud_id": hud_id,
        }

        # Store locally
        self.latest_result = deepcopy(result)
        self._history.append(result)

        # Throttled logging
        now = time.time()
        if now - self.last_push_time >= self.push_throttle:
            logger.info(f"[DeepScanSkill] Result | TrackID={track_id} | HUD={hud_id}")
            self.last_push_time = now

        # EventBus notification
        if self.event_bus:
            try:
                self.event_bus.publish("SKILL_RESULT", payload=result)
            except Exception:
                logger.warning(f"[{track_id}] EventBus publish failed")

        # Qbit signal propagation
        if self.qbit_dialer:
            try:
                self.qbit_dialer.send_track(
                    track_id=track_id,
                    skill_name=self.name,
                    payload=result,
                    hud_id=hud_id,
                )
            except Exception:
                logger.warning(f"[{track_id}] Qbit send failed")

        # End TrackSystem context
        if TrackSystem:
            try:
                TrackSystem.end()
            except Exception:
                pass

        return result

    # ------------------------------------------------------
    # Continuous loop mode
    # ------------------------------------------------------
    async def run_loop(self):
        self.running = True
        logger.info(f"[DeepScanSkill] Loop started | skill={self.name}")

        while self.running:
            try:
                if self.latest_result:
                    # Hooks for analytics / reasoning
                    pass
            except Exception as e:
                logger.warning(f"[DeepScanSkill] Loop error: {e}")

            await asyncio.sleep(self.scan_interval)

    # ------------------------------------------------------
    # SparkPlug entry
    # ------------------------------------------------------
    async def run(self, *args, **kwargs):
        await self.run_loop()

    # ------------------------------------------------------
    # Stop the skill
    # ------------------------------------------------------
    def stop(self):
        self.running = False
        logger.info(f"[DeepScanSkill] Stopped | skill={self.name}")

    # ------------------------------------------------------
    # Diagnostics / Status
    # ------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        return {
            "skill": self.name,
            "version": self.SKILL_VERSION,
            "running": self.running,
            "history_size": len(self._history),
            "last_result": self.latest_result,
        }

    # ------------------------------------------------------
    # History access
    # ------------------------------------------------------
    def get_history(self, limit: Optional[int] = None):

        if limit:
            return list(self._history)[-limit:]
        return list(self._history)
