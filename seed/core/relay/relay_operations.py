# ==========================================================
# FILE: relay_operations.py
# PATH: SEED_ROOT/seed/core/relay/relay_operations.py
# VERSION: 2.0.0
# PURPOSE: Relay operation registry and validation
# ==========================================================

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet


MODULE_ID = "CORE_RELAY_OPERATIONS"
MODULE_VERSION = "2.0.0"


class OperationClass(str, Enum):
    READ = "READ"
    REPORT = "REPORT"
    PREPARE = "PREPARE"


class RelayOperationSpec:

    def __init__(
        self,
        name: str,
        operation_class: OperationClass,
        *,
        requires_target: bool = True,
        modifies_external_state: bool = False,
    ):
        self.name = name
        self.operation_class = operation_class
        self.requires_target = requires_target
        self.modifies_external_state = modifies_external_state

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "class": self.operation_class.value,
            "requires_target": self.requires_target,
            "modifies_external_state": self.modifies_external_state,
        }


class RelayOperations:

    _REGISTRY: Dict[str, RelayOperationSpec] = {
        "READ_REPOSITORY": RelayOperationSpec(
            "READ_REPOSITORY",
            OperationClass.READ,
        ),
        "READ_ISSUE": RelayOperationSpec(
            "READ_ISSUE",
            OperationClass.READ,
        ),
        "READ_PR": RelayOperationSpec(
            "READ_PR",
            OperationClass.READ,
        ),
        "READ_COMMENTS": RelayOperationSpec(
            "READ_COMMENTS",
            OperationClass.READ,
        ),
        "CREATE_REPORT": RelayOperationSpec(
            "CREATE_REPORT",
            OperationClass.REPORT,
            requires_target=False,
        ),
        "CREATE_ISSUE": RelayOperationSpec(
            "CREATE_ISSUE",
            OperationClass.PREPARE,
        ),
        "UPDATE_TASK": RelayOperationSpec(
            "UPDATE_TASK",
            OperationClass.PREPARE,
        ),
        "CREATE_PROPOSAL": RelayOperationSpec(
            "CREATE_PROPOSAL",
            OperationClass.PREPARE,
        ),
    }

    @classmethod
    def normalize(cls, operation: str) -> str:
        return str(operation).strip().upper()

    @classmethod
    def exists(cls, operation: str) -> bool:
        return cls.normalize(operation) in cls._REGISTRY

    @classmethod
    def get(
        cls,
        operation: str,
    ) -> RelayOperationSpec | None:

        return cls._REGISTRY.get(
            cls.normalize(operation)
        )

    @classmethod
    def validate(
        cls,
        operation: str,
        target: str = "",
    ) -> tuple[bool, str]:

        normalized = cls.normalize(operation)

        spec = cls.get(normalized)

        if spec is None:
            return (
                False,
                f"Unknown relay operation: {normalized}",
            )

        if spec.requires_target and not target:
            return (
                False,
                f"Operation requires target: {normalized}",
            )

        return True, "OPERATION_VALID"

    @classmethod
    def names(cls) -> FrozenSet[str]:
        return frozenset(cls._REGISTRY.keys())

    @classmethod
    def describe(cls) -> Dict[str, dict]:
        return {
            name: spec.to_dict()
            for name, spec in cls._REGISTRY.items()
        }

    @classmethod
    def status(cls) -> dict:
        return {
            "module": MODULE_ID,
            "version": MODULE_VERSION,
            "operation_count": len(cls._REGISTRY),
            "operations": cls.describe(),
        }