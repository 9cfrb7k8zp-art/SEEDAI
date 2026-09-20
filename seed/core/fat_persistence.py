# ==========================================================
# FILE: fat_persistence.py
# PATH: SEED_ROOT/seed/core/fat_persistence.py
# PURPOSE:
#   Durable persistence for FAT entries.
#   Writes JSONL (one entry per line).
#
# EDIT GUIDE:
#   - File naming / rotation        → see _rotate_if_needed()
#   - Metadata header format        → see _write_header()
#   - Serialization rules           → see _safe_serialize()
# ==========================================================

import json
import os
import time
import threading
from typing import Dict, Any


class FATPersistence:
    """
    Thread-safe, append-only persistence layer for FAT.
    This layer MUST NEVER block or raise.
    """

    def __init__(
        self,
        storage_root: str = "./SEED_ROOT",
        filename: str = "fat.log",
        max_bytes: int = 50_000_000,  # ~50MB
    ):
        self.storage_root = storage_root
        self.path = os.path.join(storage_root, filename)
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

        os.makedirs(storage_root, exist_ok=True)

        # Write header once per file
        if not os.path.exists(self.path):
            self._write_header()

    # --------------------------------------------------
    # Header (written ONCE per log file)
    # --------------------------------------------------
    def _write_header(self):
        header = {
            "type": "FAT_LOG",
            "version": 1,
            "created": time.time(),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"__header__": header}) + "\n")

    # --------------------------------------------------
    # Rotation (SAFE, SIZE-BASED)
    # --------------------------------------------------
    def _rotate_if_needed(self):
        try:
            if os.path.getsize(self.path) < self.max_bytes:
                return

            ts = time.strftime("%Y%m%d_%H%M%S")
            rotated = self.path.replace(".log", f"_{ts}.log")
            os.rename(self.path, rotated)

            # Start fresh file
            self._write_header()

        except Exception:
            # Rotation failure must NEVER stop persistence
            pass

    # --------------------------------------------------
    # Serialization safety
    # --------------------------------------------------
    def _safe_serialize(self, entry: Dict[str, Any]) -> str:
        try:
            return json.dumps(entry, ensure_ascii=False)
        except Exception as e:
            # Last-resort fallback
            return json.dumps({
                "timestamp": time.time(),
                "source": "fat_persistence",
                "label": "serialization_error",
                "error": str(e),
                "raw_type": type(entry).__name__,
            })

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------
    def persist(self, entry: Dict[str, Any]):
        """
        Persist a single FAT entry.
        NEVER raises.
        """
        with self._lock:
            try:
                self._rotate_if_needed()
                line = self._safe_serialize(entry)

                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")

            except Exception:
                # Absolute last line of defense
                pass
