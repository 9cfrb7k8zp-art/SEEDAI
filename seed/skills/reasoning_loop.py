# ==========================================================
# FILE: reasoning_loop.py
# PATH: SEED_ROOT/seed/skills/reasoning_loop.py
# SPARKPLUG SKILL: ReasoningLoop (TRACKID + MULTI-CHANNEL HUD + QBIT + SEED AI 'S' ID)
# VERSION: 3.0
# UPDATED: 2025-12-31
# DESCRIPTION:
# - Fully TrackID-aware reasoning cycles
# - Multi-channel HUD & Qbit mapping (multi-level channels)
# - Waits for responses from queues before next input/output
# - Executes dynamic actions ("plan to action")
# - Shutdown-aware + async-safe + retry/backpressure handling
# ==========================================================

import time
import random
import logging
import asyncio
import copy
from typing import Any, Dict, Optional

from seed.core.tracked_data import TrackedData
from seed.core.event_bus import ChannelID

logger = logging.getLogger("ReasoningLoop")
logger.setLevel(logging.INFO)

class ReasoningLoop:
    def __init__(self,
                 agent_manager=None,
                 analytics_engine=None,
                 intent_engine=None,
                 event_bus=None,
                 qbit_dialer=None,
                 sparkplug=None,
                 shutdown_flag = [],
                 retry_interval = 0.05):
        self.agent_manager = agent_manager
        self.analytics_engine = analytics_engine
        self.intent_engine = intent_engine
        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer
        self.sparkplug = sparkplug
        self._running = False
        self._lock = asyncio.Lock()
        self.shutdown_flag = shutdown_flag

        self.dynamic_actions = ["active_modules", "connect_to_network", "build_driver"]
        self._qbit_input_channels = 32
        self._qbit_output_channels = 64
        self._hud_channels: Dict[str, list] = {}
        self._qbit_skill_map: Dict[str, dict] = {}
        self._channel_responses: Dict[str, asyncio.Future] = {}
        self.retry_interval = retry_interval

    # -----------------------------
    # Start / Stop
    # -----------------------------
    def start(self):
        if self._running:
            return
        self._running = True
        asyncio.create_task(self._loop_async())
        logger.info("[ReasoningLoop] Started (TrackID + HUD + Qbit + SEED AI 'S')")

    def stop(self):
        self._running = False
        logger.info("[ReasoningLoop] Stopped")

    async def _loop_async(self):
        while self._running:
            if self.shutdown_flag and self.shutdown_flag.is_set():
                await asyncio.sleep(0.05)
                continue
            try:
                await self._process_events()
            except Exception as e:
                logger.error(f"[ReasoningLoop] Loop exception: {e}")
            await asyncio.sleep(0.01)

    async def _process_events(self):
        # Placeholder for future event ingestion
        await asyncio.sleep(0.001)

    # -----------------------------
    # Safe payload copy
    # -----------------------------
    def _safe_payload(self, payload) -> Dict[str, Any]:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return copy.deepcopy(payload)
        try:
            return copy.deepcopy(vars(payload))
        except Exception:
            return {"value": payload}

    # -----------------------------
    # Single-cycle reasoning with TrackID
    # -----------------------------
    async def run_cycle_async(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from seed.core.agent_manager import TrackContext

        start_time = time.time()
        cycle_id = payload.get("cycle_id") or "S" + TrackedData._generate_track_id("cycle", "reasoning")

        try:
            sensor_data = self._safe_payload(payload.get("payload"))
            current_tp = float(payload.get("thought_pressure", 0.0))

            # --- Thought pressure computation ---
            motion = float(sensor_data.get("qbit_motion", 0.5))
            new_tp = min(max(current_tp + motion * random.uniform(0.05, 0.15), 0.0), 1.0)

            # --- Dominant intent determination ---
            dominant_intent, intent_scores = ("idle", {})
            if self.intent_engine:
                dominant_intent, intent_scores = self.intent_engine.score_intents(inputs=sensor_data)
            intent_sub_label = f"INTENT_ENGINE:{dominant_intent}"

            # --- Dynamic action selection ---
            actions_to_execute = []
            for action in self.dynamic_actions:
                if action == "active_modules" and new_tp > 0.3:
                    actions_to_execute.append(action)
                elif action == "connect_to_network" and dominant_intent in ["explore", "observe"]:
                    actions_to_execute.append(action)
                elif action == "build_driver" and new_tp > 0.6:
                    actions_to_execute.append(action)

            if self.analytics_engine:
                suggested = self.analytics_engine.suggest_actions(sensor_data)
                for a in suggested:
                    if a not in self.dynamic_actions:
                        self.dynamic_actions.append(a)
                        actions_to_execute.append(a)

            sensor_data["qbit_motion"] = motion + random.uniform(-0.02, 0.02)

            # --- Execute skills safely with HUD & TrackID ---
            executed_skills = []
            agent_sub_label = "AGENT_MANAGER"

            for idx, skill in enumerate(actions_to_execute):
                if self.shutdown_flag and self.shutdown_flag.is_set():
                    break

                # --- HUD channel allocation ---
                hud_channels = [f"HUD-{cycle_id}-{idx:02d}-C{i}" for i in range(1, 4)]
                self._hud_channels[skill] = hud_channels

                # --- Qbit input/output channel mapping ---
                input_channel = idx % self._qbit_input_channels
                output_channel = idx % self._qbit_output_channels
                self._qbit_skill_map[skill] = {"input": input_channel, "output": output_channel}

                skill_track_id = TrackContext.get_current() or f"S{TrackedData._generate_track_id('skill', skill)}"

                # --- Wait for response if channel busy ---
                while self._channel_responses.get(skill):
                    await asyncio.sleep(self.retry_interval)

                fut = asyncio.get_event_loop().create_future()
                self._channel_responses[skill] = fut

                try:
                    result = None
                    if self.agent_manager:
                        result = await self.agent_manager._trigger_skill_chain_safe(skill, sensor_data)
                    elif self.sparkplug:
                        result = await self.sparkplug.execute(skill, payload=sensor_data)

                    executed_skills.append({
                        "skill": skill,
                        "result": result or "submitted_safe",
                        "hud_channels": hud_channels,
                        "qbit_channels": self._qbit_skill_map[skill],
                        "sub_label": agent_sub_label,
                        "track_id": skill_track_id
                    })

                except Exception as e:
                    logger.warning(f"[ReasoningLoop] Skill exec failed {skill} | TrackID={skill_track_id}: {e}")
                finally:
                    if fut and not fut.done():
                        fut.set_result(True)
                    self._channel_responses.pop(skill, None)

            # --- Reasoning packet with TrackID ---
            reasoning_track_id = "S" + TrackedData._generate_track_id("reasoning", dominant_intent)
            reasoning_packet = {
                "cycle_id": cycle_id,
                "thought_pressure": new_tp,
                "payload": sensor_data,
                "dominant_intent": dominant_intent,
                "intent_scores": intent_scores,
                "plan_of_action": actions_to_execute,
                "executed_skills": executed_skills,
                "track_id": reasoning_track_id,
                "sub_labels": {
                    "intent": intent_sub_label,
                    "analytics": "ANALYTICS_ENGINE",
                    "agent_manager": agent_sub_label,
                    "system": "SYSTEM_OUTPUT"
                },
                "hud_channels": self._hud_channels.copy(),
                "qbit_skill_map": self._qbit_skill_map.copy(),
                "timestamp": time.time(),
            }

            # --- EventBus publish ---
            if self.event_bus:
                try:
                    self.event_bus.publish(
                        "REASONING_CYCLE",
                        payload=reasoning_packet,
                        source="reasoning_loop",
                        channel=ChannelID.SYSTEM.value,
                        track_id=reasoning_track_id,
                    )
                except Exception as e:
                    logger.warning(f"[ReasoningLoop] EventBus publish failed | TrackID={reasoning_track_id}: {e}")

            # --- QbitDialer submission ---
            if self.qbit_dialer:
                try:
                    self.qbit_dialer.submit_track(
                        reasoning_packet,
                        input_channels=self._qbit_input_channels,
                        output_channels=self._qbit_output_channels
                    )
                except Exception as e:
                    logger.warning(f"[ReasoningLoop] QbitDialer submit_track failed | TrackID={reasoning_track_id}: {e}")

            logger.info(
                f"[ReasoningLoop] Cycle {cycle_id} | TrackID={reasoning_track_id} | Actions: {actions_to_execute} | Time: {time.time() - start_time:.4f}s"
            )

            return reasoning_packet

        except Exception as e:
            logger.error(f"[ReasoningLoop] Exception | CycleID={cycle_id}: {e}")
            return payload

# ------------------------------------------------------
# LEGACY ENTRYPOINT (PATCHED)
# ------------------------------------------------------
async def run_async(payload: Optional[Dict[str, Any]] = None,
                    sparkplug=None,
                    agent_manager=None,
                    analytics_engine=None,
                    intent_engine=None,
                    event_bus=None,
                    qbit_dialer=None,
                    shutdown_flag: Optional[asyncio.Event] = None):
    loop = ReasoningLoop(agent_manager=agent_manager,
                         analytics_engine=analytics_engine,
                         intent_engine=intent_engine,
                         event_bus=event_bus,
                         qbit_dialer=qbit_dialer,
                         sparkplug=sparkplug,
                         shutdown_flag=shutdown_flag)
    return await loop.run_cycle_async(payload or {})
