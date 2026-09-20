# ==========================================================
# SEED HANDSHAKE PROTOCOL
# Device Discovery + Trust Establishment
# ==========================================================

import time
import uuid
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("SEEDHandshake")


HANDSHAKE_MAGIC = "SEED-HS"
HANDSHAKE_TIMEOUT = 5.0


@dataclass
class HandshakePacket:
    device_id: str
    device_name: str
    capabilities: list
    timestamp: float
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex)

    def serialize(self):
        return {
            "magic": HANDSHAKE_MAGIC,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "capabilities": self.capabilities,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }

    @staticmethod
    def validate(packet: dict):
        return (
            isinstance(packet, dict)
            and packet.get("magic") == HANDSHAKE_MAGIC
            and "device_id" in packet
            and "timestamp" in packet
        )
# ==========================================================
# SEED HANDSHAKE PROTOCOL
# ==========================================================

import time
import uuid
import hashlib

HANDSHAKE_FREQS = {
    "PING": 18.0,
    "ACK": 22.0,
    "LOCK": 26.0,
}

HANDSHAKE_TIMEOUT = 3.0


def generate_device_id():
    raw = f"{uuid.getnode()}-{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class HandshakePacket:
    def __init__(self, kind, device_id, timestamp=None):
        self.kind = kind
        self.device_id = device_id
        self.timestamp = timestamp or time.time()

    def to_payload(self):
        return {
            "kind": self.kind,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_payload(payload):
        return HandshakePacket(
            payload.get("kind"),
            payload.get("device_id"),
            payload.get("timestamp"),
        )


class SEEDHandshakeManager:
    """
    Handles discovery and trust establishment
    """

    def __init__(self, modem, device_manager, event_bus=None):
        self.modem = modem
        self.device_manager = device_manager
        self.event_bus = event_bus

        self.active_sessions = {}
        self.last_broadcast = 0

        logger.info("[HANDSHAKE] Manager initialized")

    # ======================================================
    # BROADCAST
    # ======================================================
    def broadcast_identity(self):
        now = time.time()
        if now - self.last_broadcast < 2:
            return

        packet = HandshakePacket(
            device_id=self.device_manager.local_device_id,
            device_name=self.device_manager.local_device_name,
            capabilities=self.device_manager.capabilities,
            timestamp=now,
        )

        frame = self.modem.encode(packet.serialize())
        self.modem.tx(frame)

        self.last_broadcast = now
        logger.info("[HANDSHAKE] Identity broadcast")

    # ======================================================
    # RECEIVE
    # ======================================================
    def handle_incoming(self, frame):
        payload = frame.payload

        if not HandshakePacket.validate(payload):
            return

        device_id = payload["device_id"]

        if device_id == self.device_manager.local_device_id:
            return  # ignore self

        now = time.time()
        self.active_sessions[device_id] = now

        if not self.device_manager.has_device(device_id):
            self.device_manager.register_device(
                device_id=device_id,
                name=payload.get("device_name", "Unknown"),
                capabilities=payload.get("capabilities", []),
                transport="audio",
            )
            logger.info(f"[HANDSHAKE] New device discovered: {device_id}")

            if self.event_bus:
                self.event_bus.emit(
                    "DEVICE_DISCOVERED",
                    payload={"device_id": device_id},
                )

    # ======================================================
    # CLEANUP
    # ======================================================
    def prune(self):
        now = time.time()
        for dev, ts in list(self.active_sessions.items()):
            if now - ts > HANDSHAKE_TIMEOUT:
                del self.active_sessions[dev]
