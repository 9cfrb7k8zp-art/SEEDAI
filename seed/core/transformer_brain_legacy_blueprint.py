# ==========================================================
# FILE: transformer_brain.py
# PATH: SEED_ROOT/seed/core/transformer_brain.py
# VERSION: 4.9 (FIXED THREADS / ASYNC / STATE HANDLING)
# UPDATED: 2026-01-12 Time: 12:30pm
# ==========================================================

# transformer_brain.py
import threading
import asyncio
import math
import random
import time
import logging
import traceback
from uuid import uuid4
from collections import defaultdict, deque
import cmath
from typing import Dict, Optional, Callable, Any, List, Tuple
import psutil
import tracemalloc

from seed.core.qbit import Qbit
from seed.core.audio_modem_manager import AudioModemManager

logger = logging.getLogger("TransformerBrain")
logger.setLevel(logging.INFO)

class EventBusStub:
    def __init__(self, event=None, track=None, emit=None, task=None, payload=None):
        self._callbacks = {}

    def emit(self, event_type, payload=None):
        # just log or ignore
        return True

    def subscribe(self, event_type, callback):
        # store callback safely
        self._callbacks.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type, callback):
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)

class TrackStub:
    def __call__(self, *args, **kwargs):
        return {}  # satisfies callability
    def subscribe(self, *args, **kwargs):
        pass  # satisfies subscribe calls

class EmitStub:
    def __call__(self, event_type, payload=None):
        pass
    def subscribe(self, *args, **kwargs):
        pass

class DualEmit:
    def __init__(self, *, event_bus=None, loop=None, logger=None):
        self.event_bus = event_bus
        self.loop = loop
        self.logger = logger

    # -------- SEMANTIC CHANNEL --------
    def emit_event(self, event, payload=None):
        if self.event_bus:
            return self.event_bus.emit(event, payload)
        if self.logger:
            self.logger.warning(f"[DualEmit] No event_bus for {event}")
        return False

    # -------- EXECUTION CHANNEL --------
    def emit_exec(self, target):
        if not self.loop:
            raise RuntimeError("No asyncio loop bound to DualEmit")

        if asyncio.iscoroutine(target):
            return self.loop.create_task(target)

        if callable(target):
            return self.loop.call_soon(target)

        raise TypeError(f"Cannot exec emit type: {type(target)}")



# ==========================================================
# CONSTANTS
# ==========================================================
HEARTBEAT_TIMEOUT = 1.5
TICK_ACTIVE = 0.10
TICK_PLAN = 0.15
TICK_IDLE = 0.35
CPU_LIMIT_PERCENT = 65.0
MEM_LIMIT_PERCENT = 75.0
RECOVERY_RETRY_LIMIT = 15
MAX_LIMP_ATTEMPTS = 30
YELLOW_LIMIT = 6
RED_LIMIT = 3

QBIT_TICK = "QBIT:TICK"

# ==========================================================

# ==========================================================
# TRACK ID HELPER
# ==========================================================
def gen_track_id(prefix="TRANSFORMER", parent_id=None, origin="System") -> Dict[str, str]:
    if parent_id is None:
        parent_id = TrackContext.get()
    return {
        "track_id": f"{prefix}-{str(uuid.uuid4())[:8]}",
        "parent_id": parent_id,
        "origin": origin
    }

# ==========================================================
# QUANTUM / QBIT MATH
# ==========================================================
async def qbit_state_random():
    a = complex(random.random(), random.random())
    b = complex(random.random(), random.random())
    norm = math.sqrt(abs(a)**2 + abs(b)**2) or 1.0
    return a / norm, b / norm


async def vector_gate_rotate(alpha, beta, theta):
    na = alpha * math.cos(theta) - beta * math.sin(theta)
    nb = alpha * math.sin(theta) + beta * math.cos(theta)
    norm = math.sqrt(abs(na)**2 + abs(nb)**2) or 1.0
    return na / norm, nb / norm


@staticmethod
def normalize_qbit_input(state_input: Any) -> Tuple[complex, complex]:
    if isinstance(state_input, (int, float, complex)):
        state_input = (complex(state_input), 0.0 + 0.0j)
    elif isinstance(state_input, (list, tuple)):
        state_input = tuple(complex(x) for x in state_input)
    else:
        raise ValueError(f"Cannot convert {type(state_input)} to Qbit state")

    if len(state_input) != 2:
        state_input = (state_input[0], state_input[1] if len(state_input) > 1 else 0.0 + 0.0j)

    norm = sum(abs(x)**2 for x in state_input) ** 0.5
    if norm == 0:
        state_input = (1 / 2**0.5, 1 / 2**0.5)
    return tuple(x / norm for x in state_input)


# ==========================================================
# TRANSFORMER BRAIN
# ==========================================================
class TransformerBrain:
    def __init__(self, name, payload=None, qbit=Qbit, lr=0.01):
        self.qbit = qbit
        self.name = name
        self.payload = None
        self.lr = lr
        self.weights = defaultdict(lambda: 1.0)
        self.history = deque(maxlen=128)
        self.confidence = 3.3
        self.cpu = ("cpu", qbit)       # just a reference
        self.audio = AudioModemManager # reference to existing manager
        self._lock = threading.Lock()



#        qbit_instance = qbit(payload={"heartbeat","cpu","confidence","intent","qbit","weights", "history"})  # your actual Qbit instance



# --------------------------

        self._lock = threading.Lock()

    async def adapt(self):
        if len(self.history) < 2:
            return
        delta = self.history[-1] - self.history[-2]
        with self._lock:
            for k in self.weights:
                self.weights[k] += self.lr * delta


# --------------------------
    async def compute(self, signals: Dict[str, float]) -> float:
        vals = [float(v) for v in signals.values() if isinstance(v, (int, float))]
        if not vals:
            self.confidence *= 0.98
            return self.confidence
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        score = mean / (1 + math.sqrt(variance))
        a, b = await qbit_state_random()
        a, b = await vector_gate_rotate(a, b, random.random() * math.pi)
        score += (abs(a)**2 - abs(b)**2) * 0.05
        self.history.append(score)
        self.confidence = max(0.05, min(2.5, score))
        return self.confidence

    async def adapt(self):
        if len(self.history) < 2:
            return
        delta = self.history[-1] - self.history[-2]
        for k in self.weights:
            self.weights[k] += self.lr * delta
