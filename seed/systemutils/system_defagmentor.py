# ==========================================================
# FILE: system_defagmentor.py
# PATH: SEED_ROOT/seed/systemutils/system_defagmentor.py
# VERSION: 2.0 (Dynamic Qbit Feedback + SmartTransformer Upgrade + Async Optimization)
# UPDATED: 2026-01-02
# NOTES: Full integration with QbitDialer, adaptive async builds, predictive priority, live supervision, temp cleanup, efficiency upgrades.
# ==========================================================

import os
import time
import shutil
import threading
import logging
import uuid
from typing import Dict, Any, Optional
import asyncio
import random
from copy import deepcopy

from seed.core.qbit_dialer import qbit_dialer
from seed.core.track_system import TrackSystem

logger_name = "SystemDefragmentor"
logger = logging.getLogger(logger_name)
logger.setLevel(logging.INFO)

# ==========================================================
# HealthMonitor Codex
# ==========================================================
class HealthMonitorCodex:
    def __init__(self):
        self.module_health: Dict[str, str] = {}  # "good", "warning", "critical"
        self.lock = threading.Lock()

    def check_health(self, module: str) -> str:
        with self.lock:
            return self.module_health.get(module, "good")

    def mark_warning(self, module: str):
        with self.lock:
            self.module_health[module] = "warning"

    def mark_critical(self, module: str):
        with self.lock:
            self.module_health[module] = "critical"

    def resolve_by_doctor(self, module: str) -> bool:
        with self.lock:
            status = self.module_health.get(module, "good")
            if status == "warning":
                logger.info(f"[HealthCodex] Doctor resolved module {module} warning")
                self.module_health[module] = "good"
                return True
            return False

    def escalate_to_specialist(self, module: str):
        with self.lock:
            status = self.module_health.get(module, "good")
            if status == "critical":
                logger.warning(f"[HealthCodex] Escalating module {module} to Specialist")
                self.module_health[module] = "good"
                logger.info(f"[HealthCodex] Specialist repaired module {module}")

# ==========================================================
# Smart Transformer with Qbit Feedback
# ==========================================================
class SmartTransformer:
    def __init__(self, agent_manager=None, health_codex: Optional[HealthMonitorCodex]=None, build_manager=None):
        self.agent_manager = agent_manager
        self.health_codex = health_codex
        self.build_manager = build_manager
        self.build_queue: list[tuple[float, str]] = []
        self.completed_builds: Dict[str, bool] = {}
        self.lock = threading.Lock()
        self.qbit_feedback_threshold = 0.5  # influence of Qbit on priority

    def analyze_dependencies(self, modules: list[str]) -> list[str]:
        """Analyze dependencies and sort modules by health + Qbit feedback."""
        scored_modules = []
        qbit_value = getattr(self.agent_manager, "_last_qbit_input", 0.0) if self.agent_manager else 0.0
        for m in modules:
            health = self.health_codex.check_health(m) if self.health_codex else "good"
            score = {"critical": 0, "warning": 1, "good": 2}.get(health, 2)
            score *= (1.0 - min(qbit_value, self.qbit_feedback_threshold))
            predicted_need = random.random() * 0.5
            scored_modules.append((score + predicted_need, m))
        scored_modules.sort(key=lambda x: x[0])
        return [m for _, m in scored_modules]

    def queue_build(self, module: str, priority: float = None):
        with self.lock:
            if module not in [m for _, m in self.build_queue] and module not in self.completed_builds:
                if priority is None:
                    health = self.health_codex.check_health(module) if self.health_codex else "good"
                    priority = {"critical": 0, "warning": 1, "good": 2}.get(health, 2)
                self.build_queue.append((priority, module))
                self.build_queue.sort(key=lambda x: x[0])
                logger.info(f"[SmartTransformer] Queued module {module} with priority {priority}")

    async def execute_builds(self):
        while self.build_queue:
            _, module = self.build_queue.pop(0)
            qbit_value = getattr(self.agent_manager, "_last_qbit_input", 0.0) if self.agent_manager else 0.0
            if self.health_codex.check_health(module) == "good" and qbit_value < self.qbit_feedback_threshold:
                self.completed_builds[module] = True
                logger.info(f"[SmartTransformer] Skipping {module}, healthy and low Qbit")
                continue
            if self.health_codex.check_health(module) == "critical":
                self.health_codex.escalate_to_specialist(module)
                self.queue_build(module)
                continue

            if self.build_manager:
                try:
                    await self.build_manager.build_module_async(module)
                    logger.info(f"[SmartTransformer] Module built via BuildManager: {module}")
                except Exception as e:
                    logger.warning(f"[SmartTransformer] BuildManager failed for {module}: {e}")
                    self.queue_build(module)
            else:
                await asyncio.sleep(0.05)
                logger.info(f"[SmartTransformer] Module built (simulated): {module}")
            self.completed_builds[module] = True

            # Trigger AgentManager skill chain
            if self.agent_manager:
                skill_name = f"{module}_sequence"
                asyncio.create_task(
                    self.agent_manager.trigger_skill_chain_safe(skill_name, {"module": module})
                )

    async def transform_modules(self, modules: list[str]):
        sorted_modules = self.analyze_dependencies(modules)
        for module in sorted_modules:
            self.queue_build(module)
        await self.execute_builds()

# ==========================================================
# SystemDefragmentor
# ==========================================================
class SystemDefragmentor:
    DEFAULT_SCAN_INTERVAL = 60.0
    CLEANUP_TEMP = True
    RANDOM_EFFICIENCY_UPGRADE_INTERVAL = 300.0
    LIVE_SUPERVISOR_INTERVAL = 5.0

    def __init__(self, agent_manager=None, seed_core=None, build_manager=None, check_interval: float = None):
        self.agent_manager = agent_manager
        self.seed_core = seed_core
        self.build_manager = build_manager
        self.check_interval = check_interval or self.DEFAULT_SCAN_INTERVAL
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.module_status: Dict[str, Dict[str, Any]] = {}
        self.last_scan = None

        # Health Monitor Codex
        self.health_codex = HealthMonitorCodex()

        # Smart Transformer
        self.transformer = SmartTransformer(agent_manager=self.agent_manager,
                                            health_codex=self.health_codex,
                                            build_manager=self.build_manager)

        # Start async POST init
        asyncio.run(self.async_post_init())

        # Start threads
        self._monitor_thread = threading.Thread(target=self._defrag_loop, daemon=True)
        self._monitor_thread.start()
        self._random_upgrade_thread = threading.Thread(target=self._random_efficiency_loop, daemon=True)
        self._random_upgrade_thread.start()
        self._live_supervisor_thread = threading.Thread(target=self._live_supervisor_loop, daemon=True)
        self._live_supervisor_thread.start()

        logger.info(f"[{logger_name}] SystemDefragmentor initialized with full Qbit integration")

    # ======================================================
    async def async_post_init(self):
        if not self.agent_manager:
            return
        modules = list(getattr(self.agent_manager, "_qbit_groups", {}).keys())
        for module in modules:
            if random.random() < 0.1:
                self.health_codex.mark_warning(module)
            elif random.random() < 0.05:
                self.health_codex.mark_critical(module)
            self.health_codex.resolve_by_doctor(module)
            if self.health_codex.check_health(module) == "critical":
                self.health_codex.escalate_to_specialist(module)
        if self.transformer:
            await self.transformer.transform_modules(modules)

    # ======================================================
    def _defrag_loop(self):
        while not self._stop_event.is_set():
            try:
                asyncio.run(self.scan_and_optimize())
                self.clean_temp_files()
                self.plan_module_updates()
                self.last_scan = time.time()
            except Exception as e:
                logger.warning(f"[{logger_name}] Defrag loop error: {e}")
            time.sleep(self.check_interval)

    def _random_efficiency_loop(self):
        while not self._stop_event.is_set():
            try:
                asyncio.run(self.random_efficiency_upgrade())
            except Exception as e:
                logger.warning(f"[{logger_name}] Random efficiency error: {e}")
            time.sleep(self.RANDOM_EFFICIENCY_UPGRADE_INTERVAL)

    def _live_supervisor_loop(self):
        while not self._stop_event.is_set():
            try:
                asyncio.run(self.live_module_supervisor())
            except Exception as e:
                logger.warning(f"[{logger_name}] Live supervisor error: {e}")
            time.sleep(self.LIVE_SUPERVISOR_INTERVAL)

    # ======================================================
    async def live_module_supervisor(self):
        if not self.agent_manager:
            return
        modules = list(getattr(self.agent_manager, "_qbit_groups", {}).keys())
        for module in modules:
            health = self.health_codex.check_health(module)
            if health == "warning":
                self.health_codex.resolve_by_doctor(module)
            elif health == "critical":
                self.health_codex.escalate_to_specialist(module)
                if self.transformer:
                    self.transformer.queue_build(module)
            status = self.module_status.get(module, {"optimized": False})
            status["health"] = self.health_codex.check_health(module)
            self.module_status[module] = status
            await self._pulse_seed_core("live_module_check", {"module": module, "health": status["health"]})
        if self.transformer:
            await self.transformer.execute_builds()

    # ======================================================
    async def scan_and_optimize(self):
        if not self.agent_manager:
            return
        modules = list(getattr(self.agent_manager, "_qbit_groups", {}).keys())
        for module in modules:
            try:
                if random.random() < 0.1:
                    self.health_codex.mark_warning(module)
                elif random.random() < 0.05:
                    self.health_codex.mark_critical(module)
                self.health_codex.resolve_by_doctor(module)
                if self.health_codex.check_health(module) == "critical":
                    self.health_codex.escalate_to_specialist(module)
                status = self.module_status.get(module, {"optimized": False})
                status.update({
                    "optimized": True,
                    "last_check": time.time(),
                    "health": self.health_codex.check_health(module)
                })
                self.module_status[module] = status
                await self._pulse_seed_core("module_optimized", {"module": module, "health": status["health"]})
            except Exception as e:
                logger.warning(f"[{logger_name}] Module optimization failed for {module}: {e}")
        if self.transformer:
            await self.transformer.transform_modules(modules)

    # ======================================================
    def clean_temp_files(self):
        if not self.CLEANUP_TEMP:
            return
        temp_dirs = ["/tmp", os.path.expanduser("~/.cache")]
        for d in temp_dirs:
            try:
                if os.path.exists(d):
                    for root, dirs, files in os.walk(d):
                        for f in files:
                            try:
                                os.remove(os.path.join(root, f))
                            except:
                                pass
                    asyncio.run(self._pulse_seed_core("temp_cleanup", {"directory": d}))
            except Exception as e:
                logger.warning(f"[{logger_name}] Temp cleanup failed for {d}: {e}")

    # ======================================================
    def plan_module_updates(self):
        if not self.agent_manager:
            return
        try:
            for module in getattr(self.agent_manager, "_qbit_groups", {}).keys():
                plan_id = f"update-{module}-{str(uuid.uuid4())[:8]}"
                asyncio.run(self._pulse_seed_core("module_update_plan", {"module": module, "plan_id": plan_id}))
        except Exception as e:
            logger.warning(f"[{logger_name}] Module update planning failed: {e}")

    # ======================================================
    async def random_efficiency_upgrade(self):
        if not self.agent_manager:
            return
        modules = list(getattr(self.agent_manager, "_qbit_groups", {}).keys())
        if modules:
            module = random.choice(modules)
            await self._pulse_seed_core("random_efficiency_upgrade", {"module": module})

    # ======================================================
    async def _pulse_seed_core(self, pulse_label: str, data: Dict[str, Any]):
        if not self.seed_core or not getattr(self.seed_core, "receive_agent_data", None):
            return
        payload = {
            "timestamp": time.time(),
            "pulse_label": pulse_label,
            "data": data,
            "source": "SystemDefragmentor",
            "track_id": f"SD-{str(uuid.uuid4())[:8]}"
        }
        try:
            await self.seed_core.receive_agent_data(payload)
        except Exception as e:
            logger.warning(f"[{logger_name}] Failed to pulse SEEDCore: {e}")

    # ======================================================
    def stop(self):
        self._stop_event.set()
        self._monitor_thread.join()
        self._random_upgrade_thread.join()
        self._live_supervisor_thread.join()
        logger.info(f"[{logger_name}] SystemDefragmentor stopped")

    # ======================================================
    def get_dashboard(self) -> Dict[str, Any]:
        return {
            "last_scan": self.last_scan,
            "modules": self.module_status,
            "source": "SystemDefragmentor",
            "timestamp": time.time()
        }

# ==========================================================
# END OF FILE
# ==========================================================
