# =====================================================
# FILE: seed_core_full_loop.py
# VERSION: 0.8.0
# STATUS: Alpha → Async-Sync, Log-Throttle, Conflict-Free
# PURPOSE: Full SEEDCore integration with closed feedback loop
#          - IntentEngine → AgentManager → ActuatorEngine → SparkPlugLoader
#          - Async loops, log throttling, feedback integration
# =====================================================

import asyncio
import logging
import time
from collections import deque
from copy import deepcopy

# ---------------- LOGGING ----------------
logger = logging.getLogger("SEEDCoreFullLoop")
logging.basicConfig(level=logging.INFO)

# ---------------- STUBS / BASES ----------------
class HUDInterface:
    def push(self, packet):
        logger.info(f"[HUD] Packet pushed: {packet}")

    def show_alert(self, message):
        logger.warning(f"[HUD ALERT] {message}")

# =====================================================
# INTENT ENGINE v03.2 (Loop-Safe, Log-Throttle)
# =====================================================
class IntentEngine:
    INTENT_TTL = 0.6
    AGENT_SPAWN_COOLDOWN = 1.0

    def __init__(self, analytics_engine=None, agent_manager=None, hud_interface=None):
#        from seed.core.heartbeat import HeartbeatEmitter
        self.analytics_engine = analytics_engine
        self.agent_manager = agent_manager
        self.hud_interface = hud_interface

        self.intent_history = deque(maxlen=128)
        self.intent_weights = {}
        self.last_decision_time = 0.0
        self.last_agent_spawn = {}
        self.external_inputs = {}
        self.last_logged_intent = None

        self.intents = {
            "idle":      {"seed": 0.2, "user": 0.1, "noise": -0.3, "audio": -0.2, "vision": -0.2},
            "observe":   {"seed": 0.6, "vision": 0.7, "audio": 0.4, "noise": -0.1},
            "focus":     {"user": 0.9, "seed": 0.6, "noise": -0.4},
            "explore":   {"seed": 0.8, "noise": 0.3, "vision": 0.5},
            "defensive": {"noise": 0.9, "audio": 0.6, "vision": 0.4, "user": -0.3},
        }
        logger.info("[IntentEngine] Online (Loop-Safe)")

    def _init_intent_weights(self, intent):
        if intent not in self.intent_weights:
            self.intent_weights[intent] = {"qbit": 0.6, "agent": 0.4}

    def update_inputs(self, inputs: dict):
        if isinstance(inputs, dict):
            self.external_inputs = deepcopy(inputs)

    def score_intents(self, resonance_value=0.5, inputs=None):
        now = time.time()
        if now - self.last_decision_time < self.INTENT_TTL:
            return "idle", {}

        self.last_decision_time = now
        resonance_value = max(0.0, min(1.0, float(resonance_value) if isinstance(resonance_value, (int, float)) else 0.0))
        inputs = inputs if isinstance(inputs, dict) else self.external_inputs
        channels = ["seed", "user", "noise", "audio", "vision"]
        inputs = {k: float(inputs.get(k, 0.0)) for k in channels}

        prior_scores = {intent: sum(inputs.get(ch,0.0)*w for ch,w in weights.items())
                        for intent, weights in self.intents.items()}

        fused_scores = {}
        for intent in prior_scores:
            self._init_intent_weights(intent)
            fused_scores[intent] = max(0.0, prior_scores[intent] * resonance_value)

        dominant_intent = max(fused_scores, key=fused_scores.get) if fused_scores else "idle"

        # Agent spawn debounced
        if self.agent_manager:
            last = self.last_agent_spawn.get(dominant_intent,0)
            if now - last > self.AGENT_SPAWN_COOLDOWN:
                try:
                    self.agent_manager.submit_agent_intent(
                        agent_id=f"intent_{dominant_intent}",
                        intent=dominant_intent,
                        confidence=fused_scores.get(dominant_intent,0.0)
                    )
                    self.last_agent_spawn[dominant_intent] = now
                except Exception as e:
                    logger.warning(f"[IntentEngine] Agent submit failed: {e}")

        # Log only if dominant intent changed
        if dominant_intent != self.last_logged_intent:
            logger.info(f"[IntentEngine] Dominant={dominant_intent} Scores={fused_scores}")
            self.last_logged_intent = dominant_intent

        packet = {
            "type":"intent_decision",
            "skill_name":dominant_intent,
            "dominant":dominant_intent,
            "scores":fused_scores,
            "resonance":resonance_value,
            "timestamp":now,
        }
        if self.hud_interface:
            try: self.hud_interface.push(packet)
            except Exception: pass

        self.intent_history.append(dominant_intent)
        return dominant_intent, fused_scores

# =====================================================
# AGENT MANAGER v1.51 (Async-Safe)
# =====================================================
class AgentManager:
    DAMPENING_FACTOR = 0.6
    CONFIDENCE_DECAY_RATE = 0.02

    def __init__(self, actuator=None, hud_interface=None, loop=None):
        self.actuator = actuator
        self.hud_interface = hud_interface or HUDInterface()
        self.loop = loop or asyncio.get_event_loop()

        self.agent_inputs = {}
        self.pulse_callback = None

    def set_pulse_callback(self, callback):
        self.pulse_callback = callback

    def submit_agent_intent(self, agent_id, intent, confidence):
        self.agent_inputs[agent_id] = (intent, confidence, time.time())

    async def generate_cycle(self):
        dominant_intent = "idle"
        if self.agent_inputs:
            dominant_intent = max(self.agent_inputs.values(), key=lambda x:x[1])[0]

        pulse = {
            "dominant_intent": dominant_intent,
            "commands": {"increase_analysis_depth": {}},
            "skill_requests": [{"skill_name":"deep_scan_skill","payload":{"param":42}}]
        }
        if self.pulse_callback:
            try: self.pulse_callback(pulse)
            except Exception as e:
                logger.warning(f"[AgentManager] Pulse callback error: {e}")
        return pulse

# =====================================================
# FULL ACTUATOR ENGINE (Log-Throttle)
# =====================================================
class FullActuatorEngine:
    def __init__(self, sparkplug_loader=None):
        self.channels = {}
        self.intent_gains = {"analysis_depth":1.0}
        self.sparkplug_loader = sparkplug_loader
        self.last_dominant_intent = None

    def execute_command(self, command_name, skill_payload=None):
        current_intent = skill_payload.get("dominant_intent") if skill_payload else None
        if current_intent != self.last_dominant_intent:
            logger.info(f"[Actuator] Dominant Intent Changed → {current_intent}")
            self.last_dominant_intent = current_intent

# =====================================================
# SPARKPLUG LOADER
# =====================================================
class SparkPlugLoader:
    def __init__(self):
        self.skills = {}

    def register_skill(self, name, func):
        self.skills[name] = func

    def skill_exists(self, name):
        return name in self.skills

    async def execute_skill(self, name, payload):
        if self.skill_exists(name):
            logger.info(f"[SparkPlugLoader] Executing {name} payload={payload}")
            await self.skills[name](payload)

# =====================================================
# SEEDCORE FULL LOOP
# =====================================================
class SEEDCoreFullLoop:
    def __init__(self, actuator_engine, agent_manager, intent_engine, sparkplug_loader):
        self.actuator_engine = actuator_engine
        self.agent_manager = agent_manager
        self.intent_engine = intent_engine
        self.sparkplug_loader = sparkplug_loader

        self.actuator_engine.sparkplug_loader = self.sparkplug_loader
        self.agent_manager.set_pulse_callback(self.receive_agent_data)


    async def intent_loop(self):
        while True:
            try:
                await asyncio.to_thread(self.intent_engine.score_intents)
            except Exception as e:
                logger.warning(f"[IntentEngine Loop] {e}")
            await asyncio.sleep(0.1)

    async def thought_loop(self):
        while True:
            try:
                await self.agent_manager.generate_cycle()
            except Exception as e:
                logger.error(f"[Thought Loop] {e}")
            await asyncio.sleep(0.05)

    def receive_agent_data(self, pulse: dict):
        try:
            for cmd, payload in pulse.get("commands", {}).items():
                self.actuator_engine.execute_command(cmd, skill_payload=payload)
            for skill_req in pulse.get("skill_requests", []):
                skill_name = skill_req.get("skill_name")
                payload = skill_req.get("payload")
                if skill_name and self.sparkplug_loader.skill_exists(skill_name):
                    asyncio.create_task(self.sparkplug_loader.execute_skill(skill_name, payload))
        except Exception as e:
            logger.warning(f"[SEEDCoreFullLoop] receive_agent_data error: {e}")

# =====================================================
# LAUNCH EXAMPLE
# =====================================================
if __name__=="__main__":
    actuator = FullActuatorEngine()
    agent_manager = AgentManager()
    intent_engine = IntentEngine(agent_manager=agent_manager)
    sparkplug_loader = SparkPlugLoader()

    seed_loop = SEEDCoreFullLoop(actuator, agent_manager, intent_engine, sparkplug_loader)

    # Register a test deep_scan_skill
    async def deep_scan_skill(payload):
        logger.info(f"[Skill] deep_scan_skill executed with {payload}")
    sparkplug_loader.register_skill("deep_scan_skill", deep_scan_skill)

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        logger.info("[SEEDCoreFullLoop] Shutdown requested")
