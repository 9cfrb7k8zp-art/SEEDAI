# ==========================================================
# FILE: relay_mission_bridge.py
# PATH: SEED_ROOT/seed/core/relay/relay_mission_bridge.py
# VERSION: 2.0.0
# PURPOSE: Mission-to-relay request bridge
# ==========================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from .relay_core import SEEDRelay
from .relay_protocol import RelayRequest


MODULE_ID = "CORE_RELAY_MISSION_BRIDGE"
MODULE_VERSION = "2.0.0"


class RelayMissionBridge:

    def __init__(
        self,
        relay: SEEDRelay,
    ):
        self.relay = relay

    def submit(
        self,
        *,
        operation: str,
        target: str = "",
        mission_id: str = "",
        track_id: str = "",
        channel_id: str = "",
        qbit_id: str = "",
        parent_qbit_id: str = "",
        source: str = "",
        source_of_start: str = "",
        classification: str = "",
        intent: str = "",
        provenance: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 50,
        safety_class: str = "OBSERVE",
    ):

        request = RelayRequest(
            operation=operation,
            target=target,
            payload=payload or {},
            seed_id="SEED-CORE",
            mission_id=mission_id,
            track_id=track_id,
            channel_id=channel_id,
            qbit_id=qbit_id,
            parent_qbit_id=parent_qbit_id,
            source=source,
            source_of_start=source_of_start or source,
            classification=classification,
            intent=intent,
            provenance=dict(provenance or {}),
            priority=priority,
            safety_class=safety_class,
        )

        return self.relay.submit(
            request
        )

    def status(self) -> dict:
        return {
            "module": MODULE_ID,
            "version": MODULE_VERSION,
            "relay_id": self.relay.relay_id,
            "relay_running": self.relay.status()[
                "running"
            ],
        }