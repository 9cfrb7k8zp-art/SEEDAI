# ==========================================================
# FILE: orchestrator_qbit_dynamic.py
# PATH: SEED_ROOT/seed/core/orchestrator_qbit_dynamic.py
# SEED Orchestrator with fully dynamic Qbit-driven HUD
# ==========================================================

import threading
import time
import logging
from seed.core.hud_qbit_autobalance import HUDQbitAutoBalance



logger = logging.getLogger("SEEDOrchestratorQbitDynamic")

class SEEDOrchestratorQbitDynamicHUD:
    """
    SEED Orchestrator with:
    - SEEDHandshakeManager
    - Fully dynamic Qbit-equalized HUD overlay
    - GUI with memory, Qbit channel traffic, and device events
    """

    def __init__(self, modem, device_manager, log_source=None, event_bus=None):
        self.modem = modem
        self.device_manager = device_manager
        self.log_source = log_source  # Function returning system log metrics per channel
        self.event_bus = event_bus
        self.running = False

        # -----------------------------
        # Initialize fully dynamic Qbit HUD overlay
        # -----------------------------
        from seed.core.hud_memory_overlay_qbit_dynamic import HUDMemoryOverlayQbitDynamic
        self.hud_overlay = HUDMemoryOverlayQbitDynamic(
            device_manager=device_manager,
            modem=modem,
            log_source=log_source
        )

        # -----------------------------
        # Initialize GUI with Qbit visualization
        # -----------------------------
        from seed.core.hud_gui_qbit import HUDGUIQbit
        self.hud_gui = HUDGUIQbit(self.hud_overlay)
        self.gui_thread = threading.Thread(target=self.hud_gui.run, daemon=True)
        self.gui_thread.start()

        # -----------------------------
        # Initialize handshake manager
        # -----------------------------
        from seed.core.handshake_protocol import SEEDHandshakeManager
        self.handshake_manager = SEEDHandshakeManager(
            modem=modem,
            device_manager=device_manager,
            event_bus=event_bus
        )

        logger.info("[ORCHESTRATOR] Initialized SEED orchestrator with dynamic Qbit HUD")

    # -----------------------------
    # Main orchestrator loop
    # -----------------------------
    def run(self):
        self.running = True
        while self.running:
            # 1. Handshake operations
            self.handshake_manager.broadcast_identity()
            self.handshake_manager.prune()

            # 2. Update HUD overlay with dynamic inputs
            # The overlay itself computes Qbit-weighted channels from:
            # - handshake active sessions
            # - modem TX/RX activity
            # - log metrics from log_source
            self.hud_overlay.update_memory()

            # 3. Sleep to maintain update rate
            time.sleep(0.1)  # ~10 FPS

    # Initialize auto-balancer after HUD overlay
        self.qbit_balancer = QbitAutoBalancer(self.hud_overlay)

    # In main loop:
        self.hud_overlay.update_memory()
        self.qbit_balancer.update_multipliers()



    # -----------------------------
    # Stop orchestrator
    # -----------------------------
    def stop(self):
        self.running = False
        self.hud_gui.stop()
        logger.info("[ORCHESTRATOR] SEED orchestrator with dynamic Qbit HUD stopped")
