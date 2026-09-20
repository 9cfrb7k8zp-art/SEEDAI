# =====================================================================
# File: codex.py
# Path: SEED_ROOT/seed/systemutils/codex.py
# Version: 1.0 (LIVE AUTOFIX + REPAIR ALIAS | Thread-Safe | Async-Safe)
#
# Codex Administrator | Code Database | AutoFix Executor
#
# FIXES:
# - Codex repair alias added for backward compatibility
# - Codex repair now ACTUALLY modifies files
# - Integrated AutoFixEngine execution
# - Async-safe dispatch
# - EventBus compatible
# - Thread-safe index saves
# - No fake repair logs
# =====================================================================

import os
import json
import logging
import hashlib
import threading
import asyncio
from typing import Optional, Dict, List

from seed.core.event_bus import SEEDEventBus

try:
    from seed.core.integration.autofix_engine import AutoFixEngine
except Exception:
    AutoFixEngine = None

logger = logging.getLogger("Codex")
logger.setLevel(logging.INFO)

# --------------------------------------------------
# Storage
# --------------------------------------------------
CODEX_STORAGE = os.path.join("SEED_ROOT", "seed", "codex_data")
os.makedirs(CODEX_STORAGE, exist_ok=True)
_index_lock = threading.Lock()


class Codex:
    """
    Codex
    - Central code repository
    - Real AutoFix dispatcher
    - Execution + repair authority
    """

    SUPPORTED_LANGUAGES = ["python", "c++", "java", "php", "mysql", "dotnet"]

    def __init__(
        self,
        event_bus: Optional[SEEDEventBus] = None,
        autofix_engine: Optional[AutoFixEngine] = None
    ):
        self.event_bus = event_bus
        self.autofix_engine = autofix_engine
        self._load_index()

    # ==================================================
    # INDEX MANAGEMENT
    # ==================================================
    def _load_index(self):
        self.index_path = os.path.join(CODEX_STORAGE, "codex_index.json")
        if os.path.exists(self.index_path):
            with open(self.index_path, "r", encoding="utf-8") as f:
                self.index: Dict[str, Dict] = json.load(f)
            logger.info(f"[Codex] Loaded {len(self.index)} entries")
        else:
            self.index = {}
            logger.info("[Codex] Initialized empty index")

    def _save_index(self):
        with _index_lock:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(self.index, f, indent=2)
            logger.info(f"[Codex] Index saved ({len(self.index)} entries)")

    # ==================================================
    # ENTRY MANAGEMENT
    # ==================================================
    def add_entry(
        self,
        name: str,
        language: str,
        code: str,
        description: str = "",
        register_as_skill: bool = True
    ):
        language = language.lower()
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")

        entry_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()[:8]
        entry_id = f"{name}-{entry_hash}"
        filename = f"{entry_id}.{language.replace('++', 'pp')}"
        filepath = os.path.join(CODEX_STORAGE, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        self.index[entry_id] = {
            "name": name,
            "language": language,
            "description": description,
            "filepath": filepath
        }
        self._save_index()

        logger.info(f"[Codex] Added entry {entry_id}")

        if self.event_bus and register_as_skill:
            self.event_bus.emit({
                "event": "CODEX_ENTRY_ADDED",
                "entry_id": entry_id,
                "language": language,
                "filepath": filepath
            })

        return entry_id

    def get_entry(self, entry_id: str) -> Optional[Dict]:
        return self.index.get(entry_id)

    def delete_entry(self, entry_id: str) -> bool:
        entry = self.index.get(entry_id)
        if not entry:
            return False

        try:
            if os.path.exists(entry["filepath"]):
                os.remove(entry["filepath"])
        except Exception as e:
            logger.error(f"[Codex] File delete failed: {e}")

        del self.index[entry_id]
        self._save_index()

        if self.event_bus:
            self.event_bus.emit({
                "event": "CODEX_ENTRY_DELETED",
                "entry_id": entry_id
            })

        return True

    # ==================================================
    # REAL SYSTEM REPAIR (NO FAKE LOGS)
    # ==================================================
    def attempt_repair(self, targets: Optional[List[str]] = None):
        """
        Dispatches AutoFixEngine against real files.
        This ACTUALLY modifies code.
        """
        if not self.autofix_engine:
            logger.error("[Codex] AutoFixEngine unavailable")
            return

        files: List[str] = []

        if targets:
            for entry_id in targets:
                entry = self.index.get(entry_id)
                if entry:
                    files.append(entry["filepath"])
        else:
            files = [e["filepath"] for e in self.index.values()]

        if not files:
            logger.warning("[Codex] No files to repair")
            return

        logger.info(f"[Codex] Dispatching AutoFix on {len(files)} files")

        for path in files:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    original = f.read()

                threading.Thread(
                    target=self._run_autofix,
                    args=(path, original),
                    daemon=True
                ).start()

                if self.event_bus:
                    self.event_bus.emit({
                        "event": "CODEX_AUTOFIX_DISPATCHED",
                        "file": path
                    })

            except Exception as e:
                logger.error(f"[Codex] AutoFix dispatch failed for {path}: {e}")

    def _run_autofix(self, file_path: str, content: str):
        try:
            # Run async safe
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(
                    self.autofix_engine.process_file(
                        file_path=file_path,
                        original_content=content,
                        parent_id="CODEX"
                    )
                )
            else:
                asyncio.run(
                    self.autofix_engine.process_file(
                        file_path=file_path,
                        original_content=content,
                        parent_id="CODEX"
                    )
                )
        except Exception as e:
            logger.error(f"[Codex] AutoFix execution failed: {e}")

    # ==================================================
    # EXECUTION (SAFE / PYTHON ONLY)
    # ==================================================
    def execute(self, entry_id: str, timeout: int = 10) -> Optional[str]:
        entry = self.get_entry(entry_id)
        if not entry:
            return None

        if entry["language"] != "python":
            logger.warning("[Codex] Execution limited to Python")
            return None

        try:
            import subprocess
            result = subprocess.run(
                ["python", entry["filepath"]],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            output = result.stdout.strip()

            if self.event_bus:
                self.event_bus.emit({
                    "event": "CODEX_EXECUTION_OUTPUT",
                    "entry": entry_id,
                    "stdout": output
                })

            return output

        except Exception as e:
            logger.error(f"[Codex] Execution failed: {e}")
            return None

    # ==================================================
    # BACKWARD COMPATIBILITY
    # ==================================================
    def repair(self, targets: Optional[List[str]] = None):
        """
        Legacy repair method for SEED init threading calls
        """
        self.attempt_repair(targets)


# ==================================================
# DIRECT TEST
# ==================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    codex = Codex()

    test_id = codex.add_entry(
        name="HelloSEED",
        language="python",
        code="print('Hello from REAL Codex AutoFix')",
        description="Test skill"
    )

    codex.execute(test_id)


# =====================================================================
# NOTES PRESERVED
# =====================================================================
# Codex Administrator | Code Database | AutoFix Executor
# FIXES:
# - Codex repair alias added for backward compatibility
# - Codex repair now ACTUALLY modifies files
# - Integrated AutoFixEngine execution
# - Async-safe dispatch
# - EventBus compatible
# - Thread-safe index saves
# - No fake repair logs
# =====================================================================
