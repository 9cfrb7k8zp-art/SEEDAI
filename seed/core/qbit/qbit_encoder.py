# ==========================================================
# FILE: qbit_encoder.py
# PATH: SEED_ROOT/seed/core/qbit/qbit_encoder.py
#
# SYSTEM: SEED AI OS
# COMPONENT: QbitEncoder
# VERSION: 2.0.0
#
# BUILD:
#   CANONICAL-QBIT
#   DIALER-SAFE
#   QUEUE-SAFE
#   HEARTBEAT-AWARE
#   TRACK-SAFE
#   DETERMINISTIC-FRAME
#
# PURPOSE:
#
#   Serialize canonical Qbit runtime data into a compact binary
#   frame suitable for:
#
#       Qbit
#          |
#          v
#       QbitDialer
#          |
#          v
#       QbitQueueLoop
#          |
#          v
#       QbitEncoder
#
# HeartbeatEmitter does NOT become encoded command work.
#
# Heartbeat may provide runtime/health metadata when explicitly
# supplied by the Dialer, but the encoder never manufactures
# heartbeat commands.
#
# ==========================================================


import hashlib
import json
import struct
import time
from typing import Any, Dict, Optional


# ==========================================================
# CONSTANTS
# ==========================================================

ENCODER_VERSION = 2

MAGIC = b"QBIT"

# magic
# version
# intent hash
# timestamp
# metadata size
HEADER_FORMAT = "!4s I I d I"

HEADER_SIZE = struct.calcsize(
    HEADER_FORMAT
)


# ==========================================================
# QBIT ENCODER
# ==========================================================

class QbitEncoder:
    def __init__(
        self,
        qbit_dialer=None,
        qbit_queue_loop=None,
        heartbeat_emitter=None,
        track_system=None,
        logger=None,
    ):
        self.qbit_dialer = qbit_dialer
        self.qbit_queue_loop = qbit_queue_loop
        self.heartbeat_emitter = heartbeat_emitter
        self.track_system = track_system

        self.logger = logger

        self.enabled = True

        self.last_encoded = None
        self.last_timestamp = None
        self.encode_count = 0

        self._log(
            "INFO",
            "[QbitEncoder] initialized"
        )

    # ======================================================
    # LOGGING
    # ======================================================

    def _log(
        self,
        level,
        message,
        *args,
    ):
        try:

            if self.logger is not None:

                method = getattr(
                    self.logger,
                    level.lower(),
                    None,
                )

                if callable(method):

                    method(
                        message,
                        *args,
                    )

                    return

            print(
                message
                % args
                if args
                else message
            )

        except Exception:
            pass

    # ======================================================
    # DEPENDENCY ATTACHMENT
    # ======================================================

    def attach_runtime(
        self,
        qbit_dialer=None,
        qbit_queue_loop=None,
        heartbeat_emitter=None,
        track_system=None,
    ):
        if qbit_dialer is not None:

            self.qbit_dialer = qbit_dialer

        if qbit_queue_loop is not None:

            self.qbit_queue_loop = qbit_queue_loop

        if heartbeat_emitter is not None:

            self.heartbeat_emitter = heartbeat_emitter

        if track_system is not None:

            self.track_system = track_system

        self._log(
            "INFO",
            "[QbitEncoder] runtime dependencies attached | "
            "dialer=%s | queue=%s | heartbeat=%s | track=%s",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer is not None
            else "NONE",

            type(self.qbit_queue_loop).__name__
            if self.qbit_queue_loop is not None
            else "NONE",

            type(self.heartbeat_emitter).__name__
            if self.heartbeat_emitter is not None
            else "NONE",

            type(self.track_system).__name__
            if self.track_system is not None
            else "NONE",
        )

        return True

    # ======================================================
    # QBIT VALUE EXTRACTION
    # ======================================================

    def _extract_value(
        self,
        qbit,
        name,
        default=None,
    ):

        if qbit is None:
            return default

        # Dictionary
        if isinstance(
            qbit,
            dict,
        ):

            return qbit.get(
                name,
                default,
            )

        # Object
        try:

            value = getattr(
                qbit,
                name,
            )

            return value

        except Exception:
            return default

    # ======================================================
    # QBIT IDENTIFIER
    # ======================================================

    def get_qbit_id(
        self,
        qbit,
    ):

        qbit_id = self._extract_value(
            qbit,
            "qbit_id",
        )

        if qbit_id is None:

            qbit_id = self._extract_value(
                qbit,
                "id",
            )

        if qbit_id is None:

            qbit_id = self._extract_value(
                qbit,
                "identifier",
            )

        return (
            str(qbit_id)
            if qbit_id is not None
            else None
        )

    # ======================================================
    # INTENT
    # ======================================================

    def get_intent(
        self,
        qbit,
    ):
        intent = self._extract_value(
            qbit,
            "intent",
        )

        if intent is None:

            intent = self._extract_value(
                qbit,
                "task_name",
            )

        if intent is None:

            intent = self._extract_value(
                qbit,
                "name",
            )

        return (
            str(intent)
            if intent is not None
            else ""
        )

    # ======================================================
    # INTENT HASH
    # ======================================================

    @staticmethod
    def intent_hash(
        intent,
    ):
        digest = hashlib.sha256(
            str(intent).encode(
                "utf-8"
            )
        ).digest()

        return int.from_bytes(
            digest[:4],
            byteorder="big",
            signed=False,
        )

    # ======================================================
    # TIMESTAMP
    # ======================================================

    def get_timestamp(
        self,
        qbit,
    ):

        timestamp = self._extract_value(
            qbit,
            "timestamp",
        )

        if timestamp is None:

            timestamp = self._extract_value(
                qbit,
                "created_at",
            )

        if timestamp is None:

            timestamp = time.time()

        try:

            return float(
                timestamp
            )

        except (
            TypeError,
            ValueError,
        ):

            return time.time()

    # ======================================================
    # TRACK ID
    # ======================================================

    def get_track_id(
        self,
        qbit,
    ):

        track_id = self._extract_value(
            qbit,
            "track_id",
        )

        # --------------------------------------------------
        # Do NOT generate one.
        # --------------------------------------------------

        if track_id is None:

            return None

        return str(
            track_id
        )

    # ======================================================
    # STATE
    # ======================================================

    def get_state(
        self,
        qbit,
    ):

        state = self._extract_value(
            qbit,
            "state",
        )

        if state is None:

            state = self._extract_value(
                qbit,
                "status",
            )

        if state is None:

            state = "UNKNOWN"

        return str(
            state
        )

    # ======================================================
    # MODE
    # ======================================================

    def get_mode(
        self,
        qbit,
    ):

        mode = self._extract_value(
            qbit,
            "mode",
            "UNKNOWN",
        )

        return str(
            mode
        )

    # ======================================================
    # METADATA
    # ======================================================

    def get_metadata(
        self,
        qbit,
        metadata=None,
    ):

        source = {}

        if isinstance(
            metadata,
            dict,
        ):

            source.update(
                metadata
            )

        qbit_metadata = self._extract_value(
            qbit,
            "metadata",
            {},
        )

        if isinstance(
            qbit_metadata,
            dict,
        ):

            source.update(
                qbit_metadata
            )

        qbit_id = self.get_qbit_id(
            qbit
        )

        if qbit_id is not None:

            source.setdefault(
                "qbit_id",
                qbit_id,
            )

        track_id = self.get_track_id(
            qbit
        )

        if track_id is not None:

            source.setdefault(
                "track_id",
                track_id,
            )

        source.setdefault(
            "qbit_state",
            self.get_state(
                qbit
            ),
        )

        source.setdefault(
            "qbit_mode",
            self.get_mode(
                qbit
            ),
        )

        # --------------------------------------------------
        # Runtime authority information
        # --------------------------------------------------

        if self.qbit_dialer is not None:

            source.setdefault(
                "qbit_dialer",
                type(
                    self.qbit_dialer
                ).__name__,
            )

        if self.qbit_queue_loop is not None:

            source.setdefault(
                "qbit_queue_loop",
                type(
                    self.qbit_queue_loop
                ).__name__,
            )

        if self.heartbeat_emitter is not None:

            source.setdefault(
                "heartbeat",
                type(
                    self.heartbeat_emitter
                ).__name__,
            )

        if self.track_system is not None:

            source.setdefault(
                "track_system",
                type(
                    self.track_system
                ).__name__,
            )

        return self._json_safe(
            source
        )

    # ======================================================
    # JSON SAFE CONVERSION
    # ======================================================

    def _json_safe(
        self,
        value,
    ):

        if value is None:

            return None

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):

            return value

        if isinstance(
            value,
            dict,
        ):

            return {
                str(key): self._json_safe(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return [
                self._json_safe(
                    item
                )
                for item in value
            ]

        # --------------------------------------------------
        # Enum compatibility
        # --------------------------------------------------

        enum_value = getattr(
            value,
            "value",
            None,
        )

        if enum_value is not None:

            return self._json_safe(
                enum_value
            )

        # --------------------------------------------------
        # Final safe representation
        # --------------------------------------------------

        try:

            json.dumps(
                value
            )

            return value

        except Exception:

            return str(
                value
            )

    # ======================================================
    # FRAME DICTIONARY
    # ======================================================

    def build_frame(
        self,
        qbit,
        metadata=None,
    ):

        if qbit is None:

            raise ValueError(
                "QbitEncoder requires an existing Qbit"
            )

        intent = self.get_intent(
            qbit
        )

        timestamp = self.get_timestamp(
            qbit
        )

        frame = {
            "encoder_version": ENCODER_VERSION,
            "qbit_id": self.get_qbit_id(
                qbit
            ),
            "intent": intent,
            "intent_hash": self.intent_hash(
                intent
            ),
            "timestamp": timestamp,
            "state": self.get_state(
                qbit
            ),
            "mode": self.get_mode(
                qbit
            ),
            "track_id": self.get_track_id(
                qbit
            ),
            "metadata": self.get_metadata(
                qbit,
                metadata=metadata,
            ),
        }

        return frame

    # ======================================================
    # ENCODE
    # ======================================================

    def encode(
        self,
        qbit,
        metadata=None,
    ):

        if not self.enabled:

            raise RuntimeError(
                "QbitEncoder is disabled"
            )

        frame = self.build_frame(
            qbit,
            metadata=metadata,
        )

        intent_hash = int(
            frame[
                "intent_hash"
            ]
        )

        timestamp = float(
            frame[
                "timestamp"
            ]
        )

        encoded_metadata = json.dumps(
            frame[
                "metadata"
            ],
            separators=(
                ",",
                ":",
            ),
            sort_keys=True,
            ensure_ascii=False,
        ).encode(
            "utf-8"
        )

        header = struct.pack(
            HEADER_FORMAT,
            MAGIC,
            ENCODER_VERSION,
            intent_hash,
            timestamp,
            len(encoded_metadata),
        )

        payload = (
            header
            + encoded_metadata
        )

        self.last_encoded = payload
        self.last_timestamp = timestamp
        self.encode_count += 1

        self._log(
            "DEBUG",
            "[QbitEncoder] encoded | "
            "qbit=%s | intent=%s | bytes=%d | track_id=%s",
            frame.get("qbit_id"),
            frame.get("intent"),
            len(payload),
            frame.get("track_id"),
        )

        return payload

    # ======================================================
    # DECODE
    # ======================================================

    def decode(
        self,
        payload,
    ):

        if not isinstance(
            payload,
            (
                bytes,
                bytearray,
            ),
        ):

            raise TypeError(
                "Qbit payload must be bytes"
            )

        if len(payload) < HEADER_SIZE:

            raise ValueError(
                "Qbit payload shorter than header"
            )

        (
            magic,
            version,
            intent_hash,
            timestamp,
            metadata_size,
        ) = struct.unpack(
            HEADER_FORMAT,
            payload[
                :HEADER_SIZE
            ],
        )

        if magic != MAGIC:

            raise ValueError(
                "Invalid Qbit frame magic"
            )

        if version != ENCODER_VERSION:

            raise ValueError(
                f"Unsupported Qbit frame version: "
                f"{version}"
            )

        metadata_start = HEADER_SIZE

        metadata_end = (
            metadata_start
            + metadata_size
        )

        if metadata_end > len(payload):

            raise ValueError(
                "Qbit metadata exceeds payload size"
            )

        metadata_bytes = payload[
            metadata_start:
            metadata_end
        ]

        metadata = json.loads(
            metadata_bytes.decode(
                "utf-8"
            )
        )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {}

        return {
            "encoder_version": version,
            "intent_hash": intent_hash,
            "timestamp": timestamp,
            "metadata": metadata,
        }


    # ==========================================================
    # THOUGHT PACKET
    #
    # Qbit -> ThoughtPacket
    #
    # This is the cognitive boundary.
    #
    # Qbit remains transport/data.
    # ThoughtPacket becomes normalized cognition.
    #
    # NO command execution occurs here.
    # ==========================================================

    def create_thought_packet(
        self,
        qbit,
        metadata=None,
    ):

        if qbit is None:
            raise ValueError(
                "QbitEncoder requires an existing Qbit"
            )

        frame = self.build_frame(
            qbit,
            metadata=metadata,
        )

        qbit_id = frame.get(
            "qbit_id"
        )

        task_id = self._extract_value(
            qbit,
            "task_id",
        )

        parent_id = self._extract_value(
            qbit,
            "parent_id",
        )

        channel_id = self._extract_value(
            qbit,
            "channel_id",
        )

        source = self._extract_value(
            qbit,
            "source",
        )

        module = self._extract_value(
            qbit,
            "module",
        )

        component = self._extract_value(
            qbit,
            "component",
        )

        payload = self._extract_value(
            qbit,
            "payload",
        )

        if payload is None:
            payload = self._extract_value(
                qbit,
                "data",
            )

        priority = self._extract_value(
            qbit,
            "priority",
        )

        flags = self._extract_value(
            qbit,
            "flags",
            {},
        )

        thought_packet = {
            # --------------------------------------------------
            # Packet identity
            # --------------------------------------------------

            "packet_type": "ThoughtPacket",

            "encoder_version": ENCODER_VERSION,

            "qbit_id": qbit_id,

            "task_id": task_id,

            "parent_id": parent_id,

            # --------------------------------------------------
            # Lineage / routing
            # --------------------------------------------------

            "track_id": frame.get(
                "track_id"
            ),

            "channel_id": channel_id,

            "source": source,

            "module": module,

            "component": component,

            # --------------------------------------------------
            # Cognition
            # --------------------------------------------------

            "intent": frame.get(
                "intent"
            ),

            "intent_hash": frame.get(
                "intent_hash"
            ),

            "payload": self._json_safe(
                payload
            ),

            "state": frame.get(
                "state"
            ),

            "mode": frame.get(
                "mode"
            ),

            "priority": priority,

            "flags": self._json_safe(
                flags
            ),

            # --------------------------------------------------
            # Timing
            # --------------------------------------------------

            "timestamp": frame.get(
                "timestamp"
            ),

            # --------------------------------------------------
            # Original Qbit frame
            #
            # Preserve the transport representation so the
            # ThoughtPacket never loses Qbit lineage.
            # --------------------------------------------------

            "qbit_frame": self._json_safe(
                frame
            ),

            # --------------------------------------------------
            # Cognitive stage
            # --------------------------------------------------

            "stage": "COMPUTE",

            "source_type": "QBIT",

            "command_proposal": None,

            "transformed": False,

            "admitted": False,

            "executed": False,
        }

        return self._json_safe(
            thought_packet
        )

    # ==========================================================
    # THOUGHT PACKET ALIASES
    #
    # These provide a stable contract for ComputeBrain and
    # QbitDialer without forcing either component to know the
    # encoder's internal method name.
    # ==========================================================

    def to_thought_packet(
        self,
        qbit,
        metadata=None,
    ):
        return self.create_thought_packet(
            qbit,
            metadata=metadata,
        )

    def decode_to_thought(
        self,
        qbit,
        metadata=None,
    ):
        return self.create_thought_packet(
            qbit,
            metadata=metadata,
        )

    # ==========================================================
    # COMPLETE COGNITIVE INPUT STAGE
    #
    # Qbit
    #   ->
    # binary frame
    #   ->
    # ThoughtPacket
    #
    # Still NO command admission.
    # ==========================================================

    def process_qbit(
        self,
        qbit,
        metadata=None,
    ):

        encoded = self.encode(
            qbit,
            metadata=metadata,
        )

        decoded = self.decode(
            encoded
        )

        packet = self.create_thought_packet(
            qbit,
            metadata=metadata,
        )

        packet["encoded_frame"] = encoded

        packet["decoded_frame"] = decoded

        packet["stage"] = "THOUGHT"

        return packet

    # ======================================================
    # CONNECTION STATUS
    # ======================================================

    def status(self):

        return {
            "enabled": self.enabled,
            "encode_count": self.encode_count,
            "last_timestamp": self.last_timestamp,

            "qbit": (
                self.qbit_dialer is not None
            ),

            "qbit_dialer": (
                self.qbit_dialer is not None
            ),

            "qbit_queue_loop": (
                self.qbit_queue_loop is not None
            ),

            "heartbeat_emitter": (
                self.heartbeat_emitter is not None
            ),

            "track_system": (
                self.track_system is not None
            ),
        }


# ==========================================================
# DEFAULT FACTORY
# ==========================================================

def create_qbit_encoder(
    qbit_dialer=None,
    qbit_queue_loop=None,
    heartbeat_emitter=None,
    track_system=None,
    logger=None,
):


    return QbitEncoder(
        qbit_dialer=qbit_dialer,
        qbit_queue_loop=qbit_queue_loop,
        heartbeat_emitter=heartbeat_emitter,
        track_system=track_system,
        logger=logger,
    )