# ==========================================================
# FILE: desktop_commander_adapter.py
# PATH: SEED_ROOT/seed/tools/desktop_commander_adapter.py
# SYSTEM: SEED AI OS
# COMPONENT: Desktop Commander Tool Adapter
# VERSION: 1.0.0
# PURPOSE: Give SEED an optional external tool/operator bridge.
# AUTHORITY: Proposal/request only; QbitDialer remains controller.
# ==========================================================
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


class DesktopCommanderAdapter:
    """
    Optional bridge for external operator/tool infrastructure.

    SEED never assumes ChatGPT/Desktop Commander is locally callable.
    When no bridge endpoint exists, this adapter creates a structured
    TOOL_REQUEST proposal for the existing Dialer pipeline instead.
    """

    VERSION = "1.0.0"

    def __init__(self, event_bus=None, dialer=None):
        self.event_bus = event_bus
        self.dialer = dialer
        self.enabled = os.environ.get("SEED_DESKTOP_COMMANDER_ENABLED", "1").lower() in {
            "1", "true", "yes", "on"
        }
        self.endpoint = os.environ.get("SEED_DESKTOP_COMMANDER_URL")
        self.last_request: Optional[Dict[str, Any]] = None

    def request(self, *, skill: str, reason: str, pressure: Optional[Dict[str, Any]] = None,
                inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request = {
            "type": "SEED_TOOL_REQUEST",
            "adapter": "DesktopCommanderAdapter",
            "version": self.VERSION,
            "skill": str(skill),
            "reason": str(reason),
            "pressure": dict(pressure or {}),
            "inputs": dict(inputs or {}),
            "timestamp": time.time(),
            "execution_required": False,
            "authority": "QbitDialer",
        }
        self.last_request = request

        if self.event_bus is not None:
            try:
                self.event_bus.emit("TOOL_REQUEST", request)
            except Exception:
                pass

        # An external bridge is intentionally opt-in. We don't fabricate
        # a network call from inside SEED when no bridge has been configured.
        return {
            "status": "requested",
            "bridge": self.endpoint or "dialer_pipeline",
            "request": request,
        }

    def pressure_requires_tools(self, pressure: Optional[Dict[str, Any]]) -> bool:
        p = pressure or {}
        cpu = float(p.get("cpu", 0) or 0)
        memory = float(p.get("memory", 0) or 0)
        errors = int(p.get("error_count", 0) or 0)
        return cpu >= 85 or memory >= 90 or errors >= 3

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "enabled": self.enabled,
            "endpoint_configured": bool(self.endpoint),
            "last_request": self.last_request,
        }
