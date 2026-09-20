# ==========================================================
# FILE: CoreActuatorBridge.py
# PATH: SEED_ROOT/seed/core/integration/CoreActuatorBridge.py
# PURPOSE: SEEDCore → ActuatorEngine + QbitDialer + SparkPlugLoader real-time integration
# VERSION: 0.2 (CAB ID system + multi-channel tracking + SparkPlug integration)
# UPDATED: 2025-12-27
# ==========================================================

import asyncio
import logging
import time

from seed.core.actuator_engine import ActuatorEngine
# Ensure SEEDCoreIntegration import is correct
# from seed.core.integration.seed_core_integration import SEEDCoreIntegration

logger = logging.getLogger("CoreActuatorBridge")
logging.basicConfig(level=logging.INFO)


# ==========================================================
# Actuator Bridge with CAB ID System
# ==========================================================
class SEEDCoreActuatorBridge:
    def __init__(
        self,
        seed_core,
        actuator_engine: ActuatorEngine,
        sparkplug_loader=None,
        update_interval=0.05,
        bridge_id="CAB-1"
    ):
        self.seed_core = seed_core
        self.actuator = actuator_engine
        self.sparkplug_loader = sparkplug_loader
        self.update_interval = update_interval
        self.running = False
        self.last_dominant_intent = None
        self.bridge_id = bridge_id
        self.channels = ["CH1", "CH2", "CH3"]  # Example: CH1=Actuator, CH2=Qbit, CH3=Feedback

    # -------------------------
    # Bridge Loop
    # -------------------------
    async def run_loop(self):
        self.running = True
        logger.info(f"[{self.bridge_id}] Bridge loop started")

        while self.running:
            try:
                # Get SEEDCore intent
                intent_data = self.seed_core.get_current_intent()

                # Normalize input
                if isinstance(intent_data, str):
                    intent_data = {"intent": intent_data, "dominant_intent": intent_data}
                elif not isinstance(intent_data, dict):
                    intent_data = {}

                # Normalize fields
                intent = str(intent_data.get("intent", intent_data.get("dominant_intent", "idle")))
                resonance = intent_data.get("resonance", 0.5)
                intent_scores = intent_data.get("intent_scores", {})

                if not isinstance(resonance, (float, int)):
                    resonance = 0.5
                if not isinstance(intent_scores, dict):
                    intent_scores = {}

                # -------------------------
                # Update ActuatorEngine
                # -------------------------
                if intent != self.last_dominant_intent:
                    logger.info(f"[{self.bridge_id}] Actuator update → intent={intent}")
                    self.last_dominant_intent = intent

                self.actuator.update(
                    dominant_intent=intent,
                    intent_scores=intent_scores,
                    resonance=float(resonance),
                    source_id=self.bridge_id
                )

                # -------------------------
                # Enqueue to SparkPlugLoader (if available)
                # -------------------------
                if self.sparkplug_loader:
                    for idx, ch in enumerate(self.channels):
                        payload = {
                            "dominant_intent": intent,
                            "resonance": resonance,
                            "intent_scores": intent_scores,
                            "bridge_id": self.bridge_id,
                            "channel": ch,
                            "timestamp": time.time(),
                            "channel_index": idx
                        }
                        self.sparkplug_loader.enqueue_skill(
                            skill_name="bridge_qbit_update",
                            payload=payload,
                            priority="high"
                        )

            except Exception as e:
                logger.error(f"[{self.bridge_id}] Update failure: {e}")

            await asyncio.sleep(self.update_interval)

    # -------------------------
    # Stop bridge
    # -------------------------
    def stop(self):
        self.running = False
        logger.info(f"[{self.bridge_id}] Bridge loop stopped")


# ==========================================================
# Example: Boot SEED Core Integration
# ==========================================================
async def main():
    # TODO: Replace with actual SEEDCoreIntegration instance
    seed_core = None  # SEEDCoreIntegration()
    actuator_engine = ActuatorEngine()
    sparkplug_loader = None  # Load actual SparkPlugLoader if available

    bridge = SEEDCoreActuatorBridge(
        seed_core=seed_core,
        actuator_engine=actuator_engine,
        sparkplug_loader=sparkplug_loader,
        bridge_id="CAB-1"
    )

    try:
        # Start the bridge loop
        await bridge.run_loop()
    except KeyboardInterrupt:
        bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
