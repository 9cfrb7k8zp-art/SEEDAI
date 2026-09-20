# ==========================================================
# FILE: seed_core_full_system.py
# PATH: SEED_ROOT/seed/core/seed_core_full_system.py
# VERSION: 1.0.0 (CLEAN MERGE – MASTER RUNTIME)
# UPDATED: 2025-12-26
#
# PURPOSE:
#   - Unified SEED runtime orchestrator
#   - Integrates:
#       • AgentManager
#       • QbitDialer
#       • IntentEngine
#       • AnalyticsEngine
#       • FullActuatorEngine
#       • SparkPlug (queue / debounce)
#       • SparkPlugLoader (skill authority)
#
# BLUEPRINT:
#   SEEDCoreFullSystem
#     ├── SparkPlugLoader  (owns skills, executes them)
#     ├── SparkPlug        (queues + debounces skill requests)
#     ├── AgentManager     (reasoning, intent, pulses)
#     ├── FullActuatorEngine (hardware / channel abstraction)
#     ├── QbitDialer       (independent signal source)
#     └── Trend Memory     (adaptive feedback)
#
# NOTES:
#   - SparkPlug NEVER executes skills directly
#   - SparkPlugLoader is the ONLY skill registry
#   - ActuatorEngine talks to Loader, not SparkPlug
#   - Async-safe thread → loop bridging enforced
#   - Designed to be extended, not rewritten
# ==========================================================

import asyncio
import logging
from copy import deepcopy
from threading import Thread
from collections import deque

from seed.core.seed_core_full_loop import SEEDCoreFullLoop, FullActuatorEngine
from seed.core.agent_manager import AgentManager
from seed.core.sparkplug_loader import SparkPlugLoader
from seed.skills.sparkplug import SparkPlug

logger = logging.getLogger("SEEDCoreFullSystem")
logging.basicConfig(level=logging.INFO)


class SEEDCoreFullSystem:
    TREND_WINDOW = 50

    # ------------------------------------------------------
    # INIT
    # ------------------------------------------------------
    def __init__(self, intent_engine, analytics_engine, emit=None, fiveg=None, event_bus=None,  actuator_engine=None):
        self.emit = emit      
        self.fiveG = fiveg
        self.event_bus = event_bus
        # ----------------------------
        # SparkPlugLoader (SKILL AUTHORITY)
        # ----------------------------
        self.sparkplug_loader = SparkPlugLoader(
            skills_root="./skills",
            event_bus=None
        )

        # ----------------------------
        # SparkPlug (QUEUE + DEBOUNCE)
        # ----------------------------
        self.sparkplug = SparkPlug(
            sparkplug_loader=self.sparkplug_loader,
            skills_root="./skills",
            event_bus=None
        )

        # ----------------------------
        # Actuator Engine
        # ----------------------------
        self.actuator_engine = actuator_engine or FullActuatorEngine(
            sparkplug_loader=self.sparkplug_loader
        )

        # ----------------------------
        # Engines
        # ----------------------------
        self.intent_engine = intent_engine
        self.analytics_engine = analytics_engine

        # ----------------------------
        # Agent Manager
        # ----------------------------
        self.agent_manager = AgentManager(
            actuator=self.actuator_engine,
            sparkplug=self.sparkplug,
            seed_core=self,
            intent_engine=self.intent_engine,
            loop=asyncio.get_event_loop(),
        )

        # ----------------------------
        # Core Loop
        # ----------------------------
        self.core_loop = SEEDCoreFullLoop(
            actuator_engine=self.actuator_engine,
            agent_manager=self.agent_manager,
            sparkplug_loader=self.sparkplug_loader
        )

        # ----------------------------
        # Qbit Dialer (safe fallback)
        # ----------------------------
        self.qbit_dialer = getattr(self.agent_manager, "qbit_dialer", QbitDialer())

        # ----------------------------
        # Trend Memory
        # ----------------------------
        self.qbit_trend = deque(maxlen=self.TREND_WINDOW)
        self.intent_trend = deque(maxlen=self.TREND_WINDOW)
        self.actuator_trend = deque(maxlen=self.TREND_WINDOW)
        self.analytics_trend = deque(maxlen=self.TREND_WINDOW)
        self.confidence_trend = deque(maxlen=self.TREND_WINDOW)

        # ----------------------------
        # Start Agent Thinking Loop
        # ----------------------------
        Thread(
            target=self._start_agent_manager_loop,
            daemon=True
        ).start()

        logger.info("[SEEDCoreFullSystem] Master runtime initialized")

    # ------------------------------------------------------
    # AgentManager background loop
    # ------------------------------------------------------
    def _start_agent_manager_loop(self):
        loop = getattr(self.agent_manager, "loop", asyncio.get_event_loop())
        asyncio.run_coroutine_threadsafe(
            self.agent_manager.thinking_loop(
                update_interval=0.05,
                qbit_source=self.qbit_dialer.get_random_signal
            ),
            loop
        )

    # ------------------------------------------------------
    # RECEIVE AGENT PULSE
    # ------------------------------------------------------
    async def receive_agent_data(self, pulse: dict):
        try:
            logger.info(
                f"[SEEDCoreFullSystem] Pulse received → "
                f"{pulse.get('pulse_label', 'unknown')}"
            )

            # --- Trends
            self._update_trends(pulse)
            self._adaptive_actuator_adjustments()

            # --- Analytics
            if self.analytics_engine:
                await self.analytics_engine.process_input(pulse)

            # --- Actuator Commands
            commands = pulse.get("action_data", {}).get("commands", {})
            for cmd, payload in commands.items():
                if hasattr(self.actuator_engine, "execute_command"):
                    self.actuator_engine.execute_command(
                        cmd,
                        skill_payload=payload
                    )

            # --- Skill Requests (via SparkPlug)
            for req in pulse.get("action_data", {}).get("skill_requests", []):
                skill = req.get("skill_name")
                payload = req.get("payload", {})
                priority = req.get("priority", 0.5)

                if self.sparkplug_loader.skill_exists(skill):
                    self.sparkplug.submit_skill(
                        skill_name=skill,
                        payload=payload,
                        priority=priority,
                        source="AgentManager"
                    )

        except Exception as e:
            logger.warning(
                f"[SEEDCoreFullSystem] Pulse processing error: {e}"
            )

    # ------------------------------------------------------
    # QBIT CYCLE
    # ------------------------------------------------------
    async def trigger_qbit_cycle(self):
        try:
            qbit_signal = self.qbit_dialer.get_random_signal()
            logger.info(f"[SEEDCoreFullSystem] Qbit={qbit_signal}")

            if self.intent_engine:
                thought = {
                    "qbit_input": qbit_signal,
                    "internal_motivation":
                        self.agent_manager.calculate_internal_motivation()
                }

                analytics = await self.intent_engine.process_thought_input(thought)
                self.agent_manager.process_insight(analytics)
                self.analytics_trend.append(analytics)

        except Exception as e:
            logger.warning(f"[SEEDCoreFullSystem] Qbit error: {e}")

    # ------------------------------------------------------
    # TREND MANAGEMENT
    # ------------------------------------------------------
    def _update_trends(self, pulse):
        self.qbit_trend.append(
            pulse.get("action_data", {}).get("qbit_input", 0.0)
        )
        self.intent_trend.append(
            pulse.get("dominant_intent", "idle")
        )
        self.actuator_trend.append(
            deepcopy(pulse.get("actuator_state", {}) or {})
        )
        self.confidence_trend.append(
            pulse.get("confidence", 0.0)
        )

    def _adaptive_actuator_adjustments(self):
        if not (
            self.qbit_trend and
            self.actuator_trend and
            hasattr(self.actuator_engine, "adjust_channel")
        ):
            return

        avg_qbit = sum(self.qbit_trend) / len(self.qbit_trend)
        avg_conf = (
            sum(self.confidence_trend) / len(self.confidence_trend)
            if self.confidence_trend else 0.0
        )

        for ch, val in self.actuator_trend[-1].items():
            adjustment = val + avg_qbit * 0.1 * avg_conf
            self.actuator_engine.adjust_channel(ch, adjustment)

    # ------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------
    async def main_loop(self, update_interval=0.05):
        while True:
            await self.trigger_qbit_cycle()
            await asyncio.sleep(update_interval)


# ======================================================
# ENTRYPOINT (DEV / STANDALONE)
# ======================================================
if __name__ == "__main__":

    class DummyIntentEngine:
        async def process_thought_input(self, payload):
            return {
                "feedback": f"Processed qbit {payload['qbit_input']}",
                "confidence": 0.5
            }

    class DummyAnalyticsEngine:
        async def process_input(self, payload):
            logger.info(
                f"[AnalyticsEngine] Pulse={payload.get('pulse_label')}"
            )

    system = SEEDCoreFullSystem(
        intent_engine=DummyIntentEngine(),
        analytics_engine=DummyAnalyticsEngine()
    )

    asyncio.run(system.main_loop())
