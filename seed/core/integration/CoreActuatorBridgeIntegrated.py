# ==========================================================
# FILE: CoreActuatorBridgeIntegrated.py
# PATH: SEED_ROOT/seed/core/integration/CoreActuatorBridgeIntegrated.py
# PURPOSE:
#   SEEDCore → ActuatorEngine + QbitDialer + SparkPlugLoader
#   WITH HUD ID CHANNELING + DUAL TRACK LINEAGE
#
# VERSION: 0.6.1 (SAFE MODE + FULL TRACKED DATA INTEGRATION)
# UPDATED: 2025-12-31
# ==========================================================

import asyncio
import threading
import logging
from datetime import datetime
from typing import Optional

from seed.core.actuator_engine import ActuatorEngine
from seed.core.qbit_dialer import QbitDialer
from seed.core.sparkplug_loader import SparkPlugLoader, TrackContext
from seed.core.tracked_data import TrackedData
from seed.core.limp_mode import LimpModeController

# ----------------------------------------------------------
# Logger
# ----------------------------------------------------------
logger = logging.getLogger("CoreActuatorBridgeIntegrated")
logger.setLevel(logging.INFO)

# ----------------------------------------------------------
# CONSTANT IDS
# ----------------------------------------------------------
CAB_ID = "CABI-1"              # Core Actuator Bridge channel 1
SEED_TRACK_PREFIX = "S"        # SEEDCore feed line
HUD_CHANNEL = "HUD-ACTUATOR"   # HUD logical channel

# ==========================================================
# SEED Core → Actuator Bridge
# ==========================================================
class SEEDCoreActuatorBridge:

    def __init__(
        self,
        seed_core,
        actuator: ActuatorEngine,
        qbit_dialer: Optional[QbitDialer] = None,
        sparkplug_loader: Optional[SparkPlugLoader] = None,
        update_interval: float = 0.05,
        enable_qbit: bool = True,
        enable_sparkplug: bool = True,
        enable_tracking: bool = True,
        enable_hud: bool = True,
        enable_logging: bool = True,
    ):
        self.seed_core = seed_core
        self.actuator = actuator
        self.qbit_dialer = qbit_dialer if enable_qbit else None
        self.sparkplug_loader = sparkplug_loader if enable_sparkplug else None

        self.enable_tracking = enable_tracking
        self.enable_hud = enable_hud
        self.enable_logging = enable_logging

        self.update_interval = max(0.01, float(update_interval))
        self.bridge_id = CAB_ID
        self.hud_channel = HUD_CHANNEL

        self.running = False
        self._started = False

        self.last_dominant_intent = None
        self.last_resonance = None

        self._loop = None
        self._thread = None

        # Safe limp mode fallback
        self.limp_controller = LimpModeController.safe_limp_enter

    # ------------------------------------------------------
    # Main Bridge Loop
    # ------------------------------------------------------
    async def run_loop(self):
        if self.running:
            return  # duplicate-loop guard

        self.running = True
        logger.info(f"[{self.bridge_id}] Bridge loop STARTED")

        while self.running:
            try:
                # --------------------------------------
                # SEEDCore Feed (domain S)
                # --------------------------------------
                seed_track_id = None
                if self.seed_core and hasattr(self.seed_core, "get_current_intent"):
                    seed_track_id = TrackedData.generate_input_track(
                        category="SEEDCoreIntent",
                        domain="S",
                        actuator_bridge=False,
                        emit_hud=self.enable_hud
                    )
                    intent_data = self.seed_core.get_current_intent()
                else:
                    intent_data = {
                        "intent": "idle",
                        "dominant_intent": "idle",
                        "resonance": 0.5,
                        "intent_scores": {},
                    }

                if isinstance(intent_data, str):
                    intent_data = {"intent": intent_data}

                dominant_intent = str(intent_data.get("dominant_intent", intent_data.get("intent", "idle")))
                resonance = intent_data.get("resonance", 0.5)
                intent_scores = intent_data.get("intent_scores", {})

                resonance = max(0.0, min(1.0, float(resonance))) if isinstance(resonance, (int, float)) else 0.5
                intent_scores = intent_scores if isinstance(intent_scores, dict) else {}

                # --------------------------------------
                # Qbit Dialer (domain SS)
                # --------------------------------------
                if self.qbit_dialer:
                    try:
                        qbit_val = self.qbit_dialer.calculate()
                        if isinstance(qbit_val, (int, float)):
                            resonance = (resonance + float(qbit_val)) * 0.5
                            resonance = max(0.0, min(1.0, resonance))
                    except Exception as qe:
                        logger.warning(f"[{self.bridge_id}] Qbit error: {qe}")
                        self.limp_controller("QbitError", str(qe))

                # --------------------------------------
                # Bridge TrackID (domain SS)
                # --------------------------------------
                bridge_track_id = None
                if self.enable_tracking:
                    try:
                        bridge_track_id = TrackedData.generate_input_track(
                            category="ActuatorBridge",
                            domain="SS",
                            parent_id=seed_track_id,
                            actuator_bridge=True,
                            emit_hud=self.enable_hud
                        )
                    except Exception as te:
                        logger.warning(f"[{self.bridge_id}] TrackID generation error: {te}")
                        self.limp_controller("TrackIDError", str(te))

                # --------------------------------------
                # SparkPlug Skill Feed (TRACKED)
                # --------------------------------------
                if self.sparkplug_loader:
                    try:
                        if self.enable_tracking:
                            TrackContext.push(
                                channel=self.bridge_id,
                                track_id=bridge_track_id,
                                meta={
                                    "seed_track": seed_track_id,
                                    "intent": dominant_intent,
                                },
                            )

                        await self.sparkplug_loader.execute_skill(
                            skill_name="actuator_bridge_feed",
                            payload={
                                "bridge_id": self.bridge_id,
                                "seed_track_id": seed_track_id,
                                "bridge_track_id": bridge_track_id,
                                "intent": dominant_intent,
                                "resonance": resonance,
                                "hud_channel": self.hud_channel,
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )
                    except Exception as se:
                        logger.warning(f"[{self.bridge_id}] SparkPlug skill error: {se}")
                        self.limp_controller("SparkPlugError", str(se))
                    finally:
                        if self.enable_tracking:
                            TrackContext.pop()

                # --------------------------------------
                # Actuator Update (HUD + TRACK AWARE)
                # --------------------------------------
                try:
                    self.actuator.update(
                        dominant_intent=dominant_intent,
                        intent_scores=intent_scores,
                        resonance=resonance,
                        track_id=bridge_track_id,
                        parent_track_id=seed_track_id,
                        channel=self.bridge_id,
                        hud_channel=self.hud_channel if self.enable_hud else None,
                    )
                except Exception as ae:
                    logger.warning(f"[{self.bridge_id}] Actuator update error: {ae}")
                    self.limp_controller("ActuatorUpdateError", str(ae))

                # --------------------------------------
                # Logging / HUD State Change
                # --------------------------------------
                if self.enable_logging:
                    if dominant_intent != self.last_dominant_intent or resonance != self.last_resonance:
                        logger.info(
                            f"[{self.bridge_id}] UPDATE "
                            f"intent={dominant_intent} "
                            f"res={resonance:.2f} "
                            f"S={seed_track_id} "
                            f"B={bridge_track_id}"
                        )
                        self.last_dominant_intent = dominant_intent
                        self.last_resonance = resonance

                await asyncio.sleep(self.update_interval)

            except Exception as loop_ex:
                logger.error(f"[{self.bridge_id}] Bridge loop critical error: {loop_ex}")
                self.limp_controller("BridgeLoopError", str(loop_ex))
                await asyncio.sleep(1)  # prevent tight crash loop

        logger.info(f"[{self.bridge_id}] Bridge loop STOPPED")

    # ------------------------------------------------------
    # Start (ASYNC + THREAD SAFE)
    # ------------------------------------------------------
    def start(self):
        if self._started:
            return

        self._started = True

        try:
            self._loop = asyncio.get_running_loop()
            asyncio.create_task(self.run_loop())
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._loop_runner,
                name=f"{self.bridge_id}-Thread",
                daemon=True,
            )
            self._thread.start()

    def _loop_runner(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.run_loop())

    # ------------------------------------------------------
    # Stop
    # ------------------------------------------------------
    async def stop(self):
        self.running = False
        await asyncio.sleep(0)
        logger.info(f"[{self.bridge_id}] Stop requested")


# ==========================================================
# Boot / Standalone Test
# ==========================================================
async def main():
    seed_core = None  # must implement get_current_intent()
    actuator = ActuatorEngine()
    qbit = QbitDialer()
    sparkplug = SparkPlugLoader()

    bridge = SEEDCoreActuatorBridge(
        seed_core=seed_core,
        actuator=actuator,
        qbit_dialer=qbit,
        sparkplug_loader=sparkplug,
    )

    bridge.start()
    await asyncio.sleep(5)
    await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
