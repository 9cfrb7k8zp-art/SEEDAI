# =====================================================
# FILE: pipeline.py
# PATH: SEED_ROOT/seed/core/pipeline.py
# SEED Pipeline: central wiring for HUD + Qbit + Devices
# =====================================================

import asyncio
import logging
from threading import Thread

# HUD / GUI modules
from seed.ui.hud_master_gui import HUDMasterGUI
from seed.core.hud_master_overlay import HUDMasterOverlay
from seed.core.hud_qbit_per_device import HUDQbitPerDevice
from seed.core.hud_qbit_autobalance import HUDQbitAutoBalance
from seed.core.hud_qbit_alerts import HUDQbitAlerts
from seed.core.hud_memory_overlay_qbit import HUDMemoryOverlayQbit
from seed.core.hud_memory_overlay_qbit_dynamic import HUDMemoryOverlayQbitDynamic
from seed.core.hud_memory_overlay_events import HUDMemoryOverlayEvents
from seed.ui.hud_gui_playback import HUDGUIPlayback
from seed.ui.hud_gui_alerts import HUDGUIAlerts
from seed.ui.hud_gui_live_events import HUDGUILiveEvents
from seed.ui.hud_gui_live import HUDGUILive

logger = logging.getLogger("SEEDPipeline")
logging.basicConfig(level=logging.INFO)


class SEEDPipeline:
    """
    Central pipeline connecting:
    - HUD overlay
    - Qbit modules
    - Device controls
    """

    def __init__(self, fat_queue, hud_overlay: HUDMasterOverlay, device_manager, modem, qbit_dialer):
        self.fat_queue = fat_queue
        self.hud_overlay = hud_overlay
        self.device_manager = device_manager
        self.modem = modem
        self.qbit_dialer = qbit_dialer

        # Module instances
        self.modules = []

        self._load_modules()
        self._start_module_loops()
        logger.info("[SEEDPipeline] Pipeline initialized")

    # -----------------------------
    # Load modules
    # -----------------------------
    def _load_modules(self):
        # Per-device HUD
        self.modules.append(HUDQbitPerDevice(self.device_manager, self.qbit_dialer, self.hud_overlay))
        # Auto-balance EQ
        self.modules.append(HUDQbitAutoBalance(self.hud_overlay, self.qbit_dialer))
        # Alerts
        self.modules.append(HUDQbitAlerts(self.hud_overlay))
        # Memory overlays
        self.modules.append(HUDMemoryOverlayQbit(self.hud_overlay))
        self.modules.append(HUDMemoryOverlayQbitDynamic(self.hud_overlay))
        self.modules.append(HUDMemoryOverlayEvents(self.hud_overlay))
        # GUI visual modules
        self.modules.append(HUDGUIPlayback(self.hud_overlay))
        self.modules.append(HUDGUIAlerts(self.hud_overlay))
        self.modules.append(HUDGUILiveEvents(self.hud_overlay))
        self.modules.append(HUDGUILive(self.hud_overlay))

    # -----------------------------
    # Start async loops for modules that require polling / updates
    # -----------------------------
    def _start_module_loops(self):
        for module in self.modules:
            if hasattr(module, "start_loop"):
                try:
                    Thread(target=module.start_loop, daemon=True).start()
                except Exception as e:
                    logger.warning(f"[SEEDPipeline] Failed to start loop for {module}: {e}")

    # -----------------------------
    # Push data into pipeline
    # -----------------------------
    async def push(self, data, source="unknown", label=None):
        # Forward to FAT queue
        entry = {
            "timestamp": asyncio.get_event_loop().time(),
            "source": source,
            "label": label,
            "data": data
        }
        try:
            self.fat_queue.put_nowait(entry)
        except RuntimeError:
            Thread(target=lambda: asyncio.run(self.fat_queue.put(entry)), daemon=True).start()

        # Update HUD overlay
        if hasattr(self.hud_overlay, "update_from_pipeline"):
            self.hud_overlay.update_from_pipeline(entry)

        # Push to all modules
        for module in self.modules:
            if hasattr(module, "on_pipeline_data"):
                module.on_pipeline_data(entry)
