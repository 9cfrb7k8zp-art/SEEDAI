```python
# ==========================================================
# FILE: seed_handshake_manager.py
# PATH: SEED_ROOT/seed/core/seed_handshake_manager.py
#
# MODULE:
#   SEED Handshake Manager
#
# VERSION:
#   v4.0 — FULL SYSTEM INTEGRATION
#
# UPDATED:
#   2026-08-30
#
# ==========================================================
# PURPOSE:
#
# - Audio-based device discovery & lock
# - Handshake identity and lineage management
# - ChannelID-aware transmission
# - TrackID-aware handshake lifecycle
# - Qbit-aware cognitive ingestion
# - QbitDialer integration
# - Oracle observation / metadata collection
# - EventBus integration
# - TrackSystem integration
# - Registry integration
# - HUD integration
# - Preserve device identity and capability metadata
# - Restore cognitive-loop continuity
#
# ARCHITECTURE:
#
#       MODEM
#         │
#         ▼
#   HANDSHAKE FRAME
#         │
#         ▼
#   HandshakePacket
#         │
#         ├──────────────► DeviceManager / Registry
#         │
#         ├──────────────► TrackSystem
#         │
#         ├──────────────► Oracle
#         │
#         ├──────────────► EventBus
#         │
#         ▼
#       QBIT
#         │
#         ▼
#    QbitDialer
#         │
#         ▼
#   Cognitive Receive Path
#
# IMPORTANT:
#
# - HandshakeManager is NOT command authority.
# - Raw handshake Qbits are DATA.
# - Raw Qbits must not be passed to execute_command().
# - QbitDialer remains the command authority.
# - Commands generated downstream must enter submit_command().
# - Oracle observes and collects metadata; it does not execute commands.
# - TrackSystem owns track context.
# - Qbit carries identity, lineage, payload, and transport metadata.
#
# ==========================================================

import asyncio
import inspect
import logging
import threading
import time
import uuid
from queue import Empty


# ==========================================================
# OPTIONAL / CORE IMPORTS
# ==========================================================

from seed.core.utils import generate_device_id
from seed.core.channel_id import (
    ChannelID,
    generate_hpi_agent_track,
)
from seed.core.handshake_protocol import (
    HandshakePacket,
    HANDSHAKE_MAGIC,
)
from seed.core.modem_layer import SignalFrame


logger = logging.getLogger("SEEDHandshake")


# ==========================================================
# OPTIONAL TRACK ID MANAGER
# ==========================================================

try:
    from seed.core.track_id_manager import TrackIDManager
except Exception:
    TrackIDManager = None


# ==========================================================
# OPTIONAL QBIT TYPE
# ==========================================================

try:
    from seed.core.qbit import Qbit
except Exception:
    Qbit = None


# ==========================================================
# TRACK & QBIT HELPERS
# ==========================================================

def generate_track(
    channel="CH-HANDSHAKE",
    priority="NORMAL",
    overlay=False,
    metadata=None,
    parent_id=None,
):

    metadata = dict(metadata or {})

    priority_value = (
        50
        if str(priority).upper() == "NORMAL"
        else 75
    )

    try:
        return generate_hpi_agent_track(
            channel=channel,
            agent_index=1,
            parent_id=parent_id,
            priority=priority_value,
            metadata=metadata,
            overlay=overlay,
        )

    except Exception:
        if TrackIDManager is not None:

            try:
                return TrackIDManager.generate(
                    channel_marker=channel,
                )

            except Exception:
                pass

        return (
            f"{channel}-"
            f"{uuid.uuid4().hex[:12]}"
        )


def build_qbit(
    kind,
    payload,
    track,
    *,
    device_id=None,
    task_id=None,
    pipeline_id=None,
    channel=None,
    source="SEEDHandshakeManager",
    metadata=None,
):

    metadata = dict(metadata or {})

    return {
        "qbit_type": kind,
        "qbit_id": (
            f"QBIT-HS-"
            f"{uuid.uuid4().hex[:12]}"
        ),
        "payload": payload,
        "track": track,
        "track_id": track,
        "task_id": task_id,
        "pipeline_id": pipeline_id,
        "device_id": device_id,
        "channel": channel,
        "source": source,
        "metadata": metadata,
        "timestamp": time.time(),
        "ts": time.time(),
        "authority": "QbitDialer",
        "data_type": "HANDSHAKE",
    }


# ==========================================================
# SEED HANDSHAKE MANAGER
# ==========================================================

class SEEDHandshakeManager:

    def __init__(
        self,
        modem,
        event_bus=None,
        qbit_dialer=None,
        hud=None,
        track_system=None,
        registry=None,
        module_registry=None,
        oracle=None,
        device_manager=None,
        orchestrator=None,
        seedcore=None,
        core=None,
    ):
        # ======================================================
        # CORE DEPENDENCIES
        # ======================================================

        self.modem = modem

        self.event_bus = event_bus

        self.qbit_dialer = qbit_dialer

        self.hud = hud

        self.track_system = track_system

        self.registry = (
            registry
            or module_registry
        )

        self.module_registry = (
            module_registry
            or registry
        )

        self.oracle = oracle

        self.device_manager = device_manager

        self.orchestrator = orchestrator

        self.seedcore = seedcore

        self.core = core

        # ======================================================
        # IDENTITY
        # ======================================================

        self.device_id = (
            self._resolve_local_device_id()
        )

        self.device_name = (
            self._resolve_local_device_name()
        )

        self.capabilities = (
            self._resolve_capabilities()
        )

        # ======================================================
        # RUNTIME STATE
        # ======================================================

        self.discovered = {}

        self.locked_devices = set()

        self.active_sessions = {}

        self.running = False

        self._rx_thread = None

        self._state_lock = threading.RLock()

        # ======================================================
        # TRACK / QBIT STATE
        # ======================================================

        self.last_track_id = None

        self.last_qbit_id = None

        self.last_handshake = None

        self.handshake_history = []

        self.max_handshake_history = 100

        # ======================================================
        # HUD / CHANNEL STATE
        # ======================================================

        self.channel_overlay = []

        self.channel_history = []

        # ======================================================
        # ORACLE METADATA STATE
        # ======================================================

        self.oracle_metadata = {}

        self.last_oracle_result = None

        # ======================================================
        # REGISTRY STATE
        # ======================================================

        self.registry_metadata = {}

        # ======================================================
        # COUNTERS
        # ======================================================

        self.tx_count = 0

        self.rx_count = 0

        self.qbit_count = 0

        self.discovery_count = 0

        self.lock_count = 0

        logger.info(
            "[HANDSHAKE] Manager initialized | "
            "device_id=%s | device_name=%s",
            self.device_id,
            self.device_name,
        )

        # ======================================================
        # DYNAMIC SYSTEM CONNECTION
        # ======================================================

        self._connect_system_dependencies()

    # ==========================================================
    # SYSTEM DEPENDENCY RESOLUTION
    # ==========================================================

    def _connect_system_dependencies(self):

        if self.event_bus is None:
            self.event_bus = self._resolve_dependency(
                "event_bus",
                "eventBus",
            )

        if self.qbit_dialer is None:
            self.qbit_dialer = self._resolve_dependency(
                "qbit_dialer",
                "qbitDialer",
                "dialer",
            )

        if self.track_system is None:
            self.track_system = self._resolve_dependency(
                "track_system",
                "trackSystem",
            )

        if self.registry is None:
            self.registry = self._resolve_dependency(
                "registry",
                "module_registry",
                "moduleRegistry",
            )

        if self.oracle is None:
            self.oracle = self._resolve_dependency(
                "oracle",
                "oracle_ai",
                "oracleAI",
            )

        if self.device_manager is None:
            self.device_manager = self._resolve_dependency(
                "device_manager",
                "deviceManager",
            )

        self.module_registry = (
            self.module_registry
            or self.registry
        )

    def _resolve_dependency(self, *names):

        for name in names:

            value = getattr(
                self,
                name,
                None,
            )

            if value is not None:
                return value

        containers = (
            self.seedcore,
            self.core,
            self.orchestrator,
        )

        for container in containers:

            if container is None:
                continue

            for name in names:

                value = getattr(
                    container,
                    name,
                    None,
                )

                if value is not None:
                    return value

        return None

    # ==========================================================
    # IDENTITY RESOLUTION
    # ==========================================================

    def _resolve_local_device_id(self):
        if self.device_manager is not None:

            value = getattr(
                self.device_manager,
                "local_device_id",
                None,
            )

            if value:
                return value

            value = getattr(
                self.device_manager,
                "device_id",
                None,
            )

            if value:
                return value

        return generate_device_id()

    def _resolve_local_device_name(self):
        if self.device_manager is not None:

            value = getattr(
                self.device_manager,
                "local_device_name",
                None,
            )

            if value:
                return value

            value = getattr(
                self.device_manager,
                "device_name",
                None,
            )

            if value:
                return value

        return "SEED"

    def _resolve_capabilities(self):
        if self.device_manager is not None:

            capabilities = getattr(
                self.device_manager,
                "capabilities",
                None,
            )

            if isinstance(
                capabilities,
                (list, tuple, set),
            ):
                return list(capabilities)

        return []

    # ==========================================================
    # START
    # ==========================================================

    def start(self):

        if self.running:
            logger.debug(
                "[HANDSHAKE] Already running"
            )
            return

        self._connect_system_dependencies()

        self.running = True

        self._rx_thread = threading.Thread(
            target=self._rx_loop,
            name="SEEDHandshakeRX",
            daemon=True,
        )

        self._rx_thread.start()

        self.broadcast_ping()

        self._emit_event(
            "HANDSHAKE_STARTED",
            self._build_identity_metadata(),
        )

        logger.info(
            "[HANDSHAKE] RX loop online"
        )

    # ==========================================================
    # STOP
    # ==========================================================

    def stop(self):
        """
        Stop handshake RX processing.

        Shutdown always wins.
        """

        self.running = False

        self._emit_event(
            "HANDSHAKE_STOPPED",
            self._build_identity_metadata(),
        )

        logger.info(
            "[HANDSHAKE] stopped"
        )

    # ==========================================================
    # IDENTITY METADATA
    # ==========================================================

    def _build_identity_metadata(
        self,
        *,
        track_id=None,
        task_id=None,
        pipeline_id=None,
        channel=None,
    ):

        return {
            "source": "SEEDHandshakeManager",
            "device_id": self.device_id,
            "device_name": self.device_name,
            "capabilities": list(
                self.capabilities
            ),
            "track_id": (
                track_id
                or self.last_track_id
            ),
            "task_id": task_id,
            "pipeline_id": pipeline_id,
            "channel": channel,
            "handshake_magic": HANDSHAKE_MAGIC,
            "timestamp": time.time(),
        }

    # ==========================================================
    # TX
    # ==========================================================

    def _send_frame(self, frame):
        """
        Safe modem transmit wrapper.

        Supports tx() or send().
        """

        if self.modem is None:

            logger.warning(
                "[HANDSHAKE] No modem attached"
            )

            return False

        try:

            if hasattr(
                self.modem,
                "tx",
            ):

                result = self.modem.tx(
                    frame
                )

            elif hasattr(
                self.modem,
                "send",
            ):

                result = self.modem.send(
                    frame
                )

            else:

                logger.warning(
                    "[HANDSHAKE] Modem has no "
                    "tx/send method"
                )

                return False

            self.tx_count += 1

            return result

        except Exception:

            logger.exception(
                "[HANDSHAKE] Frame transmit failed"
            )

            return False

    # ==========================================================
    # CHANNEL RESOLUTION
    # ==========================================================

    def _get_channels(self):

        try:

            channels = (
                ChannelID.get_sorted_channels(
                    hud_overlay=True
                )
            )

            if channels:
                return list(channels)

        except Exception:

            logger.debug(
                "[HANDSHAKE] ChannelID sorting unavailable",
                exc_info=True,
            )

        return [
            {
                "channel": "CH-HANDSHAKE",
                "current_id": 1000,
            }
        ]

    # ==========================================================
    # HANDSHAKE TRACK
    # ==========================================================

    def _create_handshake_track(
        self,
        event_type,
        *,
        parent_id=None,
        channel=None,
    ):
        channel_name = (
            channel
            or "CH-HANDSHAKE"
        )

        metadata = {
            "event": event_type,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "source": "SEEDHandshakeManager",
            "timestamp": time.time(),
        }

        track = generate_track(
            channel=channel_name,
            priority="NORMAL",
            overlay=True,
            metadata=metadata,
            parent_id=parent_id,
        )

        self.last_track_id = track

        return track

    # ==========================================================
    # HANDSHAKE TX
    # ==========================================================

    def broadcast_ping(self):

        track = self._create_handshake_track(
            "PING"
        )

        channels = self._get_channels()

        for ch_meta in channels:

            channel = ch_meta.get(
                "channel",
                "CH-HANDSHAKE",
            )

            packet = HandshakePacket(
                "PING",
                self.device_id,
                device_name=self.device_name,
                capabilities=self.capabilities,
            )

            frequency = (
                ch_meta.get(
                    "current_id",
                    1000,
                )
                * 0.1
                + 1000
            )

            frame = SignalFrame(
                frequency=frequency,
                amplitude=0.8,
                phase=0.0,
                payload=packet.to_payload(),
                timestamp=time.time(),
                noise=0.0,
            )

            self._send_frame(
                frame
            )

            self._emit_qbit(
                "HANDSHAKE_PING",
                {
                    "device_id": self.device_id,
                    "device_name": self.device_name,
                    "capabilities": self.capabilities,
                    "channel": channel,
                },
                track,
            )

        self._update_hud_overlay(
            "PING",
            channels,
            track_id=track,
        )

        self._emit_event(
            "HANDSHAKE_PING",
            self._build_identity_metadata(
                track_id=track,
            ),
        )

        logger.info(
            "[HANDSHAKE] PING broadcast | track=%s",
            track,
        )

    # ==========================================================
    # ACK
    # ==========================================================

    def send_ack(self, target_id):
        """
        Acknowledge a discovered device.
        """

        track = self._create_handshake_track(
            "ACK",
            parent_id=target_id,
        )

        channels = self._get_channels()

        for ch_meta in channels:

            channel = ch_meta.get(
                "channel",
                "CH-HANDSHAKE",
            )

            packet = HandshakePacket(
                "ACK",
                self.device_id,
                device_name=self.device_name,
                capabilities=self.capabilities,
            )

            frame = SignalFrame(
                frequency=(
                    ch_meta.get(
                        "current_id",
                        1100,
                    )
                    * 0.1
                    + 1000
                ),
                amplitude=0.7,
                phase=0.0,
                payload=packet.to_payload(),
                timestamp=time.time(),
                noise=0.0,
            )

            self._send_frame(
                frame
            )

            self._emit_qbit(
                "HANDSHAKE_ACK",
                {
                    "from": self.device_id,
                    "to": target_id,
                    "channel": channel,
                },
                track,
            )

        self._update_hud_overlay(
            "ACK",
            channels,
            track_id=track,
        )

        self._emit_event(
            "HANDSHAKE_ACK",
            {
                "from_device_id": self.device_id,
                "target_device_id": target_id,
                "track_id": track,
                "timestamp": time.time(),
            },
        )

        logger.info(
            "[HANDSHAKE] ACK -> %s | track=%s",
            target_id,
            track,
        )

    # ==========================================================
    # LOCK
    # ==========================================================

    def send_lock(self, target_id):

        track = self._create_handshake_track(
            "LOCK",
            parent_id=target_id,
        )

        channels = self._get_channels()

        for ch_meta in channels:

            channel = ch_meta.get(
                "channel",
                "CH-HANDSHAKE",
            )

            packet = HandshakePacket(
                "LOCK",
                self.device_id,
                device_name=self.device_name,
                capabilities=self.capabilities,
            )

            frame = SignalFrame(
                frequency=(
                    ch_meta.get(
                        "current_id",
                        1200,
                    )
                    * 0.1
                    + 1000
                ),
                amplitude=0.9,
                phase=0.0,
                payload=packet.to_payload(),
                timestamp=time.time(),
                noise=0.0,
            )

            if hasattr(
                self.modem,
                "pll",
            ):

                try:
                    self.modem.pll.target_freq = (
                        frame.frequency
                    )
                except Exception:
                    logger.debug(
                        "[HANDSHAKE] PLL update skipped",
                        exc_info=True,
                    )

            self._send_frame(
                frame
            )

            self.locked_devices.add(
                target_id
            )

            self._emit_qbit(
                "HANDSHAKE_LOCK",
                {
                    "locked_device": target_id,
                    "channel": channel,
                },
                track,
            )

        self.lock_count += 1

        self._update_hud_overlay(
            "LOCK",
            channels,
            track_id=track,
        )

        lock_metadata = {
            "device_id": target_id,
            "source_device_id": self.device_id,
            "track_id": track,
            "timestamp": time.time(),
        }

        self._emit_event(
            "DEVICE_LOCKED",
            lock_metadata,
        )

        self._oracle_observe(
            "HANDSHAKE_LOCK",
            lock_metadata,
        )

        logger.info(
            "[HANDSHAKE] LOCKED -> %s | track=%s",
            target_id,
            track,
        )

    # ==========================================================
    # RX LOOP
    # ==========================================================

    def _rx_loop(self):


        while self.running:

            try:

                rx_queue = getattr(
                    self.modem,
                    "rx_queue",
                    None,
                )

                if rx_queue is None:

                    time.sleep(0.5)

                    continue

                frame = rx_queue.get(
                    timeout=0.5
                )

                self.rx_count += 1

                payload = getattr(
                    frame,
                    "payload",
                    frame,
                )

                packet = (
                    HandshakePacket.from_payload(
                        payload
                    )
                )

                self._handle_packet(
                    packet,
                    frame=frame,
                )

            except Empty:

                continue

            except Exception as exc:

                logger.error(
                    "[HANDSHAKE] RX loop error: %s",
                    exc,
                    exc_info=True,
                )

    # ==========================================================
    # PACKET HANDLER
    # ==========================================================

    def _handle_packet(
        self,
        packet,
        frame=None,
    ):

        if packet is None:
            return

        sender = getattr(
            packet,
            "device_id",
            None,
        )

        if not sender:
            return

        if sender == self.device_id:
            return

        now = time.time()

        track = self._create_handshake_track(
            getattr(
                packet,
                "kind",
                "UNKNOWN",
            ),
            parent_id=sender,
        )

        packet_metadata = (
            self._extract_packet_metadata(
                packet
            )
        )

        packet_metadata.update(
            {
                "sender_id": sender,
                "receiver_id": self.device_id,
                "track_id": track,
                "timestamp": now,
            }
        )

        self.discovered[
            sender
        ] = now

        self.active_sessions[
            sender
        ] = now

        self.discovery_count += 1

        self.last_handshake = (
            packet_metadata
        )

        self._remember_handshake(
            packet_metadata
        )

        # ------------------------------------------------------
        # Register discovered identity.
        # ------------------------------------------------------

        self._register_device(
            packet
        )

        # ------------------------------------------------------
        # TrackSystem receives context.
        # ------------------------------------------------------

        self._track_observe(
            "HANDSHAKE_RECEIVED",
            packet_metadata,
        )

        # ------------------------------------------------------
        # Oracle receives observation/metadata.
        # ------------------------------------------------------

        self._oracle_observe(
            "HANDSHAKE_RECEIVED",
            packet_metadata,
        )

        # ------------------------------------------------------
        # EventBus receives normalized observation.
        # ------------------------------------------------------

        self._emit_event(
            "HANDSHAKE_RECEIVED",
            packet_metadata,
        )

        # ------------------------------------------------------
        # HUD receives status.
        # ------------------------------------------------------

        self._update_hud_overlay(
            "RECEIVE",
            [
                {
                    "channel": packet_metadata.get(
                        "channel",
                        "CH-HANDSHAKE",
                    ),
                    "current_id": packet_metadata.get(
                        "frequency",
                        1000,
                    ),
                }
            ],
            track_id=track,
            device_id=sender,
        )

        # ------------------------------------------------------
        # Protocol state machine.
        # ------------------------------------------------------

        kind = str(
            getattr(
                packet,
                "kind",
                "",
            )
        ).upper()

        if kind == "PING":

            self.send_ack(
                sender
            )

        elif kind == "ACK":

            if sender not in self.locked_devices:

                self.send_lock(
                    sender
                )

        elif kind == "LOCK":

            self.locked_devices.add(
                sender
            )

            complete_payload = {
                "linked_device": sender,
                "device_name": packet_metadata.get(
                    "device_name"
                ),
                "capabilities": packet_metadata.get(
                    "capabilities",
                    [],
                ),
                "track_id": track,
            }

            self._emit_qbit(
                "HANDSHAKE_COMPLETE",
                complete_payload,
                track,
            )

            self._track_observe(
                "HANDSHAKE_COMPLETE",
                complete_payload,
            )

            self._oracle_observe(
                "HANDSHAKE_COMPLETE",
                complete_payload,
            )

            self._emit_event(
                "HANDSHAKE_COMPLETE",
                {
                    "device_id": sender,
                    "track_id": track,
                    "metadata": packet_metadata,
                },
            )

            logger.info(
                "[HANDSHAKE] LINK ESTABLISHED <-> %s | "
                "track=%s",
                sender,
                track,
            )

    # ==========================================================
    # PACKET METADATA
    # ==========================================================

    def _extract_packet_metadata(
        self,
        packet,
    ):

        return {
            "kind": getattr(
                packet,
                "kind",
                None,
            ),
            "device_id": getattr(
                packet,
                "device_id",
                None,
            ),
            "device_name": getattr(
                packet,
                "device_name",
                "UnknownDevice",
            ),
            "capabilities": list(
                getattr(
                    packet,
                    "capabilities",
                    [],
                )
                or []
            ),
            "timestamp": getattr(
                packet,
                "timestamp",
                time.time(),
            ),
            "nonce": getattr(
                packet,
                "nonce",
                None,
            ),
            "source": "SEEDHandshakeManager",
        }

    # ==========================================================
    # DEVICE REGISTRY
    # ==========================================================

    def _register_device(
        self,
        packet,
    ):

        device_id = getattr(
            packet,
            "device_id",
            None,
        )

        if not device_id:
            return

        device_name = getattr(
            packet,
            "device_name",
            "UnknownDevice",
        )

        capabilities = list(
            getattr(
                packet,
                "capabilities",
                [],
            )
            or []
        )

        metadata = {
            "device_id": device_id,
            "device_name": device_name,
            "capabilities": capabilities,
            "source": "HANDSHAKE",
            "timestamp": time.time(),
        }

        self.registry_metadata[
            device_id
        ] = metadata

        # ------------------------------------------------------
        # DeviceManager
        # ------------------------------------------------------

        manager = self.device_manager

        if manager is not None:

            try:

                has_device = getattr(
                    manager,
                    "has_device",
                    None,
                )

                exists = (
                    bool(
                        has_device(
                            device_id
                        )
                    )
                    if callable(has_device)
                    else False
                )

                if not exists:

                    register = getattr(
                        manager,
                        "register_device",
                        None,
                    )

                    if callable(register):

                        register(
                            device_id=device_id,
                            name=device_name,
                            capabilities=capabilities,
                            transport="audio",
                        )

                        logger.info(
                            "[HANDSHAKE] Device registered | "
                            "device_id=%s",
                            device_id,
                        )

            except Exception:

                logger.debug(
                    "[HANDSHAKE] DeviceManager registration "
                    "skipped",
                    exc_info=True,
                )

        # ------------------------------------------------------
        # Generic Registry
        # ------------------------------------------------------

        registry = self.registry

        if registry is None:
            return

        try:

            register = getattr(
                registry,
                "register",
                None,
            )

            if callable(register):

                try:

                    register(
                        device_id,
                        metadata,
                    )

                except TypeError:

                    register(
                        device_id=device_id,
                        metadata=metadata,
                    )

                return

            register_device = getattr(
                registry,
                "register_device",
                None,
            )

            if callable(register_device):

                try:

                    register_device(
                        device_id=device_id,
                        metadata=metadata,
                    )

                except TypeError:

                    register_device(
                        device_id,
                        metadata,
                    )

        except Exception:

            logger.debug(
                "[HANDSHAKE] Registry registration skipped",
                exc_info=True,
            )

    # ==========================================================
    # QBIT EMISSION
    # ==========================================================

    def _emit_qbit(
        self,
        kind,
        payload,
        track,
    ):

        self._connect_system_dependencies()

        if self.qbit_dialer is None:

            logger.warning(
                "[HANDSHAKE] No QbitDialer attached | "
                "qbit_type=%s",
                kind,
            )

            return None

        channel = (
            payload.get(
                "channel"
            )
            if isinstance(
                payload,
                dict,
            )
            else None
        )

        metadata = self._build_identity_metadata(
            track_id=track,
            channel=channel,
        )

        qbit = build_qbit(
            kind,
            payload,
            track,
            device_id=self.device_id,
            channel=channel,
            source="SEEDHandshakeManager",
            metadata=metadata,
        )

        self.last_qbit_id = qbit.get(
            "qbit_id"
        )

        self.qbit_count += 1

        # ------------------------------------------------------
        # Prefer authoritative Qbit submission/receive methods.
        # ------------------------------------------------------

        methods = (
            "submit_qbit_command",
            "submit_qbit",
            "_process_received_qbit",
            "push_data",
        )

        for method_name in methods:

            method = getattr(
                self.qbit_dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    qbit
                )

                if inspect.isawaitable(
                    result
                ):

                    self._schedule_async(
                        result
                    )

                return result

            except TypeError:

                # Try the next compatible interface.
                continue

            except Exception:

                logger.exception(
                    "[HANDSHAKE] Qbit submission failed | "
                    "method=%s | qbit_id=%s",
                    method_name,
                    qbit.get(
                        "qbit_id"
                    ),
                )

                return None

        logger.warning(
            "[HANDSHAKE] QbitDialer has no supported "
            "Qbit ingestion method"
        )

        return None

    # ==========================================================
    # TRACKSYSTEM OBSERVATION
    # ==========================================================

    def _track_observe(
        self,
        event_type,
        metadata,
    ):

        track_system = self.track_system

        if track_system is None:
            return None

        payload = dict(
            metadata or {}
        )

        payload.setdefault(
            "event",
            event_type,
        )

        payload.setdefault(
            "source",
            "SEEDHandshakeManager",
        )

        for method_name in (
            "observe",
            "record",
            "update",
            "ingest",
            "receive",
            "register_event",
        ):

            method = getattr(
                track_system,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    payload
                )

                if inspect.isawaitable(
                    result
                ):

                    self._schedule_async(
                        result
                    )

                return result

            except TypeError:

                continue

            except Exception:

                logger.debug(
                    "[HANDSHAKE] TrackSystem observation "
                    "failed | method=%s",
                    method_name,
                    exc_info=True,
                )

                return None

        return None

    # ==========================================================
    # ORACLE OBSERVATION
    # ==========================================================

    def _oracle_observe(
        self,
        event_type,
        metadata,
    ):

        oracle = self.oracle

        if oracle is None:
            return None

        payload = dict(
            metadata or {}
        )

        payload.setdefault(
            "event",
            event_type,
        )

        payload.setdefault(
            "source",
            "SEEDHandshakeManager",
        )

        payload.setdefault(
            "authority",
            "observation",
        )

        self.oracle_metadata[
            event_type
        ] = payload

        methods = (
            "receive_qbit",
            "observe_qbit",
            "observe",
            "record",
            "ingest",
            "receive",
            "collect_metadata",
        )

        for method_name in methods:

            method = getattr(
                oracle,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                # receive_qbit() generally expects the Qbit itself,
                # while generic observation methods can accept metadata.
                if method_name == "receive_qbit":

                    qbit = build_qbit(
                        f"ORACLE_{event_type}",
                        payload,
                        payload.get(
                            "track_id"
                        ),
                        device_id=self.device_id,
                        source="SEEDHandshakeManager",
                        metadata=payload,
                    )

                    result = method(
                        qbit
                    )

                else:

                    try:

                        result = method(
                            payload
                        )

                    except TypeError:

                        result = method(
                            event_type,
                            payload,
                        )

                if inspect.isawaitable(
                    result
                ):

                    result = self._schedule_async(
                        result
                    )

                self.last_oracle_result = result

                return result

            except TypeError:

                continue

            except Exception:

                logger.debug(
                    "[HANDSHAKE] Oracle observation failed | "
                    "method=%s",
                    method_name,
                    exc_info=True,
                )

                return None

        return None

    # ==========================================================
    # EVENTBUS
    # ==========================================================

    def _emit_event(
        self,
        event_type,
        data,
    ):

        event_bus = self.event_bus

        if event_bus is None:
            return None

        payload = dict(
            data or {}
        )

        payload.setdefault(
            "source",
            "SEEDHandshakeManager",
        )

        payload.setdefault(
            "timestamp",
            time.time(),
        )

        emit = getattr(
            event_bus,
            "emit",
            None,
        )

        if not callable(emit):
            return None

        try:

            try:

                result = emit(
                    event_type,
                    data=payload,
                )

            except TypeError:

                result = emit(
                    event_type,
                    payload,
                )

            if inspect.isawaitable(
                result
            ):

                return self._schedule_async(
                    result
                )

            return result

        except Exception:

            logger.debug(
                "[HANDSHAKE] EventBus emission failed | "
                "event=%s",
                event_type,
                exc_info=True,
            )

            return None

    # ==========================================================
    # HUD
    # ==========================================================

    def _update_hud_overlay(
        self,
        event_type,
        channels,
        *,
        track_id=None,
        device_id=None,
    ):

        overlay_data = {
            "event": event_type,
            "device_id": (
                device_id
                or self.device_id
            ),
            "local_device_id": self.device_id,
            "device_name": self.device_name,
            "capabilities": list(
                self.capabilities
            ),
            "channels": channels,
            "track_id": (
                track_id
                or self.last_track_id
            ),
            "timestamp": time.time(),
            "source": "SEEDHandshakeManager",
        }

        self.channel_overlay.append(
            overlay_data
        )

        self.channel_history.append(
            overlay_data
        )

        if len(
            self.channel_history
        ) > self.max_handshake_history:

            self.channel_history = (
                self.channel_history[
                    -self.max_handshake_history:
                ]
            )

        hud = self.hud

        if hud is None:
            return

        try:

            update = getattr(
                hud,
                "update_handshake_overlay",
                None,
            )

            if callable(update):

                result = update(
                    overlay_data
                )

                if inspect.isawaitable(
                    result
                ):

                    self._schedule_async(
                        result
                    )

                return result

            # Generic HUD fallback.
            update = getattr(
                hud,
                "update",
                None,
            )

            if callable(update):

                result = update(
                    "HANDSHAKE",
                    overlay_data,
                )

                if inspect.isawaitable(
                    result
                ):

                    self._schedule_async(
                        result
                    )

        except Exception:

            logger.debug(
                "[HANDSHAKE] HUD update failed",
                exc_info=True,
            )

    # ==========================================================
    # HANDSHAKE HISTORY
    # ==========================================================

    def _remember_handshake(
        self,
        metadata,
    ):
        self.handshake_history.append(
            dict(metadata)
        )

        if len(
            self.handshake_history
        ) > self.max_handshake_history:

            self.handshake_history = (
                self.handshake_history[
                    -self.max_handshake_history:
                ]
            )

    # ==========================================================
    # ASYNC BRIDGE
    # ==========================================================

    def _schedule_async(
        self,
        awaitable,
    ):

        try:

            loop = asyncio.get_running_loop()

            return loop.create_task(
                awaitable
            )

        except RuntimeError:
            pass

        def runner():

            try:

                asyncio.run(
                    awaitable
                )

            except Exception:

                logger.debug(
                    "[HANDSHAKE] Async integration task failed",
                    exc_info=True,
                )

        thread = threading.Thread(
            target=runner,
            name="SEEDHandshakeAsync",
            daemon=True,
        )

        thread.start()

        return thread


# ==========================================================
# END OF FILE
# ==========================================================

