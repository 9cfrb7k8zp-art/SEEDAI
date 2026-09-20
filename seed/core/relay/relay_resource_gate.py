# ==========================================================
# FILE: relay_resource_gate.py
# PATH: SEED_ROOT/seed/core/relay/relay_resource_gate.py
# VERSION: 2.0.0
# PURPOSE: Resource-aware relay admission control
# ==========================================================

from __future__ import annotations

import os
from typing import Any, Dict


MODULE_ID = "CORE_RELAY_RESOURCE_GATE"
MODULE_VERSION = "2.0.0"


class RelayResourceGate:

    def __init__(
        self,
        cpu_ceiling: float = 50.0,
        memory_ceiling: float = 80.0,
    ):
        self.cpu_ceiling = float(cpu_ceiling)
        self.memory_ceiling = float(memory_ceiling)

    def snapshot(self) -> Dict[str, Any]:
        cpu = self._cpu_percent()
        memory = self._memory_percent()

        return {
            "cpu_percent": cpu,
            "memory_percent": memory,
            "cpu_ceiling": self.cpu_ceiling,
            "memory_ceiling": self.memory_ceiling,
        }

    def allow(self, requested_cpu_budget: float = 25.0) -> tuple[bool, str]:
        state = self.snapshot()

        cpu = state["cpu_percent"]
        memory = state["memory_percent"]

        if cpu >= self.cpu_ceiling:
            return (
                False,
                f"CPU gate closed: {cpu:.1f}% >= {self.cpu_ceiling:.1f}%",
            )

        if memory >= self.memory_ceiling:
            return (
                False,
                f"Memory gate closed: {memory:.1f}% >= "
                f"{self.memory_ceiling:.1f}%",
            )

        if requested_cpu_budget <= 0:
            return False, "Invalid CPU budget."

        return True, "RESOURCE_OK"

    @staticmethod
    def _cpu_percent() -> float:
        try:
            import psutil

            return float(psutil.cpu_percent(interval=0.05))
        except Exception:
            return 0.0

    @staticmethod
    def _memory_percent() -> float:
        try:
            import psutil

            return float(psutil.virtual_memory().percent)
        except Exception:
            return 0.0