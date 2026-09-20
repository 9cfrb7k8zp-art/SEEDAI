# ==========================================================
# FILE: orchestrator_master_hud.py
# PATH: SEED_ROOT/seed/core/orchestrator_master_hud.py
# SEED Orchestrator fully integrated with Master HUD
# ==========================================================

import threading
import time
import logging

logger = logging.getLogger("SEEDOrchestratorMasterHUD")

class SEEDOrchestratorMasterHUD:
    """
    SEED Orchestrator with:
    - SEEDHandshakeManager
    - Fully integrated Master HUD
    - Live + playback monitoring
    """

    def __init__(self, modem, device_manager, log_source=None, event_bus=None):
        self.modem = modem
        self.device_manager = device_manager
        self.log_source = log_source
        self.event_bus = event_bus
        self.running = False

        # -----------------------------
        # Initialize Master HUD
        # -----------------------------
        from seed.core.hud_master import HUDMaster
        self.hud_master = HUDMaster(
            device_manager=device_manager,
            modem=modem,
            log_source=log_source
        )

        # -----------------------------
        # Initialize handshake manager
        # -----------------------------
        from seed.core.handshake_protocol import SEEDHandshakeManager
        self.handshake_manager = SEEDHandshakeManager(
            modem=modem,
            device_manager=device_manager,
            event_bus=event_bus
        )

        logger.info("[ORCHESTRATOR] Initialized SEED orchestrator with Master HUD")

        # Run HUD in separate thread
        self.gui_thread = threading.Thread(target=self.hud_master.run, daemon=True)
        self.gui_thread.start()

    # -----------------------------
    # Main orchestrator loop
    # -----------------------------
    def run(self):
        self.running = True
        while self.running:
            # 1. Handshake operations
            self.handshake_manager.broadcast_identity()
            self.handshake_manager.prune()

            # 2. HUD overlay updates (Master HUD handles dynamic Qbit, auto-balancing, alerts, per-device)
            self.hud_master.hud_overlay.update_memory()
            
            # 3. Small sleep to maintain ~10 FPS
            time.sleep(0.1)

    # -----------------------------
    # Stop orchestrator
    # -----------------------------
    def stop(self):
        self.running = False
        self.hud_master.stop()
        logger.info("[ORCHESTRATOR] SEED orchestrator with Master HUD stopped")
