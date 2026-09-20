# =====================================================================
# FILE: seed_runtime_context.py
# PATH: SEED_ROOT/seed/core/seed_runtime_context.py
#
# SEED-AI CORE SUBFOLDER
# - Tracks runtime context for SEED-AI
# - Provides singleton access to core modules
# - Exports module state to JSON for control
# - Thread-safe, non-blocking
# =====================================================================

import threading
import json
import time
from pathlib import Path
from seed_root_init_logger import logger
from seed.kernel_paths import RUNTIME_STATE_FILE


# ---------------------------------------------
# Paths
# ---------------------------------------------
RUNTIME_DIR = Path(__file__).parent.parent / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = RUNTIME_STATE_FILE


# ---------------------------------------------
# Runtime singleton
# ---------------------------------------------
class SEEDRuntimeContext:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        # Core modules placeholders
        self.modules = {}  # all core modules tracked dynamically
        self.boot_time = time.time()
        self.last_snapshot = {}
        self._snapshot_lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("{}")
    # --------------------------------------------------
    # Module management
    # --------------------------------------------------

    def register_module(self, name: str, instance):
        self.modules[name] = {
            "instance": instance,
            "status": "initialized",
            "boot_time": time.time()
        }
        logger.info(f"[RUNTIME] Module registered: {name}")
        self._export_state()

    def update_module_status(self, name: str, status: str):
        if name in self.modules:
            self.modules[name]["status"] = status
            self.modules[name]["last_update"] = time.time()
            logger.info(f"[RUNTIME] Module status updated: {name} -> {status}")
            self._export_state()
        else:
            logger.warning(f"[RUNTIME] Tried to update unknown module: {name}")

    # --------------------------------------------------
    # Snapshot / JSON export
    # --------------------------------------------------

    def _export_state(self):
        try:
            with self._snapshot_lock:
                snapshot = {k: v.copy() for k, v in self.modules.items()}
                snapshot["boot_time"] = self.boot_time
                snapshot["last_snapshot_time"] = time.time()
                with STATE_FILE.open("w") as f:
                    json.dump(snapshot, f, indent=2)
                self.last_snapshot = snapshot
        except Exception as e:
            logger.warning(f"[RUNTIME] Failed to export runtime state: {e}")

    def snapshot(self):
        """Get latest snapshot for AI use (thread-safe)."""
        with self._snapshot_lock:
            return self.last_snapshot.copy()

# ---------------------------------------------
# Singleton accessor
# ---------------------------------------------
def get() -> SEEDRuntimeContext:
    return SEEDRuntimeContext()
