# ==========================================================
# FILE: seed_full_system.py
# PATH: SEED_ROOT/seed/core/seed_full_system.py
# MODULE: Full SEED AI OS Integration with TrackID, ChannelID & Handshake
# PURPOSE: Fully integrated Drive + NLP + Qbit + Core Controller + Handshake
#          Level-4 tracking, self-healing, and system tagging
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
logger = logging.getLogger("SEEDFullSystem")

# -------------------- Dummy UI --------------------
class StartUI:
    def log(self, msg):
        print(msg)

    def receive_ai_thought(self, packet):
        print(f"[UI] Received Thought: {packet}")

# -------------------- Helpers --------------------
def generate_hud_id():
    return f"HUD-{str(uuid.uuid4())[:8]}"

def generate_channel_id():
    return "AI_SIDE"

def track_and_tag_packet(state: str, metadata: dict):
    track_id = TrackSystem.push_tracked_data(
        channel=generate_channel_id(),
        state=state,
        priority=metadata.get("priority", "MED"),
        skill=metadata.get("skill"),
        agent_subclass=metadata.get("agent_subclass"),
        actuator_bridge=metadata.get("actuator_bridge", False),
        metadata=metadata
    )
    metadata["track_id"] = track_id
    metadata["hud_id"] = generate_hud_id()
    metadata["channel_id"] = generate_channel_id()
    return metadata

# -------------------- System Setup --------------------
def setup_seed_system():
    logger.info("Initializing full SEED system with Level-4 tracking and Handshake...")

    # Core Controller with internal EventBus
    controller = SEEDCoreController(interval=0.05)

    # Drive (AI thought connector)
    drive_ui = DummyUI()
    drive = Drive(ui=drive_ui, log_func=lambda m: print(f"[Drive] {m}"))

    # Link QbitDialer
    if hasattr(controller, "qbit_dialer") and controller.qbit_dialer:
        drive.qbit_dialer = controller.qbit_dialer

    # NLP Interface feeding Drive and QbitDialer
    nlp = NLPInterface(agent_manager=None, analytics_engine=None)

    # Hook NLP output to Drive with Level-4 tracking
    def nlp_to_drive(obs_text):
        metadata = {
            "text": f"NLP Observation: {obs_text}",
            "source": "NLP",
            "priority": 1
        }

        # Apply Level-4 tracking
        packet = track_and_tag_packet("NLP_OBSERVATION", metadata)

        # Send to Drive
        drive.send_thought(packet)

        # Emit Qbit
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

    nlp.listen = lambda: nlp_to_drive("Sample NLP observation")

    # -------------------- Handshake Manager --------------------
    class DummyModem:
        def __init__(self):
            self.rx_queue = Queue()

        def tx(self, frame):
            pass

    modem = DummyModem()
    handshake = SEEDHandshakeManager(modem, event_bus=controller.event_bus, qbit_dialer=controller.qbit_dialer)

    # Override emit to include Level-4 tracking & system tags
    original_emit = handshake._emit_qbit
    def tracked_emit(kind, payload, track):
        packet = {
            **payload,
            "kind": kind,
            "track_id": track.get("track_id") if isinstance(track, dict) else track,
            "channel_id": generate_channel_id(),
            "hud_id": generate_hud_id()
        }
        track_and_tag_packet(kind, packet)
        original_emit(kind, packet, track)
    handshake._emit_qbit = tracked_emit

    # Start handshake processing
    handshake.start()

    return controller, drive, nlp, handshake

# -------------------- Run Full System --------------------
if __name__ == "__main__":
    controller, drive, nlp, handshake = setup_seed_system()

    try:
        # Start SEED Core
        controller.start()

        # Test NLP observations feeding Drive and Qbit
        for _ in range(5):
            nlp.listen()
            time.sleep(0.5)

        # Test Drive direct thought injection with Level-4 tracking
        metadata = {
            "text": "Direct thought test from main loop",
            "source": "SYSTEM",
            "priority": 0
        }
        packet = track_and_tag_packet("DRIVE_THOUGHT", metadata)
        drive.send_thought(packet)

        logger.info("SEED system running with Level-4 tracking, ChannelID, TrackID, HUD ID tags, and Handshake. Press Ctrl+C to stop...")

        # Keep main loop alive while SEED processes
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Shutting down SEED system...")
        drive.shutdown()
        controller.stop()
        logger.info("SEED system fully stopped.")
