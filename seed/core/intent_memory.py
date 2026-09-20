# ==========================================================
# FILE: intent_memory.py
# PATH: SEED_ROOT/seed/core/intent_memory.py
# INTENT MEMORY – Level 2 Persistence + Decay Layer
# VERSION: 2.5 (Python 3.12-safe + Async + TimeTravel Fixed)
# UPDATED: 2026-01-06
# ==========================================================

import time
from typing import Dict, Any, List, Callable
import logging
import asyncio
import json
from collections import defaultdict, deque
from pathlib import Path
from seed.core.time_travel_engine import TimeTravelEngine

# from seed.core.qbit_dialer import QbitDialer  # Emit source - path 

logger = logging.getLogger("IntentMemory")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)

try:
    from seed.core.track_id_manager import TrackIDManager
except ImportError:
    TrackIDManager = None


class IntentMemory:
    def __init__(
        self,
        emit,
        orchestrator_command=None,
        storage_root="/SEED_ROOT",
        event_bus=None,
        qbit_dialer=None,
        command=True,
        time_travel_engine=None,
        memory_window=5.0,
        decay_rate=0.85,
        max_records=64,
        auto_decay_interval=0.5,
        snapshot_interval=10.0,
        snapshot_path="intent_memory_snapshot.json",
        **kwargs
    ):
        from seed.core.event_bus import SEEDEventBus
        if command is None:
            raise ValueError("[IntentMemory] Cannot initialize without QbitDialer.command")

        self.emit = emit
        self.event_bus = event_bus
        self.command = qbit_dialer
        self.orchestrator_command = orchestrator_command
        self.qbit_dialer = qbit_dialer
        self.memory_window = memory_window
        self.decay_rate = decay_rate
        self.max_records = max_records
        self.auto_decay_interval = auto_decay_interval
        self.snapshot_interval = snapshot_interval
        self.snapshot_path = Path(snapshot_path)
        self.event_log = []
        self._emit_history = [] 

        # ==========================================================
        # TIME TRAVEL ENGINE
        # ==========================================================
        # Use an injected engine when provided.
        # Otherwise create exactly one engine for this IntentMemory.
        # Never call methods on a None engine.

        if time_travel_engine is None:
            self.time_travel_engine = TimeTravelEngine(
                dialer=self.qbit_dialer,
                event_bus=self.event_bus,
                enable_hardware=False,
                emit=self.emit,
            )
        elif isinstance(time_travel_engine, type):
            # Constructor/class supplied instead of an instance.
            # Instantiate it using the known SEED dependencies.
            self.time_travel_engine = time_travel_engine(
                dialer=self.qbit_dialer,
                event_bus=self.event_bus,
                enable_hardware=False,
                emit=self.emit,
            )
        else:
            self.time_travel_engine = time_travel_engine

        # ----------------------------------------------------------
        # Record command metadata only.
        # Never deepcopy the live Qbit/async/event objects.
        # ----------------------------------------------------------
        if self.time_travel_engine is not None:
            self.time_travel_engine.record(
                event_type="ACTUATOR_COMMAND",
                payload={
                    "type": "command_ref",
                    "class": (
                        type(self.command).__name__
                        if self.command is not None
                        else None
                    ),
                    "methods": [
                        m
                        for m in dir(self.command)
                        if (
                            self.command is not None
                            and callable(getattr(self.command, m, None))
                            and not m.startswith("_")
                        )
                    ],
                },
            )

            # Relay only when the engine exposes relay().
            relay = getattr(self.time_travel_engine, "relay", None)
            if callable(relay):
                relay(self.command)
            else:
                logger.debug(
                    "[IntentMemory] TimeTravelEngine has no relay(); "
                    "command relay skipped."
                )
        # Memory structures
        self._memory = defaultdict(lambda: deque(maxlen=max_records))
        self._qbit_state = defaultdict(lambda: 0.0)
        self._priority_state = defaultdict(lambda: 0.0)
        self._lock = asyncio.Lock()
        self._intents = []

        # Event loop handling
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        # Start background tasks
#        self._decay_task = self.loop.create_task(self._auto_decay_loop())
#        self._snapshot_task = self.loop.create_task(self._auto_snapshot_loop())

        logger.info("[IntentMemory] Initialized with command reference and TimeTravel logged.")

# ---------------------------------------------------------------------

    def ingest(self, intent_data=[]):
        # Add timestamp if missing
        if "timestamp" not in intent_data:
            intent_data["timestamp"] = time.time()

        self._intents.append(intent_data)

        # Sync-safe: forward to QbitDialer if available
        if self.qbit_dialer:
            try:
                command = intent_data.get("intent")
                device = intent_data.get("device")
                if command and device:
                    self.qbit_dialer.send_command(command, device)
            except Exception as e:
                # Avoid crashing if QbitDialer fails
                print(f"[IntentMemory] QbitDialer send_command failed: {e}", flush=True)

    def get_all_intents(self) -> List[Dict[str, Any]]:
        return list(self._intents)

    def clear_intents(self):
        self._intents.clear()

    # method - use command
    def execute_action(self, action_name, *args, **kwargs):
        if hasattr(self.command, "execute"):
            return self.command.execute(action_name, *args, **kwargs)
        else:
            raise RuntimeError("[IntentMemory] Command object cannot execute actions.")

    # ... rest of your methods (_emit_state, ingest, prune, auto_decay_loop, etc.) remain unchanged ...


# ===============================================================================

    # top-level import
    # from seed.core.qbit_dialer import QbitDialer  # <- No - circular imports

    # ----  inside-method  ----
    def some_method_using_qbit():
        from seed.core.qbit_dialer import QbitDialer
        # now you can safely use QbitDialer here


    # --------------------------------------------------
    # EXECUTE ACTION VIA COMMAND
    # --------------------------------------------------
    def execute_action(self, action_name, *args, **kwargs):
        if hasattr(self.command, "execute"):
            return self.command.execute(action_name, *args, **kwargs)
        else:
            raise RuntimeError("[IntentMemory] Command object cannot execute actions.")

    # --------------------------------------------------
    # INGEST INTENT
    # --------------------------------------------------
    def ingest(self, intent_packet):
        try:
            intent_name = intent_packet.get("intent")
            if not intent_name:
                return
            ts = intent_packet.get("timestamp", time.time())
            track_id = self._generate_track_id(intent_name)

            record = {
                "intent": intent_name,
                "camera": intent_packet.get("camera"),
                "confidence": float(intent_packet.get("confidence", 0.0)),
                "magnitude": intent_packet.get("magnitude"),
                "direction": intent_packet.get("direction"),
                "qbit": float(intent_packet.get("qbit", 0.0)),
                "timestamp": ts,
                "track_id": track_id,
            }

            self._memory[intent_name].append(record)
            self._qbit_state[intent_name] = record["qbit"]
            self._priority_state[intent_name] = self._compute_priority(intent_name, track_id)

            asyncio.run_coroutine_threadsafe(self._emit_state(intent_name, track_id), self.loop)

        except Exception as e:
            logger.warning(f"[IntentMemory] ingest failed: {e}")

    # --------------------------------------------------
    # COMPUTE PRIORITY
    # --------------------------------------------------
    def _compute_priority(self, intent_name, track_id=None):
        now = time.time()
        records = self._memory.get(intent_name, [])
        if not records:
            return 0.0
        weighted_sum = total_weight = 0.0
        for r in reversed(records):
            age = now - r["timestamp"]
            if age > self.memory_window:
                continue
            weight = self.decay_rate ** age
            score = r["confidence"] * (0.5 + 0.5 * r["qbit"])
            weighted_sum += score * weight
            total_weight += weight
        return round(weighted_sum / total_weight, 4) if total_weight else 0.0

    # --------------------------------------------------
    # EMIT CURRENT STATE
    # --------------------------------------------------
    async def _emit_state(self, intent_name, track_id=None):
        async with self._lock:
            records = self._memory.get(intent_name, [])
            if not records:
                return
            latest = records[-1]
            state_packet = {
                "intent": intent_name,
                "confidence": round(latest["confidence"], 4),
                "camera": latest.get("camera"),
                "direction": latest.get("direction"),
                "qbit": latest.get("qbit", 0.0),
                "priority": self._priority_state.get(intent_name, 0.0),
                "timestamp": time.time(),
                "track_id": track_id or latest.get("track_id"),
            }
            logger.info(
                f"[IntentState] {intent_name} conf={state_packet['confidence']:.2f} "
                f"qbit={state_packet['qbit']:.2f} priority={state_packet['priority']:.2f} "
                f"TrackID={state_packet['track_id']}"
            )
            # EventBus emit
            if self.event_bus:
                try:
                    self.event_bus.emit("INTENT_STATE", data=state_packet)
                except Exception as e:
                    logger.warning(f"[IntentMemory] Event emit failed: {e}")
            # Qbit reporting
            if self.qbit_dialer:
                try:
                    self.qbit_dialer.submit_track(state_packet["track_id"])
                except Exception as e:
                    logger.warning(f"[IntentMemory] Qbit submit failed: {e}")

    # --------------------------------------------------
    # QUERY API
    # --------------------------------------------------
    def get_state(self, intent_name):
        records = self._memory.get(intent_name)
        if not records:
            return None
        return {**records[-1], "priority": self._priority_state.get(intent_name, 0.0)}

    def get_all_states(self):
        return {
            intent: {
                "latest": self._memory[intent][-1] if self._memory[intent] else None,
                "priority": self._priority_state.get(intent, 0.0),
                "qbit": self._qbit_state.get(intent, 0.0),
            }
            for intent in self._memory.keys()
        }

    # --------------------------------------------------
    # PRUNING
    # --------------------------------------------------
    def prune(self):
        now = time.time()
        for intent_name, records in list(self._memory.items()):
            while records and (now - records[0]["timestamp"]) > self.memory_window:
                records.popleft()
            self._priority_state[intent_name] = self._compute_priority(intent_name)

    # --------------------------------------------------
    # AUTO-DECAY LOOP
    # --------------------------------------------------
    async def _auto_decay_loop(self):
        try:
            while True:
                self.prune()
                await asyncio.sleep(self.auto_decay_interval)
        except asyncio.CancelledError:
            logger.info("[IntentMemory] Auto-decay loop stopped")

    # --------------------------------------------------
    # AUTO-SNAPSHOT LOOP
    # --------------------------------------------------
    async def _auto_snapshot_loop(self):
        try:
            while True:
                try:
                    snapshot_data = {intent: list(self._memory[intent]) for intent in self._memory.keys()}
                    tmp_path = self.snapshot_path.with_suffix(".tmp")
                    tmp_path.write_text(json.dumps(snapshot_data, indent=2))
                    tmp_path.replace(self.snapshot_path)
                    logger.info(f"[IntentMemory] Snapshot saved ({self.snapshot_path})")
                except Exception as e:
                    logger.warning(f"[IntentMemory] Snapshot save failed: {e}")
                await asyncio.sleep(self.snapshot_interval)
        except asyncio.CancelledError:
            logger.info("[IntentMemory] Auto-snapshot loop stopped")

    # --------------------------------------------------
    # TRACK ID GENERATOR
    # --------------------------------------------------
    def _generate_track_id(self, prefix="INTENT"):
        if TrackIDManager:
            return TrackIDManager.generate(channel_marker=prefix)
        import uuid
        return f"{prefix}-{str(uuid.uuid4())[:8]}"

    # --------------------------------------------------
    # CLEANUP / SHUTDOWN
    # --------------------------------------------------
    async def shutdown(self):
        tasks = [self._decay_task, self._snapshot_task]
        for t in tasks:
            if t:
                t.cancel()
        for t in tasks:
            if t:
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        logger.info("[IntentMemory] Shutdown complete")
