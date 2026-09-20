# ==================================================================
# File: SEEDErrorAutoFixManager.py
# Path: SEED_ROOT/seed/core/integration/SEEDErrorAutoFixManager.py
# v0.0.1 - Rebuilt after partial loss
# Purpose: Supervises error-driven auto-fix workflow for SEED-AI
# ==================================================================

import asyncio
import threading
import logging
import queue
import time
from typing import Optional


logger = logging.getLogger("SEED.AutoFix")


class SEEDErrorAutoFixManager:
    def __init__(self):
        from seed.core.event_bus import SEEDEventBus
        from seed.core.build_manager import BuildManager

        self.running = False
        self.fix_queue = queue.PriorityQueue()
        self.recently_fixed = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------
    # Generate tracking ID (lightweight, non-global)
    # ------------------------------------------------------
    def gen_track_id(self) -> str:
        return f"AF-{int(time.time() * 1000)}"

    # ------------------------------------------------------
    # Emit EventBus event (safe)
    # ------------------------------------------------------
    def emit_event(self, event_type, **kwargs):
        if SEEDEventBus and hasattr(SEEDEventBus, "publish"):
            try:
                SEEDEventBus.publish(event_type, **kwargs)
            except Exception as e:
                track_id = self.gen_track_id()
                logger.warning(
                    f"[{track_id}] Failed to emit event {event_type}: {e}"
                )

    # ------------------------------------------------------
    # Start manager (fixed async/thread issues)
    # ------------------------------------------------------
    def start(self):
        if self.running:
            return

        self.running = True

        def _runner():
            try:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                self._loop.run_until_complete(self.run_loop())
            except Exception as e:
                logger.error(f"[SEAFM] Loop crashed: {e}")

        self._thread = threading.Thread(
            target=_runner,
            daemon=True,
            name="SEEDErrorAutoFixLoop"
        )
        self._thread.start()

        logger.info("[SEAFM] AutoFix Supervisor started")

    # ------------------------------------------------------
    # Stop manager
    # ------------------------------------------------------
    def stop(self):
        self.running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("[SEAFM] AutoFix Supervisor stopped")

    # ------------------------------------------------------
    # Async supervisor loop
    # ------------------------------------------------------
    async def run_loop(self):
        logger.info("[SEAFM] Supervisor loop running")
        while self.running:
            await asyncio.sleep(0.1)
            self.apply_fixes()

    # ------------------------------------------------------
    # Queue a file fix
    # ------------------------------------------------------
    def queue_fix(self, file_path: str, priority: int = 5):
        if not file_path:
            return
        self.fix_queue.put((priority, file_path))
        logger.debug(f"[SEAFM] Fix queued: {file_path}")

    # ------------------------------------------------------
    # Apply fixes (deduplicated)
    # ------------------------------------------------------
    def apply_fixes(self):
        try:
            while not self.fix_queue.empty():
                priority, file_path = self.fix_queue.get_nowait()

                if file_path in self.recently_fixed:
                    continue

                self.emit_event(
                    "autofix.started",
                    file=file_path,
                    priority=priority
                )

                # Placeholder for mutation detection
                original = self._read_file(file_path)
                updated = self._attempt_fix(file_path, original)

                if updated and updated != original:
                    self._write_file(file_path, updated)
                    self.recently_fixed.add(file_path)

                    self.emit_event(
                        "autofix.completed",
                        file=file_path
                    )

        except Exception as e:
            logger.error(f"[SEAFM] apply_fixes failure: {e}")

    # ------------------------------------------------------
    # File helpers (intentionally simple)
    # ------------------------------------------------------
    def _read_file(self, path: str) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"[SEAFM] Read failed {path}: {e}")
            return None

    def _write_file(self, path: str, content: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"[SEAFM] Write failed {path}: {e}")

    # ------------------------------------------------------
    # Attempt fix (stub – logic lives elsewhere)
    # ------------------------------------------------------
    def _attempt_fix(self, file_path: str, content: Optional[str]) -> Optional[str]:
        return content


# ------------------------------------------------------
# Build Manager Runner (instance-safe)
# ------------------------------------------------------
def build_manager_runner(
    fix_queue,
    build_manager: Optional[BuildManager] = None
):
    if build_manager is None:
        build_manager = BuildManager()

    while True:
        try:
            priority, file_path = fix_queue.get()
            if file_path:
                build_manager.queue_fix(file_path)
                logger.info(
                    f"[BuildManager] Queued fix for {file_path} "
                    f"(priority {priority})"
                )
        except Exception as e:
            logger.error(
                f"[BuildManager] Failed to queue fix: {file_path} → {e}"
            )
