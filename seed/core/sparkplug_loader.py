# ==========================================================
# FILE: sparkplug_loader.py
# PATH: SEED_ROOT/seed/core/sparkplug_loader.py
# VERSION: 4.1
# STATUS: Stable / Async / Thread-safe
# UPDATED: 2026-01-10
# ==========================================================

import asyncio
import threading
import time
import hashlib
from collections import deque
import contextvars
import logging

from seed.skills.module_registry import ModuleRegistry
from seed.core.track_id_manager import TrackIDManager
from seed.core.limp_mode import LimpModeController

logger = logging.getLogger("SparkPlugLoader")
logger.setLevel(logging.INFO)


# ==========================================================
# TrackID context
# ==========================================================
class TrackContext:
    _current_id = contextvars.ContextVar("track_current_id", default=None)

    @classmethod
    def get_current(cls):
        return cls._current_id.get()

    @classmethod
    def push(cls, channel=None, skill=None, qbit_callback=None, parent_id=None):
        parent_id = parent_id or cls._current_id.get()
        new_id = TrackIDManager.generate(
            channel_marker=channel or "SPK",
            skill_name=skill or "TASK",
            qbit_callback=qbit_callback,
            parent_id=parent_id
        )
        cls._current_id.set(new_id)
        return new_id, parent_id

    @classmethod
    def pop(cls):
        cls._current_id.set(None)


# ==========================================================
# Fixed Track function
# ==========================================================
def track(channel, state, *, skill=None, priority="MED", loop_id=None,
          input_from=None, output_to=None, note=None, qbit_callback=None):
    try:
        current_id, parent_id = TrackContext.push(channel, skill=skill, qbit_callback=qbit_callback)

        parts = [
            "[A-S-1]",
            f"CHANNEL={channel}",
            f"STATE={state}",
            f"ID={current_id}",
            f"PRIORITY={priority.upper()}"
        ]
        if parent_id:
            parts.append(f"PARENT={parent_id}")
        if loop_id:
            parts.append(f"LOOP={loop_id}")
        if input_from:
            parts.append(f"IN={input_from}")
        if output_to:
            parts.append(f"OUT={output_to}")
        if note:
            parts.append(f"NOTE={note}")

        message = " | ".join(parts)
        print(message, flush=True)

        if qbit_callback:
            try:
                qbit_callback(message)
            except Exception as e:
                logger.warning(f"[Track] Qbit callback failed: {e}")
    finally:
        TrackContext.pop()


# ==========================================================
# SparkPlugLoader
# ==========================================================
class SparkPlugLoader:
    _registered_skills = {}

    def __init__(self, event_bus=None, debug_trace=False, qbit_dialer=None, limp_mode: LimpModeController = None):
        self.event_bus = event_bus if hasattr(event_bus, "subscribe") else None
        self.qbit_dialer = qbit_dialer
        self.debug_trace = debug_trace
        self.limp_mode = limp_mode

        self.skill_queue = deque()
        self.priority_levels = {"high": 3, "medium": 2, "low": 1}

        self._lock = threading.Lock()
        self._shutdown_flag = False
        self._in_flight = set()
        self._last_exec_time = {}
        self._last_emit_time = {}
        self._queued_hashes = set()
        self.skill_cooldown = 0.05
        self.event_debounce = 0.05

        # EventBus subscriptions
        if self.event_bus:
            try:
                self.event_bus.subscribe("qbit.result", self._on_qbit_result, async_callback=True)
                self.event_bus.subscribe("sparkplug.override", self._on_skill_override, async_callback=True)
            except Exception as e:
                track("INIT", "SUBSCRIBE-FAIL", priority="HIGH", note=str(e),
                      qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

        track("INIT", "LOADER-INIT", priority="CRITICAL",
              qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)
        logger.info("[SparkPlugLoader] Initialized")

        # Queue task placeholder
        self._queue_task = None

    # ==========================================================
    # Start queue task safely
    # ==========================================================
    def start(self):
        """Start the skill queue processing task inside the running loop."""
        if not self._queue_task:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            self.loop = loop
            self._queue_task = self.loop.create_task(self._process_queue())
            track("INIT", "QUEUE-STARTED", priority="HIGH",
                  qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

    @property
    def skills(self):
        with self._lock:
            return dict(self._registered_skills)

    def register_skill(self, skill_instance, priority="medium"):
        name = getattr(skill_instance, "name", f"skill_{id(skill_instance)}")
        with self._lock:
            if name in self._registered_skills:
                logger.info(f"[SparkPlugLoader] Skill already registered: {name}")
                return
            self._registered_skills[name] = skill_instance
            setattr(skill_instance, "_priority_level", self.priority_levels.get(priority, 2))
        track("REG", "SKILL-REGISTERED", priority=priority, note=name,
              qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

    def _payload_hash(self, skill_name, payload):
        raw = f"{skill_name}:{repr(payload)}".encode()
        return hashlib.sha1(raw).hexdigest()

    # ==========================================================
    # Primary skill queue method
    # ==========================================================
    def enqueue_skill(self, skill_name, payload=None, priority="medium"):
        if not ModuleRegistry.validate_track(skill_name, limp_mode=self.limp_mode):
            track("QUEUE", "SKILL-REJECTED", priority="HIGH",
                  note=f"Unknown or unauthorized: {skill_name}",
                  qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)
            logger.warning(f"[SparkPlugLoader] Rejected unknown/unauthorized skill: {skill_name}")
            return

        level = self.priority_levels.get(priority, 2)
        h = self._payload_hash(skill_name, payload)

        with self._lock:
            if h in self._queued_hashes:
                return
            self._queued_hashes.add(h)
            self.skill_queue.append((level, skill_name, payload, h))
            self.skill_queue = deque(sorted(self.skill_queue, key=lambda x: -x[0]))

        track("QUEUE", "SKILL-QUEUED", priority=priority, note=skill_name,
              qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

    async def submit_skill(self, skill_name, payload=None, priority="medium"):
        if threading.current_thread() is threading.main_thread():
            self.enqueue_skill(skill_name, payload=payload, priority=priority)
        else:
            future = asyncio.run_coroutine_threadsafe(
                self._enqueue_async(skill_name, payload, priority), self.loop
            )
            future.result()

    async def _enqueue_async(self, skill_name, payload=None, priority="medium"):
        self.enqueue_skill(skill_name, payload=payload, priority=priority)

    # ==========================================================
    # Skill execution
    # ==========================================================
    async def execute_skill(self, skill_name, payload=None):
        now = time.time()

        if not ModuleRegistry.validate_track(skill_name, limp_mode=self.limp_mode):
            track("EXEC", "SKILL-SKIPPED", priority="MED",
                  note=f"Unknown/unauthorized: {skill_name}",
                  qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)
            return

        with self._lock:
            if skill_name in self._in_flight:
                return
            last = self._last_exec_time.get(skill_name, 0)
            if now - last < self.skill_cooldown:
                return
            self._in_flight.add(skill_name)
            self._last_exec_time[skill_name] = now

        skill = self._registered_skills.get(skill_name)
        if not skill:
            track("EXEC", "SKILL-NOT-FOUND", priority="HIGH", note=skill_name,
                  qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)
            with self._lock:
                self._in_flight.discard(skill_name)
            return

        track("EXEC", "SKILL-START", priority="HIGH", note=skill_name,
              qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

        try:
            if hasattr(skill, "execute_async"):
                await skill.execute_async(payload or {})
            elif hasattr(skill, "execute"):
                await self.loop.run_in_executor(None, lambda: skill.execute(payload or {}))

            await self._safe_emit(f"SPARKPLUG_SKILL_RUN:{skill_name}", {"payload": payload}, skill_name=skill_name)

            track("EXEC", "SKILL-DONE", priority="HIGH", note=skill_name,
                  qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

        except Exception as e:
            track("EXEC", "SKILL-ERROR", priority="CRITICAL", note=str(e),
                  qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)
            logger.exception(e)
        finally:
            with self._lock:
                self._in_flight.discard(skill_name)

    # ==========================================================
    # Queue processing
    # ==========================================================
    async def _process_queue(self):
        try:
            while not self._shutdown_flag:
                item = None
                with self._lock:
                    if self.skill_queue:
                        item = self.skill_queue.popleft()
                if item:
                    _, skill_name, payload, h = item
                    with self._lock:
                        self._queued_hashes.discard(h)
                    await self.execute_skill(skill_name, payload)
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            track("QUEUE", "CANCELLED", priority="HIGH",
                  qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)
            raise
        finally:
            track("QUEUE", "TASK-CLEANED", priority="HIGH",
                  qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

    # ==========================================================
    # Event callbacks
    # ==========================================================
    async def _on_qbit_result(self, event):
        track("EVT", "QBIT-RESULT", qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

    async def _on_skill_override(self, event):
        track("EVT", "SKILL-OVERRIDE", qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)

    # ==========================================================
    # Shutdown
    # ==========================================================
    async def shutdown(self):
        self._shutdown_flag = True
        if self._queue_task:
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                track("SHUTDOWN", "QUEUE-CANCELLED", priority="HIGH",
                      qbit_callback=self.qbit_dialer.submit_track if self.qbit_dialer else None)
