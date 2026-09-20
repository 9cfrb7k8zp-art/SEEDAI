# ==========================================================
# FILE: network_data_plane.py
# PATH: SEED_ROOT/seed/core/network_data_plane.py
# VERSION: 1.0.0
# BUILD: OFFLINE-FIRST / QBIT-DATA-SYNC
#
# PURPOSE:
#   Bounded local outbox for SEED records that must reach the
#   network database when connectivity is available.
#
# AUTHORITY:
#   Qbit remains the data carrier.
#   QbitDialer remains command authority.
#   This module is storage/synchronization only.
# ==========================================================

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


class NetworkDataPlane:
    VERSION = "1.0.0"
    MAX_PENDING = 500

    def __init__(self, root=None):
        base = Path(root or os.getenv("SEED_ROOT", "."))
        self.path = base / "runtime" / "network_outbox.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read(self):
        try:
            if not self.path.exists():
                return []
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError, TypeError):
            return []

    def _write(self, rows):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows[-self.MAX_PENDING:], default=str), encoding="utf-8")
        tmp.replace(self.path)

    def enqueue(self, table, payload):
        row = {
            "queued_at": time.time(),
            "table": str(table),
            "payload": payload,
        }
        with self._lock:
            rows = self._read()
            rows.append(row)
            self._write(rows)
        return row

    def pending(self):
        with self._lock:
            return list(self._read())

    def size(self):
        return len(self.pending())

    def drain(self, sender, limit=25):
        sent = 0
        failed = 0
        with self._lock:
            rows = self._read()
            remaining = []
            for row in rows:
                if sent >= int(limit):
                    remaining.append(row)
                    continue
                try:
                    result = sender(row["table"], row["payload"])
                    if result is None:
                        failed += 1
                        remaining.append(row)
                    else:
                        sent += 1
                except Exception:
                    failed += 1
                    remaining.append(row)
            self._write(remaining)
        return {"sent": sent, "failed": failed, "pending": len(remaining)}

    def status(self):
        return {
            "version": self.VERSION,
            "path": str(self.path),
            "pending": self.size(),
            "max_pending": self.MAX_PENDING,
            "mode": "OFFLINE_FIRST",
        }
