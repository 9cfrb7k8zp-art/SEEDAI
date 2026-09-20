# FILE: qtv_test.py

import asyncio
from COM.quantum_object import QuantumObject


async def run(seed_core):
    print(">>> QTV TEST RUN STARTED <<<")

    q = QuantumObject(
        source="SEED",
        intent="create",
        payload="Hello Quantum World",
        tags=["text"]
    )

    print(">>> Q OBJECT CREATED <<<")

    await seed_core.quantum_tv.start()
    print(">>> QTV START CALLED <<<")

    await seed_core.quantum_tv.broadcast(q)
    print(">>> BROADCAST CALLED <<<")

