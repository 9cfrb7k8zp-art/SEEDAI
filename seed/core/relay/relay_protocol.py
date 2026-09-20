# ==========================================================
# FILE: relay_protocol.py
# PATH: SEED_ROOT/seed/core/relay/relay_protocol.py
# VERSION: 2.0.0
# PURPOSE: Relay request/response protocol
# ==========================================================

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid


MODULE_ID = "CORE_RELAY_PROTOCOL"
MODULE_VERSION = "2.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RelayStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DEFERRED = "deferred"
    STOPPED = "stopped"


class RelayOperation(str, Enum):
    READ_REPOSITORY = "READ_REPOSITORY"
    READ_ISSUE = "READ_ISSUE"
    READ_PR = "READ_PR"
    READ_COMMENTS = "READ_COMMENTS"

    CREATE_REPORT = "CREATE_REPORT"
    CREATE_ISSUE = "CREATE_ISSUE"
    UPDATE_TASK = "UPDATE_TASK"
    CREATE_PROPOSAL = "CREATE_PROPOSAL"


@dataclass
class RelayRequest:
    operation: str
    target: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    seed_id: str = "SEED-CORE"
    mission_id: str = ""
    track_id: str = ""
    channel_id: str = ""

    # Qbit lineage and cognition context are carried through Relay unchanged.
    qbit_id: str = ""
    parent_qbit_id: str = ""
    source: str = ""
    source_of_start: str = ""
    classification: str = ""
    intent: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    priority: int = 50
    safety_class: str = "OBSERVE"

    cpu_budget: float = 25.0
    memory_budget: float = 25.0

    request_id: str = field(
        default_factory=lambda: f"RELAY-{uuid.uuid4().hex[:12]}"
    )

    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RelayResponse:
    request_id: str
    status: RelayStatus

    operation: str = ""
    target: str = ""

    result: Any = None
    error: Optional[str] = None

    relay_id: str = "SEED-RELAY-2"
    completed_at: str = field(default_factory=utc_now)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data