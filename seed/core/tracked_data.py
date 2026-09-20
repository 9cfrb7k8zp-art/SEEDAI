# ==========================================================
# FILE: tracked_data.py
# PATH: C:\SEED_ROOT\seed\core\tracked_data.py
#
# MODULE: TrackedData
# ROLE: CANONICAL TRACK / QBIT DATA ADAPTER
#
# VERSION: 5.0
# UPDATED: 2026-08-29
#
# ==========================================================
#
# [ARCHITECTURE]
#
#                         SYSTEM
#                            |
#                            v
#                       HEARTBEAT
#                            |
#                            v
#                          QBIT
#                    identity + lineage
#                            |
#                            v
#                      TRACKED DATA
#                            |
#                            v
#                       TRACK SYSTEM
#                            |
#                            v
#                      QBIT QUEUE LOOP
#                            |
#                            v
#                       QBIT DIALER
#                            |
#                            v
#                    COMMAND ADMISSION
#
# ==========================================================
#
# [AUTHORITY]
#
# Heartbeat
#   = system clock / pulse / observation
#
# Qbit
#   = data carrier / blood cell / identity carrier
#
# TrackedData
#   = normalized data + Qbit/Track identity bridge
#
# TrackIDManager
#   = Track identity generation
#
# TrackRegistry
#   = Track data persistence
#
# TrackSystem
#   = track/channel authority
#
# QbitQueueLoop
#   = temporal Qbit transport / queue
#
# QbitDialer
#   = Qbit processing / routing / COMMAND AUTHORITY
#
# EventBus
#   = event distribution
#
# ==========================================================
#
# [IMPORTANT]
#
# TrackedData DOES:
#
#   - create/attach the Qbit carrier
#   - preserve Qbit identity
#   - preserve Track identity
#   - preserve parent Track identity
#   - preserve channel identity
#   - preserve correlation identity
#   - create normalized frames
#   - maintain Qbit <-> Track lineage
#   - adapt events into tracked frames
#   - bridge TrackRegistry
#   - notify subscribers
#
# TrackedData DOES NOT:
#
#   - execute commands
#   - instantiate QbitDialer
#   - instantiate QbitQueueLoop
#   - control Heartbeat
#   - control boot/shutdown
#   - directly control HUD
#
# ==========================================================
#
# [DATA AXIOM]
#
#     INPUT
#       |
#       v
#     QBIT
#       |
#       +---- Qbit ID
#       +---- Track ID
#       +---- Parent ID
#       +---- Channel ID
#       +---- Correlation ID
#       |
#       v
#   TRACKED DATA
#       |
#       v
#   TRACK SYSTEM
#       |
#       v
#   QBIT QUEUE LOOP
#       |
#       v
#   QBIT DIALER
#
# ==========================================================
#
# [DESIGN RULE]
#
# Qbit is the blood cell.
#
# TrackedData does not become the brain.
#
# QbitDialer remains the sole command authority.
#
# ==========================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid

from typing import (
    Any,
    Callable,
    Dict,
    Optional,
)

from seed.core.qbit import Qbit

from seed.core.track_base import (
    TrackContextBase as TrackContext,
)

from seed.core.track_id_manager import (
    TrackIDManager,
)

from seed.core.channel_id import (
    ChannelID,
)

from seed.core.track_id import (
    TrackRegistry,
)


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("TrackedData")

if not logger.handlers:
    logger.addHandler(logging.NullHandler())

logger.setLevel(logging.INFO)


# ==========================================================
# MODULE IDENTITY
# ==========================================================

CABI_ID = "CABI-1"
MODULE_ID = "TD-1"
VERSION = "5.0"

DEFAULT_CHANNEL = "GEN"
DEFAULT_PRIORITY = 50
DEFAULT_SOURCE = "SYSTEM"


# ==========================================================
# CHANNEL HELPERS
# ==========================================================

CHANNEL_CORE = "CORE"
CHANNEL_SYSTEM = "SYSTEM"
CHANNEL_USER = "USER"
CHANNEL_QBIT = "QBIT"
CHANNEL_VECTOR = "VECTOR"
CHANNEL_ERROR = "ERROR"


# ==========================================================
# TRACKED DATA
# ==========================================================

class TrackedData:


    _subscribers = []

    # ======================================================
    # INITIALIZATION
    # ======================================================

    def __init__(
        self,
        track_id: str = None,
        data: Optional[dict] = None,
        payload: Any = None,
        qbit: Optional[Qbit] = None,
        **kwargs,
    ):

        # --------------------------------------------------
        # ACTIVE TRACK CONTEXT
        # --------------------------------------------------

        current_track = self._safe_context_get()

        # --------------------------------------------------
        # TRACK IDENTITY
        #
        # Explicit Track ID wins.
        #
        # Existing context is next.
        #
        # Temporary identity is last-resort protection.
        # --------------------------------------------------

        self.track_id = (
            track_id
            or kwargs.pop("track_id", None)
            or current_track
            or self._temporary_track_id()
        )

        # --------------------------------------------------
        # QBIT CARRIER
        #
        # Qbit is now a first-class part of TrackedData.
        #
        # Supplied authoritative Qbit wins.
        #
        # Otherwise a Qbit is created here so the data object
        # never has to exist without a carrier identity.
        #
        # This does NOT create a Dialer or QueueLoop.
        # --------------------------------------------------

        supplied_qbit = (
            qbit
            if qbit is not None
            else kwargs.pop(
                "qbit",
                None,
            )
        )

        self.qbit = self._resolve_qbit(
            supplied_qbit
        )

        # --------------------------------------------------
        # QBIT ID
        # --------------------------------------------------

        self.qbit_id = self._get_qbit_id(
            self.qbit
        )

        # --------------------------------------------------
        # PARENT TRACK
        # --------------------------------------------------

        self.parent_id = kwargs.pop(
            "parent_id",
            current_track,
        )

        # If no parent exists, the current Track is its
        # own root lineage.
        if self.parent_id is None:
            self.parent_id = self.track_id

        # --------------------------------------------------
        # CHANNEL
        # --------------------------------------------------

        self.channel = str(
            kwargs.pop(
                "channel",
                DEFAULT_CHANNEL,
            )
            or DEFAULT_CHANNEL
        ).upper()

        # --------------------------------------------------
        # PRIORITY
        # --------------------------------------------------

        self.priority = self._normalize_priority(
            kwargs.pop(
                "priority",
                DEFAULT_PRIORITY,
            )
        )

        # --------------------------------------------------
        # DATA
        # --------------------------------------------------

        kwargs.pop(
            "data",
            None,
        )

        self.data = (
            dict(data)
            if isinstance(data, dict)
            else (
                data
                if data is not None
                else {}
            )
        )

        # --------------------------------------------------
        # PAYLOAD
        # --------------------------------------------------

        self.payload = payload

        # --------------------------------------------------
        # METADATA
        # --------------------------------------------------

        metadata = kwargs.pop(
            "metadata",
            None,
        )

        self.metadata = dict(
            metadata or {}
        )

        # --------------------------------------------------
        # SOURCE
        # --------------------------------------------------

        self.source_id = kwargs.pop(
            "source_id",
            DEFAULT_SOURCE,
        )

        # --------------------------------------------------
        # DEVICE
        # --------------------------------------------------

        self.device_id = kwargs.pop(
            "device_id",
            None,
        )

        # --------------------------------------------------
        # TIMESTAMP
        # --------------------------------------------------

        self.timestamp = kwargs.pop(
            "timestamp",
            int(time.time() * 1000),
        )

        # --------------------------------------------------
        # STATE
        # --------------------------------------------------

        self.status = kwargs.pop(
            "status",
            "ACTIVE",
        )

        # --------------------------------------------------
        # RESULT
        # --------------------------------------------------

        self.result = kwargs.pop(
            "result",
            None,
        )

        # --------------------------------------------------
        # ERROR
        # --------------------------------------------------

        self.error = kwargs.pop(
            "error",
            None,
        )

        # --------------------------------------------------
        # CORRELATION
        #
        # Track remains the primary logical correlation.
        # Qbit is the physical/data carrier identity.
        # --------------------------------------------------

        self.correlation_id = kwargs.pop(
            "correlation_id",
            self.track_id,
        )

        # --------------------------------------------------
        # QBIT LINEAGE METADATA
        # --------------------------------------------------

        self.lineage = {
            "qbit_id": self.qbit_id,
            "track_id": self.track_id,
            "parent_id": self.parent_id,
            "channel": self.channel,
            "correlation_id": self.correlation_id,
            "source_id": self.source_id,
            "timestamp": self.timestamp,
        }

        # --------------------------------------------------
        # COPY IDENTITY INTO QBIT WHEN SUPPORTED
        #
        # Do not assume a particular Qbit implementation.
        # Only synchronize attributes that actually exist or
        # can safely be assigned.
        # --------------------------------------------------

        self._bind_qbit_identity()

        # --------------------------------------------------
        # PRESERVE LEGACY ATTRIBUTES
        # --------------------------------------------------

        for key, value in kwargs.items():

            setattr(
                self,
                key,
                value,
            )

    # ======================================================
    # QBIT RESOLUTION
    # ======================================================

    @staticmethod
    def _resolve_qbit(
        qbit: Optional[Qbit],
    ):

        # --------------------------------------------------
        # Existing Qbit wins.
        # --------------------------------------------------

        if isinstance(
            qbit,
            Qbit,
        ):

            return qbit

        # --------------------------------------------------
        # Reject an invalid supplied carrier rather than
        # silently treating arbitrary objects as Qbits.
        # --------------------------------------------------

        if qbit is not None:

            logger.warning(
                "[TrackedData] Invalid Qbit carrier rejected | "
                "type=%s",
                type(qbit).__name__,
            )

        # --------------------------------------------------
        # Create canonical Qbit carrier.
        #
        # Qbit() is the observed runtime construction
        # contract.
        # --------------------------------------------------

        try:

            carrier = Qbit()

            logger.debug(
                "[TrackedData] Qbit carrier created | "
                "qbit=%s",
                TrackedData._get_qbit_id(
                    carrier
                ),
            )

            return carrier

        except Exception as exc:

            logger.error(
                "[TrackedData] Qbit carrier creation failed: %s",
                exc,
                exc_info=True,
            )

            return None

    # ======================================================
    # QBIT ID
    # ======================================================

    @staticmethod
    def _get_qbit_id(
        qbit,
    ):

        if qbit is None:
            return None

        return getattr(
            qbit,
            "qbit_id",
            getattr(
                qbit,
                "id",
                None,
            ),
        )

    # ======================================================
    # QBIT IDENTITY BINDING
    # ======================================================

    def _bind_qbit_identity(
        self,
    ):

        if self.qbit is None:
            return

        # --------------------------------------------------
        # Track ID
        # --------------------------------------------------

        try:

            if hasattr(
                self.qbit,
                "track_id",
            ):

                self.qbit.track_id = (
                    self.track_id
                )

        except Exception:
            pass

        # --------------------------------------------------
        # Parent Track ID
        # --------------------------------------------------

        try:

            if hasattr(
                self.qbit,
                "parent_id",
            ):

                self.qbit.parent_id = (
                    self.parent_id
                )

        except Exception:
            pass

        # --------------------------------------------------
        # Channel
        # --------------------------------------------------

        try:

            if hasattr(
                self.qbit,
                "channel",
            ):

                self.qbit.channel = (
                    self.channel
                )

        except Exception:
            pass

        # --------------------------------------------------
        # Correlation ID
        # --------------------------------------------------

        try:

            if hasattr(
                self.qbit,
                "correlation_id",
            ):

                self.qbit.correlation_id = (
                    self.correlation_id
                )

        except Exception:
            pass

    # ======================================================
    # TEMPORARY TRACK ID
    # ======================================================

    @staticmethod
    def _temporary_track_id():

        return (
            "TMP-"
            + uuid.uuid4().hex[:8]
        )

    # ======================================================
    # TRACK CONTEXT
    # ======================================================

    @staticmethod
    def _safe_context_get():

        try:

            return TrackContext.get()

        except Exception:

            try:

                return TrackContext.current()

            except Exception:

                return None

    # ======================================================
    # PRIORITY
    # ======================================================

    @staticmethod
    def _normalize_priority(
        priority,
    ):

        if isinstance(
            priority,
            str,
        ):

            values = {
                "LOW": 10,
                "MED": 50,
                "MEDIUM": 50,
                "HIGH": 80,
                "CRITICAL": 100,
            }

            return values.get(
                priority.upper(),
                DEFAULT_PRIORITY,
            )

        try:

            return int(priority)

        except Exception:

            return DEFAULT_PRIORITY

    # ======================================================
    # QBIT FRAME
    # ======================================================

    def to_frame(
        self,
    ):

        """
        Return the canonical transport frame.

        This is data only.

        It does not execute anything.
        """

        return {
            "qbit": self.qbit,
            "qbit_id": self.qbit_id,
            "track_id": self.track_id,
            "parent_id": self.parent_id,
            "channel": self.channel,
            "priority": self.priority,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "data": self.data,
            "metadata": dict(self.metadata),
            "source_id": self.source_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "lineage": dict(self.lineage),
        }

    # ======================================================
    # TRACK GENERATION
    # ======================================================

    @staticmethod
    def generate_track(
        *,
        channel="GEN",
        skill=None,
        parent_id=None,
        priority=DEFAULT_PRIORITY,
        domain_override=None,
        actuator_bridge=False,
        qbit_callback=None,
        input_data=None,
        output_data=None,
        module=None,
        driver=None,
        metadata=None,
        emit_hud=False,
        qbit=None,
    ):

        channel = str(
            channel or DEFAULT_CHANNEL
        ).upper()

        metadata = dict(
            metadata or {}
        )

        parent_id = (
            parent_id
            or TrackedData._safe_context_get()
        )

        qbit_callback = (
            list(qbit_callback)
            if isinstance(
                qbit_callback,
                (list, tuple),
            )
            else (
                [qbit_callback]
                if qbit_callback is not None
                else []
            )
        )

        input_data = (
            []
            if input_data is None
            else input_data
        )

        output_data = (
            []
            if output_data is None
            else output_data
        )

        module = (
            []
            if module is None
            else module
        )

        driver = (
            []
            if driver is None
            else driver
        )

        # --------------------------------------------------
        # CREATE / RESOLVE QBIT FIRST
        #
        # This establishes the blood-cell carrier before
        # the Track frame is constructed.
        # --------------------------------------------------

        carrier = TrackedData._resolve_qbit(
            qbit
        )

        qbit_id = TrackedData._get_qbit_id(
            carrier
        )

        try:

            mgr = TrackIDManager()

            track_id = mgr.new(
                channel=channel,
                skill=skill,
                parent_id=parent_id,
                priority=TrackedData._normalize_priority(
                    priority
                ),
                actuator_bridge=actuator_bridge,
                metadata=metadata,
                domain_override=domain_override,
                reasoning_input={
                    "input": input_data,
                    "qbit_id": qbit_id,
                },
                qbit_callback=qbit_callback,
            )

            # --------------------------------------------------
            # Bind Track identity into Qbit.
            # --------------------------------------------------

            if carrier is not None:

                try:

                    if hasattr(
                        carrier,
                        "track_id",
                    ):

                        carrier.track_id = track_id

                    if hasattr(
                        carrier,
                        "parent_id",
                    ):

                        carrier.parent_id = (
                            parent_id
                        )

                    if hasattr(
                        carrier,
                        "channel",
                    ):

                        carrier.channel = (
                            channel
                        )

                    if hasattr(
                        carrier,
                        "correlation_id",
                    ):

                        carrier.correlation_id = (
                            track_id
                        )

                except Exception as exc:

                    logger.debug(
                        "[TrackedData] Qbit identity "
                        "binding skipped: %s",
                        exc,
                    )

            # --------------------------------------------------
            # CHANNEL ID
            # --------------------------------------------------

            try:

                channel_id = ChannelID.next(
                    channel
                )

            except Exception:

                channel_id = channel

            # --------------------------------------------------
            # CANONICAL FRAME
            # --------------------------------------------------

            frame = {
                "qbit": carrier,
                "qbit_id": qbit_id,
                "track_id": track_id,
                "parent_id": parent_id,
                "channel": channel,
                "channel_id": channel_id,
                "skill": skill,
                "priority": TrackedData._normalize_priority(
                    priority
                ),
                "domain": (
                    domain_override
                    or "AUTO"
                ),
                "actuator_bridge": (
                    CABI_ID
                    if actuator_bridge
                    else None
                ),
                "module": module,
                "driver": driver,
                "metadata": metadata,
                "timestamp": int(
                    time.time() * 1000
                ),
                "input": input_data,
                "output": output_data,
                "status": "CREATED",
                "source": MODULE_ID,
                "correlation_id": track_id,
                "lineage": {
                    "qbit_id": qbit_id,
                    "track_id": track_id,
                    "parent_id": parent_id,
                    "channel": channel,
                    "correlation_id": track_id,
                },
            }

            # --------------------------------------------------
            # HUD publication is optional.
            # --------------------------------------------------

            if emit_hud:

                TrackedData.publish(
                    frame
                )

                return frame

            return track_id

        except Exception as exc:

            logger.error(
                "[TrackedData] generate_track failed: %s",
                exc,
                exc_info=True,
            )

            return None

    # ======================================================
    # ASYNC TRACK GENERATION
    # ======================================================

    @staticmethod
    async def generate_track_async(
        **kwargs,
    ):

        await asyncio.sleep(0)

        return TrackedData.generate_track(
            **kwargs
        )

    # ======================================================
    # NORMALIZATION
    # ======================================================

    @staticmethod
    def normalize(
        payload,
        *,
        track_id=None,
        channel=DEFAULT_CHANNEL,
        priority=DEFAULT_PRIORITY,
        metadata=None,
        source_id=DEFAULT_SOURCE,
        parent_id=None,
        qbit=None,
    ):

        current = (
            track_id
            or TrackedData._safe_context_get()
        )

        carrier = TrackedData._resolve_qbit(
            qbit
        )

        qbit_id = TrackedData._get_qbit_id(
            carrier
        )

        return {
            "qbit": carrier,
            "qbit_id": qbit_id,
            "track_id": current,
            "parent_id": (
                parent_id
                or current
            ),
            "channel": str(
                channel or DEFAULT_CHANNEL
            ).upper(),
            "priority": TrackedData._normalize_priority(
                priority
            ),
            "payload": payload,
            "metadata": dict(
                metadata or {}
            ),
            "source_id": source_id,
            "timestamp": time.time(),
            "correlation_id": current,
            "lineage": {
                "qbit_id": qbit_id,
                "track_id": current,
                "parent_id": (
                    parent_id
                    or current
                ),
                "channel": str(
                    channel or DEFAULT_CHANNEL
                ).upper(),
                "correlation_id": current,
            },
        }

    # ======================================================
    # SUBSCRIBERS
    # ======================================================

    @classmethod
    def subscribe(
        cls,
        callback: Callable,
    ):

        if not callable(callback):
            return False

        if callback not in cls._subscribers:

            cls._subscribers.append(
                callback
            )

        return True

    # ------------------------------------------------------

    @classmethod
    def unsubscribe(
        cls,
        callback: Callable,
    ):

        try:

            cls._subscribers.remove(
                callback
            )

            return True

        except ValueError:

            return False

    # ------------------------------------------------------

    @classmethod
    def publish(
        cls,
        payload: dict,
    ):

        delivered = 0

        for callback in list(
            cls._subscribers
        ):

            try:

                result = callback(
                    payload
                )

                if inspect.isawaitable(
                    result
                ):

                    logger.debug(
                        "[TrackedData] Async subscriber "
                        "returned awaitable"
                    )

                delivered += 1

            except Exception as exc:

                logger.warning(
                    "[TrackedData] subscriber failed: %s",
                    exc,
                )

        return delivered

    # ======================================================
    # EVENT -> TRACK ADAPTER
    # ======================================================

    @staticmethod
    def emit_event(
        *,
        event: str,
        channel: str,
        payload=None,
        system_phase=None,
        success=None,
        qbit_callback=None,
        metadata=None,
        module=None,
        qbit=None,
    ):

        metadata = dict(
            metadata or {}
        )

        if system_phase is not None:

            metadata[
                "system_phase"
            ] = system_phase

        if success is not None:

            metadata[
                "success"
            ] = success

        return TrackedData.generate_track(
            channel=channel,
            skill=event,
            metadata=metadata,
            input_data=payload,
            module=module,
            qbit_callback=qbit_callback,
            qbit=qbit,
        )

    # ======================================================
    # PHASE EVENT
    # ======================================================

    @staticmethod
    def emit_phase_event(
        phase: str,
        source: str,
        qbit_callback=None,
        metadata=None,
        qbit=None,
    ):

        metadata = dict(
            metadata or {}
        )

        metadata["phase"] = phase
        metadata["source"] = source

        return TrackedData.generate_track(
            channel=CHANNEL_SYSTEM,
            skill="PHASE",
            metadata=metadata,
            qbit_callback=qbit_callback,
            qbit=qbit,
        )

    # ======================================================
    # QBIT RESULT ADAPTER
    # ======================================================

    @staticmethod
    def emit_qbit_result(
        *,
        track_id,
        result=None,
        success=None,
        metadata=None,
        qbit=None,
    ):

        metadata = dict(
            metadata or {}
        )

        carrier = TrackedData._resolve_qbit(
            qbit
        )

        qbit_id = TrackedData._get_qbit_id(
            carrier
        )

        metadata.update(
            {
                "qbit_result": True,
                "success": success,
            }
        )

        frame = {
            "qbit": carrier,
            "qbit_id": qbit_id,
            "track_id": track_id,
            "channel": CHANNEL_QBIT,
            "state": "RESULT",
            "result": result,
            "success": success,
            "metadata": metadata,
            "timestamp": time.time(),
            "source": MODULE_ID,
            "correlation_id": track_id,
            "lineage": {
                "qbit_id": qbit_id,
                "track_id": track_id,
                "channel": CHANNEL_QBIT,
                "correlation_id": track_id,
            },
        }

        TrackedData.publish(
            frame
        )

        return frame

    # ======================================================
    # ERROR ADAPTER
    # ======================================================

    @staticmethod
    def emit_error(
        *,
        track_id=None,
        error=None,
        priority="HIGH",
        metadata=None,
        qbit=None,
    ):

        carrier = TrackedData._resolve_qbit(
            qbit
        )

        qbit_id = TrackedData._get_qbit_id(
            carrier
        )

        resolved_track = (
            track_id
            or TrackedData._safe_context_get()
        )

        frame = {
            "qbit": carrier,
            "qbit_id": qbit_id,
            "track_id": resolved_track,
            "channel": CHANNEL_ERROR,
            "state": "ERROR",
            "priority": TrackedData._normalize_priority(
                priority
            ),
            "error": str(error),
            "metadata": dict(
                metadata or {}
            ),
            "timestamp": time.time(),
            "source": MODULE_ID,
            "correlation_id": resolved_track,
            "lineage": {
                "qbit_id": qbit_id,
                "track_id": resolved_track,
                "channel": CHANNEL_ERROR,
                "correlation_id": resolved_track,
            },
        }

        TrackedData.publish(
            frame
        )

        return frame

    # ======================================================
    # REGISTRY HELPERS
    # ======================================================

    @staticmethod
    def push_data(
        track_id: str,
        data: Any,
    ) -> bool:

        if not track_id:
            return False

        try:

            TrackRegistry.push(
                track_id,
                data,
            )

            return True

        except Exception as exc:

            logger.warning(
                "[TrackedData] push_data failed: %s",
                exc,
            )

            return False

    # ------------------------------------------------------

    @staticmethod
    def pull_data(
        track_id: str,
    ) -> Any:

        if not track_id:
            return None

        try:

            return TrackRegistry.pull(
                track_id
            )

        except Exception as exc:

            logger.warning(
                "[TrackedData] pull_data failed: %s",
                exc,
            )

            return None

    # ======================================================
    # CONTEXT
    # ======================================================

    @classmethod
    def get(cls):

        return cls._safe_context_get()

    # ------------------------------------------------------

    @classmethod
    def current(cls):

        return cls._safe_context_get()

    # ------------------------------------------------------

    @classmethod
    def write(
        cls,
        *args,
        **kwargs,
    ):

        # Legacy compatibility.
        #
        # Do not mutate TrackContext here.
        # TrackSystem remains responsible for context.

        logger.debug(
            "[TrackedData] write called | "
            "args=%s | kwargs=%s",
            args,
            kwargs,
        )

        return False


# ==========================================================
# END FILE
# ==========================================================