# ==========================================================
# FILE: heartbeat_vector.py
# ==========================================================

import random
from collections import deque


class HeartbeatVectorCore:
    def __init__(self, max_history=128):
        self.history = deque(maxlen=max_history)
        self.last_value = 0

    def process_tick(self, tick, core_status, system_status, user_status):
        qbit_val = (
            (tick ^ int(core_status * 100))
            + int(system_status * 50)
            - int(user_status * 25)
        ) & 0xFFFFFFFF

        qbit_val ^= random.getrandbits(32)
        self.last_value = qbit_val

        vector = {
            "tick": tick,
            "qbit_value": qbit_val,
            "vector": [
                core_status,
                system_status,
                user_status,
                (qbit_val & 0xFF) / 255.0,
            ],
        }

        self.history.append(vector)
        return vector
