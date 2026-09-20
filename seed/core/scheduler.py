# ==========================================================
# FILE: scheduler.py
# PATH: SEED_ROOT/core/scheduler.py
# VERSION: 3.2
# LABEL: L-3 Dynamic AI Scheduler Patch
# ==========================================================

import time
import threading
import logging
from seed.core.event_bus import COMMAND_EXECUTED

logger = logging.getLogger("Scheduler")
logger.setLevel(logging.INFO)

class Scheduler:

    def __init__(self, event_bus=None, registry=None):
        self.event_bus = event_bus
        self.registry = registry

        self._tasks = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._task_counter = 0

        self._dynamic_attached = event_bus is not None

        if self.registry:
            try:
                self.registry.register(
                    "Scheduler",
                    heartbeat_timeout=15,
                    restartable=True,
                    critical=True
                )
            except Exception as e:
                logger.warning(f"[Scheduler] Registry registration failed | {e}")

    def attach_event_bus(self, event_bus):
        if event_bus:
            self.event_bus = event_bus
            self._dynamic_attached = True
            logger.info("[Scheduler] EventBus dynamically attached")

    def schedule(self, func, delay: float = 0) -> int:
        run_at = time.time() + delay
        with self._lock:
            self._task_counter += 1
            task_id = self._task_counter
            self._tasks.append((run_at, task_id, func))
        return task_id

    def cancel(self, task_id: int) -> bool:
        with self._lock:
            initial_len = len(self._tasks)
            self._tasks = [t for t in self._tasks if t[1] != task_id]
            cancelled = len(self._tasks) < initial_len
        return cancelled

    def call_later(self, delay: float, callback, *args, **kwargs) -> int:
        def wrapped():
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"[Scheduler] Scheduled callback failed | {e}")
        return self.schedule(wrapped, delay=delay)

    def _loop(self):
        self._running = True
        while self._running:
            now = time.time()
            ready = []
            with self._lock:
                ready = [t for t in self._tasks if t[0] <= now]
                self._tasks = [t for t in self._tasks if t[0] > now]

            for _, task_id, task in ready:
                try:
                    task()
                    if self._dynamic_attached and self.event_bus:
                        try:
                            self.event_bus.publish(COMMAND_EXECUTED, {"task_id": task_id})
                        except Exception:
                            pass
                except Exception:
                    pass

            if self.registry:
                try:
                    self.registry.update_heartbeat("Scheduler")
                except Exception:
                    pass

            time.sleep(0.5)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)

    def flush_tasks(self):
        with self._lock:
            self._tasks.clear()

    def dynamic_task_count(self) -> int:
        with self._lock:
            return len(self._tasks)
