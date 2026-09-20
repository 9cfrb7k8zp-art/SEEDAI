# ==========================================================
# FILE: CoreActuatorBridgeMultiCAB.py
# PATH: SEED_ROOT/seed/core/integration/CoreActuatorBridgeMultiCAB.py
# PURPOSE: Multi-CAB SEEDCore → ActuatorEngine + QbitDialer + SparkPlugLoader integration
# VERSION: 0.4 (TrackID + dynamic multi-CAB + weighted merging)
# UPDATED: 2025-12-28
# ==========================================================

import asyncio
import threading
import logging
import uuid
from copy import deepcopy
from datetime import datetime

from seed.core.actuator_engine import ActuatorEngine
from seed.core.qbit_dialer import QbitDialer
from seed.core.sparkplug_loader import SparkPlugLoader, TrackContext

logger = logging.getLogger("CoreActuatorBridgeMultiCAB")
logger.setLevel(logging.INFO)


# ==========================================================
# Track ID helper
# ==========================================================
def gen_track_id(prefix="CAB"):
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


# ==========================================================
# Multi-CAB Actuator Bridge
# ==========================================================
class SEEDCoreActuatorBridgeMultiCAB:

    def __init__(self, seed_core, actuator: ActuatorEngine,
                 qbit_dialer: QbitDialer = None,
                 sparkplug_loader: SparkPlugLoader = None,
                 update_interval=0.05):

        self.seed_core = seed_core
        self.actuator = actuator
        self.qbit_dialer = qbit_dialer
        self.sparkplug_loader = sparkplug_loader
        self.update_interval = update_interval
        self.running = False
        self._loop = None

        # CAB channels: key=marker (CAB1, CAB3,...), value=dict(last_intent, resonance, weight)
        self.cab_channels = {}
        self.base_cabs = ["CAB1", "CAB3", "CAB6", "CAB9"]
        for cab in self.base_cabs:
            self.cab_channels[cab] = {
                "last_dominant_intent": None,
                "last_logged_intent": None,
                "resonance": 0.5,
                "weight": 1.0
            }

    # --------------------------------------------------
    # Loop runner
    # --------------------------------------------------
    async def run_loop(self):
        self.running = True
        logger.info("[MultiCAB] Bridge loop started")

        while self.running:
            try:
                merged_target = {k: 0.0 for k in self.actuator.channels}
                total_weight = 0.0

                for cab_marker in list(self.cab_channels.keys()):
                    cab = self.cab_channels[cab_marker]

                    # -------------------------
                    # Get SEEDCore intent
                    # -------------------------
                    if hasattr(self.seed_core, "get_current_intent"):
                        intent_data = self.seed_core.get_current_intent(cab_marker=cab_marker)
                    else:
                        intent_data = {}

                    if isinstance(intent_data, str):
                        intent_data = {"intent": intent_data, "dominant_intent": intent_data}
                    elif not isinstance(intent_data, dict):
                        intent_data = {}

                    dominant_intent = str(intent_data.get("intent",
                                            intent_data.get("dominant_intent", "idle")))
                    resonance = intent_data.get("resonance", cab["resonance"])
                    intent_scores = intent_data.get("intent_scores", {})

                    # -------------------------
                    # QbitDialer influence
                    # -------------------------
                    if self.qbit_dialer:
                        qbit_val = self.qbit_dialer.calculate()
                        if isinstance(qbit_val, (float, int)):
                            resonance = (resonance + qbit_val) / 2.0

                    # Update CAB state
                    cab["last_dominant_intent"] = dominant_intent
                    cab["resonance"] = resonance

                    # -------------------------
                    # SparkPlug skill feed (Track ID)
                    # -------------------------
                    if self.sparkplug_loader:
                        track_id, parent_id = TrackContext.push(cab_marker)
                        await self.sparkplug_loader.execute_skill(
                            "actuator_bridge_feed",
                            {"intent": dominant_intent, "resonance": resonance, "cab": cab_marker}
                        )
                        TrackContext.pop()

                    # -------------------------
                    # Compute actuator target for this CAB
                    # -------------------------
                    cab_target = self.actuator.map_intent(dominant_intent, resonance, intent_scores)

                    # -------------------------
                    # Merge weighted
                    # -------------------------
                    weight = cab.get("weight", 1.0)
                    for k, v in cab_target.items():
                        merged_target[k] += v * weight
                    total_weight += weight

                    # -------------------------
                    # Log if dominant intent changed
                    # -------------------------
                    if dominant_intent != cab.get("last_logged_intent"):
                        logger.info(f"[{cab_marker}] Actuator update → intent={dominant_intent} res={resonance:.2f}")
                        cab["last_logged_intent"] = dominant_intent

                # Normalize merged target
                if total_weight > 0:
                    for k in merged_target:
                        merged_target[k] /= total_weight

                # -------------------------
                # Apply final actuator update with Track ID
                # -------------------------
                final_track_id = gen_track_id("MultiCAB")
                self.actuator.update(
                    dominant_intent="merged",
                    intent_scores={},
                    resonance=0.0,  # already merged into merged_target
                    track_id=final_track_id
                )
                if self.actuator.actuator_feed:
                    self.actuator.actuator_feed.update(**merged_target, _track_id=final_track_id)

            except Exception as e:
                logger.error(f"[MultiCAB] Bridge loop error: {e}")

            await asyncio.sleep(self.update_interval)

    # --------------------------------------------------
    # Start bridge async-safe
    # --------------------------------------------------
    def start(self):
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        threading.Thread(target=self._loop_runner, daemon=True).start()

    def _loop_runner(self):
        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.run_loop(), self._loop)
        else:
            self._loop.run_until_complete(self.run_loop())

    # --------------------------------------------------
    # Stop bridge
    # --------------------------------------------------
    async def stop(self):
        self.running = False
        logger.info("[MultiCAB] Bridge loop stopped")

    # --------------------------------------------------
    # Add dynamic CAB channel if new marker appears
    # --------------------------------------------------
    def add_cab_channel(self, cab_marker):
        if cab_marker not in self.cab_channels:
            self.cab_channels[cab_marker] = {
                "last_dominant_intent": None,
                "last_logged_intent": None,
                "resonance": 0.5,
                "weight": 1.0
            }
            logger.info(f"[MultiCAB] Added new CAB channel: {cab_marker}")
