# ==========================================================
# FILE: relay_github.py
# PATH: SEED_ROOT/seed/core/relay/relay_github.py
# VERSION: 2.0.0
# PURPOSE: GitHub relay adapter
# ==========================================================

from __future__ import annotations

from typing import Any, Dict

from .relay_protocol import RelayRequest


MODULE_ID = "CORE_RELAY_GITHUB"
MODULE_VERSION = "2.0.0"


class RelayGitHub:

    def __init__(self):
        self.enabled = False

    def execute(self, request: RelayRequest) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "success": False,
                "status": "DISABLED",
                "operation": request.operation,
                "target": request.target,
                "message": (
                    "GitHub adapter is not enabled. "
                    "Relay nucleus is operating in safe mode."
                ),
            }

        return {
            "success": False,
            "status": "NOT_IMPLEMENTED",
            "operation": request.operation,
            "target": request.target,
        }

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False