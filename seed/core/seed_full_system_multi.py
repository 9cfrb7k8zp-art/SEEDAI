# ==========================================================
# FILE: seed_full_system_multi.py
# PATH: SEED_ROOT/seed/core/seed_full_system_multi.py
# MODULE: Full SEED AI OS Integration — Multi-Device Handshake + ChannelID
# PURPOSE: Simulate multiple devices, each with unique ChannelID, TrackID & HUD ID
# AUTHOR: Oracle / Carlos A. Clarke
# UPDATED: 2025-12-31
# ==========================================================

import time
import logging
import threading
import asyncio
import uuid
from queue import Queue

# -------------------- Core Modules --------------------
from seed.core.drive import Drive, TrackContext
from seed.core.nlp_interface import NLPInterface
from seed.core.qbit_dialer import QbitDialer
from seed.core.seed_core_controller import SEEDCoreController
from seed.core.track_system import TrackSystem
from seed.core.seed_handshake_manager import SEEDHandshakeManager

# -------------------- Logging Setup --------------------
logging.basicConfig(
    format='[%(asctime)s] %(name)s | %(levelname)s | %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("SEEDFullSystemMulti")

# -------------------- Dummy UI --------------------
class DummyUI:
    def log(self, msg):
        print(msg)

    def receive_ai_thought(self, packet):
        print(f"[UI] Received Thought: {packet}")

# -------------------- Helpers --------------------
def generate_hud_id():
    return f"HUD-{str(uuid.uuid4())[:8]}"

def generate_channel_id(device_index=0):
    return f"AI_SIDE_{device_index}"

def track_and_tag_packet(state: str, metadata: dict):
    """Create a tracked data packet with Level-4 authority"""
    track_id = TrackSystem.push_tracked_data(
        channel=metadata.get("channel_id", "AI_SIDE"),
        state=state,
        priority=metadata.get("priority", "MED"),
        skill=metadata.get("skill"),
        agent_subclass=metadata.get("agent_subclass"),
        actuator_bridge=metadata.get("actuator_bridge", False),
        metadata=metadata
    )
    metadata["track_id"] = track_id
    metadata["hud_id"] = generate_hud_id()
    metadata["channel_id"] = metadata.get("channel_id", generate_channel_id())
    return metadata

# -------------------- Multi-Device Setup --------------------
def setup_multi_device_system(device_count=3):
    logger.info(f"Initializing SEED system with {device_count} devices...")

    # Core Controller
    controller = SEEDCoreController(interval=0.05)

    # Drive (AI thought connector)
    drive_ui = DummyUI()
    drive = Drive(ui=drive_ui, log_func=lambda m: print(f"[Drive] {m}"))
    if hasattr(controller, "qbit_dialer") and controller.qbit_dialer:
        drive.qbit_dialer = controller.qbit_dialer

    # NLP Interface feeding Drive and QbitDialer
    nlp = NLPInterface(agent_manager=None, analytics_engine=None)

    # Multi-device Handshake
    devices = []
    for i in range(device_count):
        class DummyModem:
            def __init__(self):
                self.rx_queue = Queue()
            def tx(self, frame):
                logger.info(f"[Device {i}] TX frame sent")

        modem = DummyModem()
        handshake = SEEDHandshakeManager(
            modem,
            event_bus=controller.event_bus,
            qbit_dialer=controller.qbit_dialer
        )

        # Override emit to include Level-4 tracking & system tags
        original_emit = handshake._emit_qbit
        def tracked_emit(kind, payload, track, device_index=i):
            payload["channel_id"] = generate_channel_id(device_index)
            payload["hud_id"] = generate_hud_id()
            payload["track_id"] = track.get("track_id") if isinstance(track, dict) else track
            track_and_tag_packet(kind, payload)
            original_emit(kind, payload, track)

        handshake._emit_qbit = tracked_emit
        handshake.start()
        devices.append(handshake)

    # Hook NLP output to Drive with Level-4 tracking
    def nlp_to_drive(obs_text):
        for idx, _ in enumerate(devices):
            metadata = {
                "text": f"NLP Observation from device {idx}: {obs_text}",
                "source": "NLP",
                "priority": 1,
                "channel_id": generate_channel_id(idx)
            }
            packet = track_and_tag_packet("NLP_OBSERVATION", metadata)
            drive.send_thought(packet)

            # Emit Qbit for each device
            if drive.qbit_dialer:
                qbit_payload = {
                    "text": obs_text,
                    "source": "NLP",
                    "track_id": packet["track_id"],
                    "channel_id": packet["channel_id"],
                    "hud_id": packet["hud_id"]
                }
                if hasattr(drive.qbit_dialer, "submit_qbit"):
                    drive.qbit_dialer.submit_qbit(qbit_payload)

    nlp.listen = lambda: nlp_to_drive("Sample multi-device observation")

    return controller, drive, nlp, devices

# -------------------- Run Full Multi-Device System --------------------
if __name__ == "__main__":
    controller, drive, nlp, devices = setup_multi_device_system(device_count=3)

    try:
        controller.start()

        # Simulate NLP observations
        for _ in range(5):
            nlp.listen()
            time.sleep(0.5)

        # Inject direct Drive thought with multi-device tagging
        for idx in range(len(devices)):
            metadata = {
                "text": f"Direct thought from main loop for device {idx}",
                "source": "SYSTEM",
                "priority": 0,
                "channel_id": generate_channel_id(idx)
            }
            packet = track_and_tag_packet("DRIVE_THOUGHT", metadata)
            drive.send_thought(packet)

        logger.info("SEED multi-device system running with ChannelID, TrackID, HUD ID, and Handshake. Press Ctrl+C to stop...")

        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Shutting down SEED multi-device system...")
        drive.shutdown()
        controller.stop()
        logger.info("SEED multi-device system fully stopped.")
