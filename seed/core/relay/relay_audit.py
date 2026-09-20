# ==========================================================
# FILE: relay_audit.py
# PATH: SEED_ROOT/seed/core/relay/relay_audit.py
# VERSION: 2.0.0
# PURPOSE: Relay operation audit trail
# ==========================================================

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict


MODULE_ID = "CORE_RELAY_AUDIT"
MODULE_VERSION = "2.0.0"


class RelayAudit:
    def __init__(self, path: str = "SEED_ROOT/relay_audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()

    def record(self, event: Dict[str, Any]) -> None:
        payload = dict(event)

        with self._lock:
            with self.path.open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )

    def record_request(self, request: Any) -> None:
        self.record(
            {
                "event": "relay_request",
                "request": request.to_dict()
                if hasattr(request, "to_dict")
                else str(request),
            }
        )

    def record_response(self, response: Any) -> None:
        self.record(
            {
                "event": "relay_response",
                "response": response.to_dict()
                if hasattr(response, "to_dict")
                else str(response),
            }
        )