# ==========================================================
# FILE: boot_sequence.py
# PATH: SEED_ROOT/core/boot_sequence.py
# SEED Boot Sequence v3.0
# PURPOSE:
#   - Orchestrate SEED system boot
#   - Full TrackID system integration
#   - Control over module boot order
#   - Prevent multi-module simultaneous boot
# ==========================================================

import time
import uuid
import logging
import threading

from core.event_bus import SEEDEventBus
from core.security import SEEDSecurityManager
from core.memory_manager import SEEDMemoryManager
from core.analytics_engine import SEEDAnalyticsEngine
from core.scheduler import SEEDScheduler
from core.agent_manager import SEEDAgentManager
from core.backup_engine import SEEDBackupEngine
from core.adaptive_engine import SEEDAdaptiveEngine
from core.shutdown_recovery import SEEDShutdownRecovery
from core.watchdog import SEEDWatchdog

logger = logging.getLogger("SEEDBootSequence")
logging.basicConfig(level=logging.INFO)


def gen_track_id(prefix="SCM"):
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


class SEEDBootSequence:


    def __init__(self, event_bus=None, storage_root="./SEED_ROOT"):
        self.storage_root = storage_root
        self.track_id = gen_track_id("SCM")
        self.boot_lock = threading.Lock()  # Prevent multi-module boot

        # Core Event Bus
        self.event_bus = event_bus or SEEDEventBus()

        # Security & Access
        self.security = SEEDSecurityManager()
        self.security.grant_authority("ID_SCM", level="high")

        # Memory & Analytics
        self.memory_manager = SEEDMemoryManager()
        self.analytics = SEEDAnalyticsEngine()

        # Scheduler
        self.scheduler = SEEDScheduler(self.event_bus)

        # Agents
        self.agent_manager = SEEDAgentManager(self.event_bus)

        # Backup
        self.backup_engine = SEEDBackupEngine(
            storage_root=self.storage_root,
            memory_manager=self.memory_manager,
            analytics_engine=self.analytics,
            event_bus=self.event_bus
        )

        # Adaptive Engine
        self.adaptive_engine = SEEDAdaptiveEngine(
            event_bus=self.event_bus,
            scheduler=self.scheduler,
            memory_manager=self.memory_manager,
            analytics_engine=self.analytics
        )

        # Watchdog
        self.watchdog = SEEDWatchdog(self.event_bus, self.memory_manager)

        # Shutdown / Recovery
        self.shutdown_manager = SEEDShutdownRecovery(
            orchestrator=self,
            event_bus=self.event_bus,
            backup_engine=self.backup_engine
        )

        self.system_ready = False

        # Register initial SCM boot event
        self.memory_manager.record_event(
            event_type="SCM_BOOT_INIT",
            payload={"track_id": self.track_id, "timestamp": time.time()}
        )

    # ----------------------------
    # BOOT SEQUENCE
    # ----------------------------
    def boot(self):
        boot_track_id = gen_track_id("BOOT")
        with self.boot_lock:  # Prevent simultaneous module boots
            try:
                logger.info(f"[BOOT] Initializing SEED system | TrackID={boot_track_id}")

                # Boot modules in controlled order
                self._boot_scheduler(track_id=boot_track_id)
                self._boot_adaptive_engine(track_id=boot_track_id)
                self._boot_watchdog(track_id=boot_track_id)
                self._verify_backups(track_id=boot_track_id)
                self._scm_actions(track_id=boot_track_id)

                # Mark system ready
                self.system_ready = True
                self.event_bus.publish("SYSTEM_READY", payload={
                    "message": "SEED system boot completed successfully.",
                    "track_id": boot_track_id
                })
                logger.info(f"[BOOT] SEED system ready | TrackID={boot_track_id}")

            except Exception as e:
                logger.critical(f"[BOOT] Critical failure | TrackID={boot_track_id}: {e}")
                self.shutdown_manager.emergency_recover()

    # ----------------------------
    # Module boot steps
    # ----------------------------
    def _boot_scheduler(self, track_id=None):
        track_id = track_id or gen_track_id("SCH")
        logger.info(f"[BOOT] Starting Scheduler | TrackID={track_id}")
        self.scheduler.start()
        self.event_bus.publish("MODULE_BOOTED", payload={"module": "Scheduler", "track_id": track_id})

    def _boot_adaptive_engine(self, track_id=None):
        track_id = track_id or gen_track_id("ADP")
        logger.info(f"[BOOT] Starting Adaptive Engine | TrackID={track_id}")
        self.adaptive_engine.start()
        self.event_bus.publish("MODULE_BOOTED", payload={"module": "AdaptiveEngine", "track_id": track_id})

    def _boot_watchdog(self, track_id=None):
        track_id = track_id or gen_track_id("WDG")
        logger.info(f"[BOOT] Starting Watchdog | TrackID={track_id}")
        self.watchdog.start()
        self.event_bus.publish("MODULE_BOOTED", payload={"module": "Watchdog", "track_id": track_id})

    def _verify_backups(self, track_id=None):
        track_id = track_id or gen_track_id("BKP")
        backups = self.backup_engine.restore(layer="local")
        if backups is None:
            logger.warning(f"[BOOT] No local backups found | TrackID={track_id}")
        self.event_bus.publish("BACKUP_VERIFIED", payload={"track_id": track_id})

    # ----------------------------
    # SCM authority actions
    # ----------------------------
    def _scm_actions(self, track_id=None):
        track_id = track_id or gen_track_id("SCM")
        if not self.security.has_authority("ID_SCM"):
            logger.warning(f"[SCM] SCM authority missing | TrackID={track_id}")
            return

        logger.info(f"[SCM] SCM authority granted | TrackID={track_id}")
        self._request_driver_builds(track_id=track_id)
        self._check_system_upgrades(track_id=track_id)
        self._ensure_network_control(track_id=track_id)

    def _request_driver_builds(self, track_id=None):
        track_id = track_id or gen_track_id("DRV")
        logger.info(f"[SCM] Requesting driver builds | TrackID={track_id}")
        self.event_bus.publish("SCM_DRIVER_BUILD_REQUEST", payload={"track_id": track_id})

    def _check_system_upgrades(self, track_id=None):
        track_id = track_id or gen_track_id("UPG")
        logger.info(f"[SCM] Checking system upgrades | TrackID={track_id}")
        self.event_bus.publish("SCM_SYSTEM_UPGRADE_CHECK", payload={"track_id": track_id})

    def _ensure_network_control(self, track_id=None):
        track_id = track_id or gen_track_id("NET")
        logger.info(f"[SCM] Ensuring network control | TrackID={track_id}")
        self.event_bus.publish("SCM_NETWORK_CONTROL", payload={"track_id": track_id})

    # ----------------------------
    # SHUTDOWN SEQUENCE
    # ----------------------------
    def shutdown(self):
        shutdown_track_id = gen_track_id("SHUT")
        logger.info(f"[SHUTDOWN] Initiating SEED shutdown | TrackID={shutdown_track_id}")
        self.shutdown_manager.shutdown()
        self.event_bus.publish("SYSTEM_SHUTDOWN", payload={"track_id": shutdown_track_id})
