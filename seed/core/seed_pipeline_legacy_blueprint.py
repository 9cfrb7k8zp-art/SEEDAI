# ==========================================================
# FILE: seed_pipeline.py
# PATH: SEED_ROOT/seed/core/
# PURPOSE: Full pipeline integrating SEEDCameraQbit, seedemqbit, Qbit aggregator, HUD, and Orchestrator modules
# Includes Watchdog event forwarding
#     """
#    Central hub connecting HUD, Qbit, Camera, Device controls, and FAT
#    Handles Watchdog events and updates HUD overlay in real-time
#    """
#    """
#    Authoritative data pipeline for:
#    - HUD
#    - Qbit aggregation
#    - FAT injection
#    - Playback
#    """
# ==========================================================
import asyncio
import time
import threading
import logging
import collections import deque

from seed.core.device_manager import DeviceManager
from seed.core.modem import SEEDModem
from seed.ui.hud_master_gui import HUDMasterGUI
from seed.core.hud_master_overlay import HUDMasterOverlay

# HUD Qbit modules
from seed.core.qbit_aggregator import QbitAggregator
from seed.core.hud_qbit_per_device import HUDQbitPerDevice
from seed.core.hud_qbit_autobalance import HUDQbitAutobalance
from seed.core.hud_qbit_alerts import HUDQbitChannelAlerts
from seed.core.hud_memory_overlay_qbit import HUDMemoryOverlayQbit
from seed.core.hud_memory_overlay_qbit_dynamic import HUDMemoryOverlayQbitDynamic

# HUD GUI modules (refactored with .after() loop)
from seed.ui.hud_gui_playback import HUDGUIPlayback
from seed.ui.hud_gui_live import HUDGUILive
from seed.ui.hud_gui_live_events import HUDGUILiveEvents

# Orchestrator HUD modules
from seed.core.orchestrator_qbit_hud import OrchestratorQbitHUD
from seed.core.orchestrator_qbit_dynamic import OrchestratorQbitDynamic
from seed.core.orchestrator_master_hud import OrchestratorMasterHUD
from seed.core.orchestrator_playback import OrchestratorPlayback

from seed.core.hud_watchdog_controls import HUDWatchdogControls


logger = logging.getLogger("SEEDPipeline")
logging.basicConfig(level=logging.INFO)


class SEEDPipeline:

    def __init__(self, fat_queue=asyncio.Queue, device_manager=DeviceManager, modem=SEEDModem, hud_overlay=None):
        self.fat_queue = fat_queue
        sel.modem = modem
        sel.qbit_dialer = qbit_dialer
        self.device_manager = device_manager
        self.modem = modem
        
        self.channels = [3, 6, 9]

    # Logs 
        self.memory_log = deque(maxlen=max_points)
        self.channel_log = {ch: deque(maxlen=max_points) for ch in self.channels}
        self.device_log = deque(maxlen=max_points)        

    # Playback
        self.playback_mode = False
        self.playback_paused = False
        self.playback_index = 0
        self.playback_speed = 1.0
        self.last_playback_time = time.time()

        # Thresholds
        self.warning_threshold = 50
        self.critical_threshold = 100

        self.last_memory_mb = 0.0

    # -------------------------
    # FAT push
    # -------------------------
    async def push_to_fat(self, entry):
        await self.fat_queue.put(entry)

    # -------------------------
    # Watchdog hook
    # -------------------------
    def _on_watchdog_event(self, packet):
        self.device_log.append((time.time(), packet))

    # -------------------------
    # Playback controls
    # -------------------------
    def pause_playback(self): self.playback_paused = True
    def resume_playback(self): self.playback_paused = False
    def rewind_playback(self, steps=10):
        self.playback_index = max(0, self.playback_index - steps)
    def fast_forward_playback(self, steps=10):
        self.playback_index = min(len(self.memory_log) - 1, self.playback_index + steps)
    def set_playback_speed(self, speed):
        self.playback_speed = max(0.01, speed)

    # -------------------------
    # State access (HUD)
    # -------------------------
    def get_current_state(self):
        if not self.memory_log:
            return 0, {}, {}

        idx = self.playback_index if self.playback_mode else -1
        mem = self.memory_log[idx][1]
        channels = {ch: self.channel_log[ch][idx][1] for ch in self.channels}
        devices = self.device_log[idx][1] if self.device_log else {}

        return mem, channels, devices



        # Watchdog controls
        self.hud_watchdog = HUDWatchdogControls(self.device_manager)

        # -------------------------
        # HUD overlay + GUI
        # -------------------------
        self.hud_overlay = hud_overlay or HUDMasterOverlay(
            device_manager=device_manager,
            modem=modem,
            channels=(3, 6, 9)
        )

        # Forward watchdog events to HUD overlay
        if hasattr(self.device_manager, "watchdog"):
            self.device_manager.watchdog.register_event_callback(self.handle_watchdog_event)

        # Master GUI for playback/live control
        self.hud_gui = HUDMasterGUI(self.hud_overlay)

        # -------------------------
        # Refactored live GUI modules
        # -------------------------
        self.gui_playback = HUDGUIPlayback(self.hud_gui)
        self.gui_live = HUDGUILive(self.hud_gui, None)  # handshake_manager optional for HUDGUILive
        self.gui_live_events = HUDGUILiveEvents(self.hud_gui, None)  # handshake_manager optional

        # -------------------------
        # Qbit Aggregator
        # -------------------------
        self.qbit_aggregator = QbitAggregator(
            device_manager=device_manager,
            modem=modem,
            hud_overlay=self.hud_overlay
        )

        # -------------------------
        # Device-level HUD modules
        # -------------------------
        self.per_device = HUDQbitPerDevice(self.hud_overlay, device_manager)
        self.autobalance = HUDQbitAutobalance(self.hud_overlay, device_manager)
        self.alerts = HUDQbitAlerts(self.hud_overlay, device_manager)
        self.memory_overlay = HUDMemoryOverlayQbit(self.hud_overlay, device_manager)
        self.memory_overlay_dynamic = HUDMemoryOverlayQbitDynamic(self.hud_overlay, device_manager)

        # -------------------------
        # Orchestrator HUD modules
        # -------------------------
        self.orch_qbit_hud = OrchestratorQbitHUD(self.hud_overlay, self.qbit_aggregator)
        self.orch_qbit_dynamic = OrchestratorQbitDynamic(self.hud_overlay, self.qbit_aggregator)
        self.orch_master_hud = OrchestratorMasterHUD(self.hud_overlay)
        self.orch_playback = OrchestratorPlayback(self.hud_gui)

        # -------------------------
        # Wire pipeline
        # -------------------------
        self.wire_pipeline()
        self.running = True

    # -------------------------
    # Connect all modules
    # -------------------------
    def wire_pipeline(self):
        # Qbit aggregator → HUD → FAT
        self.qbit_aggregator.set_fat_queue(self.fat_queue)
        self.qbit_aggregator.set_hud_overlay(self.hud_overlay)

        # Device control → Qbit aggregator
        self.per_device.set_aggregator(self.qbit_aggregator)
        self.autobalance.set_aggregator(self.qbit_aggregator)
        self.alerts.set_aggregator(self.qbit_aggregator)

        # Memory overlays → HUD overlay
        self.memory_overlay.set_hud_overlay(self.hud_overlay)
        self.memory_overlay_dynamic.set_hud_overlay(self.hud_overlay)

        # Orchestrator HUD → HUD overlay
        self.orch_qbit_hud.set_hud_overlay(self.hud_overlay)
        self.orch_qbit_dynamic.set_hud_overlay(self.hud_overlay)
        self.orch_master_hud.set_hud_overlay(self.hud_overlay)

        # Playback / live modules → HUD GUI
        self.gui_playback.set_gui(self.hud_gui)

        logger.info("[SEEDPipeline] Modules wired successfully")

    # -------------------------
    # Async push to FAT
    # -------------------------
    async def push_to_fat(self, entry):
        await asyncio.to_thread(self.fat_queue.put_nowait, entry)

    # -------------------------
    # Forward Watchdog events to HUD overlay
    # -------------------------
    def handle_watchdog_event(self, packet):
        if hasattr(self.hud_overlay, "handle_watchdog_event"):
            self.hud_overlay.handle_watchdog_event(packet)

    # -------------------------
    # HUD update loop (optional if using .after() in GUI)
    # -------------------------
    def hud_update_loop(self):
        while self.running:
            self.hud_overlay.update()
            self.hud_gui.update()
            time.sleep(0.05)

    # -------------------------
    # Start all loops
    # -------------------------
    def start(self):
        threading.Thread(target=self.hud_update_loop, daemon=True).start()
        logger.info("[SEEDPipeline] HUD update loop started")

    # -------------------------
    # Stop pipeline
    # -------------------------
    def stop(self):
        self.running = False
        logger.info("[SEEDPipeline] Stopped all modules and loops")
