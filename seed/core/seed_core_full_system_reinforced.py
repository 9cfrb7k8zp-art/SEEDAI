# ==========================================================
# FILE: seed_core_full_system.py
# PATH: SEED_ROOT/seed/core/seed_core_full_system.py
# PURPOSE: Full SEEDCore integration with AgentManager, QbitDialer,
#          IntentEngine, AnalyticsEngine, ActuatorEngine, SparkPlug
#          + adaptive trend feedback and learning
# UPDATED: 2025-12-26 (patched for safety and async consistency)
# ==========================================================

import asyncio
import logging
import time
from copy import deepcopy
from threading import Thread
from collections import deque

from seed.core.seed_core_full_loop import SEEDCoreFullLoop, FullActuatorEngine
from seed.core.agent_manager import AgentManager, QbitDialer
from seed.core.sparkplug_loader import SparkPlugLoader 
from seed.skills.sparkplug import SparkPlug

logger = logging.getLogger("SEEDCoreFullSystem")
logging.basicConfig(level=logging.INFO)


class SEEDCoreFullSystem:
    """
    Fully integrated SEEDCore system:
    - QbitDialer feeds IntentEngine for independent thought
    - Analytics output feeds back to AgentManager
    - AgentManager relays commands to ActuatorEngine
    - SparkPlug skills triggered asynchronously
    - Adaptive trend feedback updates actuator and confidence dynamically
    """

    TREND_WINDOW = 50

    def __init__(self, intent_engine, analytics_engine, actuator_engine=None, sparkplug=None):
        # Initialize SparkPlugLoader / SparkPlug
        self.sparkplug = sparkplugLoader(skills_root="./skills", event_bus=None)

        self.sparkplug = SparkPlug(self.sparkplug_loader)


        # ActuatorEngine
        self.actuator_engine = actuator_engine or FullActuatorEngine(
            sparkplug_loader=self.sparkplug
        )

        # AgentManager with QbitDialer
        self.agent_manager = AgentManager(
            actuator=self.actuator_engine,
            sparkplug=self.sparkplug,
            seed_core=self,
            intent_engine=intent_engine,
            loop=asyncio.get_event_loop(),
        )

        # Engines
        self.intent_engine = intent_engine
        self.analytics_engine = analytics_engine

        # Full Loop Integration
        self.core_loop = SEEDCoreFullLoop(
            actuator_engine=self.actuator_engine,
            agent_manager=self.agent_manager,
            sparkplug_loader=self.sparkplug
        )

        # QbitDialer for independent thought (safe fallback)
        self.qbit_dialer = getattr(self.agent_manager, "qbit_dialer", QbitDialer())

        # Adaptive trend data
        self.qbit_trend = deque(maxlen=self.TREND_WINDOW)
        self.intent_trend = deque(maxlen=self.TREND_WINDOW)
        self.actuator_trend = deque(maxlen=self.TREND_WINDOW)
        self.analytics_trend = deque(maxlen=self.TREND_WINDOW)
        self.confidence_trend = deque(maxlen=self.TREND_WINDOW)

        # Start AgentManager thinking loop in background
        Thread(target=self._start_agent_manager_loop, daemon=True).start()

    def _start_agent_manager_loop(self):
        loop = getattr(self.agent_manager, "loop", asyncio.get_event_loop())
        asyncio.run_coroutine_threadsafe(
            self.agent_manager.thinking_loop(update_interval=0.05, qbit_source=self.qbit_dialer.get_random_signal),
            loop
        )

    # ======================================================
    # Receive pulses from AgentManager → feed Thought Loop / feedback
    # ======================================================
    async def receive_agent_data(self, pulse: dict):
        try:
            logger.info(f"[SEEDCoreFullSystem] Received agent pulse: {pulse.get('pulse_label')}")

            # Track trends
            self._update_trends(pulse)

            # Adjust actuator behavior adaptively
            self._adaptive_actuator_adjustments()

            # 1. Relay analytics to AnalyticsEngine
            if self.analytics_engine:
                await self.analytics_engine.process_input(pulse)

            # 2. Update ActuatorEngine via FullActuatorEngine
            commands = pulse.get("action_data", {}).get("commands", {})
            for cmd, payload in commands.items():
                if hasattr(self.actuator_engine, "execute_command"):
                    self.actuator_engine.execute_command(cmd, skill_payload=payload)

            # 3. Relay skill requests via SparkPlug
            for skill_request in pulse.get("action_data", {}).get("skill_requests", []):
                skill_name = skill_request.get("skill_name")
                payload = skill_request.get("payload")
                if skill_name and self.sparkplug.skill_exists(skill_name):
                    loop = getattr(self.agent_manager, "loop", asyncio.get_event_loop())
                    asyncio.run_coroutine_threadsafe(
                        self.sparkplug.execute_skill(skill_name, payload),
                        loop
                    )

        except Exception as e:
            logger.warning(f"[SEEDCoreFullSystem] Error processing agent pulse: {e}")

    # ======================================================
    # Trigger a single Qbit cycle for independent thought
    # ======================================================
    async def trigger_qbit_cycle(self):
        qbit_signal = self.qbit_dialer.get_random_signal()
        logger.info(f"[SEEDCoreFullSystem] Qbit signal: {qbit_signal}")

        # IntentEngine input
        if self.intent_engine:
            intent_signals = {
                "qbit_input": qbit_signal,
                "internal_motivation": self.agent_manager.calculate_internal_motivation()
            }
            analytics_output = await self.intent_engine.process_thought_input(intent_signals)
            # Feed analytics output back to AgentManager
            self.agent_manager.process_insight(analytics_output)

            # Track analytics trend
            self.analytics_trend.append(analytics_output)

    # ======================================================
    # Adaptive trend handling
    # ======================================================
    def _update_trends(self, pulse):
        self.qbit_trend.append(pulse.get("action_data", {}).get("qbit_input", 0.0))
        self.intent_trend.append(pulse.get("dominant_intent", "idle"))
        self.actuator_trend.append(deepcopy(pulse.get("actuator_state", {}) or {}))
        self.confidence_trend.append(pulse.get("confidence", 0.0))

    def _adaptive_actuator_adjustments(self):
        """
        Use trends to modulate actuator channels dynamically.
        Example: increase actuator responsiveness if high qbit trend.
        """
        if not self.actuator_trend or not self.qbit_trend or not hasattr(self.actuator_engine, "adjust_channel"):
            return

        avg_qbit = sum(self.qbit_trend)/len(self.qbit_trend) if self.qbit_trend else 0.0
        avg_conf = sum(self.confidence_trend)/len(self.confidence_trend) if self.confidence_trend else 0.0

        # Increase actuator gain slightly if qbit trend high
        for ch, last_val in (self.actuator_trend[-1] or {}).items():
            adjustment = last_val + avg_qbit * 0.1 * avg_conf
            self.actuator_engine.adjust_channel(ch, adjustment)

    # ======================================================
    # Main async loop
    # ======================================================
    async def main_loop(self, update_interval=0.05):
        while True:
            await self.trigger_qbit_cycle()
            await asyncio.sleep(update_interval)


# ======================================================
# Entrypoint
# ======================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Placeholder engines
    class DummyIntentEngine:
        async def process_thought_input(self, payload):
            return {"feedback": f"Processed qbit {payload['qbit_input']}"}

    class DummyAnalyticsEngine:
        async def process_input(self, payload):
            logger.info(f"[AnalyticsEngine] Processed pulse {payload.get('pulse_label')}")

    intent_engine = DummyIntentEngine()
    analytics_engine = DummyAnalyticsEngine()

    system = SEEDCoreFullSystem(intent_engine, analytics_engine)
    asyncio.run(system.main_loop())
