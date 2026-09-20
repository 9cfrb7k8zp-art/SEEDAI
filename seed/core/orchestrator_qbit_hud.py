# ==========================================================
# FILE: orchestrator_qbit_hud.py
# PATH: SEED_ROOT/seed/core/orchestrator_qbit_hud.py
# SEED Orchestrator with full Qbit HUD integration and Camera Qbit support
# ==========================================================

import threading
import time
import logging
from seed.core.qbit_dialer import QbitDialer
from seed.core.SEEDCameraQbit import SEEDCameraQbit
from seed.core.hud_master_overlay import HUDMasterOverlay

logger = logging.getLogger("SEEDOrchestratorQbit")

class SEEDOrchestratorQbitHUD:
    """
    SEED Orchestrator with:
    - SEEDHandshakeManager
    - Qbit-equalized HUD overlay
    - Camera Qbit integration
    - GUI with memory, Qbit channel traffic, and device events
    """

    def __init__(self, modem, device_manager, event_bus=None):
        self.modem = modem
        self.device_manager = device_manager
        self.event_bus = event_bus
        self.running = False

        # -----------------------------
        # Qbit Dialer (central data bus)
        # -----------------------------
        self.qbit_dialer = QbitDialer()

        # -----------------------------
        # Master HUD overlay
        # -----------------------------
        self.hud_overlay = HUDMasterOverlay(
            device_manager=device_manager,
            modem=modem
        )

        # -----------------------------
        # Initialize Camera Qbit module
        # -----------------------------
        self.camera_qbit = SEEDCameraQbit(
            qbit_dialer=self.qbit_dialer,
            max_cameras=4,
            poll_interval=0.05,
            push_interval=0.2
        )

        # -----------------------------
        # Wire Qbit callbacks to HUD overlay
        # -----------------------------
        self.qbit_dialer.register_callback(self._on_qbit_push)

        # -----------------------------
        # GUI (optional)
        # -----------------------------
        try:
            from seed.core.hud_gui_qbit import HUDGUIQbit
            self.hud_gui = HUDGUIQbit(self.hud_overlay)
            self.gui_thread = threading.Thread(target=self.hud_gui.run, daemon=True)
            self.gui_thread.start()
        except ImportError:
            self.hud_gui = None
            logger.warning("[ORCHESTRATOR] HUD GUI not available. Continuing without GUI.")

        # -----------------------------
        # Handshake manager
        # -----------------------------
        try:
            from seed.core.handshake_protocol import SEEDHandshakeManager
            self.handshake_manager = SEEDHandshakeManager(
                modem=modem,
                device_manager=device_manager,
                event_bus=event_bus
            )
        except ImportError:
            self.handshake_manager = None
            logger.warning("[ORCHESTRATOR] Handshake manager not available.")

        logger.info("[ORCHESTRATOR] Initialized SEED orchestrator with Qbit HUD")

    # -----------------------------
    # Callback for Qbit pushes (camera/system)
    # -----------------------------
    def _on_qbit_push(self, payload):
        """
        Handle Qbit data and update HUD overlay
        """
        try:
            if payload["type"] == "camera_qbit":
                cam_id = payload["camera_id"]
                light_qbit = payload["light_qbit"]
                objects = payload.get("objects", [])

                timestamp = payload.get("timestamp", time.time())

                # Update memory log
                self.hud_overlay.memory_log.append((timestamp, light_qbit.get("avg_intensity", 0)))

                # Update channel log (camera-based)
                if cam_id not in self.hud_overlay.channel_log:
                    self.hud_overlay.channel_log[cam_id] = []
                self.hud_overlay.channel_log[cam_id].append((timestamp, light_qbit.get("freq", 0)))

                # Optional: update objects in HUD overlay
                if hasattr(self.hud_overlay, "update_camera_objects"):
                    self.hud_overlay.update_camera_objects(cam_id, objects)

        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Qbit callback error: {e}")

    # -----------------------------
    # Main orchestrator loop
    # -----------------------------
    def run(self):
        self.running = True
        while self.running:
            try:
                # 1. Handshake operations
                if self.handshake_manager:
                    self.handshake_manager.broadcast_identity()
                    self.handshake_manager.prune()

                # 2. Gather channel input values
                channel_inputs = {}
                for ch in self.hud_overlay.channels:
                    active_sessions_count = len(self.handshake_manager.active_sessions) if self.handshake_manager else 0
                    channel_inputs[ch] = active_sessions_count * (ch / 3)  # scaling example

                # 3. Update HUD overlay
                self.hud_overlay.update()

                # 4. Sleep for update rate (~10 FPS)
                time.sleep(0.1)

            except Exception as e:
                logger.warning(f"[ORCHESTRATOR] Exception in main loop: {e}")

    # -----------------------------
    # Stop orchestrator
    # -----------------------------
    def stop(self):
        self.running = False
        if self.hud_gui:
            self.hud_gui.stop()
        self.camera_qbit.stop()
        logger.info("[ORCHESTRATOR] SEED orchestrator with Qbit HUD stopped")
