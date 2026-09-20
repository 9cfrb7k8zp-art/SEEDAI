# =====================================================
# FILE: SEEDPipeline.py
# PATH: SEED_ROOT/seed/core/pipeline/SEEDPipeline.py
# VERSION: 1.2 – Track ID + async FAT + HUD update
# Updated: SEEDCore → ActuatorEngine integration + track_id
# =====================================================

import asyncio
import time
import threading
import logging
import traceback
import uuid

from seed.core.device_manager import DeviceManager
from seed.core.modem_controller import SEEDModemController
from seed.ui.hud_master_gui import HUDMasterGUI
from seed.core.hud_master_overlay import HUDMasterOverlay

# Qbit modules
from seed.core.qbit_aggregator import QbitAggregator
from seed.core.hud_qbit_per_device import HUDQbitPerDevice
from seed.core.hud_qbit_autobalance import HUDQbitAutoBalance
from seed.core.hud_qbit_alerts import HUDQbitChannelAlerts as HUDQbitAlerts
from seed.core.hud_memory_overlay_qbit import HUDMemoryOverlayQbit
from seed.core.hud_memory_overlay_qbit_dynamic import HUDMemoryOverlayQbitDynamic

# HUD GUI modules
from seed.ui.hud_gui_playback import HUDGUIPlayback
from seed.ui.hud_gui_live import HUDGUILive
from seed.ui.hud_gui_live_events import HUDGUILiveEvents

# Orchestrator HUD modules
from seed.core.orchestrator_qbit_hud import SEEDOrchestratorQbitHUD
from seed.core.orchestrator_qbit_dynamic import SEEDOrchestratorQbitDynamicHUD
from seed.core.orchestrator_master_hud import SEEDOrchestratorMasterHUD
from seed.core.orchestrator_playback import SEEDOrchestratorPlayback

# Actuator Integration
from seed.core.actuator_engine import ActuatorEngine
from seed.core.integration.seed_core_integration import SEEDCoreActuatorBridge

logger = logging.getLogger("SEEDPipeline")
logging.basicConfig(level=logging.INFO)


def trace_error(exc: Exception):
    tb = exc.__traceback__
    while tb:
        frame = tb.tb_frame
        lineno = tb.tb_lineno
        filename = frame.f_code.co_filename
        funcname = frame.f_code.co_name
        exc_type = type(exc).__name__
        exc_msg = str(exc)
        logger.error(f"[TRACE] Exception in file '{filename}', function '{funcname}', line {lineno}:\n  {exc_type}: {exc_msg}")
        tb = tb.tb_next


def gen_track_id(prefix="SEEDPIPE"):
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


class SEEDPipeline:


    def __init__(self, fat_queue, device_manager, modem, qbit_dialer, seed_core):
        self.fat_queue = fat_queue
        self.device_manager = device_manager
        self.modem = modem
        self.qbit_dialer = qbit_dialer
        self.seed_core = seed_core
        self.running = False

        # HUD overlay + GUI
        try:
            self.hud_overlay = HUDMasterOverlay(
                device_manager=device_manager,
                modem=modem,
                channels=(3, 6, 9)
            )
            self.hud_gui = HUDMasterGUI(self.hud_overlay)
            logger.info("[SEEDPipeline] HUD overlay and GUI initialized")
        except Exception as e:
            trace_error(e)
            self.hud_overlay = None
            self.hud_gui = None
            logger.warning("[SEEDPipeline] HUD overlay/GUI failed to initialize")

        # Qbit Aggregator
        try:
            self.qbit_aggregator = QbitAggregator(
                device_manager=device_manager,
                modem=modem,
                qbit_dialer=qbit_dialer
            )
            if self.hud_overlay:
                self.qbit_aggregator.set_hud_overlay(self.hud_overlay)
            if self.fat_queue:
                self.qbit_aggregator.set_fat_queue(self.fat_queue)
            logger.info("[SEEDPipeline] QbitAggregator initialized")
        except Exception as e:
            trace_error(e)
            self.qbit_aggregator = None
            logger.warning("[SEEDPipeline] QbitAggregator failed to initialize")

        # Device-level HUD modules
        try:
            self.per_device = HUDQbitPerDevice(self.hud_overlay, device_manager)
            self.autobalance = HUDQbitAutoBalance(self.hud_overlay, device_manager)
            self.alerts = HUDQbitAlerts(self.hud_overlay, device_manager)
            self.memory_overlay = HUDMemoryOverlayQbit(self.hud_overlay, device_manager)
            self.memory_overlay_dynamic = HUDMemoryOverlayQbitDynamic(self.hud_overlay, device_manager)
            logger.info("[SEEDPipeline] Device-level HUD modules initialized")
        except Exception as e:
            trace_error(e)
            self.per_device = None
            self.autobalance = None
            self.alerts = None
            self.memory_overlay = None
            self.memory_overlay_dynamic = None
            logger.warning("[SEEDPipeline] Device HUD modules failed to initialize")

        # Playback / live modules
        try:
            self.gui_playback = HUDGUIPlayback(self.hud_gui)
            self.gui_live = HUDGUILive(self.hud_gui)
            self.gui_live_events = HUDGUILiveEvents(self.hud_gui)
            logger.info("[SEEDPipeline] Playback/live modules initialized")
        except Exception as e:
            trace_error(e)
            self.gui_playback = None
            self.gui_live = None
            self.gui_live_events = None
            logger.warning("[SEEDPipeline] Playback/live modules failed to initialize")

        # Orchestrator HUD modules
        try:
            self.orch_qbit_hud = SEEDOrchestratorQbitHUD(self.hud_overlay, self.qbit_aggregator)
            self.orch_qbit_dynamic = SEEDOrchestratorQbitDynamicHUD(self.hud_overlay, self.qbit_aggregator)
            self.orch_master_hud = SEEDOrchestratorMasterHUD(self.hud_overlay)
            self.orch_playback = SEEDOrchestratorPlayback(self.hud_gui)
            logger.info("[SEEDPipeline] Orchestrator HUD modules initialized")
        except Exception as e:
            trace_error(e)
            self.orch_qbit_hud = None
            self.orch_qbit_dynamic = None
            self.orch_master_hud = None
            self.orch_playback = None
            logger.warning("[SEEDPipeline] Orchestrator HUD modules failed to initialize")

        # ActuatorEngine & SEEDCore bridge
        try:
            self.actuator_engine = ActuatorEngine(fat_layer=None, hud_interface=self.hud_overlay)
            self.seed_actuator_bridge = SEEDCoreActuatorBridge(seed_core=self.seed_core,
                                                               actuator_engine=self.actuator_engine,
                                                               update_interval=0.05)
            self._bridge_task = asyncio.create_task(self.seed_actuator_bridge.run_loop())
            logger.info("[SEEDPipeline] SEEDCore → ActuatorEngine bridge initialized")
        except Exception as e:
            trace_error(e)
            self.actuator_engine = None
            self.seed_actuator_bridge = None
            logger.warning("[SEEDPipeline] Actuator bridge failed to initialize")

        # Wire pipeline
        self.wire_pipeline()

    # -------------------------
    # Connect all modules safely
    # -------------------------
    def wire_pipeline(self):
        try:
            for module in [self.per_device, self.autobalance, self.alerts]:
                if module and hasattr(module, 'set_aggregator'):
                    module.set_aggregator(self.qbit_aggregator)

            for module in [self.memory_overlay, self.memory_overlay_dynamic]:
                if module and hasattr(module, 'set_hud_overlay'):
                    module.set_hud_overlay(self.hud_overlay)

            for module in [self.orch_qbit_hud, self.orch_qbit_dynamic, self.orch_master_hud]:
                if module and hasattr(module, 'set_hud_overlay'):
                    module.set_hud_overlay(self.hud_overlay)

            for module in [self.gui_playback, self.gui_live, self.gui_live_events]:
                if module and hasattr(module, 'set_gui'):
                    module.set_gui(self.hud_gui)

            logger.info("[SEEDPipeline] Modules wired successfully")
        except Exception as e:
            trace_error(e)
            logger.warning("[SEEDPipeline] Pipeline wiring failed")

    # -------------------------
    # Async push to FAT with track_id
    # -------------------------
    async def push_to_fat(self, entry):
        entry = dict(entry)  # copy
        entry["track_id"] = entry.get("track_id", gen_track_id())
        if self.fat_queue:
            try:
                await asyncio.to_thread(self.fat_queue.put_nowait, entry)
            except Exception as e:
                trace_error(e)
        else:
            logger.warning("[SEEDPipeline] FAT queue not set, entry dropped")

    # -------------------------
    # HUD update loop
    # -------------------------
    def hud_update_loop(self):
        self.running = True
        while self.running:
            try:
                if self.hud_overlay:
                    overlay_entry = {"update": True, "timestamp": time.time(), "track_id": gen_track_id()}
                    self.hud_overlay.update(overlay_entry)
                if self.hud_gui:
                    self.hud_gui.update()
                time.sleep(0.05)
            except Exception as e:
                trace_error(e)

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
        if self.seed_actuator_bridge:
            self.seed_actuator_bridge.stop()
        logger.info("[SEEDPipeline] Stopped all modules and loops")
