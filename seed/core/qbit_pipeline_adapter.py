# ==========================================================
# FILE: qbit_pipeline_adapter.py
# PATH: SEED_ROOT/seed/core/qbit_pipeline_adapter.py
# SEED Qbit Pipeline Adapter v2.3
# PURPOSE:
#   - Connect Camera, Audio, Qbit, seedemqbit, AnalyticsEngine, Fusion → HUD + FAT
#   - Supports QbitDialer and module wiring
#   - Async-safe processing with threads
#   - Track ID system fully integrated
#   - Device/channel aware for multi-device pipelines
# ==========================================================

import time
import asyncio
import logging
from threading import Thread
import uuid

logger = logging.getLogger("QbitPipelineAdapter")
logging.basicConfig(level=logging.INFO)

from seed.core.device import DeviceManager  # Ensure DeviceManager is integrated
from seed.core.qbit_dialer import QbitDialer
from seed.core.seed_camera_qbit import SEEDCameraQbit
from seed.core.analytics_engine import SEEDAnalyticsEngine, AnalyticsFusionEngine

# ==========================================================
# Track ID Generator
# ==========================================================
def gen_track_id(prefix="QPIPE", device=None, channel=None):
    """Generate a unique Track ID for packets/events with optional device/channel tagging"""
    tag = f"{device.device_id}" if device else (channel or "GEN")
    return f"{prefix}-{tag}-{str(uuid.uuid4())[:8]}"

# ==========================================================
# Wire Qbit Pipeline
# ==========================================================
def wire_qbit_pipeline(fat_queue, hud_overlay, device_manager=None, modem=None, qbit_dialer=None):
    """
    Wires the following pipeline safely:

        Camera / Audio Input → SEEDCameraQbit → SEEDAnalyticsEngine → AnalyticsFusionEngine → QbitDialer → FAT → HUDOverlay

    Features:
    - Robust handling for camera failures
    - Async-safe FAT queue
    - Track ID propagation across all modules
    - Device/channel aware
    """
    modules = {}

    # -----------------------------
    # Initialize DeviceManager and Modem
    # -----------------------------
    if device_manager is None:
        device_manager = DeviceManager()
    if modem is None:
        modem = None  # Replace with actual SEEDModemController if needed

    # -----------------------------
    # Initialize Qbit Dialer
    # -----------------------------
    if qbit_dialer is None:
        qbit_dialer = QbitDialer(storage_root=None, event_bus=None)
    modules['qbit_dialer'] = qbit_dialer
    logger.info("[PIPELINE] QbitDialer initialized")

    # -----------------------------
    # Initialize Camera Qbit with Safe Loop + TrackID
    # -----------------------------
    try:
        camera_qbit = SEEDCameraQbit(qbit_dialer=qbit_dialer, event_bus=None)

        def safe_loop(self):
            while self.running:
                for cam_id, cap in list(self.cameras.items()):
                    try:
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            self._health[cam_id] *= 0.9
                            self._emit_warning(cam_id)
                            try:
                                cap.release()
                                for backend in self.backends:
                                    new_cap = self._safe_videocapture(int(cam_id.split("_")[1]), backend)
                                    if new_cap and new_cap.isOpened():
                                        self.cameras[cam_id] = new_cap
                                        logger.info(f"[SEEDCameraQbit] Reopened camera: {cam_id} via backend {backend}")
                                        break
                                    if new_cap:
                                        new_cap.release()
                                if new_cap is None or not new_cap.isOpened():
                                    logger.warning(f"[SEEDCameraQbit] Camera {cam_id} still unavailable, will retry next loop")
                            except Exception as e:
                                logger.warning(f"[SEEDCameraQbit] Retry failed for camera {cam_id}: {e}")
                            continue

                        # Device-aware Track ID
                        device = device_manager.get_device_by_name(cam_id)
                        channel = device.channels[0] if device else None
                        track_id = gen_track_id("CAM", device=device, channel=channel)

                        self._process_frame(cam_id, frame, track_id=track_id)

                    except Exception as e:
                        logger.warning(f"[SEEDCameraQbit] Camera loop error {cam_id}: {e}")
                time.sleep(0.03)

        camera_qbit._loop = safe_loop.__get__(camera_qbit, SEEDCameraQbit)
        modules['camera_qbit'] = camera_qbit
        logger.info("[PIPELINE] SEEDCameraQbit initialized with safe loop")

    except Exception as e:
        logger.error(f"[PIPELINE] Failed to initialize Camera Qbit: {e}")
        return modules  # Return partial modules to avoid full crash

    # -----------------------------
    # Analytics Engine
    # -----------------------------
    analytics_engine = SEEDAnalyticsEngine()
    modules['analytics_engine'] = analytics_engine
    logger.info("[PIPELINE] SEEDAnalyticsEngine initialized")

    # -----------------------------
    # Analytics Fusion Engine
    # -----------------------------
    fusion_engine = AnalyticsFusionEngine()
    modules['fusion_engine'] = fusion_engine
    logger.info("[PIPELINE] AnalyticsFusionEngine initialized")

    # -----------------------------
    # Camera Callback with TrackID propagation
    # -----------------------------
    def camera_callback(packet):
        try:
            device_name = packet.get("device_name")
            device = device_manager.get_device_by_name(device_name)
            channel = device.channels[0] if device else None

            packet["track_id"] = packet.get("track_id") or gen_track_id("CB", device=device, channel=channel)
            packet["trust"] = getattr(packet, "trust", 1.0)

            # Analytics ingestion
            analytics_engine.ingest_qbit(packet)
            packet["confidence"] *= packet.get("trust", 1.0)

            # Fusion ingestion
            fusion_engine.ingest_insight(packet)

            # Push to Qbit Dialer
            qbit_dialer.push_data(packet)

            # Push to FAT queue safely
            try:
                asyncio.get_running_loop().call_soon_threadsafe(fat_queue.put_nowait, packet)
            except RuntimeError:
                Thread(target=lambda: asyncio.run(fat_queue.put(packet)), daemon=True).start()

        except Exception as e:
            logger.warning(f"[PIPELINE] Camera callback error: {e}")

    camera_qbit.add_qbit_callback(camera_callback)

    # -----------------------------
    # HUD Modules Wiring (Device-aware)
    # -----------------------------
    try:
        from seed.core.hud_modules import (
            QbitAggregator,
            HUDQbitPerDevice,
            HUDQbitAutoBalance,
            HUDMemoryOverlayQbit
        )

        aggregator = QbitAggregator(device_manager=device_manager, modem=modem, qbit_dialer=qbit_dialer)
        aggregator.set_hud_overlay(hud_overlay)
        aggregator.set_fat_queue(fat_queue)
        modules['aggregator'] = aggregator

        per_device = HUDQbitPerDevice(hud_overlay, device_manager)
        per_device.set_aggregator(aggregator)
        modules['per_device'] = per_device

        autobalance = HUDQbitAutoBalance(hud_overlay, device_manager)
        autobalance.set_aggregator(aggregator)
        modules['autobalance'] = autobalance

        memory_overlay = HUDMemoryOverlayQbit(hud_overlay, device_manager)
        modules['memory_overlay'] = memory_overlay

        logger.info("[PIPELINE] HUD Qbit modules wired successfully")

    except Exception as e:
        logger.warning("[PIPELINE] Failed to wire HUD Qbit modules")
        logger.error(e)

    # -----------------------------
    # Start modules safely
    # -----------------------------
    try:
        camera_qbit.start()
        analytics_engine.start_async()
        fusion_engine.start_async()
        logger.info("[PIPELINE] Camera → Analytics → Fusion → Qbit → FAT → HUD pipeline started")
    except Exception as e:
        logger.error(f"[PIPELINE] Failed to start pipeline: {e}")

    return modules
