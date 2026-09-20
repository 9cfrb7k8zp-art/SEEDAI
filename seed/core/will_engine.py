# ==========================================================
# FILE: will_engine.py
# Path: C:\SEED_ROOT\seed\core\will_engine.py
# SEED CORE – WILL / INTENT ENGINE
# ==========================================================

import time
import threading
import logging

from seed.core.heartbeat import Heartbeat
from seed.core.emitters.heartbeatemitter import HeartbeatEmitter
from seed.core.dialers.qbit_dialer import QbitDialer
from seed.core.qbit import Qbit


log = logging.getLogger("WILL")

class OracleWill:

    def __init__(self):
        self.alive = True
        self.last_decision = None
        self.heartbeat = HeartbeatEmitter()


        self.thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        self.thread.start()

        log.info("OracleWill initialized and running")

    def _run(self):
        while self.alive:
            qbit = Qbit.capture_system_state()

            decision = self.evaluate(qbit)

            if decision:
                self.authorize(qbit, decision)

            time.sleep(0.05)  # non-blocking, OS-safe

    def evaluate(self, qbit: Qbit) -> str | None:

        if qbit.has_error():
            return "HANDLE_ERROR"

        if qbit.system_idle_too_long():
            return "EXPLORE"

        if qbit.external_signal_detected():
            return "RESPOND"

        return None

    def authorize(self, qbit: Qbit, decision: str):
        self.last_decision = decision

        self.heartbeat.emit(
            source="OracleWill",
            intent=decision,
            qbit=qbit
        )

        log.debug(f"WILL authorized action: {decision}")


# AUTO-INIT ON IMPORT
OracleWill()
