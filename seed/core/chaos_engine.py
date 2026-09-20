# ==========================================================
# FILE: chaos_engine.py
# PATH: SEED_ROOT/seed/core/chaos_engine.py
# VERSION: 2.2.0
# UPDATED: 2026-01-20
#
# SEED CHAOS ENGINE — FULL SYSTEM CORE (HARDENED)
# ==========================================================

import asyncio
import logging
import time
import random
from collections import deque
from typing import Optional, Dict, Any

from seed.core.track_id_manager import TrackIDManager
from seed.core.sparkplug_loader import TrackContext

logger = logging.getLogger("ChaosEngine")
logger.setLevel(logging.INFO)

HUD_CHANNELS = {
    "CORE": "HUD_CORE",
    "CHAOS": "HUD_CHAOS",
    "ENTROPY": "HUD_ENTROPY",
    "MUTATION": "HUD_MUTATION",
    "INTENT": "HUD_INTENT",
    "ANALYTICS": "HUD_ANALYTICS",
    "QBIT": "HUD_QBIT",
}

class ChaosEngine:

    def __init__(
        self,
        event_bus=None,
        sparkplug=None,
        agent_manager=None,
        intent_engine=None,
        analytics_engine=None,
        qbit_dialer=None,
        entropy_window: int = 128,
    ):
        self.event_bus = event_bus
        self.sparkplug = sparkplug
        self.agent_manager = agent_manager
        self.intent_engine = intent_engine
        self.analytics_engine = analytics_engine
        self.qbit_dialer = qbit_dialer

        self.entropy_window = entropy_window
        self.entropy_history = deque(maxlen=entropy_window)

        self._task_map: Dict[str, Dict[str, Any]] = {}
        self._active_tasks: set[str] = set()
        self._mutation_enabled: bool = True

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        logger.info("[ChaosEngine] Online | Adaptive chaos enabled")

    # ------------------------------------------------------
    # Chaos Scalar (SYSTEM CONTRACT)
    # ------------------------------------------------------
    def get_chaos_level(self) -> float:
        if not self.entropy_history:
            return 0.0
        return round(
            sum(self.entropy_history) / max(len(self.entropy_history), 1),
            4,
        )

    # ------------------------------------------------------
    # TrackID
    # ------------------------------------------------------
    def _track_id(self, name: str, channel: str = "CHAOS") -> str:
        return TrackIDManager.generate(
            channel_marker=channel,
            skill_name=name,
            qbit_callback=getattr(self.qbit_dialer, "submit_track", None),
        )

    # ------------------------------------------------------
    # Safe Emit Helpers
    # ------------------------------------------------------
    def _safe_event_emit(self, topic: str, payload: Dict[str, Any]):
        if not self.event_bus:
            return
        try:
            if hasattr(self.event_bus, "emit"):
                self.event_bus.emit(topic, payload)
            elif hasattr(self.event_bus, "publish"):
                self.event_bus.publish(topic=topic, payload=payload)
        except Exception as e:
            logger.debug(f"[ChaosEngine] EventBus suppressed error: {e}")

    def _safe_qbit_push(self, message: str):
        if not self.qbit_dialer or not hasattr(self.qbit_dialer, "push_data"):
            return
        try:
            push = self.qbit_dialer.push_data
            if asyncio.iscoroutinefunction(push):
                asyncio.run_coroutine_threadsafe(push(message), self._loop)
            else:
                push(message)
        except Exception:
            pass

    # ------------------------------------------------------
    # Submit Chaos Task
    # ------------------------------------------------------
    def submit(
        self,
        task_name: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: float = 0.5,
        allow_mutation: bool = False,
        source: str = "system",
    ) -> str:
        track_id = self._track_id(task_name)

        self._task_map[track_id] = {
            "task": task_name,
            "payload": payload or {},
            "priority": priority,
            "allow_mutation": allow_mutation,
            "source": source,
            "created": time.time(),
            "entropy": 0.0,
        }

        asyncio.run_coroutine_threadsafe(self._execute(track_id), self._loop)
        return track_id

    # ------------------------------------------------------
    # Execution Pipeline
    # ------------------------------------------------------
    async def _execute(self, track_id: str):
        entry = self._task_map.get(track_id)
        if not entry:
            return

        TrackContext.push(channel=HUD_CHANNELS["CHAOS"], skill=entry["task"])
        self._active_tasks.add(track_id)

        try:
            entropy = self._calculate_entropy(entry)
            entry["entropy"] = entropy
            self.entropy_history.append(entropy)

            self._safe_qbit_push(f"{track_id}$ENTROPY:{entropy:.4f}")

            if entry["allow_mutation"] and self._mutation_enabled:
                self._mutate_payload(entry, track_id)

            if self.sparkplug:
                self.sparkplug.submit_skill(
                    skill_name=entry["task"],
                    payload=entry["payload"],
                    priority=entry["priority"],
                    source="ChaosEngine",
                    channel_marker="S",
                    track_id=track_id,
                    require_approval=True,
                )

            self._safe_event_emit(
                entry["task"],
                {
                    "track_id": track_id,
                    "payload": entry["payload"],
                    "entropy": entropy,
                    "chaos": self.get_chaos_level(),
                },
            )

            if self.agent_manager:
                self.agent_manager.handle_task(
                    task_name=entry["task"],
                    payload=entry["payload"],
                    track_id=track_id,
                )

            if self.intent_engine:
                self.intent_engine.evaluate(
                    task_name=entry["task"],
                    payload=entry["payload"],
                    track_id=track_id,
                )

            if self.analytics_engine:
                self.analytics_engine.observe(
                    task_name=entry["task"],
                    payload=entry["payload"],
                    track_id=track_id,
                    entropy=entropy,
                )

            self._safe_event_emit(
                HUD_CHANNELS["CHAOS"],
                {
                    "track_id": track_id,
                    "entropy": entropy,
                    "chaos": self.get_chaos_level(),
                    "priority": entry["priority"],
                    "mutated": entry["allow_mutation"],
                },
            )

            self._safe_qbit_push(f"{track_id}$DONE:{entropy:.3f}")

        finally:
            self._active_tasks.discard(track_id)
            self._task_map.pop(track_id, None)
            TrackContext.pop()

    # ------------------------------------------------------
    # Entropy
    # ------------------------------------------------------
    def _calculate_entropy(self, entry: Dict[str, Any]) -> float:
        base = random.random() * 0.4
        priority_factor = min(entry["priority"], 1.0) * 0.3
        age_factor = min((time.time() - entry["created"]) / 5.0, 1.0) * 0.3
        return round(min(base + priority_factor + age_factor, 1.0), 4)

    # ------------------------------------------------------
    # Mutation
    # ------------------------------------------------------
    def _mutate_payload(self, entry: Dict[str, Any], track_id: str):
        payload = entry["payload"]
        if not isinstance(payload, dict):
            return

        payload["_mutation"] = {
            "strength": entry["entropy"],
            "timestamp": time.time(),
            "seed": random.random(),
        }

        self._safe_qbit_push(f"{track_id}$MUTATE:{entry['entropy']:.3f}")

    # ------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "active_tasks": list(self._active_tasks),
            "chaos": self.get_chaos_level(),
            "mutation_enabled": self._mutation_enabled,
        }
