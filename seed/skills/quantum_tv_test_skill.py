# ==========================================================
# FILE: quantum_tv_test_skill.py
# PURPOSE: Controlled QTV test skill
# ==========================================================

import asyncio
from COM.quantum_object import QuantumObject


class QuantumTVTestSkill:

    def __init__(self, seed_core):
        self.seed = seed_core
        self.qtv = seed_core.quantum_tv

    async def run(self):
        q = QuantumObject(
            source="SEED",
            intent="create",
            payload="Hello Quantum World",
            tags=["text"]
        )

        await self.qtv.start()
        await self.qtv.broadcast(q)

        self.event_bus.publish(
            "CUSTOM_EVENT",
            {"intent": "broadcast", "qobj": q}
         )