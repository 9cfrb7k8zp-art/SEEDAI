# ==========================================================
# FILE: seed_master_runtime_chained.py
# PATH: SEED_ROOT/seed/core/seed_master_runtime_chained.py
# PURPOSE: Fully unified SEED runtime with skill chaining
# UPDATED: 2025-12-26
# ==========================================================

import asyncio
import logging
import time
from copy import deepcopy
from threading import Thread
from collections import deque
import random

# ----------------------
# SkillBase
# ----------------------
class SkillBase:
    """Base class for SEED skills with chaining support"""
    def __init__(self, name=None, throttle_interval=0.1, actuator_engine=None):
        self.name = name or "unnamed_skill"
        self.throttle_interval = throttle_interval
        self._last_execution = 0
        self._event_queue = deque()
        self.actuator_engine = actuator_engine
        self.skill_chain = []  # names of skills to execute after this
        self._chain_throttle_interval = 0.05
        self._last_chain_time = 0
        self.logger = logging.getLogger(f"SkillBase.{self.name}")

    async def execute_async(self, *args, **kwargs):
        now = time.time()
        if now - self._last_execution < self.throttle_interval:
            return
        self._last_execution = now
        try:
            if asyncio.iscoroutinefunction(self.execute):
                result = await self.execute(*args, **kwargs)
            else:
                result = self.execute(*args, **kwargs)
        except Exception as e:
            self.logger.exception(f"[{self.name}] Execution error: {e}")
            result = None

        # Trigger chained skills
        await self.execute_chain(result)
        return result

    def execute(self, *args, **kwargs):
        raise NotImplementedError("execute must be implemented by subclass")

    def set_skill_chain(self, chain_list):
        self.skill_chain = chain_list or []

    async def execute_chain(self, payload):
        now = time.time()
        if now - self._last_chain_time < self._chain_throttle_interval:
            return
        self._last_chain_time = now

        for skill_name in self.skill_chain:
            if self.actuator_engine and hasattr(self.actuator_engine, "sparkplug"):
                sparkplug = self.actuator_engine.sparkplug
                if sparkplug and skill_name in sparkplug.skills:
                    await sparkplug.execute_skill(skill_name, deepcopy(payload))


# ----------------------
# DeepScanSkill
# ----------------------
class DeepScanSkill(SkillBase):
    def __init__(self, actuator_engine=None):
        super().__init__(name="deep_scan_skill", actuator_engine=actuator_engine)
        self.mode = "default"
        self.status = "idle"

    def execute(self, data=None):
        self.status = "running"
        scan_input = data.get("scan_input") if isinstance(data, dict) else data
        self.send_actuator_command(
            dominant_intent="focus",
            intent_scores={"focus": 1.0},
            resonance=0.7
        )
        self.status = "completed"
        return {"result": {"status": "success", "mode": self.mode, "input": scan_input}}


# ----------------------
# LightScanSkill (example chained skill)
# ----------------------
class LightScanSkill(SkillBase):
    def __init__(self, actuator_engine=None):
        super().__init__(name="light_scan_skill", actuator_engine=actuator_engine)
        self.mode = "default"

    def execute(self, data=None):
        scan_input = data.get("scan_input") if isinstance(data, dict) else data
        self.send_actuator_command(dominant_intent="observe", intent_scores={"observe":1.0}, resonance=0.5)
        return {"result": {"status":"light_scan_complete", "input": scan_input}}


# ----------------------
# SparkPlug
# ----------------------
class SparkPlug:
    def __init__(self):
        self.skills = {}
        self.logger = logging.getLogger("SparkPlug")

    def register_skill(self, skill_obj):
        self.skills[skill_obj.name] = skill_obj
        self.logger.info(f"[SparkPlug] Skill registered: {skill_obj.name}")

    async def execute_skill(self, skill_name, payload):
        skill = self.skills.get(skill_name)
        if skill:
            await skill.execute_async(payload)


# ----------------------
# FullActuatorEngine
# ----------------------
class FullActuatorEngine:
    def __init__(self, sparkplug_loader=None):
        self.channels = {}
        self.sparkplug = sparkplug_loader

    def update(self, **kwargs):
        pass

    def execute_command(self, cmd, skill_payload=None):
        pass

    def adjust_channel(self, ch, value):
        self.channels[ch] = value


# ----------------------
# QbitDialer
# ----------------------
class QbitDialer:
    def get_random_signal(self):
        return random.random()


# ----------------------
# AgentManager
# ----------------------
class AgentManager:
    def __init__(self, actuator=None, seed_core=None, sparkplug=None, loop=None):
        self.actuator = actuator
        self.seed_core = seed_core
        self.sparkplug = sparkplug
        self.loop = loop or asyncio.get_event_loop()
        self.qbit_dialer = QbitDialer()
        self._last_actuator_values = {}
        self._confidence = 0.3

    async def thinking_loop(self, update_interval=0.05, qbit_source=lambda: 0.0):
        while True:
            qbit_input = float(qbit_source() or 0.0)
            pulse = {"pulse_label": "qbit_cycle", "action_data": {"qbit_input": qbit_input}, "dominant_intent": "idle", "actuator_state": deepcopy(self._last_actuator_values), "confidence": self._confidence}
            if self.seed_core:
                await self.seed_core.receive_agent_data(pulse)
            await asyncio.sleep(update_interval)

    def calculate_internal_motivation(self):
        return min(1.0, 0.5 + 0.05*len([]))

    def process_insight(self, insight_data):
        pass


# ----------------------
# SEEDCoreFullSystem with Skill Chaining
# ----------------------
class SEEDCoreFullSystem:
    TREND_WINDOW = 50
    def __init__(self, intent_engine, analytics_engine):
        self.sparkplug = SparkPlug()
        self.actuator_engine = FullActuatorEngine(sparkplug_loader=self.sparkplug)
        self.agent_manager = AgentManager(actuator=self.actuator_engine, seed_core=self, sparkplug=self.sparkplug, loop=asyncio.get_event_loop())
        self.intent_engine = intent_engine
        self.analytics_engine = analytics_engine
        self.qbit_trend = deque(maxlen=self.TREND_WINDOW)
        self.intent_trend = deque(maxlen=self.TREND_WINDOW)
        self.actuator_trend = deque(maxlen=self.TREND_WINDOW)
        self.analytics_trend = deque(maxlen=self.TREND_WINDOW)
        self.confidence_trend = deque(maxlen=self.TREND_WINDOW)

        # Preload skills
        self.deep_scan_skill = DeepScanSkill(actuator_engine=self.actuator_engine)
        self.light_scan_skill = LightScanSkill(actuator_engine=self.actuator_engine)

        # Chain light_scan -> deep_scan
        self.light_scan_skill.set_skill_chain(["deep_scan_skill"])

        # Register skills
        self.sparkplug.register_skill(self.deep_scan_skill)
        self.sparkplug.register_skill(self.light_scan_skill)

        # Start AgentManager thinking loop
        Thread(target=self._start_agent_manager_loop, daemon=True).start()

    def _start_agent_manager_loop(self):
        loop = self.agent_manager.loop or asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(
            self.agent_manager.thinking_loop(update_interval=0.05, qbit_source=self.agent_manager.qbit_dialer.get_random_signal),
            loop
        )

    async def receive_agent_data(self, pulse: dict):
        self._update_trends(pulse)
        if self.analytics_engine:
            await self.analytics_engine.process_input(pulse)

        # Trigger chained skills on each Qbit pulse
        if self.sparkplug.skill_exists("light_scan_skill"):
            await self.sparkplug.execute_skill("light_scan_skill", {"scan_input": pulse.get("action_data", {}).get("qbit_input")})

    def _update_trends(self, pulse):
        self.qbit_trend.append(pulse.get("action_data", {}).get("qbit_input", 0.0))
        self.intent_trend.append(pulse.get("dominant_intent", "idle"))
        self.actuator_trend.append(deepcopy(pulse.get("actuator_state", {})))
        self.confidence_trend.append(pulse.get("confidence", 0.0))

    async def trigger_qbit_cycle(self):
        qbit_signal = self.agent_manager.qbit_dialer.get_random_signal()
        if self.intent_engine:
            intent_signals = {"qbit_input": qbit_signal}
            analytics_output = await self.intent_engine.process_thought_input(intent_signals)
            self.agent_manager.process_insight(analytics_output)
            self.analytics_trend.append(analytics_output)

    async def main_loop(self, update_interval=0.05):
        while True:
            await self.trigger_qbit_cycle()
            await asyncio.sleep(update_interval)


# ======================================================
# Entrypoint
# ======================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Dummy engines
    class DummyIntentEngine:
        async def process_thought_input(self, payload):
            return {"feedback": f"Processed qbit {payload['qbit_input']}"}

    class DummyAnalyticsEngine:
        async def process_input(self, payload):
            logging.info(f"[AnalyticsEngine] Processed pulse {payload.get('pulse_label')}")

    system = SEEDCoreFullSystem(DummyIntentEngine(), DummyAnalyticsEngine())
    asyncio.run(system.main_loop())
