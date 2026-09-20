# ==========================================================
# FILE: orchestrator_gui.py
# PATH: SEED_ROOT/seed/core/orchestrator_gui.py
# SEED Orchestrator with live GUI HUD integration
# ==========================================================

import threading
import time
import logging

logger = logging.getLogger("SEEDOrchestratorGUI")

class SEEDOrchestratorGUI:
    """
    SEED Orchestrator integrated with:
    - SEEDHandshakeManager
    - Live HUD GUI overlay with memory & channel visualization
    - Interactive playback controls
    """

    def __init__(self, modem, device_manager, event_bus=None):
        self.modem = modem
        self.device_manager = device_manager
        self.event_bus = event_bus
        self.running = False

        # -----------------------------
        # Initialize HUD overlay
        # -----------------------------
        from seed.core.hud_memory_overlay import HUDMemoryOverlay
        self.hud_overlay = HUDMemoryOverlay(hud=None, device_manager=device_manager)

        # -----------------------------
        # Initialize live GUI
        # -----------------------------
        from seed.core.hud_gui_live import HUDGUILive
        self.hud_gui = HUDGUILive(self.hud_overlay)
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

        logger.info("[ORCHESTRATOR] Initialized SEED orchestrator with live GUI HUD")

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        self.running = True
        while self.running:
            # 1. Handshake operations
            self.handshake_manager.broadcast_identity()
            self.handshake_manager.prune()

            # 2. Gather channel weights for HUD
            # Assuming handshake_manager maintains per-channel Qbit weights
            if hasattr(self.handshake_manager, "channel_weights"):
                channel_weights = self.handshake_manager.channel_weights
            else:
                channel_weights = {ch: 0 for ch in self.hud_overlay.channels}

            # 3. Update HUD overlay
            self.hud_overlay.update_memory(channel_weights)

            # 4. Sleep for update interval
            time.sleep(0.1)  # ~10 FPS

    # -----------------------------
    # Stop orchestrator
    # -----------------------------
    def stop(self):
        self.running = False
        self.hud_gui.stop()
        logger.info("[ORCHESTRATOR] SEED orchestrator stopped")
