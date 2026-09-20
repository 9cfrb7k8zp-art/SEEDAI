# ==========================================================
# FILE: actuator_engine.py
# PATH: SEED_ROOT/seed/core/actuator_engine.py
# VERSION: 4.4 (HUD & TRACK SYSTEM INTEGRATED | QBIT 3-BUNDLE)
# UPDATED: 2026-01-01
#     """Context-safe Track ID management for L4 routing"""
#
# 
# 
# ==========================================================

import logging
import threading
import time
import asyncio
import uuid
import contextvars
from datetime import datetime
from copy import deepcopy
from collections import deque
from enum import Enum

logger = logging.getLogger("ActuatorEngine")
logger.setLevel(logging.INFO)

# ==========================================================
# TRACK CONTEXT
# ==========================================================
_track_id_ctx = contextvars.ContextVar("A-E", default=None)

class TrackContext:
    @classmethod
    def push(cls, channel="AC"):
        parent = _track_id_ctx.get()
        tid = f"{channel}-{uuid.uuid4().hex[:8]}"
        _track_id_ctx.set(tid)
        return tid, parent

    @classmethod
    def pop(cls):
        _track_id_ctx.set(None)

    @classmethod
    def current(cls, full=False):
        tid = _track_id_ctx.get()
        if full:
            return tid, getattr(cls, "_hud_id", None)
        return tid

def track(channel, state, *, priority="MED", note=None):
    tid, parent = TrackContext.push(channel)
    try:
        msg = [
            "[TRACK]", channel,
            f"| {state}",
            f"| ID={tid}",
            f"| PRIORITY={priority}"
        ]
        if parent:
            msg.append(f"| PARENT={parent}")
        if note:
            msg.append(f"| NOTE={note}")
        print(" ".join(msg), flush=True)
    finally:
        TrackContext.pop()

# ==========================================================
# CHANNEL ID GENERATOR
# ==========================================================

#class ChannelID(Enum):
#    ACTUATOR = "actuator"
#    FEED = "feed"
# generate a unique ID
#uid = ChannelID.next("E")  # -> "D.1"

# get registered metadata
#meta = ChannelID.get("ACTUATOR")
#print(meta)
# Output: {'controller': 'ACTUATOR', 'metadata': {'authority': 'SYSTEM'}}


# ==========================================================
# TRACK ID HELPER
# ==========================================================
def gen_track_id(prefix="ACTUATORENGINE", parent_id=None, origin="System") -> dict[str, str]:
    if parent_id is None:
        parent_id = TrackContext.get()
    return {
        "track_id": f"{prefix}-{str(uuid.uuid4())[:8]}",
        "parent_id": parent_id,
        "origin": origin
    }

# ==========================================================

# ==========================================================
# ACTUATOR FEED
# ==========================================================
class ActuatorFeed:
    def __init__(self):
        self.state = {k: 0.0 for k in
            ["EM_1","EM_2","Motor_Left","Motor_Right","Audio","LED"]
        }
        self.callbacks = []

    def update(self, **kwargs):
        self.state.update(kwargs)
        for cb in list(self.callbacks):
            try:
                cb(self.state)
                track("AC-FEED","CALLBACK_EXEC",priority="LOW",
                      note=f"channel_id={kwargs.get('_channel_id')}")
            except Exception as e:
                track("AC-FEED","CALLBACK_ERR",priority="HIGH",note=str(e))

    def register_callback(self, cb):
        if cb not in self.callbacks:
            self.callbacks.append(cb)
            track("AC-FEED","REGISTER_CB",priority="LOW",note=f"callback={cb.__name__}")

# ==========================================================
# ACTUATOR ENGINE
# ==========================================================
class ActuatorEngine:
    ACTUATOR_LIMITS = {k:(0.0,1.0) for k in
        ["EM_1","EM_2","Motor_Left","Motor_Right","Audio","LED"]
    }

    MAX_DELTA = 0.12
    MAX_POWER_BUDGET = 2.2
    BOOT_GRACE_PERIOD = 1.0
    AGENT_INTENT_TTL = 0.75
    REPLAY_BUFFER = 128

    # ------------------------------------------------------
    def __init__(self,
                 fat_layer=None,
                 hud_interface=None,
                 hardware_driver=None,
                 event_bus=None,
                 actuator_feed=None):

        track("AC-INIT","ENTER",priority="CRITICAL")

        self.fat_layer = fat_layer
        self.hud_interface = hud_interface
        self.hardware_driver = hardware_driver
        self.event_bus = event_bus
        self.actuator_feed = actuator_feed

        self._lock = threading.RLock()
        self._integration_lock = False

        self.channels = {k:0.0 for k in self.ACTUATOR_LIMITS}
        self._last_channels = deepcopy(self.channels)

        self.agent_inputs = {}
        self._received_any_input = False

        self._boot_time = time.time()
        self._last_update = time.time()

        self.replay_log = deque(maxlen=self.REPLAY_BUFFER)

        self._declare_presence()

        track("AC-INIT","COMPLETE",priority="CRITICAL")

    # ------------------------------------------------------
    def _declare_presence(self):
        if self.event_bus and not self._integration_lock:
            self._integration_lock = True
            self.event_bus.publish(
                "SYSTEM_COMPONENT_READY",
                payload={"component":"ActuatorEngine"},
                source="actuator_engine",
                channel="system",
                priority=10
            )
            track("AC-INIT","DECLARED",priority="CRITICAL")

    # ======================================================
    # SAFE ASYNC DISPATCH
    # ======================================================
    def _dispatch_async(self, coro):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(asyncio.create_task, coro)
            except Exception:
                track("AC-ASYNC","NO_LOOP",priority="LOW")

    # ======================================================
    # AGENT INPUT + ARBITRATION
    # ======================================================
    def submit_agent_intent(self, agent_id, intent, confidence=1.0):
        self.agent_inputs[agent_id] = (intent, confidence, time.time())
        self._received_any_input = True

    def _resolve_agent_intent(self):
        now = time.time()
        valid = {
            aid: data for aid, data in self.agent_inputs.items()
            if now - data[2] <= self.AGENT_INTENT_TTL
        }
        self.agent_inputs = valid

        if not valid:
            return "idle", 0.0

        total_conf = {}
        for intent, conf, _ in valid.values():
            total_conf.setdefault(intent, 0.0)
            total_conf[intent] += conf

        dominant = max(total_conf.items(), key=lambda x:x[1])
        return dominant[0], dominant[1]

    # ======================================================
    # INTENT → ACTUATOR MAP
    # ======================================================
    def map_intent(self, intent, resonance, confidence):
        target = {k:0.0 for k in self.channels}

        if intent == "idle":
            target["LED"] = 0.05
        elif intent == "observe":
            target["LED"] = 0.5
            target["EM_1"] = 0.2 * resonance
            target["EM_2"] = 0.2 * resonance
        elif intent == "explore":
            target["Motor_Left"] = 0.5 * resonance
            target["Motor_Right"] = 0.5 * resonance
            target["LED"] = 0.4
        elif intent == "focus":
            target["EM_1"] = 0.5 * resonance
            target["EM_2"] = 0.5 * resonance
        elif intent == "defensive":
            target["EM_1"] = 0.8 * resonance
            target["EM_2"] = 0.8 * resonance
            target["LED"] = 0.7

        for k in target:
            target[k] *= min(1.0, confidence)

        return target

    # ======================================================
    # PROCESS INTENT SCORES (TRACKED)
    # ======================================================
    def _process_intent_scores(self, scores):
        track("AC-INTENT","SCORES_PROCESSED",note=str(scores))
        # Optional: emit via event_bus
        if self.event_bus:
            self._dispatch_async(self._emit_qbit_bundle({"intent_scores": scores}))

    # ======================================================
    # MAIN UPDATE LOOP
    # ======================================================
    def update(self, *args, intent_scores=None, dominant_intent=None, resonance=0.5, **kwargs):
        with self._lock:
            self._last_update = time.time()

            if intent_scores is not None:
                self._process_intent_scores(intent_scores)

            if (not self._received_any_input and
                time.time() - self._boot_time < self.BOOT_GRACE_PERIOD):
                return deepcopy(self.channels)

            if not dominant_intent:
                dominant_intent, confidence = self._resolve_agent_intent()
            else:
                confidence = 1.0

            target = self.map_intent(dominant_intent, resonance, confidence)

            total_power = sum(target.values())
            if total_power > self.MAX_POWER_BUDGET:
                scale = self.MAX_POWER_BUDGET / total_power
                for k in target:
                    target[k] *= scale

            for k, v in target.items():
                lo, hi = self.ACTUATOR_LIMITS[k]
                prev = self._last_channels[k]
                delta = v - prev
                if abs(delta) > self.MAX_DELTA:
                    v = prev + self.MAX_DELTA * (1 if delta > 0 else -1)
                self.channels[k] = max(lo, min(v, hi))

            self._last_channels = deepcopy(self.channels)

            snapshot = {
                "intent": dominant_intent,
                "confidence": confidence,
                "channels": deepcopy(self.channels),
                "timestamp": time.time()
            }
            self.replay_log.append(snapshot)

            if self.actuator_feed:
                self.actuator_feed.update(
                    **self.channels,
                    _channel_id=ChannelID.next("S")
                )

            self._dispatch_async(self._emit_qbit_bundle(snapshot))

            track("AC-UPDATE","EXECUTED",note=dominant_intent)
            return deepcopy(self.channels)

    # ======================================================
    # QBIT 3-BUNDLE EMIT
    # ======================================================
    async def _emit_qbit_bundle(self, snapshot):
        if not self.event_bus:
            return
        try:
            for idx, channel in enumerate(("qbit","qbit.secondary","qbit.telemetry")):
                self.event_bus.publish(
                    "ACTUATOR_UPDATE",
                    payload={**snapshot,"bundle_index":idx,"iso_time":datetime.now().isoformat()},
                    source="actuator_engine",
                    channel=channel,
                    priority=5
                )
            track("AC-QBIT","BUNDLE_SENT",note=snapshot.get("intent","N/A"))
        except Exception as e:
            track("AC-QBIT","ERROR",priority="HIGH",note=str(e))

    # ======================================================
    # DETERMINISTIC REPLAY
    # ======================================================
    def replay(self, steps=10):
        with self._lock:
            return list(self.replay_log)[-steps:]

# ==========================================================
# QIA LOOP (MODULE-LEVEL, IMPORTABLE)
# ==========================================================
def qia_loop_safe(actuator, intent_engine, resonance_source, update_interval=0.05):
    last_cycle = time.time()
    while True:
        try:
            now = time.time()
            if now - last_cycle < update_interval:
                time.sleep(0.005)
                continue
            last_cycle = now

            dominant_intent, intent_scores, intent_channel = "idle", {}, None
            if intent_engine and hasattr(intent_engine, "score_intents"):
                dominant_intent, intent_scores, intent_channel = intent_engine.score_intents(
                    resonance_value=resonance_source(),
                    inputs=getattr(intent_engine, "latest_inputs", {})
                )

            actuator.update(
                dominant_intent=dominant_intent,
                resonance=resonance_source()
            )
            track("AC-QIA", "CYCLE_COMPLETE", priority="LOW", note=f"{dominant_intent}")
        except Exception as e:
            track("AC-QIA", "ERROR", priority="HIGH", note=str(e))
        time.sleep(update_interval)

def start_actuator_qia_loop(actuator, intent_engine, resonance_source):
    threading.Thread(
        target=qia_loop_safe,
        args=(actuator, intent_engine, resonance_source),
        daemon=True
    ).start()

# ==========================================================
# MODULE EXPORTS
# ==========================================================
__all__ = [
    "ActuatorEngine",
    "ActuatorFeed",
    "qia_loop_safe",
    "start_actuator_qia_loop",
    "ChannelID",
    "track",
    "TrackContext"
]

# ==========================================================
# END OF FILE
# ==========================================================
