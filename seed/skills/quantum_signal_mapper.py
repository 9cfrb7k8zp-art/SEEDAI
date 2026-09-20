# ==========================================================
# FILE: quantum_signal_mapper.py
# PATH: SEED_ROOT/seed/core/skills/quantum_signal_mapper.py
# MODULE: Quantum Signal Mapper – Runtime-Wired System Awareness
# VERSION: 1.7.6 (SEEDRuntime Wired / Autonomous)
# UPDATED: 2026-01-10
# ==========================================================

import os
import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
import uuid
import threading


# -----------------------------
# Logger
# -----------------------------
logger = logging.getLogger("QuantumSignalMapper")
logging.basicConfig(level=logging.INFO)


# -----------------------------
# SEED ROOT DETECTION
# -----------------------------
def get_seed_root():
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        if (parent / "seed").exists():
            return parent
    return current_path.parent


SYSTEM_ROOT = get_seed_root()
MODULE_PATH = SYSTEM_ROOT / "seed" / "core"
SCRIPT_PATH = SYSTEM_ROOT / "seed" / "core" / "skills"
SCAN_LOG = SYSTEM_ROOT / "logs" / "signal_mapper_log.json"


# -----------------------------
# Track ID Generator
# -----------------------------
def gen_track_id(prefix="QSM"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ==========================================================
# Quantum Signal Mapper (Runtime-Wired)
# ==========================================================
class QuantumSignalMapper:
    CHANNELS = ("modules", "scripts", "unknown_files")

    def __init__(
        self,
        *,
        emit=None,
        track=None,
        task=None,
        qbit=None,
        runtime=None,
        sparkplug=None,
        qbit_dialer=None,
        event_bus=None,
        hud_pipeline=None,
        track_system=None,
        channel_id=None,
        **kwargs
    ):
        from seed.core.dialers.qbit_dialer import QbitDialer
        from seed.skills.sparkplug import SparkPlug

        from seed.core.event_bus import SEEDEventBus
        from seed.core.channel_id import ChannelID
        from seed.core.track_system import TrackSystem, TrackedData

        # --- Core bindings ---
        self.runtime = runtime
        self.sparkplug = sparkplug
        self.qbit_dialer = qbit_dialer
        self.event_bus = event_bus
        self.hud_pipeline = hud_pipeline
        self.track_system = TrackSystem
        self.channel_id = channel_id
        self.track = track
        self.emit = emit
        self.task = task
        self.qbit = qbit

        # --- Runtime inheritence ---
        if runtime:
            self.event_bus = self.event_bus or getattr(runtime, "event_bus", None)
            self.qbit_dialer = self.qbit_dialer or getattr(runtime, "qbit_dialer", None)

        # --- State ---
        self.system_map = {
            "timestamp": None,
            "modules": [],
            "scripts": [],
            "unknown_files": [],
            "qbit_seeds": {},
            "registered_skills": {},
            "permissions": {},
            "hud_channels": {},
            "runtime_node": getattr(runtime, "node_id", None),
        }

        self._system_ready = False
        self._paused = False
        self._lock = threading.RLock()

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        logger.info("[QSM] Initialized (runtime-wired=%s)", bool(runtime))


    # ------------------------------------------------------
    # Runtime Control
    # ------------------------------------------------------
    def set_system_ready(self, ready: bool = True):
        self._system_ready = ready
        logger.info("[QSM] System readiness = %s", ready)

    def on_runtime_idle(self):
        logger.info("[QSM] Paused (runtime idle)")
        self._paused = True


    def on_runtime_wake(self):
        logger.info("[QSM] Resumed (runtime wake)")
        self._paused = False


    # ------------------------------------------------------
    # Directory Scan
    # ------------------------------------------------------
    def _scan_dir(self, path: Path):
        results = []
        if not path.exists():
            return results
        for root, _, files in os.walk(path):
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    full = Path(root) / f
                    results.append(str(full.relative_to(SYSTEM_ROOT)))
        return results


    # ------------------------------------------------------
    # HUD Channel Assignment
    # ------------------------------------------------------
    def _assign_hud_channels(self):
        for channel in self.CHANNELS:
            self.system_map["hud_channels"].setdefault(channel, {})
            for item in self.system_map[channel]:
                hud_id = f"HUD-{abs(hash(item)) % 10_000_000}"
                self.system_map["hud_channels"][channel][item] = hud_id
                self.track_system.register_channel(
                    item_id=item,
                    hud_id=hud_id,
                    source="QuantumSignalMapper",
                )


    # ------------------------------------------------------
    # Full Scan
    # ------------------------------------------------------
    def run_scan(self):
        with self._lock:
            self.system_map["timestamp"] = datetime.utcnow().isoformat()

            self.system_map["modules"] = self._scan_dir(MODULE_PATH)
            self.system_map["scripts"] = self._scan_dir(SCRIPT_PATH)

            if self._system_ready:
                all_files = set(self._scan_dir(SYSTEM_ROOT))
                known = set(self.system_map["modules"]) | set(self.system_map["scripts"])
                self.system_map["unknown_files"] = sorted(all_files - known)

            self._assign_hud_channels()


    # ------------------------------------------------------
    # Qbit + Skill Registration
    # ------------------------------------------------------
    def inject_qbit_and_register(self):
        with self._lock:
            for channel in self.CHANNELS:
                seed = abs(hash(f"{channel}-{time_now()}")) % 1_000_000
                self.system_map["qbit_seeds"][channel] = seed

                if self.qbit_dialer:
                    self.qbit_dialer.submit_skill(
                        skill_name="quantum_signal_map_seed",
                        payload={
                            "channel": channel,
                            "seed": seed,
                            "count": len(self.system_map[channel]),
                        },
                        priority=1.0,
                        source="QSM",
                    )

                for file_path in self.system_map[channel]:
                    skill = Path(file_path).stem
                    track_id = gen_track_id(skill)
                    self.system_map["registered_skills"][track_id] = file_path
                    self.system_map["permissions"][skill] = (
                        "QSM-ADMIN" if "core" in file_path else "QSM-USER"
                    )


    # ------------------------------------------------------
    # Unknown Module Escalation
    # ------------------------------------------------------
    def submit_unknown_modules(self):
        if not self._system_ready or not self.sparkplug:
            return

        for file in self.system_map.get("unknown_files", []):
            self.sparkplug.submit_skill(
                skill_name="integrate_unknown_module",
                payload={
                    "file": file,
                    "hud": self.system_map["hud_channels"]["unknown_files"].get(file),
                    "node": self.system_map["runtime_node"],
                },
                priority=0.7,
                source="QuantumSignalMapper",
            )


    # ------------------------------------------------------
    # Runtime Watch Loop
    # ------------------------------------------------------
    async def watch(self, interval=5.0):
        logger.info("[QSM] Live watch loop started")
        while True:
            self.run_scan()
            self.inject_qbit_and_register()
            self.submit_unknown_modules()

            if self.event_bus:
                self.event_bus.emit(
                    "quantum.signal.map.updated",
                    payload=self.system_map,
                )
            if not self._system_ready or self._paused:
                await asyncio.sleep(1.0)
                continue

            try:
                await self._scan_and_emit()
            except Exception as e:
                logger.exception("[QSM] Scan error: %s", e)

            await asyncio.sleep(interval)


    async def _scan_and_emit(self):
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "node": self.runtime.node_id,
        }

        if self.qbit_dialer:
            self.qbit_dialer.submit_skill(
                skill_name="quantum_signal_mapper_tick",
                payload=payload,
                priority=0.1,
                source="QSM",
            )

        if self.event_bus:
            self.event_bus.emit("qsm.tick", payload)

    # ------------------------------------------------------
    # Export
    # ------------------------------------------------------
    def export(self):
        SCAN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SCAN_LOG, "w") as f:
            json.dump(self.system_map, f, indent=2)


# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------
def time_now():
    return datetime.utcnow().isoformat()
