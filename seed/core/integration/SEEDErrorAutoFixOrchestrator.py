# ==========================================================
# FILE: SEEDErrorAutoFixOrchestrator.py
# VERSION: 2.8 (BOOT-SAFE | ASYNC-CLEAN | SKILL-AWARE | QBIT v3.8)
# UPDATED: 2026-01-17
# ==========================================================

import os
import sys
import asyncio
import logging
import traceback
import time
from threading import Lock, Thread
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from seed.security import _init_ as security_init  # SecurityRegistry

# ==========================================================
# CHANNEL ID GENERATOR
# ==========================================================
#class ChannelID:
#    COUNTERS = {}
#    @staticmethod
#    def next(marker="AFO"):
#        ChannelID.COUNTERS.setdefault(marker, 0)
#        ChannelID.COUNTERS[marker] += 1
#        return f"{marker}.{ChannelID.COUNTERS[marker]}"

# SAFE IMPORTS
try:
    from seed.core.track_id_manager import TrackIDManager
except Exception:
    TrackIDManager = None

try:
    from seed.core.agent_manager import AgentManager
except Exception:
    AgentManager = None

try:
    from seed.core.qbit_dialer import QbitDialer
except Exception:
    QbitDialer = None

try:
    from seed.core.build_manager import BuildManager
except Exception:
    BuildManager = None

try:
    from seed.ui.hud_channel import HUDChannel
except Exception:
    HUDChannel = None

try:
    from seed.core.integration.autofix_skill_loader import AutoFixSkillLoader
    from seed.core.integration.autofix_engine import AutoFixEngine
except Exception:
    AutoFixSkillLoader = None
    AutoFixEngine = None

# CONFIG
SEED_ROOT = r"C:\SEED_ROOT\seed"
AUTOFIX_SKILLS_ROOT = os.path.join(SEED_ROOT, "skills", "autofix")
SCAN_INTERVAL = 10
MAX_THREADS = 4
SUPPORTED_EXTENSIONS: List[str] = [".py"]

logger = logging.getLogger("SEEDErrorAutoFixOrchestrator")
logger.setLevel(logging.INFO)


# ==========================================================
# FILE IO TOOL (NON-BLOCKING EMIT)
# ==========================================================
class FileIOTool:
    def __init__(self, track_manager=None, qbit=None, default_path: Optional[str] = None):
        self.track_manager = track_manager
        self.qbit = qbit
        if default_path:
            self._emit_event("FILE_READ", default_path)

    def _emit_event(self, event_type: str, path: str):
        track_id = (
            self.track_manager.new("SS", event_type, metadata={"file": path})
            if self.track_manager else None
        )
        if self.qbit:
            try:
                self.qbit.emit_safe({"event": event_type, "file": path}, track_id=track_id)
            except Exception:
                logger.warning(f"[FileIOTool] Emit failed for {event_type} on {path}")

    def read(self, path: str) -> str:
        self._emit_event("FILE_READ", path)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def write(self, path: str, content: str):
        self._emit_event("FILE_WRITE", path)
        with open(path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(content)


# ==========================================================
# AUTOFIX ORCHESTRATOR (INTEGRATED WITH SECURITY REGISTRY)
# ==========================================================
class SEEDErrorAutoFixOrchestrator:
    WAIT_QBIT_TIMEOUT = 60  # seconds to wait for QbitDialer
    CYCLE_INTERVAL = 360     # seconds for internal health cycle

    def __init__(self, seed_core=None, hud_channel: Optional[HUDChannel] = None, limp_mode=False):
        self.seed_core = seed_core
        self.hud_channel = hud_channel
        self.limp_mode = limp_mode

        # Managers
        self.track_manager = TrackIDManager() if TrackIDManager else None
        self.agent_manager = AgentManager() if AgentManager else None
        self.qbit = None
        self.build_manager = BuildManager() if BuildManager else None

        self.file_io = FileIOTool(self.track_manager, self.qbit)
        self.running = False
        self.lock = Lock()
        self.executor = ThreadPoolExecutor(max_workers=MAX_THREADS)
        self.task_queue = []

        # Autofix Engine + Loader
        self.autofix_loader = (
            AutoFixSkillLoader(skills_dir=AUTOFIX_SKILLS_ROOT) if AutoFixSkillLoader else None
        )
        self.autofix_engine = None  # will be initialized after Qbit

        # Register in SecurityRegistry
        if security_init.REGISTRY:
            security_init.REGISTRY.register("SEEDErrorAutoFixOrchestrator", self)

        # Start cycle thread
        self._stop_flag = False
        self._cycle_thread = Thread(target=self._cycle_loop, daemon=True)
        self._cycle_thread.start()

        logger.info("[SEAFM] Initialized v2.8 (BOOT-SAFE | SecurityRegistry integrated)")

    # ------------------------------------------------------
    # WAIT AND ATTACH QBIT
    # ------------------------------------------------------
    def _wait_for_qbit(self):
        start = time.time()
        while True:
            try:
                qbit_mod = sys.modules.get("seed.core.qbit_dialer")
                if qbit_mod and hasattr(qbit_mod, "QbitDialer"):
                    self.qbit = qbit_mod.QbitDialer()
                    self.file_io.qbit = self.qbit
                    # Initialize AutoFixEngine once Qbit is ready
                    if AutoFixEngine:
                        self.autofix_engine = AutoFixEngine(
                            file_reader_skill=getattr(self.seed_core, "file_reader", None),
                            build_manager=self.build_manager,
                            agent_manager=self.agent_manager,
                            qbit_dialer=self.qbit,
                            skill_loader=self.autofix_loader
                        )
                    logger.info("[SEAFM] QbitDialer attached, AutoFixEngine ready")
                    return
            except Exception:
                pass
            if time.time() - start > self.WAIT_QBIT_TIMEOUT:
                logger.warning("[SEAFM] QbitDialer unavailable, operating in limp mode")
                return
            time.sleep(1)

    # ------------------------------------------------------
    # APPLY FIXES (THREAD-SAFE + ASYNC)
    # ------------------------------------------------------
    def apply_fixes(self, file_path: str):
        if not any(file_path.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            return

        if not self.autofix_engine:
            # Queue for later if engine not ready
            self.task_queue.append(file_path)
            return

        try:
            original = self.file_io.read(file_path)
            track_id = (
                self.track_manager.new("SS", "AUTO_FIX", metadata={"file": file_path})
                if self.track_manager else None
            )

            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self._apply_async(original, file_path, track_id),
                loop
            )

            if self.hud_channel:
                self.hud_channel.notify(
                    title="AutoFix",
                    message=f"Analyzed {os.path.basename(file_path)}",
                    track_id=track_id
                )

        except Exception:
            logger.error(f"[SEAFM] AutoFix failed for {file_path}")
            logger.error(traceback.format_exc())

    async def _apply_async(self, original: str, file_path: str, track_id=None):
        try:
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self.autofix_engine.process_file(
                    file_path=file_path,
                    original_content=original,
                    parent_id=track_id
                )
            )
        except Exception:
            logger.error(f"[SEAFM] Async AutoFix failed for {file_path}")
            logger.error(traceback.format_exc())

    # ------------------------------------------------------
    # SCAN LOOP
    # ------------------------------------------------------
    async def _scan_loop(self):
        while self.running:
            for root, _, files in os.walk(SEED_ROOT):
                for f in files:
                    if any(f.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                        self.executor.submit(self.apply_fixes, os.path.join(root, f))
            await asyncio.sleep(SCAN_INTERVAL)

    # ------------------------------------------------------
    # CYCLE LOOP (HEALTH CHECK + QUEUE PROCESSING)
    # ------------------------------------------------------
    def _cycle_loop(self):
        while not self._stop_flag:
            try:
                # Ensure Qbit is attached
                if not self.qbit:
                    self._wait_for_qbit()

                # Retry queued tasks
                if self.autofix_engine and self.task_queue:
                    queued = list(self.task_queue)
                    self.task_queue.clear()
                    for file_path in queued:
                        self.apply_fixes(file_path)

                # Optional: security registry health snapshot
                if security_init.REGISTRY:
                    snapshot = security_init.REGISTRY.audit_snapshot()
                    if snapshot["failures"]:
                        logger.warning(f"[SEAFM] SecurityRegistry snapshot: {snapshot['failures']}")

            except Exception:
                logger.error("[SEAFM] Error in cycle loop")
                logger.error(traceback.format_exc())

            time.sleep(self.CYCLE_INTERVAL)

    # ------------------------------------------------------
    # START / STOP
    # ------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        Thread(target=lambda: asyncio.run(self._scan_loop()), daemon=True).start()
        logger.info("[SEAFM] AutoFix Orchestrator started")

    def stop(self):
        self.running = False
        self._stop_flag = True
        self.executor.shutdown(wait=False)
        logger.info("[SEAFM] AutoFix Orchestrator stopped")
