# ==========================================================
# FILE: orchestrator_agent_integration.py
# PATH: SEED_ROOT/seed/core/orchestrator_agent_integration.py
# MODULE: SEED AI OS — Orchestrator AgentManager Integration
# UPDATED: 2026-01-02
# ==========================================================

import asyncio
import logging
import time
from typing import Optional

from seed.core.agent_manager import AgentManager
from seed.core.intent_engine import IntentEngine
from seed.core.actuator_engine import ActuatorEngine
from seed.core.analytics_engine import SEEDAnalyticsEngine
from seed.core.device_manager import DeviceManager
from seed.core.drive import Drive  # Drive integration

logger = logging.getLogger("OrchestratorAgentIntegration")
logger.setLevel(logging.INFO)


class SEEDOrchestratorWithAgent:
    def __init__(self, storage_root: str = "./SEED_ROOT", drive: Optional[Drive] = None):
        # -------------------- Core --------------------
        self.storage_root = storage_root
        self.running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # -------------------- Devices --------------------
        self.device_manager = DeviceManager(storage_root)
        self.qbit_device = self.device_manager.get_best_qbit_device()
        self.em_device = self.device_manager.get_best_em_device()

        # -------------------- Analytics --------------------
        self.analytics_engine = SEEDAnalyticsEngine(storage_root)

        # -------------------- Intent + Actuator --------------------
        self.intent_engine = IntentEngine(analytics_engine=self.analytics_engine)
        self.actuator_engine = ActuatorEngine(fat_layer=None)  # Optional FAT layer integration

        # -------------------- AgentManager --------------------
        self.agent_manager = AgentManager(
            intent_engine=self.intent_engine,
            actuator_engine=self.actuator_engine,
            analytics_engine=self.analytics_engine
        )

        # -------------------- Drive --------------------
        self.drive = drive or Drive(ui=None, log_func=self.log)
        self.agent_manager.drive = self.drive  # attach Drive to AgentManager

        logger.info("[OrchestratorAgentIntegration] Initialized")

    # ======================================================
    # QIA loop integration
    # ======================================================
    async def _qia_loop(self, update_interval: float = 0.05):
        while self.running:
            try:
                # -------------------- Qbit resonance --------------------
                resonance = 0.0
                inputs = {}

                if self.qbit_device and hasattr(self.qbit_device, "device"):
                    resonance = float(getattr(self.qbit_device.device, "resonance_value", 0.0))
                    inputs = getattr(self.qbit_device.device, "inputs", {}) or {}

                # -------------------- Intent scoring --------------------
                dominant_intent, intent_scores = self.intent_engine.score_intents(
                    resonance_value=resonance,
                    inputs=inputs
                )

                if not isinstance(intent_scores, dict):
                    intent_scores = {}

                # -------------------- Submit to AgentManager --------------------
                self.agent_manager.submit_agent_input(
                    agent_id="QIA_Main",
                    intent=dominant_intent,
                    confidence=max(intent_scores.get(dominant_intent, 0.0), 0.0)
                )

                # -------------------- Send AI thought to Drive --------------------
                thought_text = f"Dominant intent: {dominant_intent} | Confidence: {intent_scores.get(dominant_intent, 0.0):.2f}"
                self.drive.send_thought({
                    "text": thought_text,
                    "intent": dominant_intent,
                    "source": "QIA_Main",
                    "priority": 1
                })

                await asyncio.sleep(update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[SEEDOrchestratorWithAgent][QIA] Loop exception: {e}")

    # ======================================================
    # Boot / start
    # ======================================================
    async def boot_async(self):
        self.running = True
        self.loop = asyncio.get_running_loop()

        # DeviceManager init
        await self.device_manager.initialize()

        # Start AgentManager async loop
        self.agent_manager.start_async()

        # Start QIA loop
        self._qia_task = asyncio.create_task(self._qia_loop())

        logger.info("[SEEDOrchestratorWithAgent] Boot complete")

    def boot(self):
        asyncio.run(self.boot_async())

    # ======================================================
    # Shutdown
    # ======================================================
    async def shutdown_async(self):
        self.running = False

        if hasattr(self, "_qia_task") and self._qia_task:
            self._qia_task.cancel()
            try:
                await self._qia_task
            except asyncio.CancelledError:
                pass

        self.agent_manager.stop_async()
        self.device_manager.stop_polling()
        logger.info("[SEEDOrchestratorWithAgent] Shutdown complete")

    def shutdown(self):
        asyncio.run(self.shutdown_async())

    # ======================================================
    # Logging passthrough for Drive and Orchestrator
    # ======================================================
    def log(self, msg: str):
        logger.info(f"[DriveLog] {msg}")
        if self.drive:
            self.drive.send_thought({
                "text": msg,
                "intent": "log",
                "source": "orchestrator_integration",
                "priority": 2
            })
