# ==========================================================
# FILE: L5_ControlCenter.py
# PATH: SEED_ROOT/seed/systemutils/L5_ControlCenter.py
# VERSION: 1.0 – FULL L-5 CONTROL INTEGRATION
# UPDATED: 2026-01-03
# ==========================================================

import asyncio
import logging
import time
import uuid
from threading import Lock

from seed.core.healthmonitor import HealthMonitor
from seed.systemutils.Adim_Manager import Adim_Manager
from seed.skills.action_registry import execute_action, get_registered_actions
from seed.core.tracked_data import TrackedData

logger = logging.getLogger("L5Control")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)


# ==========================================================
# L-5 CONTROL CENTER
# ==========================================================
class L5_ControlCenter:
    def __init__(self, seed_core=None, agent_manager=None, smart_transformer=None, qbit_dialer=None):
        self.seed_core = seed_core
        self.agent_manager = agent_manager
        self.smart_transformer = smart_transformer
        self.qbit_dialer = qbit_dialer

        # Locks for thread-safe operations
        self.lock = Lock()

        # Core modules
        self.health_monitor = HealthMonitor(agent_manager=agent_manager, seed_core=seed_core)
        self.admin_manager = Adim_Manager(
            agent_manager=agent_manager,
            smart_transformer=smart_transformer,
            qbit_dialer=qbit_dialer,
            seed_core=seed_core
        )

        # Control loop interval
        self.loop_interval = 2.0  # seconds
        self._running = False

    # ======================================================
    # SYNC SYSTEM STATS
    # ======================================================
    def sync_system_stats(self):
        stats = {
            "flow_rate": self.admin_manager.system_stats.get("flow_rate", 0.0),
            "progress": self.admin_manager.system_stats.get("progress", 0.0),
            "health_score": self.admin_manager.system_stats.get("health_score", 1.0)
        }
        self.admin_manager.update_system_stats(**stats)

    # ======================================================
    # PULSE TRACKING
    # ======================================================
    def pulse_event(self, label, payload):
        track_id = f"L5-{uuid.uuid4().hex[:8]}"
        payload["track_id"] = track_id
        TrackedData.emit_event(event=label, channel="CONTROL", payload=payload)

    # ======================================================
    # MAIN CONTROL LOOP
    # ======================================================
    async def control_loop(self):
        self._running = True
        logger.info("[L5_ControlCenter] Starting main control loop")

        while self._running:
            try:
                # 1. Sync stats from HealthMonitor -> AdminManager
                self.sync_system_stats()

                # 2. HealthMonitor evaluates system and records faults
                #    Any critical faults trigger advisory / repair actions
                await asyncio.to_thread(self.health_monitor._monitor_loop)

                # 3. AdminManager evaluates health and performs auto-upgrades
                await self.admin_manager.auto_upgrade_loop(interval=self.loop_interval)

                # 4. Track system stats each loop
                self.pulse_event("SYSTEM_SYNC", self.admin_manager.get_system_stats())

                # 5. Process registered actions from skills / modules
                actions = get_registered_actions()
                for action_name, action_func in actions.items():
                    try:
                        result = await asyncio.to_thread(action_func)
                        self.pulse_event("ACTION_EXECUTED", {"action": action_name, "result": result})
                    except Exception as e:
                        logger.warning(f"[L5_ControlCenter] Action {action_name} failed: {e}")
                        self.health_monitor.record_fault("ActionRegistry", e)

            except Exception as e:
                logger.error(f"[L5_ControlCenter] Control loop error: {e}")
            await asyncio.sleep(self.loop_interval)

    # ======================================================
    # START / STOP
    # ======================================================
    def start(self):
        asyncio.create_task(self.control_loop())

    def stop(self):
        self._running = False
        self.health_monitor.stop()
        logger.info("[L5_ControlCenter] Control loop stopped")

# ==========================================================
# END OF FILE
# ==========================================================
