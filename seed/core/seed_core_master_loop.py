# ==========================================================
# FILE: seed_core_master_loop.py
# PATH: SEED_ROOT/seed/core/seed_core_master_loop.py
# PURPOSE: SEEDCore Master System v5.1 — Async & Safe Trends
# UPDATED: 2026-01-02
# ==========================================================

import asyncio
import logging
import time
from collections import deque, defaultdict
from copy import deepcopy

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# -------------------------------
# Import core components
# -------------------------------
from seed.core.seed_core_full_loop import SEEDCoreFullLoop, FullActuatorEngine
from seed.core.agent_manager import AgentManager, QbitDialer
from seed.skills.sparkplug import SparkPlug

logger = logging.getLogger("SEEDCoreMasterLoop")
logging.basicConfig(level=logging.INFO)


# ==========================================================
# Master SEEDCore System
# ==========================================================
class SEEDCoreMasterSystem:
    TREND_WINDOW = 50

    def __init__(self, intent_engine, analytics_engine, actuator_engine=None, sparkplug=None):
        self.loop = asyncio.get_event_loop()

        self.sparkplug = sparkplug or SparkPlug(skills_root="./skills", event_bus=None)
        self.actuator_engine = actuator_engine or FullActuatorEngine(sparkplug_loader=self.sparkplug)

        # -------------------------------
        # AgentManager
        # -------------------------------
        self.agent_manager = AgentManager(
            actuator=self.actuator_engine,
            sparkplug=self.sparkplug,
            seed_core=self,
            loop=self.loop
        )

        # Engines
        self.intent_engine = intent_engine
        self.analytics_engine = analytics_engine

        # Core loop
        self.core_loop = SEEDCoreFullLoop(
            actuator_engine=self.actuator_engine,
            agent_manager=self.agent_manager,
            sparkplug_loader=self.sparkplug
        )

        self.qbit_dialer = self.agent_manager.qbit_dialer

        # -------------------------------
        # Trends (thread-safe via asyncio.Lock)
        # -------------------------------
        self._trend_lock = asyncio.Lock()
        self.qbit_trend = deque(maxlen=self.TREND_WINDOW)
        self.intent_trend = deque(maxlen=self.TREND_WINDOW)
        self.actuator_trend = deque(maxlen=self.TREND_WINDOW)
        self.confidence_trend = deque(maxlen=self.TREND_WINDOW)
        self.channel_rewards = defaultdict(lambda: 1.0)
        self.channel_history = defaultdict(lambda: deque(maxlen=self.TREND_WINDOW))

    # ======================================================
    # Receive pulses
    # ======================================================
    async def receive_agent_data(self, pulse: dict):
        try:
            async with self._trend_lock:
                # Update trends
                qbit_input = pulse.get("action_data", {}).get("qbit_input", 0.0)
                self.qbit_trend.append(qbit_input)
                self.intent_trend.append(pulse.get("dominant_intent", "idle"))
                self.actuator_trend.append(deepcopy(pulse.get("actuator_state", {})))
                self.confidence_trend.append(pulse.get("confidence", 0.0))

                # Update per-channel history
                last_act = pulse.get("actuator_state", {})
                for ch, val in last_act.items():
                    self.channel_history[ch].append(val)

                # Adaptive actuator adjustments
                self._adaptive_actuator_adjustments()

                # Reinforce confidence decay
                self._reinforce_confidence_decay()

            # Analytics
            if self.analytics_engine:
                analytics_output = await self.analytics_engine.process_input(pulse)
                self.agent_manager.process_insight(analytics_output)
                self._update_channel_rewards(analytics_output)

            # Execute commands
            commands = pulse.get("action_data", {}).get("commands", {})
            for cmd, payload in commands.items():
                self.actuator_engine.execute_command(cmd, skill_payload=payload)

            # Execute SparkPlug skills
            for skill_request in pulse.get("action_data", {}).get("skill_requests", []):
                skill_name = skill_request.get("skill_name")
                payload = skill_request.get("payload")
                if skill_name and self.sparkplug.skill_exists(skill_name):
                    asyncio.create_task(self.sparkplug.execute_skill(skill_name, payload))

        except Exception as e:
            logger.warning(f"[SEEDCoreMaster] Error processing pulse: {e}")

    # ======================================================
    # Trigger Qbit cycle
    # ======================================================
    async def trigger_qbit_cycle(self):
        qbit_signal = self.qbit_dialer.get_random_signal()
        async with self._trend_lock:
            self.qbit_trend.append(qbit_signal)

        if self.intent_engine:
            intent_signals = {
                "qbit_input": qbit_signal,
                "internal_motivation": self.agent_manager.calculate_internal_motivation()
            }
            analytics_output = await self.intent_engine.process_thought_input(intent_signals)
            self.agent_manager.process_insight(analytics_output)
            async with self._trend_lock:
                self.confidence_trend.append(analytics_output.get("reward_score", 1.0))
                self._update_channel_rewards(analytics_output)

    # ======================================================
    # Adaptive actuator adjustments
    # ======================================================
    def _adaptive_actuator_adjustments(self):
        if not self.actuator_trend or not self.qbit_trend:
            return

        avg_qbit = sum(self.qbit_trend)/len(self.qbit_trend)
        avg_conf = sum(self.confidence_trend)/len(self.confidence_trend)
        last_actuators = self.actuator_trend[-1] or {}

        for ch, last_val in last_actuators.items():
            reward_factor = self.channel_rewards.get(ch, 1.0)
            adjustment = last_val + avg_qbit * 0.1 * avg_conf * reward_factor
            adjustment = min(max(adjustment, 0.0), 1.0)  # clamp
            self.actuator_engine.adjust_channel(ch, adjustment)

    # ======================================================
    # Confidence decay reinforcement
    # ======================================================
    def _reinforce_confidence_decay(self):
        avg_conf = sum(self.confidence_trend)/len(self.confidence_trend) if self.confidence_trend else 0.5
        self.agent_manager.CONFIDENCE_DECAY_RATE = 0.02 * (1.5 - avg_conf)
        self.agent_manager.DAMPENING_FACTOR = 0.6 * (0.5 + avg_conf)

    # ======================================================
    # Update channel rewards
    # ======================================================
    def _update_channel_rewards(self, analytics_output):
        reward_score = analytics_output.get("reward_score", 1.0)
        last_actuators = self.actuator_trend[-1] or {}
        for ch in last_actuators:
            self.channel_rewards[ch] = self.channel_rewards.get(ch, 1.0) * reward_score

    # ======================================================
    # Visualization loop
    # ======================================================
    async def start_visualization(self):
        plt.style.use("seaborn-darkgrid")
        fig, axs = plt.subplots(3, 1, figsize=(10, 8))
        fig.suptitle("SEEDCore Master Trends")

        async def get_trends_copy():
            async with self._trend_lock:
                return (
                    list(self.qbit_trend),
                    list(self.intent_trend),
                    {ch: list(hist) for ch, hist in self.channel_history.items()}
                )

        def animate(i):
            qbit_trend, intent_trend, channel_hist = asyncio.run(get_trends_copy())
            
            axs[0].cla()
            axs[1].cla()
            axs[2].cla()

            # Qbit trend
            axs[0].plot(qbit_trend, label="Qbit Input")
            axs[0].set_ylabel("Qbit")
            axs[0].legend(loc="upper right")

            # Intent trend
            intent_labels = list(range(len(intent_trend)))
            intent_values = [hash(str(i)) % 10 for i in intent_trend]
            axs[1].plot(intent_labels, intent_values, label="Intent")
            axs[1].set_ylabel("Intent (hashed)")
            axs[1].legend(loc="upper right")

            # Actuator trend
            for ch, hist in channel_hist.items():
                axs[2].plot(hist, label=f"Channel {ch}")
            axs[2].set_ylabel("Actuators")
            axs[2].legend(loc="upper right")

        ani = FuncAnimation(fig, animate, interval=250)
        plt.show()

    # ======================================================
    # Main loop
    # ======================================================
    async def main_loop(self, update_interval=0.05):
        while True:
            await self.trigger_qbit_cycle()
            await asyncio.sleep(update_interval)
