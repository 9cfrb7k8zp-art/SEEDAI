# ==========================================================
# FILE: boot_integration.py
# PATH: SEED_ROOT/seed/skills/boot_integration.py
# SPARKPLUG SKILL: BootIntegration v2.1
# UPDATED: 2025-12-30
# FEATURES:
# - Full TrackID integration
# - Hierarchical track correlation (mapper, reasoning, agent, replay)
# - Loop metrics aggregation
# - Dynamic loop control with health monitor
# - Qbit vector multiplier
# ==========================================================

import asyncio
import threading
import logging
import time
import random

from seed.skills.skill_base import SkillBase
from seed.core.event_bus import SEEDEventBus
from seed.core.track_id_manager import TrackIDManager
from seed.core.intent_to_action_mapper import IntentToActionMapper
from seed.skills.reasoning_loop import ReasoningLoop
from seed.core.agent_manager import AgentManager

logger = logging.getLogger("BootIntegration")
logger.setLevel(logging.INFO)


class BootIntegration(SkillBase):
    HEALTH_CHECK_INTERVAL = 2.0
    LOOP_TIMEOUT = 5.0

    def __init__(self, event_bus=None):
        super().__init__()
        self.event_bus = event_bus or SEEDEventBus()
        self.agent_manager = AgentManager(event_bus=self.event_bus)
        self.mapper = IntentToActionMapper(event_bus=self.event_bus, agent_manager=self.agent_manager)
        self.reasoning_loop = ReasoningLoop(event_bus=self.event_bus, skill_manager=self, mapper=self.mapper)

        self._replay_queue = []
        self._lock = threading.Lock()
        self.skill_name = "BootIntegration"
        self.active = True
        self._tick = 0
        self._loops_tasks = {}
        self._main_loop = None
        self._loop_active_flags = {"mapper": True, "reasoning": True, "agent": True, "replay": True}
        self._loop_last_heartbeat = {k: time.time() for k in self._loop_active_flags}
        self._track_priority = {}
        self._loop_log_levels = {k: logging.INFO for k in self._loop_active_flags}
        self._qbit_vector = {}
        self._loop_metrics = {k: {"ticks": 0, "events": 0, "latency": 0.0} for k in self._loop_active_flags}

        self._wrap_mapper_handler()

        self.event_bus.subscribe("LOOP_CONTROL", self._handle_loop_control)
        self.event_bus.subscribe("UPDATE_LOG_LEVEL", self._update_log_level)
        self.event_bus.subscribe("QBIT_PUSH", self._handle_qbit_emit)

        if self._main_loop is None:
            self._main_loop = asyncio.get_event_loop()
        asyncio.create_task(self._health_monitor_loop())
        asyncio.create_task(self._metrics_report_loop())

    # -----------------------------
    # Mapper wrapper with TrackID
    # -----------------------------
    def _wrap_mapper_handler(self):
        original_handler = self.mapper._handle_intent_state

        def wrapped_handler(event):
            track_id = TrackIDManager.generate(channel_marker="MAPPER")
            priority = self._track_priority.get(track_id, random.randint(1, 10))
            start_time = time.time()
            try:
                original_handler(event)
                latency = time.time() - start_time
                self._loop_last_heartbeat["mapper"] = time.time()
                self._loop_metrics["mapper"].update({"ticks": self._loop_metrics["mapper"]["ticks"]+1,
                                                     "events": self._loop_metrics["mapper"]["events"]+1,
                                                     "latency": latency})
                self.event_bus.publish(
                    "MAPPER_EVENT",
                    payload={
                        "track_id": track_id,
                        "event": event,
                        "status": "success",
                        "priority": priority,
                        "latency": latency
                    }
                )
                self._emit_qbit(track_id, multiplier=priority)
            except Exception as e:
                logger.warning(f"[{self.skill_name}] Mapper failed: {e} | track_id={track_id}")
                self.push_to_replay(event, track_id)

        self.mapper._handle_intent_state = wrapped_handler

    # -----------------------------
    # Emit Qbit vector with TrackID
    # -----------------------------
    def _emit_qbit(self, track_id, multiplier=1):
        vector_value = random.random() * multiplier
        self._qbit_vector[track_id] = vector_value
        self.event_bus.publish(
            "QBIT_VECTOR",
            payload={"track_id": track_id, "vector": vector_value, "multiplier": multiplier}
        )

    # -----------------------------
    # Run loops
    # -----------------------------
    def run(self, payload=None):
        if self._main_loop is None:
            self._main_loop = asyncio.get_event_loop()
        asyncio.create_task(self._start_all_loops())
        boot_id = TrackIDManager.generate(channel_marker="BOOT")
        logger.info(f"[{self.skill_name}] BootIntegration running | track_id={boot_id}")
        return {"status": "BootIntegration started", "track_id": boot_id}

    async def _start_all_loops(self):
        await asyncio.gather(
            self.start_loop("mapper"),
            self.start_loop("reasoning"),
            self.start_loop("agent"),
            self.start_loop("replay")
        )

    async def start_loop(self, loop_name):
        if loop_name in self._loops_tasks:
            task = self._loops_tasks[loop_name]
            if not task.done():
                task.cancel()
                await asyncio.sleep(0.05)
                logger.info(f"[{self.skill_name}] {loop_name} cancelled | track_id={TrackIDManager.generate('LOOP_CANCEL')}")

        loop_mapping = {"mapper": self._mapper_loop,
                        "reasoning": self._reasoning_loop,
                        "agent": self._agent_thinking_loop,
                        "replay": self._replay_loop}

        if loop_name not in loop_mapping:
            logger.error(f"[{self.skill_name}] Unknown loop: {loop_name}")
            return

        task = asyncio.create_task(loop_mapping[loop_name]())
        self._loops_tasks[loop_name] = task
        self._loop_last_heartbeat[loop_name] = time.time()
        logger.info(f"[{self.skill_name}] {loop_name} started | track_id={TrackIDManager.generate('LOOP_START')}")

    # -----------------------------
    # Loops
    # -----------------------------
    async def _mapper_loop(self):
        try:
            self.mapper.start_loop()
            while self.active and self._loop_active_flags["mapper"]:
                self._loop_last_heartbeat["mapper"] = time.time()
                self._loop_metrics["mapper"]["ticks"] += 1
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info(f"[{self.skill_name}] Mapper cancelled | track_id={TrackIDManager.generate('LOOP_CANCEL')}")
        except Exception as e:
            logger.error(f"[{self.skill_name}] Mapper error: {e}")

    async def _reasoning_loop(self):
        try:
            self.reasoning_loop.start()
            while self.active and self._loop_active_flags["reasoning"]:
                self._loop_last_heartbeat["reasoning"] = time.time()
                self._loop_metrics["reasoning"]["ticks"] += 1
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info(f"[{self.skill_name}] Reasoning cancelled | track_id={TrackIDManager.generate('LOOP_CANCEL')}")
        except Exception as e:
            logger.error(f"[{self.skill_name}] Reasoning error: {e}")

    async def _agent_thinking_loop(self):
        try:
            while self.active and self._loop_active_flags["agent"]:
                start_time = time.time()
                try:
                    await self.agent_manager.thinking_loop()
                    self._tick += 1
                    self._loop_last_heartbeat["agent"] = time.time()
                    latency = time.time() - start_time
                    self._loop_metrics["agent"].update({"ticks": self._loop_metrics["agent"]["ticks"]+1, "latency": latency})
                    track_id = TrackIDManager.generate("AGENT")
                    priority = random.randint(1, 10)
                    self._track_priority[track_id] = priority
                    self.event_bus.publish(
                        "AGENT_TICK",
                        payload={"track_id": track_id, "tick": self._tick, "priority": priority, "latency": latency}
                    )
                    self._emit_qbit(track_id, multiplier=priority)
                except Exception as e:
                    logger.warning(f"[{self.skill_name}] Agent error: {e}")
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            logger.info(f"[{self.skill_name}] Agent cancelled | track_id={TrackIDManager.generate('LOOP_CANCEL')}")

    async def _replay_loop(self):
        try:
            while self.active and self._loop_active_flags["replay"]:
                self._loop_last_heartbeat["replay"] = time.time()
                with self._lock:
                    queue_copy = self._replay_queue.copy()
                    self._replay_queue.clear()

                for event, track_id in queue_copy:
                    start_time = time.time()
                    try:
                        self.mapper._handle_intent_state({"data": event})
                        latency = time.time() - start_time
                        priority = random.randint(1, 10)
                        self._track_priority[track_id] = priority
                        self._loop_metrics["replay"].update({"ticks": self._loop_metrics["replay"]["ticks"]+1,
                                                             "latency": latency,
                                                             "events": self._loop_metrics["replay"]["events"]+1})
                        self.event_bus.publish(
                            "REPLAY_EVENT",
                            payload={"track_id": track_id, "event": event, "status": "replayed", "priority": priority, "latency": latency}
                        )
                        self._emit_qbit(track_id, multiplier=priority)
                    except Exception as e:
                        logger.warning(f"[{self.skill_name}] Replay failed {event} | track_id={track_id}: {e}")
                        with self._lock:
                            self._replay_queue.append((event, track_id))
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info(f"[{self.skill_name}] Replay cancelled | track_id={TrackIDManager.generate('LOOP_CANCEL')}")

    # -----------------------------
    # Replay push
    # -----------------------------
    def push_to_replay(self, event, track_id=None):
        if track_id is None:
            track_id = TrackIDManager.generate("REPLAY")
        with self._lock:
            self._replay_queue.append((event, track_id))
            logger.debug(f"[{self.skill_name}] Queued for replay: {event} | track_id={track_id}")

    # -----------------------------
    # Event bus handlers
    # -----------------------------
    def _handle_loop_control(self, event):
        try:
            payload = event.get("data", {})
            loop_name = payload.get("loop")
            action = payload.get("action")
            if loop_name not in self._loop_active_flags:
                logger.warning(f"[{self.skill_name}] Unknown loop: {loop_name}")
                return

            if action == "enable":
                self._loop_active_flags[loop_name] = True
                asyncio.create_task(self.start_loop(loop_name))
                logger.info(f"[{self.skill_name}] Loop enabled: {loop_name} | track_id={TrackIDManager.generate('LOOP')}")
            elif action == "disable":
                self._loop_active_flags[loop_name] = False
                logger.info(f"[{self.skill_name}] Loop disabled: {loop_name} | track_id={TrackIDManager.generate('LOOP')}")
            elif action == "restart":
                asyncio.create_task(self.start_loop(loop_name))
                logger.info(f"[{self.skill_name}] Loop restarted: {loop_name} | track_id={TrackIDManager.generate('LOOP')}")
            else:
                logger.warning(f"[{self.skill_name}] Unknown action: {action}")
        except Exception as e:
            logger.error(f"[{self.skill_name}] Loop control error: {e}")

    def _update_log_level(self, event):
        try:
            payload = event.get("data", {})
            loop_name = payload.get("loop")
            level = payload.get("level", logging.INFO)
            if loop_name in self._loop_log_levels:
                self._loop_log_levels[loop_name] = level
                logger.setLevel(level)
                logger.info(f"[{self.skill_name}] Log level updated: {loop_name} -> {level} | track_id={TrackIDManager.generate('LOG')}")
        except Exception as e:
            logger.error(f"[{self.skill_name}] Log level update error: {e}")

    def _handle_qbit_emit(self, event):
        try:
            payload = event.get("data", {})
            track_id = payload.get("track_id")
            multiplier = payload.get("multiplier", 1)
            self._emit_qbit(track_id, multiplier=multiplier)
        except Exception as e:
            logger.error(f"[{self.skill_name}] Qbit emit handler error: {e}")

    # -----------------------------
    # Health monitor
    # -----------------------------
    async def _health_monitor_loop(self):
        while True:
            now = time.time()
            for loop_name, last_beat in self._loop_last_heartbeat.items():
                if self._loop_active_flags.get(loop_name, False):
                    if now - last_beat > self.LOOP_TIMEOUT:
                        logger.warning(f"[{self.skill_name}] {loop_name} unresponsive, auto-restarting | track_id={TrackIDManager.generate('HEALTH')}")
                        asyncio.create_task(self.start_loop(loop_name))
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)

    # -----------------------------
    # Metrics reporter
    # -----------------------------
    async def _metrics_report_loop(self):
        while True:
            try:
                metrics_snapshot = {k: v.copy() for k, v in self._loop_metrics.items()}
                self.event_bus.publish(
                    "LOOP_METRICS",
                    payload={"timestamp": time.time(), "metrics": metrics_snapshot}
                )
            except Exception as e:
                logger.error(f"[{self.skill_name}] Metrics report error: {e}")
            await asyncio.sleep(5.0)

    # -----------------------------
    # Stop all loops
    # -----------------------------
    def stop(self):
        self.active = False
        for loop_name, task in self._loops_tasks.items():
            if not task.done():
                task.cancel()
        try:
            self.reasoning_loop.stop()
        except Exception as e:
            logger.warning(f"[{self.skill_name}] Error stopping ReasoningLoop: {e}")
        self._loops_tasks.clear()
        logger.info(f"[{self.skill_name}] BootIntegration stopped | track_id={TrackIDManager.generate('STOP')}")
