# ==========================================================
# FILE: relay_policy.py
# PATH: SEED_ROOT/seed/core/relay/relay_policy.py
# VERSION: 2.0.0
# PURPOSE: Relay authorization policy
# ==========================================================

from __future__ import annotations

from typing import Set

from .relay_protocol import RelayOperation, RelayRequest


MODULE_ID = "CORE_RELAY_POLICY"
MODULE_VERSION = "2.0.0"


class RelayPolicy:

    DEFAULT_ALLOWED: Set[str] = {
        RelayOperation.READ_REPOSITORY.value,
        RelayOperation.READ_ISSUE.value,
        RelayOperation.READ_PR.value,
        RelayOperation.READ_COMMENTS.value,
        RelayOperation.CREATE_REPORT.value,
    }

    PREPARE_ALLOWED: Set[str] = {
        RelayOperation.CREATE_ISSUE.value,
        RelayOperation.UPDATE_TASK.value,
        RelayOperation.CREATE_PROPOSAL.value,
    }

    def __init__(self, allow_prepare: bool = False):
        self.allow_prepare = bool(allow_prepare)

    def allowed_operations(self) -> Set[str]:
        allowed = set(self.DEFAULT_ALLOWED)

        if self.allow_prepare:
            allowed.update(self.PREPARE_ALLOWED)

        return allowed

    def authorize(self, request: RelayRequest) -> tuple[bool, str]:
        operation = str(request.operation).upper()

        if operation not in self.allowed_operations():
            return (
                False,
                f"Operation denied by relay policy: {operation}",
            )

        if request.safety_class.upper() not in {
            "OBSERVE",
            "THINK",
            "TEST",
            "PROPOSE",
        }:
            return (
                False,
                f"Unsupported safety class: {request.safety_class}",
            )

        if not request.target and operation != RelayOperation.CREATE_REPORT.value:
            return False, "Relay target is required."

        return True, "AUTHORIZED"