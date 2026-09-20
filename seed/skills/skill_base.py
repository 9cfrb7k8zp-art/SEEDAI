# ==========================================================
# FILE: skill_base.py
# PATH: SEED_ROOT/seed/skills/skill_base.py
# VERSION: 6.0.0
# PURPOSE: Boot-safe skill contract for the authoritative SEED runtime
# AUTHORITY: main3.py supplies EventBus/QbitDialer/Track/Registry dependencies
# ==========================================================

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional

from seed.core.channel_id import generate_track_id

SKILLS_ROOT = os.path.dirname(__file__)
INBOX_DIR = os.path.join(SKILLS_ROOT, "inbox")
OUTBOX_DIR = os.path.join(SKILLS_ROOT, "outbox")
ARCHIVE_DIR = os.path.join(SKILLS_ROOT, "_archive")
for _path in (INBOX_DIR, OUTBOX_DIR, ARCHIVE_DIR):
    os.makedirs(_path, exist_ok=True)


class SkillBase:
    """Common skill lifecycle; passive until explicitly scheduled by the runtime."""
    _inbox_seen = set()
    _repair_success_stats = defaultdict(lambda: defaultdict(int))

    def __init__(self, name: Optional[str] = None, actuator_engine=None,
                 sparkplug=None, event_bus=None, throttle_interval: float = 0.1,
                 scheduler_tokens: int = 1):
        self.name = name or self.__class__.__name__
        self.actuator_engine = actuator_engine
        self.sparkplug = sparkplug
        self.event_bus = event_bus
        self.throttle_interval = max(0.0, throttle_interval)
        self.scheduler_tokens = max(1, int(scheduler_tokens))
        self.tokens_used = 0
        self._last_exec = 0.0
        self.track_channel = self.name.upper()
        self.logger = logging.getLogger(f"Skill.{self.name}")
        self._history = deque(maxlen=100)
        self.running = False
        self.success_count = 0
        self.fail_count = 0
        self.status = "GOOD"
        self.qbit_dialer = None
        self.track_system = None
        self.registry = None

    def bind_runtime(self, *, event_bus=None, actuator_engine=None,
                     sparkplug=None, qbit_dialer=None, track_system=None, registry=None):
        """Bind existing authorities. This method never creates runtime singletons."""
        if event_bus is not None: self.event_bus = event_bus
        if actuator_engine is not None: self.actuator_engine = actuator_engine
        if sparkplug is not None: self.sparkplug = sparkplug
        if qbit_dialer is not None: self.qbit_dialer = qbit_dialer
        if track_system is not None: self.track_system = track_system
        if registry is not None: self.registry = registry
        return self

    async def execute_async(self, payload: Optional[Dict[str, Any]] = None,
                            parent_track_id: Optional[str] = None):
        while self.tokens_used >= self.scheduler_tokens:
            await asyncio.sleep(0.05)
        now = time.time()
        if now - self._last_exec < self.throttle_interval:
            return None
        self.tokens_used += 1
        self._last_exec = now
        track_id = generate_track_id(skill_name=self.name, channel_marker=self.track_channel,
                                     parent_id=parent_track_id)
        try:
            result = await self.execute(payload or {}, track_id=track_id)
            self._history.append((track_id, result))
            self._record_result(True)
            return result
        except Exception as exc:
            self.logger.error("[%s] execution failed: %s", self.name, exc)
            self._record_result(False)
            return None
        finally:
            self.tokens_used -= 1

    async def execute(self, payload: Dict[str, Any], track_id: str):
        raise NotImplementedError

    async def run(self):
        self.running = True
        while self.running:
            await asyncio.sleep(0.2)

    def stop(self):
        self.running = False

    def _record_result(self, success: bool):
        if success:
            self.success_count += 1
            self.status = "GOOD"
        else:
            self.fail_count += 1
            self.status = "BAD" if self.fail_count > self.success_count else self.status

    def health_status(self) -> Dict[str, Any]:
        return {"skill": self.name, "status": self.status,
                "success_count": self.success_count, "fail_count": self.fail_count,
                "running": self.running, "history_len": len(self._history),
                "inbox_seen": len(self._inbox_seen)}

    def _archive_old(self, fname: str, code: str):
        path = os.path.join(ARCHIVE_DIR, f"{fname}.{int(time.time())}.bak")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)

    def _write_outbox(self, fname: str, code: str):
        with open(os.path.join(OUTBOX_DIR, fname), "w", encoding="utf-8") as fh:
            fh.write(code)
