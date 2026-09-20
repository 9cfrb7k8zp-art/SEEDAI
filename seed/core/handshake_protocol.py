# ==========================================================
# FILE: handshake_protocol.py
# PATH: SEED_ROOT/seed/core/handshake_protocol.py
#
# MODULE:
#   SEED Handshake Protocol
#
# VERSION:
#   2.6 — SYSTEM INTEGRATED
#
# PURPOSE:
#   - Device identity handshake
#   - Qbit-aware channel selection
#   - EventBus integration
#   - DeviceManager integration
#   - HUD memory telemetry
#   - ConstraintGuardian-aware throttling
#   - Oracle metadata observation
#   - QbitDialer receive integration
#   - Track / task / pipeline identity propagation
#
# ARCHITECTURE:
#
#   Modem
#      │
#      ▼
#   HandshakeManager
#      │
#      ├── DeviceManager
#      ├── EventBus
#      ├── Oracle
#      ├── QbitDialer
#      ├── TrackSystem
#      ├── HUD
#      └── ConstraintGuardian
#
# IMPORTANT:
#   HandshakeManager observes and establishes identity.
#   It does NOT become command authority.
#
#   QbitDialer remains the sole command authority.
#
# ==========================================================

import asyncio
import csv
import hashlib
import inspect
import logging
import os
import time
import tracemalloc
import uuid

from collections import deque


try:
    from seed.core.utils import generate_device_id
except ImportError:
    generate_device_id = None


logger = logging.getLogger("SEEDHandshake")


# ==========================================================
# CONSTANTS
# ==========================================================

HANDSHAKE_MAGIC = "SEED-HS"

HANDSHAKE_TIMEOUT = 5.0

MIN_BROADCAST_INTERVAL = 2.0

NEW_DEVICE_INTERVAL = 0.5

MEMORY_LOG_CSV = "./seed_memory_log.csv"

MEMORY_WARNING_THRESHOLD_MB = 100

MEMORY_GROWTH_DELTA_MB = 10


# ==========================================================
# HANDSHAKE PACKET
# ==========================================================

class HandshakePacket:

    def __init__(
        self,
        kind,
        device_id,
        device_name=None,
        capabilities=None,
        timestamp=None,
        metadata=None,
        track_id=None,
        task_id=None,
        pipeline_id=None,
        qbit_id=None,
    ):

        self.kind = kind

        self.device_id = device_id

        self.device_name = (
            device_name
            or "UnknownDevice"
        )

        self.capabilities = (
            capabilities
            or []
        )

        self.timestamp = (
            timestamp
            or time.time()
        )

        self.nonce = uuid.uuid4().hex

        self.metadata = (
            dict(metadata)
            if isinstance(metadata, dict)
            else {}
        )

        self.track_id = track_id

        self.task_id = task_id

        self.pipeline_id = pipeline_id

        self.qbit_id = qbit_id

    # ------------------------------------------------------
    # SERIALIZE
    # ------------------------------------------------------

    def serialize(self):

        return {
            "magic": HANDSHAKE_MAGIC,

            "kind": self.kind,

            "device_id": self.device_id,

            "device_name": self.device_name,

            "capabilities": self.capabilities,

            "timestamp": self.timestamp,

            "nonce": self.nonce,

            "metadata": dict(self.metadata),

            "track_id": self.track_id,

            "task_id": self.task_id,

            "pipeline_id": self.pipeline_id,

            "qbit_id": self.qbit_id,
        }

    # ------------------------------------------------------
    # VALIDATE
    # ------------------------------------------------------

    @staticmethod
    def validate(packet):

        return (
            isinstance(packet, dict)
            and packet.get("magic") == HANDSHAKE_MAGIC
            and "device_id" in packet
            and "timestamp" in packet
        )

    # ------------------------------------------------------
    # FROM PAYLOAD
    # ------------------------------------------------------

    @staticmethod
    def from_payload(payload):

        if not HandshakePacket.validate(payload):

            raise ValueError(
                "Invalid handshake payload"
            )

        return HandshakePacket(

            kind=payload.get(
                "kind"
            ),

            device_id=payload.get(
                "device_id"
            ),

            device_name=payload.get(
                "device_name"
            ),

            capabilities=payload.get(
                "capabilities"
            ),

            timestamp=payload.get(
                "timestamp"
            ),

            metadata=payload.get(
                "metadata"
            ),

            track_id=payload.get(
                "track_id"
            ),

            task_id=payload.get(
                "task_id"
            ),

            pipeline_id=payload.get(
                "pipeline_id"
            ),

            qbit_id=payload.get(
                "qbit_id"
            ),
        )

    # ------------------------------------------------------
    # PAYLOAD
    # ------------------------------------------------------

    def to_payload(self):

        return self.serialize()

    # ------------------------------------------------------
    # DEVICE ID
    # ------------------------------------------------------

    @staticmethod
    def generate_device_id(
        prefix="HS-P-1"
    ):

        return hashlib.sha256(
            f"{prefix}-{uuid.uuid4().hex}".encode()
        ).hexdigest()[:16]


# ==========================================================
# HUD MEMORY OVERLAY
# ==========================================================

class HUDMemoryOverlay:

    def __init__(
        self,
        hud,
        device_manager=None,
        max_points=50,
        predict_steps=10,
        smoothing_window=3,
        base_warning_mb=(
            MEMORY_WARNING_THRESHOLD_MB * 0.7
        ),
        base_critical_mb=(
            MEMORY_WARNING_THRESHOLD_MB
        ),
        growth_warning_mb=(
            MEMORY_GROWTH_DELTA_MB * 0.5
        ),
        growth_critical_mb=(
            MEMORY_GROWTH_DELTA_MB
        ),
    ):

        self.hud = hud

        self.device_manager = (
            device_manager
        )

        self.max_points = max_points

        self.predict_steps = predict_steps

        self.smoothing_window = (
            smoothing_window
        )

        self.memory_log = deque(
            maxlen=max_points
        )

        self.start_time = time.time()

        self.base_warning = (
            base_warning_mb
        )

        self.base_critical = (
            base_critical_mb
        )

        self.warning_threshold = (
            self.base_warning
        )

        self.critical_threshold = (
            self.base_critical
        )

        self.growth_warning = (
            growth_warning_mb
        )

        self.growth_critical = (
            growth_critical_mb
        )

        self.last_memory_mb = 0

        self.alert_triggered = False

    # ------------------------------------------------------
    # MEMORY UPDATE
    # ------------------------------------------------------

    def update_memory(self):

        snapshot = (
            tracemalloc.take_snapshot()
        )

        current_mem_mb = (
            sum(
                stat.size
                for stat in snapshot.statistics(
                    "lineno"
                )
            )
            / (1024 * 1024)
        )

        timestamp = (
            time.time()
            - self.start_time
        )

        self.memory_log.append(
            (
                timestamp,
                current_mem_mb,
            )
        )

        growth = (
            current_mem_mb
            - self.last_memory_mb
        )

        self.last_memory_mb = (
            current_mem_mb
        )

        self.dynamic_threshold_adaptation()

        self.network_aware_scaling()

        return (
            current_mem_mb,
            growth,
        )

    # ------------------------------------------------------
    # DYNAMIC THRESHOLDS
    # ------------------------------------------------------

    def dynamic_threshold_adaptation(self):

        if (
            len(self.memory_log)
            < self.smoothing_window + 1
        ):

            return

        recent_points = list(
            self.memory_log
        )[
            -self.smoothing_window - 1:
        ]

        slopes = []

        for i in range(
            len(recent_points) - 1
        ):

            dt = (
                recent_points[i + 1][0]
                - recent_points[i][0]
            )

            if dt == 0:

                dt = 1

            slope = (
                recent_points[i + 1][1]
                - recent_points[i][1]
            ) / dt

            slopes.append(
                slope
            )

        if not slopes:

            return

        avg_slope = (
            sum(slopes)
            / len(slopes)
        )

        adaptation_factor = (
            avg_slope * 0.5
        )

        self.warning_threshold = max(
            self.base_warning,
            self.warning_threshold
            + adaptation_factor,
        )

        self.critical_threshold = max(
            self.base_critical,
            self.critical_threshold
            + adaptation_factor,
        )

        self.warning_threshold = min(
            self.warning_threshold,
            self.base_critical * 0.95,
        )

        self.critical_threshold = min(
            self.critical_threshold,
            self.base_critical * 1.5,
        )

    # ------------------------------------------------------
    # NETWORK SCALING
    # ------------------------------------------------------

    def network_aware_scaling(self):

        if not self.device_manager:

            return

        device_count = len(
            getattr(
                self.device_manager,
                "devices",
                {},
            )
        )

        scale_factor = (
            1
            + device_count * 0.05
        )

        self.warning_threshold = min(
            self.warning_threshold
            * scale_factor,
            self.base_critical * 1.5,
        )

        self.critical_threshold = min(
            self.critical_threshold
            * scale_factor,
            self.base_critical * 2.0,
        )

    # ------------------------------------------------------
    # MEMORY TREND
    # ------------------------------------------------------

    def compute_smoothed_trend(self):

        if len(self.memory_log) < 2:

            return []

        points = list(
            self.memory_log
        )

        slopes = []

        for i in range(
            1,
            len(points),
        ):

            dt = (
                points[i][0]
                - points[i - 1][0]
            )

            dm = (
                points[i][1]
                - points[i - 1][1]
            )

            slopes.append(
                dm / dt
                if dt != 0
                else 0
            )

        smoothed_slopes = []

        for i in range(
            len(slopes)
        ):

            window = slopes[
                max(
                    0,
                    i
                    - self.smoothing_window
                    + 1,
                ):
                i + 1
            ]

            smoothed_slopes.append(
                sum(window)
                / len(window)
            )

        avg_slope = (
            smoothed_slopes[-1]
            if smoothed_slopes
            else 0
        )

        t_last, m_last = points[-1]

        projected_points = []

        dt = (
            points[-1][0]
            - points[-2][0]
            if len(points) >= 2
            else 1
        )

        for i in range(
            1,
            self.predict_steps + 1,
        ):

            proj_time = (
                t_last
                + dt * i
            )

            proj_mem = (
                m_last
                + avg_slope * i * dt
            )

            projected_points.append(
                (
                    proj_time,
                    proj_mem,
                )
            )

        return projected_points


# ==========================================================
# SEED HANDSHAKE MANAGER
# ==========================================================

class SEEDHandshakeManager:

    def __init__(
        self,
        modem,
        device_manager,
        event_bus=None,
        hud=None,
        enable_csv_log=True,
        oracle=None,
        qbit_dialer=None,
        qbit=None,
        track_system=None,
        constraint_guardian=None,
        module_registry=None,
        seedcore=None,
        orchestrator=None,
        emit=None,
    ):

        self.modem = modem

        self.device_manager = (
            device_manager
        )

        self.event_bus = event_bus

        self.hud = hud

        self.oracle = oracle

        self.qbit_dialer = (
            qbit_dialer
        )

        self.qbit = qbit

        self.track_system = (
            track_system
        )

        self.constraint_guardian = (
            constraint_guardian
        )

        self.module_registry = (
            module_registry
        )

        self.seedcore = seedcore

        self.orchestrator = (
            orchestrator
        )

        self.emit = (
            emit
            or getattr(
                event_bus,
                "emit",
                None,
            )
        )

        self.active_sessions = {}

        self.last_broadcast = 0

        self.base_broadcast_interval = (
            MIN_BROADCAST_INTERVAL
        )

        self.broadcast_interval = (
            self.base_broadcast_interval
        )

        self.last_prune = 0

        self.base_prune_interval = (
            HANDSHAKE_TIMEOUT / 2
        )

        self.prune_interval = (
            self.base_prune_interval
        )

        self.last_memory_mb = 0

        self.enable_csv_log = (
            enable_csv_log
        )

        self.memory_log = []

        self.handshake_metadata = {}

        self.discovered_devices = {}

        self.last_identity = None

        self.last_received_packet = None

        self.last_qbit_context = None

        self._closed = False

        # ------------------------------------------------------
        # Tracemalloc
        # ------------------------------------------------------

        try:

            if not tracemalloc.is_tracing():

                tracemalloc.start()

        except Exception:

            logger.debug(
                "[HANDSHAKE] tracemalloc unavailable",
                exc_info=True,
            )

        # ------------------------------------------------------
        # HUD
        # ------------------------------------------------------

        self.hud_overlay = (
            HUDMemoryOverlay(
                hud,
                device_manager=device_manager,
            )
            if hud
            else None
        )

        # ------------------------------------------------------
        # Channel equalizer
        # ------------------------------------------------------

        self.channels = [
            3,
            6,
            9,
        ]

        self.channel_weights = {
            ch: 1.0
            for ch in self.channels
        }

        # ------------------------------------------------------
        # Persistence
        # ------------------------------------------------------

        if (
            self.enable_csv_log
            and not os.path.exists(
                MEMORY_LOG_CSV
            )
        ):

            try:

                with open(
                    MEMORY_LOG_CSV,
                    "w",
                    newline="",
                ) as f:

                    writer = csv.writer(f)

                    writer.writerow(
                        [
                            "timestamp",
                            "memory_mb",
                        ]
                    )

            except Exception:

                logger.warning(
                    "[HANDSHAKE] Unable to create memory CSV",
                    exc_info=True,
                )

        logger.info(
            "[HANDSHAKE] Fully integrated manager initialized"
        )

    # ======================================================
    # DYNAMIC DEPENDENCY RESOLUTION
    # ======================================================

    def _resolve_dependency(
        self,
        attribute_names,
    ):

        for name in attribute_names:

            value = getattr(
                self,
                name,
                None,
            )

            if value is not None:

                return value

        containers = (
            self.seedcore,
            self.orchestrator,
            getattr(
                self,
                "core",
                None,
            ),
        )

        for container in containers:

            if container is None:

                continue

            for name in attribute_names:

                value = getattr(
                    container,
                    name,
                    None,
                )

                if value is not None:

                    return value

        return None

    # ======================================================
    # EMIT
    # ======================================================

    def _emit(
        self,
        event_name,
        data=None,
    ):

        emitter = self.emit

        if not callable(emitter):

            emitter = getattr(
                self.event_bus,
                "emit",
                None,
            )

        if not callable(emitter):

            return None

        try:

            result = emitter(
                event_name,
                data=data,
            )

            return result

        except TypeError:

            try:

                return emitter(
                    event_name,
                    data,
                )

            except Exception:

                logger.debug(
                    "[HANDSHAKE] Event emission failed",
                    exc_info=True,
                )

        except Exception:

            logger.debug(
                "[HANDSHAKE] Event emission failed",
                exc_info=True,
            )

        return None

    # ======================================================
    # MEMORY MONITORING
    # ======================================================

    def check_memory(self):

        try:

            snapshot = (
                tracemalloc.take_snapshot()
            )

            current_mem_mb = (
                sum(
                    stat.size
                    for stat in snapshot.statistics(
                        "lineno"
                    )
                )
                / (1024 * 1024)
            )

        except Exception:

            current_mem_mb = (
                self.last_memory_mb
            )

        timestamp = time.time()

        growth = (
            current_mem_mb
            - self.last_memory_mb
        )

        self.last_memory_mb = (
            current_mem_mb
        )

        self.memory_log.append(
            {
                "timestamp": timestamp,
                "memory_mb": current_mem_mb,
                "growth_mb": growth,
            }
        )

        if len(self.memory_log) > 100:

            self.memory_log = (
                self.memory_log[-100:]
            )

        if self.enable_csv_log:

            try:

                with open(
                    MEMORY_LOG_CSV,
                    "a",
                    newline="",
                ) as f:

                    writer = csv.writer(f)

                    writer.writerow(
                        [
                            timestamp,
                            current_mem_mb,
                        ]
                    )

            except Exception:

                logger.debug(
                    "[HANDSHAKE] Memory CSV write failed",
                    exc_info=True,
                )

        projected = (
            self.hud_overlay.compute_smoothed_trend()
            if self.hud_overlay
            else []
        )

        predicted_max = max(
            [
                memory
                for _, memory in projected
            ],
            default=current_mem_mb,
        )

        warning_threshold = (
            self.hud_overlay.warning_threshold
            if self.hud_overlay
            else MEMORY_WARNING_THRESHOLD_MB
        )

        if predicted_max >= warning_threshold:

            self.broadcast_interval = max(
                self.base_broadcast_interval * 2,
                MIN_BROADCAST_INTERVAL * 4,
            )

            self.prune_interval = max(
                self.base_prune_interval / 2,
                0.5,
            )

            logger.warning(
                "[HANDSHAKE] Forecast-driven mitigation activated | "
                "predicted_memory=%.2f MB",
                predicted_max,
            )

        else:

            self.broadcast_interval = (
                self.base_broadcast_interval
            )

            self.prune_interval = (
                self.base_prune_interval
            )

        if (
            current_mem_mb
            >= MEMORY_WARNING_THRESHOLD_MB * 1.2
        ):

            logger.warning(
                "[HANDSHAKE] Memory extremely high; "
                "skipping broadcast cycle"
            )

            self.last_broadcast = time.time()

        if self.hud_overlay:

            self.hud_overlay.update_memory()

        return (
            current_mem_mb,
            growth,
        )

    # ======================================================
    # QBIT VALUE
    # ======================================================

    def get_qbit_value(self):

        qbit = self.qbit

        if qbit is None:

            qbit = self._resolve_dependency(
                (
                    "qbit",
                    "current_qbit",
                    "active_qbit",
                )
            )

        if qbit is None:

            return 1.0

        for field in (
            "value",
            "qbit_value",
            "signal",
            "strength",
        ):

            value = getattr(
                qbit,
                field,
                None,
            )

            if isinstance(
                value,
                (int, float),
            ):

                return max(
                    0.0,
                    min(
                        1.0,
                        float(value),
                    ),
                )

        if isinstance(
            qbit,
            (int, float),
        ):

            return max(
                0.0,
                min(
                    1.0,
                    float(qbit),
                ),
            )

        return 1.0

    # ======================================================
    # CHANNEL WEIGHTING
    # ======================================================

    def compute_channel_weights(
        self,
        qbit_value=None,
    ):

        qbit = (
            qbit_value
            if qbit_value is not None
            else self.get_qbit_value()
        )

        mem_ratio = (
            self.last_memory_mb
            / MEMORY_WARNING_THRESHOLD_MB
        )

        devices = getattr(
            self.device_manager,
            "devices",
            {},
        )

        session_ratio = (
            len(devices)
            / max(
                1,
                len(self.channels),
            )
        )

        for ch in self.channels:

            base_weight = 1.0

            channel_mult = (
                ch / 3
            )

            weight = (
                base_weight
                * channel_mult
                * (1 + mem_ratio)
                * (1 + session_ratio)
                * qbit
            )

            self.channel_weights[
                ch
            ] = weight

        logger.debug(
            "[HANDSHAKE] Channel weights: %s",
            self.channel_weights,
        )

    # ======================================================
    # SELECT CHANNELS
    # ======================================================

    def select_channels(self):

        total_weight = sum(
            self.channel_weights.values()
        )

        if total_weight <= 0:

            return []

        probabilities = {
            ch: weight / total_weight
            for ch, weight
            in self.channel_weights.items()
        }

        return [
            ch
            for ch, probability
            in probabilities.items()
            if probability >= 0.3
        ]

    # ======================================================
    # APPLY CHANNEL WEIGHT
    # ======================================================

    def apply_channel_weight(
        self,
        frame,
        weight,
    ):

        frame.meta = getattr(
            frame,
            "meta",
            {},
        )

        if not isinstance(
            frame.meta,
            dict,
        ):

            frame.meta = {}

        frame.meta[
            "weight"
        ] = weight

        return frame

    # ======================================================
    # IDENTITY METADATA
    # ======================================================

    def collect_identity_metadata(
        self,
        packet=None,
    ):

        metadata = {}

        device_manager = (
            self.device_manager
        )

        if device_manager is not None:

            metadata.update(
                {
                    "local_device_id":
                        getattr(
                            device_manager,
                            "local_device_id",
                            None,
                        ),

                    "local_device_name":
                        getattr(
                            device_manager,
                            "local_device_name",
                            None,
                        ),

                    "capabilities":
                        getattr(
                            device_manager,
                            "capabilities",
                            [],
                        ),
                }
            )

        if packet is not None:

            if isinstance(
                packet,
                HandshakePacket,
            ):

                packet_data = (
                    packet.serialize()
                )

            elif isinstance(
                packet,
                dict,
            ):

                packet_data = packet

            else:

                packet_data = {}

            metadata.update(
                {
                    "remote_device_id":
                        packet_data.get(
                            "device_id"
                        ),

                    "remote_device_name":
                        packet_data.get(
                            "device_name"
                        ),

                    "remote_capabilities":
                        packet_data.get(
                            "capabilities",
                            [],
                        ),

                    "nonce":
                        packet_data.get(
                            "nonce"
                        ),

                    "track_id":
                        packet_data.get(
                            "track_id"
                        ),

                    "task_id":
                        packet_data.get(
                            "task_id"
                        ),

                    "pipeline_id":
                        packet_data.get(
                            "pipeline_id"
                        ),

                    "qbit_id":
                        packet_data.get(
                            "qbit_id"
                        ),
                }
            )

            packet_metadata = packet_data.get(
                "metadata"
            )

            if isinstance(
                packet_metadata,
                dict,
            ):

                metadata.update(
                    packet_metadata
                )

        return metadata

    # ======================================================
    # ORACLE METADATA OBSERVATION
    # ======================================================

    def _send_to_oracle(
        self,
        packet,
        metadata,
    ):

        oracle = (
            self.oracle
            or self._resolve_dependency(
                (
                    "oracle",
                    "Oracle",
                )
            )
        )

        if oracle is None:

            return None

        receive_methods = (
            "receive_handshake",
            "receive_identity",
            "receive_metadata",
            "observe",
            "receive",
        )

        payload = {
            "type": "HANDSHAKE",
            "source": "SEEDHandshakeManager",
            "packet": packet,
            "metadata": dict(metadata),
            "timestamp": time.time(),
        }

        for method_name in receive_methods:

            method = getattr(
                oracle,
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

                    try:

                        loop = asyncio.get_running_loop()

                        loop.create_task(
                            result
                        )

                    except RuntimeError:

                        pass

                return result

            except TypeError:

                try:

                    result = method(
                        packet
                    )

                    if inspect.isawaitable(
                        result
                    ):

                        try:

                            loop = asyncio.get_running_loop()

                            loop.create_task(
                                result
                            )

                        except RuntimeError:

                            pass

                    return result

                except Exception:

                    logger.debug(
                        "[HANDSHAKE] Oracle method failed | method=%s",
                        method_name,
                        exc_info=True,
                    )

            except Exception:

                logger.debug(
                    "[HANDSHAKE] Oracle observation failed | method=%s",
                    method_name,
                    exc_info=True,
                )

        return None

    # ======================================================
    # QBIT DIALER OBSERVATION
    # ======================================================

    def _send_to_qbit_dialer(
        self,
        packet,
        metadata,
    ):

        dialer = (
            self.qbit_dialer
            or self._resolve_dependency(
                (
                    "qbit_dialer",
                    "dialer",
                )
            )
        )

        if dialer is None:

            return None

        receive = getattr(
            dialer,
            "_process_received_qbit",
            None,
        )

        if not callable(receive):

            receive = getattr(
                dialer,
                "_process_qbit",
                None,
            )

        if not callable(receive):

            return None

        # --------------------------------------------------
        # Handshake data is metadata/observation.
        #
        # Do not fabricate a Qbit or directly execute a
        # command from the handshake layer.
        # --------------------------------------------------

        payload = {
            "type": "HANDSHAKE",
            "source": "SEEDHandshakeManager",
            "metadata": dict(metadata),
            "packet": packet,
            "device_id": metadata.get(
                "remote_device_id"
            ),
            "track_id": metadata.get(
                "track_id"
            ),
            "task_id": metadata.get(
                "task_id"
            ),
            "pipeline_id": metadata.get(
                "pipeline_id"
            ),
            "qbit_id": metadata.get(
                "qbit_id"
            ),
            "timestamp": time.time(),
        }

        try:

            result = receive(
                payload
            )

            if inspect.isawaitable(
                result
            ):

                try:

                    loop = asyncio.get_running_loop()

                    loop.create_task(
                        result
                    )

                except RuntimeError:

                    pass

            return result

        except Exception:

            logger.debug(
                "[HANDSHAKE] QbitDialer metadata handoff failed",
                exc_info=True,
            )

        return None

    # ======================================================
    # TRACK SYSTEM REGISTRATION
    # ======================================================

    def _register_track_context(
        self,
        metadata,
    ):

        track_system = (
            self.track_system
            or self._resolve_dependency(
                (
                    "track_system",
                    "trackSystem",
                )
            )
        )

        if track_system is None:

            return None

        track_id = metadata.get(
            "track_id"
        )

        if track_id is None:

            return None

        context = dict(
            metadata
        )

        context[
            "track_id"
        ] = track_id

        for method_name in (
            "register_track",
            "register_context",
            "update_track",
            "observe",
        ):

            method = getattr(
                track_system,
                method_name,
                None,
            )

            if not callable(method):

                continue

            try:

                return method(
                    track_id,
                    context,
                )

            except TypeError:

                try:

                    return method(
                        context
                    )

                except Exception:

                    logger.debug(
                        "[HANDSHAKE] Track registration failed",
                        exc_info=True,
                    )

            except Exception:

                logger.debug(
                    "[HANDSHAKE] Track registration failed",
                    exc_info=True,
                )

        return None

    # ======================================================
    # BROADCAST IDENTITY
    # ======================================================

    def broadcast_identity(self):

        if self._closed:

            return False

        now = time.time()

        interval = getattr(
            self,
            "broadcast_interval",
            self.base_broadcast_interval,
        )

        devices = getattr(
            self.device_manager,
            "devices",
            {},
        )

        if len(devices) == 0:

            interval = NEW_DEVICE_INTERVAL

        unknown_devices = [
            device_id
            for device_id, timestamp
            in self.active_sessions.items()
            if now - timestamp
            > HANDSHAKE_TIMEOUT
        ]

        if (
            not unknown_devices
            and now - self.last_broadcast
            < interval
        ):

            return False

        if (
            self.last_memory_mb
            >= MEMORY_WARNING_THRESHOLD_MB * 1.2
        ):

            logger.warning(
                "[HANDSHAKE] Broadcast suppressed by memory pressure"
            )

            return False

        qbit_input = (
            self.get_qbit_value()
        )

        self.compute_channel_weights(
            qbit_input
        )

        channels_to_process = (
            self.select_channels()
        )

        if not channels_to_process:

            return False

        local_device_id = getattr(
            self.device_manager,
            "local_device_id",
            "unknown",
        )

        local_device_name = getattr(
            self.device_manager,
            "local_device_name",
            "UnknownDevice",
        )

        capabilities = getattr(
            self.device_manager,
            "capabilities",
            [],
        )

        packet = HandshakePacket(

            kind="PING",

            device_id=local_device_id,

            device_name=local_device_name,

            capabilities=capabilities,

            timestamp=now,

            metadata={
                "source":
                    "SEEDHandshakeManager",

                "channel_count":
                    len(channels_to_process),
            },
        )

        payload = packet.serialize()

        for channel in channels_to_process:

            try:

                frame = self.modem.encode(
                    payload
                )

                weighted_frame = (
                    self.apply_channel_weight(
                        frame,
                        self.channel_weights[
                            channel
                        ],
                    )
                )

                if hasattr(
                    weighted_frame,
                    "meta",
                ):

                    weighted_frame.meta[
                        "channel"
                    ] = channel

                self.modem.tx(
                    weighted_frame
                )

            except Exception:

                logger.exception(
                    "[HANDSHAKE] Broadcast failed | channel=%s",
                    channel,
                )

        self.last_broadcast = now

        self.check_memory()

        self._emit(
            "HANDSHAKE_BROADCAST",
            {
                "device_id":
                    local_device_id,

                "device_name":
                    local_device_name,

                "channels":
                    channels_to_process,

                "timestamp":
                    now,
            },
        )

        return True

    # ======================================================
    # HANDLE INCOMING FRAME
    # ======================================================

    def handle_incoming(
        self,
        frame,
    ):

        try:

            payload = getattr(
                frame,
                "payload",
                {},
            )

            if not isinstance(
                payload,
                dict,
            ):

                return False

            if not HandshakePacket.validate(
                payload
            ):

                return False

            packet = (
                HandshakePacket.from_payload(
                    payload
                )
            )

            device_id = (
                packet.device_id
            )

            local_device_id = getattr(
                self.device_manager,
                "local_device_id",
                None,
            )

            if (
                device_id
                == local_device_id
            ):

                return False

            now = time.time()

            self.active_sessions[
                device_id
            ] = now

            metadata = (
                self.collect_identity_metadata(
                    packet
                )
            )

            metadata[
                "received_at"
            ] = now

            metadata[
                "transport"
            ] = "audio"

            metadata[
                "frame_type"
            ] = type(frame).__name__

            self.last_identity = (
                metadata
            )

            self.last_received_packet = (
                packet
            )

            self.handshake_metadata[
                device_id
            ] = dict(metadata)

            self.discovered_devices[
                device_id
            ] = {
                "device_id":
                    device_id,

                "device_name":
                    packet.device_name,

                "capabilities":
                    list(
                        packet.capabilities
                    ),

                "last_seen":
                    now,

                "metadata":
                    dict(metadata),
            }

            # --------------------------------------------------
            # DEVICE MANAGER
            # --------------------------------------------------

            has_device = getattr(
                self.device_manager,
                "has_device",
                None,
            )

            known_device = (
                bool(
                    has_device(
                        device_id
                    )
                )
                if callable(has_device)
                else device_id
                in getattr(
                    self.device_manager,
                    "devices",
                    {},
                )
            )

            if not known_device:

                register_device = getattr(
                    self.device_manager,
                    "register_device",
                    None,
                )

                if callable(
                    register_device
                ):

                    register_device(

                        device_id=device_id,

                        name=packet.device_name,

                        capabilities=(
                            packet.capabilities
                        ),

                        transport="audio",
                    )

                logger.info(
                    "[HANDSHAKE] New device discovered: %s",
                    device_id,
                )

                self._emit(
                    "DEVICE_DISCOVERED",
                    {
                        "device_id":
                            device_id,

                        "device_name":
                            packet.device_name,

                        "capabilities":
                            packet.capabilities,

                        "metadata":
                            metadata,
                    },
                )

            else:

                self._emit(
                    "DEVICE_HANDSHAKE",
                    {
                        "device_id":
                            device_id,

                        "metadata":
                            metadata,
                    },
                )

            # --------------------------------------------------
            # TRACK SYSTEM
            # --------------------------------------------------

            self._register_track_context(
                metadata
            )

            # --------------------------------------------------
            # ORACLE
            # --------------------------------------------------

            self._send_to_oracle(
                packet,
                metadata,
            )

            # --------------------------------------------------
            # QBIT DIALER
            # --------------------------------------------------

            self._send_to_qbit_dialer(
                packet,
                metadata,
            )

            # --------------------------------------------------
            # MEMORY
            # --------------------------------------------------

            self.check_memory()

            return True

        except Exception as exc:

            logger.warning(
                "[HANDSHAKE] Failed to handle incoming frame: %s",
                exc,
                exc_info=True,
            )

            return False

    # ======================================================
    # PRUNE INACTIVE SESSIONS
    # ======================================================

    def prune(self):

        if self._closed:

            return

        now = time.time()

        interval = getattr(
            self,
            "prune_interval",
            self.base_prune_interval,
        )

        if (
            now - self.last_prune
            < interval
        ):

            return

        expired = []

        for device_id, timestamp in list(
            self.active_sessions.items()
        ):

            if (
                now - timestamp
                > HANDSHAKE_TIMEOUT
            ):

                expired.append(
                    device_id
                )

                del self.active_sessions[
                    device_id
                ]

                logger.info(
                    "[HANDSHAKE] Session expired: %s",
                    device_id,
                )

        self.last_prune = now

        for device_id in expired:

            self._emit(
                "DEVICE_SESSION_EXPIRED",
                {
                    "device_id":
                        device_id,

                    "timestamp":
                        now,
                },
            )

        self.check_memory()

    # ======================================================
    # STATUS
    # ======================================================

    def get_status(self):

        return {

            "online":
                not self._closed,

            "active_sessions":
                len(
                    self.active_sessions
                ),

            "known_devices":
                len(
                    getattr(
                        self.device_manager,
                        "devices",
                        {},
                    )
                ),

            "last_memory_mb":
                self.last_memory_mb,

            "broadcast_interval":
                self.broadcast_interval,

            "prune_interval":
                self.prune_interval,

            "oracle_connected":
                self.oracle is not None,

            "qbit_dialer_connected":
                self.qbit_dialer is not None,

            "track_system_connected":
                self.track_system is not None,

            "event_bus_connected":
                self.event_bus is not None,

            "modem_connected":
                self.modem is not None,
        }

    # ======================================================
    # RUNTIME ATTACHMENT
    # ======================================================

    def attach_runtime(
        self,
        *,
        oracle=None,
        qbit_dialer=None,
        qbit=None,
        track_system=None,
        constraint_guardian=None,
        event_bus=None,
        module_registry=None,
        seedcore=None,
        orchestrator=None,
        emit=None,
        hud=None,
    ):

        if oracle is not None:

            self.oracle = oracle

        if qbit_dialer is not None:

            self.qbit_dialer = (
                qbit_dialer
            )

        if qbit is not None:

            self.qbit = qbit

        if track_system is not None:

            self.track_system = (
                track_system
            )

        if constraint_guardian is not None:

            self.constraint_guardian = (
                constraint_guardian
            )

        if event_bus is not None:

            self.event_bus = event_bus

        if module_registry is not None:

            self.module_registry = (
                module_registry
            )

        if seedcore is not None:

            self.seedcore = seedcore

        if orchestrator is not None:

            self.orchestrator = (
                orchestrator
            )

        if emit is not None:

            self.emit = emit

        if hud is not None:

            self.hud = hud

            self.hud_overlay = (
                HUDMemoryOverlay(
                    hud,
                    device_manager=(
                        self.device_manager
                    ),
                )
            )

        logger.info(
            "[HANDSHAKE] Runtime dependencies attached | "
            "oracle=%s | qbit_dialer=%s | "
            "track_system=%s | guardian=%s",
            self.oracle is not None,
            self.qbit_dialer is not None,
            self.track_system is not None,
            self.constraint_guardian is not None,
        )

        return self

    # ======================================================
    # SHUTDOWN
    # ======================================================

    def shutdown(self):

        self._closed = True

        self.active_sessions.clear()

        self.discovered_devices.clear()

        self.handshake_metadata.clear()

        logger.info(
            "[HANDSHAKE] Manager shutdown"
        )


# ==========================================================
# END OF FILE
# ==========================================================