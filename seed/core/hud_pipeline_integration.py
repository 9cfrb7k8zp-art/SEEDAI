# ==========================================================
# FILE: hud_pipeline_integration.py
# HUDPipelineIntegration v40
# Fully integrated with ChannelID system, HPI agent subclasses
# ==========================================================

import asyncio
import logging
import time
import os
import json
from copy import deepcopy
from queue import PriorityQueue
from itertools import count
import threading
from datetime import datetime
from pathlib import Path
from collections import deque

from seed.core.device_manager import DeviceManager
# from seed.core.modem_controller import modem_controller   # User Side Netwok, access , IoT, connections - 'U' - channel
from seed.core.SEEDModemController import SEEDModemController   # SEED AI Side, access , IoT, connections - 'S' - channel
from seed.core.hud_master_overlay import HUDMasterOverlay
from seed.ui.hud_master_gui import HUDMasterGUI
from seed.core.seed_camera_qbit import SEEDCameraQbit
from seed.core.qbit_dialer import QbitDialer
from seed.skills.sparkplug import SparkPlug
from seed.core.actuator_engine import ActuatorEngine
from seed.core.integration.CoreActuatorBridgeIntegrated import SEEDCoreActuatorBridge
from seed.core.event_bus import SEEDEventBus
from seed.core.channel_id import ChannelID

# Limp Mode Integration
try:
    from seed.core.limp_mode import LimpModeController
    limp_controller = LimpModeController(recovery_interval=10)
except Exception as e:
    limp_controller = None
    print(f"[LIMP MODE] Initialization failed: {e}")

logger = logging.getLogger("HUDPipelineIntegration")
logging.basicConfig(level=logging.INFO)

# ===============================
# Quantum Signal Mapper
# ===============================
SYSTEM_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = SYSTEM_ROOT / "modules"
SCRIPT_PATH = SYSTEM_ROOT / "scripts"
SCAN_LOG = SYSTEM_ROOT / "logs" / "signal_mapper_log.json"

class QuantumSignalMapper:
    def __init__(self):
        self.system_map = {
            "timestamp": str(datetime.now()),
            "modules": [],
            "scripts": [],
            "unknown_files": [],
        }

    def scan_directory(self, path, tag):
        results = []
        for root, _, files in os.walk(path):
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, SYSTEM_ROOT)
                    results.append(rel_path)
        self.system_map[tag] = results

    def run_scan(self):
        self.scan_directory(MODULE_PATH, "modules")
        self.scan_directory(SCRIPT_PATH, "scripts")
        # Detect unknown files
        all_files = set()
        for dirpath, _, filenames in os.walk(SYSTEM_ROOT):
            for file in filenames:
                if file.endswith(".py") and not file.startswith("__"):
                    rel = os.path.relpath(os.path.join(dirpath, file), SYSTEM_ROOT)
                    all_files.add(rel)
        known = set(self.system_map["modules"] + self.system_map["scripts"])
        unknown = list(all_files - known)
        self.system_map["unknown_files"] = unknown

    def export_results(self):
        os.makedirs(os.path.dirname(SCAN_LOG), exist_ok=True)
        with open(SCAN_LOG, "w") as log_file:
            json.dump(self.system_map, log_file, indent=2)

    def get_scan_map(self):
        return deepcopy(self.system_map)

# ===============================
# Safe SparkPlug Wrapper
# ===============================
class SafeSparkPlug:
    def __init__(self, sparkplug_instance, storage_root=None, event_bus=None, loop=None, max_retries=3):
        self._storage_root = storage_root
        self._event_bus = event_bus
        self._loop = loop or asyncio.new_event_loop()
        self.max_retries = max_retries
        self._pending_skills = {}  # track_id -> {skill_name, payload, retries, channel}
        if isinstance(sparkplug_instance, SparkPlug):
            self._instance = sparkplug_instance
        else:
            self._instance = self._create_instance()

    def _create_instance(self):
        try:
            instance = SparkPlug(skills_root=self._storage_root, event_bus=self._event_bus)
            if self._loop:
                instance._loop = self._loop
            return instance
        except Exception as e:
            if limp_controller:
                limp_controller.enter("SafeSparkPlug init failure", str(e))
            return None

    def submit_skill(self, skill_name, payload=None, priority=0.5, source="unknown", channel_marker="S", track_id=None, parent_id=None):
        if track_id is None:
            track_id = generate_track_id(skill_name, channel_marker)

        if track_id in self._pending_skills:
            existing = self._pending_skills[track_id]
            if priority > existing["priority"]:
                existing["payload"] = payload
                existing["priority"] = priority
            return track_id

        self._pending_skills[track_id] = {
            "skill_name": skill_name,
            "payload": payload,
            "priority": priority,
            "source": source,
            "retries": 0,
            "channel_marker": channel_marker,
            "parent_id": parent_id
        }

        if self._instance:
            asyncio.run_coroutine_threadsafe(
                self._submit_with_retry(track_id),
                self._loop
            )
        return track_id

    async def _submit_with_retry(self, track_id):
        skill_entry = self._pending_skills.get(track_id)
        if not skill_entry:
            return

        try:
            td_payload = TrackedData(
                payload=skill_entry["payload"],
                source_id=skill_entry["source"],
                channel=skill_entry["channel_marker"],
                track_id=track_id,
                parent_id=skill_entry.get("parent_id"),
                priority=skill_entry["priority"]
            )
            await asyncio.to_thread(
                self._instance.submit_skill,
                skill_name=skill_entry["skill_name"],
                payload=td_payload,
                priority=skill_entry["priority"],
                source=skill_entry["source"],
                channel_marker=skill_entry["channel_marker"]
            )
            self._pending_skills.pop(track_id, None)
        except Exception as e:
            skill_entry["retries"] += 1
            if skill_entry["retries"] <= self.max_retries:
                logger.warning(f"[SafeSparkPlug] Retry {skill_entry['retries']} for {track_id}")
                await asyncio.sleep(0.2)
                await self._submit_with_retry(track_id)
            else:
                logger.error(f"[SafeSparkPlug] Failed to submit skill {track_id} after {self.max_retries} retries")
                if limp_controller:
                    limp_controller.enter("Skill submission failed", track_id)
                self._pending_skills.pop(track_id, None)

    def __getattr__(self, item):
        if self._instance and hasattr(self._instance, item):
            return getattr(self._instance, item)
        else:
            return lambda *a, **k: None

# ===============================
# HUDPipelineIntegration v40
# ===============================
class HUDPipelineIntegration:
    def __init__(self,
                 hud_overlay=False,
                 seed_core=None,
                 analytics_engine=None,
                 nlp_interface=None,
                 agent_manager=None,
                 storage_root=None,
                 event_bus=None,
                 fat_layer=None,
                 loop=None,
                 camera_hud_push_interval=0.1,
                 high_priority_threshold=100.0,
                 inject_mock_frame=False,
                 mock_frame_timeout=5.0,
                 actuator_engine=None,
                 sparkplug=SparkPlug,
                 dual_feed=True,
                 bus=True,
                 smoothing_window=5):

        self.hud_overlay = hud_overlay
        self.seed_core = seed_core
        self.analytics_engine = analytics_engine
        self.nlp_interface = nlp_interface
        self.agent_manager = agent_manager
        self.storage_root = storage_root
        self.event_bus = event_bus
        self.fat_layer = fat_layer
        self.inject_mock_frame = inject_mock_frame
        self.mock_frame_timeout = float(mock_frame_timeout)
        self.camera_hud_push_interval = camera_hud_push_interval
        self.high_priority_threshold = high_priority_threshold
        self.dual_feed = dual_feed
        self.bus = SEEDEventBus(debug=True)
        self.smoothing_window = smoothing_window
        self.qbit_history = deque(maxlen=smoothing_window)

        try:
            self.loop = loop or asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self._counter = count()
        self.us_queue = PriorityQueue()
        self.sa_queue = PriorityQueue()
        self._lock = threading.Lock()
        self._running = True
        self._tasks = []
        self.user_data_queue = PriorityQueue()
        self.seedai_data_queue = PriorityQueue()
        self._initialized = False
        self.skill_chain_map = {"light_scan_skill": ["light_scan_skill","log_light_event","notify_operator"]}
        self._first_frame_event = asyncio.Event()

        # -----------------------------
        # Actuator and SafeSparkPlug
        # -----------------------------
        skills_path = f"{storage_root}/seed/skills" if storage_root else None
        raw_sp = sparkplug(skills_root=skills_path, event_bus=event_bus) if callable(sparkplug) else sparkplug
        self.sparkplug = SafeSparkPlug(raw_sp, storage_root=storage_root, event_bus=event_bus, loop=self.loop)
        self.actuator_engine = actuator_engine or ActuatorEngine(fat_layer=fat_layer, hud_interface=hud_overlay)

        # -----------------------------
        # QuantumSignalMapper
        # -----------------------------
        self.quantum_mapper = QuantumSignalMapper()
        self.quantum_mapper.run_scan()
        scan_map = self.quantum_mapper.get_scan_map()
        if self.event_bus and hasattr(self, "sparkplug"):
            for unknown_file in scan_map.get("unknown_files", []):
                payload = {"file": unknown_file, "qbit": None}
                self.sparkplug.submit_skill(skill_name="integrate_unknown_module", payload=payload,
                                            priority=0.6, source="quantum_mapper")

        # -----------------------------
        # Device / HUD / Camera
        # -----------------------------
        self.device_manager = DeviceManager(event_bus=event_bus)
        self.modem = SEEDModemController(event_bus=event_bus)
        self.hud_gui = HUDMasterGUI(hud_overlay)
        self.qbit_dialer = QbitDialer(storage_root=storage_root, event_bus=event_bus)
        self.camera_qbit = SEEDCameraQbit(qbit_dialer=self.qbit_dialer, event_bus=event_bus, hud_overlay=hud_overlay, fat_layer=fat_layer)
        self.camera_qbit.set_hud_push_interval(camera_hud_push_interval)
        self.camera_qbit.add_qbit_callback(self._on_qbit_received)
        try:
            self.camera_qbit.start()
        except Exception as e:
            logger.warning(f"[HUDPipeline] camera_qbit start failed: {e}")
            if limp_controller:
                limp_controller.enter("camera_qbit start failed", str(e))

        # Actuator bridge
        self.seed_actuator_bridge = SEEDCoreActuatorBridge(seed_core=seed_core, actuator=self.actuator_engine, update_interval=0.05)
        try:
            self._bridge_task = self.loop.create_task(self.seed_actuator_bridge.run_loop())
        except RuntimeError:
            self._bridge_task = None

        # Tasks
        self._tasks.append(self.loop.create_task(self._hud_loop()))
        self._tasks.append(self.loop.create_task(self._agent_loop()))
        try:
            self.loop.create_task(self._ensure_first_frame())
        except Exception:
            def _deferred_ensure():
                try:
                    asyncio.run(self._ensure_first_frame())
                except Exception:
                    pass
            threading.Thread(target=_deferred_ensure, daemon=True).start()

        logger.info("[HUDPipeline] v40 initialized — ChannelID + HPI agent subclass fully integrated")

    # ===============================
    # Priority-safe queue insertion
    # ===============================
    def _queue_put(self, queue: PriorityQueue, priority: float, item: dict, channel_marker="HUD"):
        if not isinstance(item, TrackedData):
            track_id = generate_track_id("hud_data", channel_marker)
            item = TrackedData(payload=item, track_id=track_id)
        queue.put((priority, next(self._counter), item))

    # ===============================
    # Qbit callback with smoothing
    # ===============================
    def _on_qbit_received(self, qbit_data):
        if not qbit_data:
            return
        if not self._first_frame_event.is_set():
            self.loop.call_soon_threadsafe(self._first_frame_event.set)

        avg_intensity = qbit_data.get("light_qbit", {}).get("avg_intensity", qbit_data.get("value", 0.0))
        motion_level = qbit_data.get("light_qbit", {}).get("motion_level", 0.0)
        self.qbit_history.append((avg_intensity, motion_level))
        smoothed_intensity = sum(i for i,_ in self.qbit_history)/len(self.qbit_history)
        smoothed_motion = sum(m for _,m in self.qbit_history)/len(self.qbit_history)
        high_priority = smoothed_intensity >= self.high_priority_threshold or smoothed_motion >= self.high_priority_threshold

        entry = {"timestamp": time.time(), "source": "camera_qbit", "data": deepcopy(qbit_data),
                 "smoothed_intensity": smoothed_intensity, "smoothed_motion": smoothed_motion}

        try:
            td_entry = TrackedData(payload=entry, track_id=generate_track_id("hud_qbit_data", "HUD"))
            self._queue_put(self.us_queue, 10, td_entry)
            if self.dual_feed and high_priority:
                self._queue_put(self.sa_queue, 0, td_entry)
                self._trigger_skill_chain("light_scan_skill", qbit_data)
                if hasattr(self, "seed_actuator_bridge") and self.seed_actuator_bridge:
                    try:
                        self.seed_actuator_bridge.submit_intent(qbit_data)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"[HUDPipeline] Qbit callback queue failed: {e}")
            if limp_controller:
                limp_controller.enter("Qbit callback failure")

        if self.actuator_engine:
            light_data = {"avg_intensity": avg_intensity, "motion_level": motion_level,
                          "camera_id": qbit_data.get("camera_id", "CAM_UNKNOWN"),
                          "timestamp": qbit_data.get("timestamp", time.time()), "raw": deepcopy(qbit_data)}
            try:
                self.actuator_engine.submit_light_scan(light_data)
            except Exception:
                if limp_controller:
                    limp_controller.enter("Actuator submit_light_scan failure")

    # ===============================
    # SparkPlug skill chain
    # ===============================
    def _trigger_skill_chain(self, start_skill, payload):
        chain = self.skill_chain_map.get(start_skill, [start_skill])
        for skill_name in chain:
            try:
                track_id = generate_track_id(skill_name, "HUD")
                self.sparkplug.submit_skill(skill_name=skill_name, payload=deepcopy(payload),
                                            priority=0.7, source="hud_pipeline", track_id=track_id)
            except Exception as e:
                logger.warning(f"[HUDPipeline] Skill queue failed: {skill_name} — {e}")
                if limp_controller:
                    limp_controller.enter("SparkPlug skill submission failure")

    # ===============================
    # HUD loop
    # ===============================
    async def _hud_loop(self):
        while True:
            try:
                while not self.us_queue.empty():
                    _, _, entry = self.us_queue.get()
                    entry_data = entry.payload if isinstance(entry, TrackedData) else entry
                    try:
                        if self.hud_overlay:
                            self.hud_overlay.update(entry_data)
                    except Exception:
                        logger.debug("[HUDPipeline] HUD update failed")
            except Exception:
                logger.exception("[HUDPipeline] HUD loop failure")
                if limp_controller:
                    limp_controller.enter("HUD loop failure")
            await asyncio.sleep(0.01)

    # ===============================
    # Agent loop with HPI agent subclasses
    # ===============================
    async def _agent_loop(self):
        while True:
            try:
                while not self.sa_queue.empty():
                    _, _, entry = self.sa_queue.get()
                    data = getattr(entry, "payload", entry) if isinstance(entry, TrackedData) else entry

                    if self.analytics_engine:
                        try:
                            self.analytics_engine.update_problem_metrics(f"seedai_{int(time.time()*1000)}", "observed")
                        except Exception:
                            pass

                    if self.agent_manager:
                        try:
                            # Assign HPI agent subclasses dynamically
                            for i in range(1, 4):  # AgM-1, AgM-2, AgM-3
                                agent_track_id = generate_hpi_agent_track("agent_decision", agent_index=i)
                                decisions = self.agent_manager._process_decisions(data)
                                for action in decisions:
                                    action["track_id"] = agent_track_id
                                    execute_fn = getattr(self.agent_manager, "execute_action", None) \
                                                 or getattr(self.agent_manager, "_execute_action_damped", None)
                                    if asyncio.iscoroutinefunction(execute_fn):
                                        await execute_fn(action)
                                    else:
                                        await asyncio.to_thread(execute_fn, action)
                        except Exception:
                            logger.debug("[HUDPipeline] Agent manager processing failed")
            except Exception:
                logger.exception("[HUDPipeline] Agent loop failure")
                if limp_controller:
                    limp_controller.enter("Agent loop failure")
            await asyncio.sleep(0.01)

    # ===============================
    # First frame gating
    # ===============================
    async def _ensure_first_frame(self):
        try:
            await asyncio.wait_for(self._first_frame_event.wait(), timeout=self.mock_frame_timeout)
        except asyncio.TimeoutError:
            logger.warning("[HUDPipeline] First frame timeout")
            if limp_controller:
                limp_controller.enter("First frame timeout")

    # ===============================
    # Shutdown
    # ===============================
    def stop(self):
        for task in self._tasks:
            task.cancel()
        if hasattr(self, "_bridge_task") and self._bridge_task:
            self._bridge_task.cancel()
        if hasattr(self.camera_qbit, "stop"):
            self.camera_qbit.stop()
        logger.info("[HUDPipeline] Shutdown complete")
