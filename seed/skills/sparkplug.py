# ==========================================================
# FILE: sparkplug.py
# PATH: SEED_ROOT/seed/skills/sparkplug.py
# VERSION: 3.2 – Full TrackID + HUD Channels + Silent _S_ Skill Approval
# UPDATED: 2025-12-30
# ==========================================================

import os
import threading
import importlib.util
import logging
import asyncio
import time
from heapq import heappush, heappop
from itertools import count
import contextvars

from seed.core.track_id_manager import TrackIDManager
from seed.skills.module_registry import ModuleRegistry
from seed.core.limp_mode import LimpModeController

logger = logging.getLogger("SparkPlug")

# ==========================================================
# Track Context
# ==========================================================
class TrackContext:
    _current_id = contextvars.ContextVar("track_current_id", default=None)

    @classmethod
    def get_current(cls):
        return cls._current_id.get()

    @classmethod
    def push(cls, channel=None, skill=None, agent_subclass=None,
             qbit_callback=None, parent_id=None):
        parent_id = parent_id or cls._current_id.get()
        new_id = TrackIDManager.generate(
            channel_marker=channel or "SPK",
            skill_name=skill or "TASK",
            agent_subclass=agent_subclass,
            qbit_callback=qbit_callback,
            parent_id=parent_id
        )
        cls._current_id.set(new_id)
        return new_id, parent_id

    @classmethod
    def pop(cls):
        cls._current_id.set(None)


def track(channel, state, *, skill=None, agent_subclass=None,
          priority="MED", note=None, qbit_callback=None):
    try:
        current_id, parent_id = TrackContext.push(
            channel, skill=skill,
            agent_subclass=agent_subclass,
            qbit_callback=qbit_callback
        )

        parts = [
            "[TRACK]",
            f"{channel}",
            f"| {state}",
            f"| ID={current_id}",
            f"| PRIORITY={priority}"
        ]
        if parent_id:
            parts.append(f"| PARENT={parent_id}")
        if note:
            parts.append(f"| NOTE={note}")

        print(" ".join(parts), flush=True)
    finally:
        TrackContext.pop()


# ==========================================================
# Constants
# ==========================================================
MAX_QUEUE_SIZE = 50
DEFAULT_DEBOUNCE = 0.3
COALESCE_SKILLS = True

CHANNELS = {
    "INIT": "HUD_INIT",
    "QUEUE": "HUD_QUEUE",
    "EXEC": "HUD_EXEC",
    "REG": "HUD_REG",
}


# ==========================================================
# SparkPlug
# ==========================================================
class SparkPlug:
    def __init__(
        self,
        skills_root = r"./SEED_ROOT/seed/skills",
        event_bus=None,
        loader=None,
        agent_manager=None,
        qbit_dialer=None,
        debounce_interval=DEFAULT_DEBOUNCE,
        limp_mode: LimpModeController = None,
    ):
        self.skills_root = skills_root
        self.event_bus = event_bus
        self.agent_manager = agent_manager
        self.qbit_dialer = qbit_dialer
        self.debounce_interval = debounce_interval
        self.limp_mode = limp_mode
        self.loader = loader

        self.skills = {}
        self.skill_chain_map = {}
        self._priority_queue = []
        self._running_skills = set()
        self._counter = count()
        self._boot_complete = False

        self._user_approved_skills = set()
        self._silent_approved_skills = set()

        self._ensure_init_file()
        self._discover_skills()
        self._register_deep_scan_skill()

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        if self.event_bus:
            try:
                self.event_bus.on("SKILL_COMMAND", self._queue_skill_async)
            except Exception as e:
                logger.warning(f"[SparkPlug] EventBus hook failed: {e}")

        track(
            CHANNELS["INIT"],
            "LOADER-ONLINE",
            priority="CRITICAL",
            note=f"Skills loaded: {list(self.skills.keys())}",
            qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None,
        )

        threading.Thread(target=self._queue_loop, daemon=True).start()
        self._boot_complete = True
        logger.info("[SparkPlug] Online")

    # ==========================================================
    # Init Helpers
    # ==========================================================
    def _ensure_init_file(self):
        try:
            os.makedirs(self.skills_root, exist_ok=True)
        except Exception as e:
            logger.error(f"[SparkPlug] Skills root init failed: {e}")

    def _discover_skills(self):
        if not os.path.isdir(self.skills_root):
            return

        for fname in os.listdir(self.skills_root):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue

            path = os.path.join(self.skills_root, fname)
            mod_name = f"skill_{fname[:-3]}"

            try:
                spec = importlib.util.spec_from_file_location(mod_name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "register"):
                    module.register(self)
                elif hasattr(module, "Skill"):
                    skill = module.Skill()
                    self.register_skill(skill.name, skill.execute)

            except Exception as e:
                logger.error(f"[SparkPlug] Failed loading {fname}: {e}")

    def _register_deep_scan_skill(self):
        try:
            from seed.skills.deep_scan_skill import DeepScanSkill
            skill = DeepScanSkill()
            self.register_skill(skill.name, skill.execute)
        except Exception:
            pass

    # ==========================================================
    # Skill Registry
    # ==========================================================
    def register_skill(self, skill_name: str, callable_obj):
        if callable(callable_obj):
            self.skills[skill_name] = callable_obj
            track(CHANNELS["REG"], "SKILL-REGISTERED", note=skill_name)
        else:
            track(CHANNELS["REG"], "SKILL-NOT-CALLABLE", priority="HIGH", note=skill_name)

    # ==========================================================
    # Queue + Execution
    # ==========================================================
    async def _queue_skill_async(self, event):
        await asyncio.to_thread(self.queue_skill, event)

    def queue_skill(self, event):
        data = event.get("data", event) if isinstance(event, dict) else {}
        skill_name = data.get("skill_name")
        payload = data.get("payload", {})
        priority = float(data.get("priority", 0.5))

        if not skill_name:
            return

        track_id = TrackIDManager.generate(
            "SPK",
            skill_name,
            parent_id=TrackContext.get_current(),
            qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None,
        )

        if "_S_" in skill_name:
            self._user_approved_skills.add(skill_name)
            self._silent_approved_skills.add(skill_name)
            ModuleRegistry.register_skill(skill_name)

        if skill_name not in self._user_approved_skills:
            if not ModuleRegistry.validate_track(skill_name, limp_mode=self.limp_mode):
                track(CHANNELS["QUEUE"], "SKILL-REJECTED", priority="HIGH", note=skill_name)
                return
            self._user_approved_skills.add(skill_name)

        heappush(
            self._priority_queue,
            (-priority, next(self._counter), skill_name, payload, track_id),
        )

        track(CHANNELS["QUEUE"], "SKILL-QUEUED", note=skill_name)

    def _queue_loop(self):
        while True:
            if not self._priority_queue:
                time.sleep(0.05)
                continue

            _, _, skill_name, payload, track_id = heappop(self._priority_queue)
            self.execute(skill_name, payload)
            time.sleep(self.debounce_interval)

    def execute(self, skill_name: str, payload=None):
        if skill_name not in self.skills:
            track(CHANNELS["EXEC"], "SKILL-NOT-FOUND", priority="HIGH", note=skill_name)
            return

        try:
            self._running_skills.add(skill_name)
            result = self.skills[skill_name](
                payload or {},
                event_bus=self.event_bus,
                agent_manager=self.agent_manager,
            )
            track(CHANNELS["EXEC"], "SKILL-DONE", note=skill_name)
            return result
        except Exception as e:
            track(
                CHANNELS["EXEC"],
                "SKILL-ERROR",
                priority="CRITICAL",
                note=f"{skill_name}: {e}",
            )
        finally:
            self._running_skills.discard(skill_name)
