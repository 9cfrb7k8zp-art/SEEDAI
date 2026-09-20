# ==========================================================
# FILE: seed_core_controller.py
# PATH: SEED_ROOT/seed/core/seed_core_controller.py
# UPDATED: 2025-12-31
#
# PURPOSE: SEED AI side CORE controller
# - Independent SEED AI OS pulse
# - CORE = power, heartbeat = life
# - QbitDialer integration (signal + state)
# - Runs safely until AgentManager Master is online
#
# IDENTITY:
#   CHANNEL_ID : SEED-AI
#   TRACK_ID   : CORE-0
#   HUD_ID     : HUD-CORE
# ==========================================================

import logging
import threading
import time

# ---------------- SAFE IMPORTS ----------------
from seed.core.event_bus import SEEDEventBus
from seed.core.qbit_dialer import QbitDialer
from seed.core.heartbeatemitter import HeartbeatEmitter

# ------------------------------------------------
# Logging
# ------------------------------------------------
logger = logging.getLogger("SEEDCoreController")
logging.basicConfig(level=logging.INFO)

CHANNEL_ID = "SEED-AI"
TRACK_ID = "CORE-0"
HUD_ID = "HUD-CORE"


# ==========================================================
# SEED CORE CONTROLLER
# ==========================================================
class SEEDCoreController:
    def __init__(
        self,
        storage_root: str = "./SEED_ROOT",
        interval: float = 0.05,
        enable_qbit: bool = True,
    ):
        self.storage_root = storage_root
        self.interval = interval
        self.enable_qbit = enable_qbit

        # ---------------- CORE STATE ----------------
        self.shutdown_flag = threading.Event()
        self.running = False

        # ---------------- EVENT BUS -----------------
        self.event_bus = event_bus or SEEDEventBus()

        # ---------------- QBIT DIALER ---------------
        self.qbit_dialer = qbit_dialer or QbitDialer(
            event_bus=self.event_bus
        )

        # ---------------- HEARTBEAT -----------------
        self.heartbeat = HeartbeatEmitter(
            module_name="SEED_CORE",
            event_bus=self.event_bus,
            interval=self.interval,
            enable_qbit=self.enable_qbit,
        )

        # Wire heartbeat → Qbit
        self.heartbeat.qbit_callback = self.qbit_dialer.inject_heartbeat

        logger.info(
            "[SEEDCoreController] Initialized | "
            f"CHANNEL={CHANNEL_ID} TRACK={TRACK_ID} HUD={HUD_ID}"
        )

    # ======================================================
    # START CORE
    # ======================================================
    def start(self):
        """
        Start the independent SEED AI core loop.
        """
        if self.running:
            return

        logger.info("[SEEDCoreController] Starting CORE")

        self.running = True

        # Start heartbeat (this is life)
        self.heartbeat.start()

        logger.info(
            "[SEEDCoreController] CORE ONLINE | "
            "Heartbeat active | QbitDialer linked"
        )

    # ======================================================
    # STOP CORE
    # ======================================================
    def stop(self):
        """
        Graceful shutdown of CORE.
        """
        if not self.running:
            return

        logger.info("[SEEDCoreController] Stopping CORE")

        self.running = False
        self.shutdown_flag.set()

        try:
            self.heartbeat.stop()
        except Exception:
            pass

        logger.info("[SEEDCoreController] CORE stopped safely")

    # ======================================================
    # CORE LOOP (OPTIONAL)
    # ======================================================
    def run_forever(self):
        """
        Blocking run loop for standalone CORE mode.
        """
        self.start()
        try:
            while not self.shutdown_flag.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()


# ==========================================================
# STANDALONE MODE
# ==========================================================
if __name__ == "__main__":
    controller = SEEDCoreController(interval=0.05)
    logger.info("[SEEDCoreController] SEED AI OS CORE is alive — Ctrl+C to stop")
    controller.run_forever()
