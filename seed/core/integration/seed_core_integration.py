# ==========================================================
# FILE: seed_core_integration.py
# PATH: SEED_ROOT/seed/core/integration/seed_core_integration.py
# PURPOSE: SEEDCore → ActuatorEngine + QbitDialer + SparkPlugLoader real-time integration
# VERSION: 2.2 (ActuatorEngine unified, fully compatible with HUDPipelineIntegration)
# UPDATED: 2025-12-27
# ==========================================================

import asyncio
import logging
from collections import deque
from seed.core.actuator_engine import ActuatorEngine
from seed.core.qbit_dialer import QbitDialer
from seed.core.sparkplug_loader import SparkPlugLoader
from seed.core.event_bus import SEEDEventBus
from seed.core.modem_controller import SEEDModemController
from seed.core.integration.CoreActuatorBridgeIntegrated import SEEDCoreActuatorBridge

logger = logging.getLogger("SEEDCoreIntegration")
logging.basicConfig(level=logging.INFO)


# ==========================================================
# SEED Core Integration
# ==========================================================
class SEEDCoreIntegration:

    def __init__(self, storage_root="./SEED_ROOT", actuator_engine: ActuatorEngine = None):
        self.storage_root = storage_root
        self.allow_thinking_loop = True

        # ---------------- ActuatorEngine ----------------
        self.actuator_engine = actuator_engine or ActuatorEngine()

        # ---------------- EventBus ----------------
        self.event_bus = SEEDEventBus()

        # ---------------- SparkPlugLoader ----------------
        self.sparkplug_loader = SparkPlugLoader(event_bus=self.event_bus)

        # ---------------- Modem ----------------
        self.modem_controller = SEEDModemController(storage_root, self.event_bus)

        # ---------------- QbitDialer ----------------
        self.qbit_dialer = QbitDialer(
            storage_root=storage_root,
            event_bus=self.event_bus,
            seed_core=self,
            sparkplug_loader=self.sparkplug_loader,
            fat_layer=None,
            hud_interface=None
        )

        self._tasks = []
        self.history = deque(maxlen=128)
        self.last_dominant_intent = None

    # --------------------------------------------------
    # Start all core systems asynchronously
    # --------------------------------------------------
    async def start(self):
        logger.info("[SEEDCoreIntegration] Starting SEED Core...")

        # Start QbitDialer
        await self.qbit_dialer.start()

        # Start SparkPlugLoader processing loop
        self._tasks.append(asyncio.create_task(self._sparkplug_loop()))

        # Start Modem
        self.modem_controller.start()

        # Start actuator update loop
        self._tasks.append(asyncio.create_task(self._actuator_loop()))

        logger.info("[SEEDCoreIntegration] SEED Core ONLINE")

    # --------------------------------------------------
    # SparkPlug skill processing loop
    # --------------------------------------------------
    async def _sparkplug_loop(self):
        while self.allow_thinking_loop:
            combined_result = self.qbit_dialer.calculate()
            if combined_result is not None:
                payload = {
                    "dominant_intent": str(self.qbit_dialer.inputs.get("dominant_intent", "idle")),
                    "combined": combined_result
                }
                self.sparkplug_loader.enqueue_skill("qbit_processing", payload, priority="high")
            await asyncio.sleep(0.01)

    # --------------------------------------------------
    # Actuator update loop
    # --------------------------------------------------
    async def _actuator_loop(self):
        while self.allow_thinking_loop:
            last = self.get_last_resonance()
            if last and "payload" in last:
                intent = str(last["payload"].get("dominant_intent", "idle"))
                intent_scores = last["payload"].get("intent_scores", {})
                resonance = last["results"]["combined"] if last.get("results") else 0.5

                if intent != self.last_dominant_intent:
                    logger.info(f"[SEEDCoreIntegration] Actuator update → intent={intent}")
                    self.last_dominant_intent = intent

                self.actuator_engine.update(
                    dominant_intent=intent,
                    intent_scores=intent_scores,
                    resonance=float(resonance)
                )

            await asyncio.sleep(0.05)

    # --------------------------------------------------
    # Stop all core systems
    # --------------------------------------------------
    async def stop(self):
        logger.info("[SEEDCoreIntegration] Stopping SEED Core...")
        self.allow_thinking_loop = False

        # Stop QbitDialer
        await self.qbit_dialer.stop()

        # Stop SparkPlugLoader
        await self.sparkplug_loader.shutdown()

        # Stop Modem
        self.modem_controller.stop()

        # Cancel remaining tasks
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("[SEEDCoreIntegration] SEED Core STOPPED")

    # --------------------------------------------------
    # External actuator input -> QbitDialer
    # --------------------------------------------------
    def feed_actuator_state(self, actuator_state: dict):
        self.qbit_dialer.process_input(actuator_state)

    # --------------------------------------------------
    # External sensor or module input
    # --------------------------------------------------
    def inject_input(self, channel, value):
        self.qbit_dialer.inject(channel, value)

    # --------------------------------------------------
    # Retrieve last combined resonance result
    # --------------------------------------------------
    def get_last_resonance(self):
        if self.qbit_dialer.history:
            return self.qbit_dialer.history[-1]
        return None

    # --------------------------------------------------
    # Retrieve current intent
    # --------------------------------------------------
    def get_current_intent(self):
        last = self.get_last_resonance()
        if last and "payload" in last:
            return last["payload"].get("dominant_intent", "idle")
        return "idle"


# ==========================================================
# Example: Boot SEED Core Integration
# ==========================================================
async def main():
    seed_core = SEEDCoreIntegration()
    await seed_core.start()

    # Simulate actuator input
    for i in range(10):
        seed_core.feed_actuator_state({"motor_1": 0.5, "motor_2": 0.7})
        await asyncio.sleep(0.1)

    await seed_core.stop()


if __name__ == "__main__":
    asyncio.run(main())
