# ==========================================================
# FILE: orchestrator_playback.py
# PATH: SEED_ROOT/seed/core/orchestrator_playback.py
# SEED Orchestrator with live + playback HUD integration
# ==========================================================

import threading
import time
import logging

logger = logging.getLogger("SEEDOrchestratorPlayback")

class SEEDOrchestratorPlayback:
    """
    SEED Orchestrator with:
    - SEEDHandshakeManager
    - Playback-capable HUD overlay
    - GUI with memory, channel traffic, and device events
    """

    def __init__(self, modem, device_manager, event_bus=None):
        self.modem = modem
        self.device_manager = device_manager
        self.event_bus = event_bus
        self.running = False

        # -----------------------------
        # Initialize playback-capable HUD overlay
        # -----------------------------
        from seed.core.hud_memory_overlay_events import HUDMemoryOverlayEvents
        self.hud_overlay = HUDMemoryOverlayEvents(device_manager=device_manager)

        # -----------------------------
        # Initialize GUI playback HUD
        # -----------------------------
        from seed.core.hud_gui_playback import HUDGUIPlayback
        self.hud_gui = HUDGUIPlayback(self.hud_overlay)
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

        logger.info("[ORCHESTRATOR] Initialized SEED orchestrator with playback HUD")

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        self.running = True
        while self.running:
            # 1. Handshake operations
            self.handshake_manager.broadcast_identity()
            self.handshake_manager.prune()

            # 2. Update channel weights for HUD overlay
            channel_weights = getattr(self.handshake_manager, "channel_weights", {ch: 0 for ch in self.hud_overlay.channels})

            # 3. Update HUD overlay with memory, channels, and device events
            self.hud_overlay.update_memory(channel_weights)

            # 4. Sleep to maintain update rate
            time.sleep(0.1)  # ~10 FPS

    # -----------------------------
    # Stop orchestrator
    # -----------------------------
    def stop(self):
        self.running = False
        self.hud_gui.stop()
        logger.info("[ORCHESTRATOR] SEED orchestrator with playback HUD stopped")
