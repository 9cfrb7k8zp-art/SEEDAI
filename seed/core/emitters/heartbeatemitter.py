# ==========================================================
# FILE: heartbeatemitter.py
# PATH: SEED_ROOT/seed/core/emitters/heartbeatemitter.py
#
# SYSTEM: SEED AI OS
# COMPONENT: HeartbeatEmitter
# VERSION: 4.0.0
# BUILD: HEARTBEAT → QBIT → QBITLEQUEUELOOP → QBIT DIALER
# UPDATED: 2026-08-29
#
# ==========================================================
#
# PURPOSE
# ----------------------------------------------------------
# HeartbeatEmitter is the SEED runtime heartbeat clock.
#
# HEARTBEAT IS THE HEART.
#
# It produces runtime SIGNALS.
#
# It does NOT:
#   - create commands
#   - submit commands
#   - execute commands
#   - become the QbitDialer
#   - bypass QbitQueueLoop
#
# The canonical runtime path is:
#
#     HEARTBEAT
#          |
#          v
#        QBIT
#          |
#          v
#    QBIT QUEUE LOOP
#          |
#          v
#     QBIT DIALER
#          |
#          v
#    COMMAND PLANE
#
# Qbit is the canonical data transporter.
#
# ==========================================================
#
# AUTHORITY MODEL
# ----------------------------------------------------------
#
# HEARTBEAT EMITTER
#       |
#       | signal only
#       v
# QBIT
#       |
#       | canonical data / lineage
#       v
# QBIT QUEUE LOOP
#       |
#       | authoritative processing handoff
#       v
# QBIT DIALER
#       |
#       | sole command authority
#       v
# submit_command()
#       |
#       v
# COMMAND PLANE
#
# EVENT BUS
#       |
#       +---- telemetry
#       +---- observation
#       +---- feedback
#
# EventBus does NOT own Qbit state.
# EventBus does NOT recursively route a Qbit back into Dialer.
#
# ==========================================================
#
# HARD CONTRACT
# ----------------------------------------------------------
#
# 1. One heartbeat cycle creates "one" Qbit. " "dont assume the system uses or just has one, if its the data carrier "qbit=bloodcell=data call" 
# 2. Qbit remains the canonical signal/data object.
# 3. Qbit carries identity and lineage. " is this connected to QbitQueueloop" and heartbeatemitter?
# 4. TrackSystem / TrackContext owns track context.
# 5. QbitQueueLoop is the preferred and authoritative Qbit handoff.
# 6. QbitDialer is not called directly when QueueLoop exists.
# 7. The same Qbit object must retain its lineage through the path.
# 8. _process_qbit() MUST NOT queue the Qbit again.
# 9. EventBus is transport/telemetry only.
# 10. HeartbeatEmitter never creates or submits commands.
# 11. HeartbeatEmitter never calls submit_command().
# 12. HeartbeatEmitter never calls create_task() for commands.
# 13. No EventBus → Dialer → EventBus recursive bounce.
# 14. QueueLoop.receive_qbit() is preferred when available.
# 15. put/enqueue/submit are compatibility adapters only.
# 16. Direct Dialer compatibility exists only when NO QueueLoop
#     is attached.
# 17. Missing dependencies fail safely.
# 18. Async processing must not manufacture a second heartbeat Qbit.
# 19. Feedback may influence heartbeat timing/state only.
# 20. Heartbeat output is signal data, never command authority.
#
# ==========================================================


import asyncio
import hashlib
import inspect
import json
import logging
import os
import random
import threading
import time
from pathlib import Path


# ----------------------------------------------------------
# SEED DEPENDENCIES
# ----------------------------------------------------------

from seed.core.track_context import TrackContext
from seed.core.track_id_manager import TrackIDManager
from seed.core.qbit.qbit import Qbit
from seed.core.channel_manager import ChannelManager, ChannelNode
from seed.core.compiler.qbit_compiler import QbitCompiler
from seed.core.neural.neural_bridge import NeuralBridge


# ----------------------------------------------------------
# LOGGER
# ----------------------------------------------------------

logger = logging.getLogger("HeartbeatEmitter")
logger.setLevel(logging.INFO)


class HeartbeatEmitter:

    HEARTBEAT_EVENT = "HEARTBEAT"

    # ------------------------------------------------------
    # Signal-only fields.
    #
    # These are explicitly NOT command admission fields.
    # ------------------------------------------------------

    COMMAND_FIELDS = {
        "command",
        "commands",
        "command_list",
        "command_queue",
        "execute",
        "execution",
        "submit_command",
        "action",
        "actions",
    }

    # ======================================================
    # INIT
    # ======================================================

    def __init__(
        self,
        *,
        emit=None,
        ethicsmanager=None,
        qbit=None,
        new_qbit=None,
        track=None,
        track_id=None,
        task_id=None,
        module_name=None,
        event_bus=None,
        qbit_dialer=None,
        queue_loop=None,
        kernel_bus=None,
        heartbeat=None,
        interval=3.0,
        channels=None,
        memory_crystallizer=None,
        constraint_guardian=None,
        **kwargs,
    ):

        # --------------------------------------------------
        # Delayed imports preserved.
        #
        # These imports are intentionally tolerant because
        # HeartbeatEmitter can be initialized before all
        # runtime components have finished booting.
        # --------------------------------------------------

        try:
            from seed.core.event_bus import SEEDEventBus  # noqa: F401
        except Exception:
            SEEDEventBus = None

        try:
            from seed.core.heartbeat import Heartbeat  # noqa: F401
        except Exception:
            Heartbeat = None

        try:
            from seed.core.dialers.qbit_dialer import QbitDialer  # noqa: F401
        except Exception:
            QbitDialer = None

        # --------------------------------------------------
        # Core references
        # --------------------------------------------------

        self.module_name = (
            module_name
            or "HeartbeatEmitter"
        )

        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer
        self.qbit_queue_loop = queue_loop
        self.queue_loop = queue_loop
        self.kernel_bus = kernel_bus
        self.heartbeat = heartbeat
        self.emit = event_bus.emit

        self.memory_crystallizer = (
            memory_crystallizer
        )

        self.constraint_guardian = (
            constraint_guardian
        )

        self.ethicsmanager = ethicsmanager

        self.qbit = qbit
        self.new_qbit = new_qbit

        self.track = track
        self.track_id = track_id
        self.task_id = task_id
        self._submitted_qbit_ids = set()

        # --------------------------------------------------
        # Runtime configuration
        # --------------------------------------------------

        try:
            self.interval = max(
                0.05,
                float(interval),
            )
        except Exception:
            self.interval = 3.0

        # --------------------------------------------------
        # Preserve unknown runtime configuration.
        # --------------------------------------------------

        self.runtime_config = dict(kwargs)

        # --------------------------------------------------
        # Channels
        # --------------------------------------------------

        if channels is None:

            self.channels = [
                ChannelNode(
                    "Qbit",
                    path="/seed/qbit",
                ),
                ChannelNode(
                    "Analytics",
                    path="/seed/analytics",
                ),
                ChannelNode(
                    "Logging",
                    path="/seed/logs",
                ),
            ]

        elif isinstance(
            channels,
            (list, tuple),
        ):

            self.channels = list(
                channels
            )

        else:

            self.channels = [
                channels
            ]

        # --------------------------------------------------
        # Processing components
        # --------------------------------------------------

        try:

            self.compiler = QbitCompiler()

        except Exception:

            self.compiler = None

            logger.warning(
                "[HeartbeatEmitter] "
                "QbitCompiler unavailable",
                exc_info=True,
            )

        try:

            self.neural = NeuralBridge()

        except Exception:

            self.neural = None

            logger.warning(
                "[HeartbeatEmitter] "
                "NeuralBridge unavailable",
                exc_info=True,
            )

        # --------------------------------------------------
        # Runtime loop state
        # --------------------------------------------------

        self.loops = []

        self._running = False
        self._thread = None

        # --------------------------------------------------
        # Async loop reference.
        #
        # Used only when an active runtime loop exists.
        # --------------------------------------------------

        self._async_loop = None

        # --------------------------------------------------
        # Legacy external emit callback.
        #
        # IMPORTANT:
        # Do NOT replace self.emit with another method.
        #
        # The previous architecture dynamically replaced
        # emit(), which could cause duplicate heartbeat/Qbit
        # creation.
        # --------------------------------------------------

        self._external_emit = emit

        # --------------------------------------------------
        # Event history
        # --------------------------------------------------

        self.event_log = []

        # --------------------------------------------------
        # Heartbeat state
        # --------------------------------------------------

        self._tick = 0
        self._last = 0.0
        self._start_time = time.time()

        # --------------------------------------------------
        # Runtime signal metrics
        # --------------------------------------------------

        self._avg_delta = 0.0
        self._drift = 0.0

        # --------------------------------------------------
        # Last runtime objects
        # --------------------------------------------------

        self.last_qbit = None
        self.last_payload = None
        self.last_track_id = None
        self.last_queue_result = None

        # --------------------------------------------------
        # Queue statistics
        # --------------------------------------------------

        self.queue_put_count = 0
        self.queue_error_count = 0

        # --------------------------------------------------
        # Queue routing statistics
        # --------------------------------------------------

        self.queue_receive_count = 0
        self.queue_compat_count = 0
        self.queue_async_count = 0

        # --------------------------------------------------
        # Dialer fallback statistics.
        #
        # Should remain zero whenever QueueLoop is correctly
        # attached.
        # --------------------------------------------------

        self.dialer_fallback_count = 0
        self.dialer_fallback_error_count = 0

        # --------------------------------------------------
        # Feedback statistics
        # --------------------------------------------------

        self.feedback_count = 0
        self.feedback_error_count = 0

        # --------------------------------------------------
        # Safety statistics
        # --------------------------------------------------

        self.command_field_rejection_count = 0
        self.duplicate_dispatch_count = 0

        logger.info(
            "[HeartbeatEmitter] Initialized | "
            "module=%s | interval=%.3fs | "
            "queue_loop=%s | dialer=%s",
            self.module_name,
            self.interval,
            bool(self.queue_loop),
            bool(self.qbit_dialer),
        )

    # ======================================================
    # COMMAND SAFETY
    # ======================================================

    def _sanitize_signal_metadata(
        self,
        metadata,
        preserve_fields=None,
    ):
        if preserve_fields is None:

            preserve_fields = set()

        else:

            preserve_fields = {
                str(field).strip().lower()
                for field in preserve_fields
            }

        if not isinstance(
            metadata,
            dict,
        ):
            return metadata

        sanitized = {}

        for key, value in metadata.items():

            normalized = str(
                key
            ).strip().lower()

            if (
                normalized in self.COMMAND_FIELDS
                and normalized not in preserve_fields
            ):

                self.command_field_rejection_count += 1

                logger.warning(
                    "[HeartbeatEmitter] "
                    "Command field rejected from heartbeat signal: %s",
                    key,
                )

                continue

            sanitized[key] = value

        return sanitized
    # ======================================================
    # QBIT CREATION
    # ======================================================

    def create_qbit(
        self,
        payload=None,
    ):

        if payload is None:

            payload = {
                "module": self.module_name,
                "tick": getattr(
                    self,
                    "_tick",
                    0,
                ),
                "timestamp": time.time(),
                "source": self.module_name,
                "type": self.HEARTBEAT_EVENT,
            }

        if not isinstance(
            payload,
            dict,
        ):

            payload = {
                "value": payload,
                "module": self.module_name,
                "tick": self._tick,
                "timestamp": time.time(),
                "source": self.module_name,
                "type": self.HEARTBEAT_EVENT,
            }

        # --------------------------------------------------
        # Enforce signal-only metadata.
        # --------------------------------------------------

        # --------------------------------------------------
        # Enforce signal-only metadata.
        #
        # Heartbeat planning fields such as "action" are
        # preserved as DATA. They are NOT commands here.
        # --------------------------------------------------

        payload = self._sanitize_signal_metadata(
            payload,
            preserve_fields={
                "action",
            },
        )
        try:

            qbit = Qbit(
                payload=payload
            )

            logger.debug(
                "[HeartbeatEmitter] Qbit created | "
                "id=%s | tick=%s",
                getattr(
                    qbit,
                    "id",
                    None,
                ),
                payload.get(
                    "tick"
                ),
            )

            return qbit

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Qbit creation failed"
            )

            return None

    # ======================================================
    # QUEUE LOOP ATTACHMENT
    # ======================================================

    def attach_queue_loop(
        self,
        queue_loop,
    ):

        self.queue_loop = queue_loop

        logger.info(
            "[HeartbeatEmitter] "
            "QbitQueueLoop attached | type=%s",
            (
                type(queue_loop).__name__
                if queue_loop
                else None
            ),
        )

        return queue_loop

    # ======================================================
    # QBIT DIALER ATTACHMENT
    # ======================================================

    def attach_qbit_dialer(
        self,
        qbit_dialer,
        memory_crystallizer=None,
    ):

        self.qbit_dialer = qbit_dialer

        if memory_crystallizer is not None:

            self.memory_crystallizer = (
                memory_crystallizer
            )

        logger.info(
            "[HeartbeatEmitter] "
            "QbitDialer attached | type=%s",
            (
                type(qbit_dialer).__name__
                if qbit_dialer
                else None
            ),
        )

        return qbit_dialer

    # ======================================================
    # KERNEL BUS ATTACHMENT
    # ======================================================

    def attach_kernel_bus(
        self,
        kernel_bus,
    ):

        self.kernel_bus = kernel_bus

        logger.info(
            "[HeartbeatEmitter] "
            "KernelBus attached | type=%s",
            (
                type(kernel_bus).__name__
                if kernel_bus
                else None
            ),
        )

        return kernel_bus

    # ======================================================
    # EVENT BUS ATTACHMENT
    # ======================================================

    def attach_event_bus(
        self,
        event_bus,
    ):

        self.event_bus = event_bus

        logger.info(
            "[HeartbeatEmitter] "
            "EventBus attached | type=%s",
            (
                type(event_bus).__name__
                if event_bus
                else None
            ),
        )

        return event_bus

    # ======================================================
    # LOOP REGISTRATION
    # ======================================================

    def schedule_loop(
        self,
        coro,
        fn=None,
    ):

        if fn is not None:

            self.loops.append(
                fn
            )

        try:

            loop = asyncio.get_running_loop()

            self._async_loop = loop

            if inspect.iscoroutinefunction(
                coro
            ):

                loop.create_task(
                    coro()
                )

            elif callable(coro):

                result = coro()

                if inspect.isawaitable(
                    result
                ):

                    loop.create_task(
                        result
                    )

        except RuntimeError:

            logger.debug(
                "[HeartbeatEmitter] "
                "No running asyncio loop "
                "for scheduled coroutine"
            )

    # ======================================================
    # AUXILIARY PULSE
    # ======================================================

    def pulse(self):

        for fn in list(
            self.loops
        ):

            try:

                result = fn()

                if inspect.isawaitable(
                    result
                ):

                    try:

                        loop = (
                            asyncio.get_running_loop()
                        )

                        self._async_loop = loop

                        loop.create_task(
                            result
                        )

                    except RuntimeError:

                        pass

            except Exception:

                logger.exception(
                    "[HeartbeatEmitter] "
                    "Auxiliary pulse failed"
                )

    # ======================================================
    # POST CHECK
    # ======================================================

    def post_check(self):

        if self.interval <= 0:

            raise ValueError(
                "Heartbeat interval must be > 0"
            )

        if self.queue_loop is None:

            logger.warning(
                "[HeartbeatEmitter] "
                "POST CHECK: QbitQueueLoop "
                "not attached"
            )

        if self.event_bus is None:

            logger.warning(
                "[HeartbeatEmitter] "
                "POST CHECK: EventBus "
                "not attached"
            )

        if (
            self.queue_loop is not None
            and self.qbit_dialer is None
        ):

            logger.warning(
                "[HeartbeatEmitter] "
                "QueueLoop attached but "
                "QbitDialer not yet attached"
            )

        logger.info(
            "[POST] HeartbeatEmitter %s OK | "
            "interval=%.3fs | queue=%s | "
            "dialer=%s | event_bus=%s",
            self.module_name,
            self.interval,
            bool(self.queue_loop),
            bool(self.qbit_dialer),
            bool(self.event_bus),
        )

        return True

    # ======================================================
    # WAIT FOR RUNTIME DEPENDENCIES
    # ======================================================

    def _wait_for_modules(
        self,
        timeout=5.0,
    ):

        start_time = time.time()

        while (
            time.time() - start_time
            < timeout
        ):

            track_ready = hasattr(
                TrackIDManager,
                "generate",
            )

            queue_ready = (
                self.queue_loop
                is not None
            )

            event_ready = (
                self.event_bus is not None
                and hasattr(
                    self.event_bus,
                    "publish",
                )
            )

            dialer_ready = (
                self.qbit_dialer
                is not None
            )

            # --------------------------------------------------
            # QueueLoop is the preferred runtime handoff.
            #
            # EventBus alone is NOT considered sufficient for
            # command-plane synchronization.
            # --------------------------------------------------

            if (
                track_ready
                and (
                    queue_ready
                    or event_ready
                    or dialer_ready
                )
            ):

                return True

            time.sleep(
                0.05
            )

        logger.warning(
            "[HeartbeatEmitter] "
            "Dependency wait expired | "
            "event_bus=%s | queue_loop=%s | "
            "dialer=%s",
            bool(self.event_bus),
            bool(self.queue_loop),
            bool(self.qbit_dialer),
        )

        return False

    # ======================================================
    # QUEUE LOOP SUBMISSION
    # ======================================================

    def _queue_qbit(
        self,
        qbit,
    ):

        if qbit is None:

            logger.warning(
                "[HeartbeatEmitter] "
                "Refusing to queue None Qbit"
            )

            return False

        # ==================================================
        # QBIT IDENTITY / GENERATION
        # ==================================================

        qbit_id = getattr(
            qbit,
            "qbit_id",
            None,
        )

        if qbit_id is None:

            qbit_id = getattr(
                qbit,
                "id",
                None,
            )

        # --------------------------------------------------
        # A Qbit may legitimately return through this
        # emitter as feedback for another planning cycle.
        #
        # Processing is NOT duplication.
        #
        # The same generation must not be admitted twice,
        # but a feedback/new-generation Qbit must receive
        # its own identity while preserving lineage.
        # --------------------------------------------------

        payload = getattr(
            qbit,
            "payload",
            None,
        )

        if not isinstance(
            payload,
            dict,
        ):

            payload = {}

        metadata = getattr(
            qbit,
            "metadata",
            None,
        )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {}

        # --------------------------------------------------
        # Determine whether this is a feedback/new-generation
        # submission.
        # --------------------------------------------------

        feedback = bool(
            payload.get(
                "feedback"
            )
            or payload.get(
                "feedback_qbit"
            )
            or payload.get(
                "feedback_loop"
            )
            or metadata.get(
                "feedback"
            )
            or metadata.get(
                "feedback_qbit"
            )
            or metadata.get(
                "feedback_loop"
            )
        )

        generation = (
            payload.get(
                "generation"
            )
            if payload.get(
                "generation"
            ) is not None
            else metadata.get(
                "generation"
            )
        )

        if generation is None:

            generation = getattr(
                qbit,
                "generation",
                0,
            )

        try:

            generation = int(
                generation
            )

        except Exception:

            generation = 0

        # ==================================================
        # FEEDBACK GENERATION
        # ==================================================

        if feedback:

            # --------------------------------------------------
            # Preserve the original identity as lineage.
            # --------------------------------------------------

            parent_qbit_id = (
                payload.get(
                    "parent_qbit_id"
                )
                or metadata.get(
                    "parent_qbit_id"
                )
                or payload.get(
                    "source_qbit_id"
                )
                or metadata.get(
                    "source_qbit_id"
                )
                or qbit_id
            )

            # --------------------------------------------------
            # Feedback represents a NEW generation.
            #
            # It must not be blocked merely because its parent
            # Qbit was already processed.
            # --------------------------------------------------

            generation = generation + 1

            new_qbit_id = (
                "QBIT."
                + uuid.uuid4().hex[:12]
            )

            # --------------------------------------------------
            # Preserve lineage/history in payload metadata.
            # --------------------------------------------------

            payload[
                "parent_qbit_id"
            ] = parent_qbit_id

            payload[
                "source_qbit_id"
            ] = qbit_id

            payload[
                "generation"
            ] = generation

            payload[
                "feedback"
            ] = True

            payload[
                "feedback_loop"
            ] = True

            payload[
                "processed"
            ] = True

            payload[
                "learning_from_history"
            ] = True

            payload[
                "previous_generation"
            ] = generation - 1

            # --------------------------------------------------
            # Keep the lineage visible to the next cognitive
            # stage without creating another authority.
            # --------------------------------------------------

            history = (
                payload.get(
                    "history"
                )
            )

            if not isinstance(
                history,
                list,
            ):

                history = []

            history.append(
                {
                    "qbit_id":
                        qbit_id,

                    "generation":
                        generation - 1,

                    "feedback":
                        True,

                    "timestamp":
                        time.time(),
                }
            )

            # Bound local lineage history.
            payload[
                "history"
            ] = history[-64:]

            # --------------------------------------------------
            # Attempt to update the canonical Qbit identity.
            #
            # This does NOT create another Qbit object.
            # It advances the identity of the processed Qbit
            # into its next feedback generation.
            # --------------------------------------------------

            try:

                setattr(
                    qbit,
                    "qbit_id",
                    new_qbit_id,
                )

            except Exception:

                pass

            try:

                setattr(
                    qbit,
                    "id",
                    new_qbit_id,
                )

            except Exception:

                pass

            try:

                setattr(
                    qbit,
                    "generation",
                    generation,
                )

            except Exception:

                pass

            try:

                qbit.payload = payload

            except Exception:

                pass

            try:

                if isinstance(
                    getattr(
                        qbit,
                        "metadata",
                        None,
                    ),
                    dict,
                ):

                    qbit.metadata.update(
                        {
                            "parent_qbit_id":
                                parent_qbit_id,

                            "source_qbit_id":
                                qbit_id,

                            "generation":
                                generation,

                            "feedback":
                                True,

                            "feedback_loop":
                                True,

                            "learning_from_history":
                                True,
                        }
                    )

            except Exception:

                logger.debug(
                    "[HeartbeatEmitter] "
                    "Unable to update Qbit metadata "
                    "for feedback generation",
                    exc_info=True,
                )

            qbit_id = new_qbit_id

            logger.debug(
                "[HeartbeatEmitter] "
                "Qbit feedback generation created | "
                "qbit=%s | parent=%s | generation=%s",
                qbit_id,
                parent_qbit_id,
                generation,
            )

        # ==================================================
        # NORMAL GENERATION IDENTITY
        # ==================================================

        if qbit_id is None:

            qbit_id = (
                "QBIT."
                + uuid.uuid4().hex[:12]
            )

            try:

                setattr(
                    qbit,
                    "qbit_id",
                    qbit_id,
                )

            except Exception:

                pass

            try:

                setattr(
                    qbit,
                    "id",
                    qbit_id,
                )

            except Exception:

                pass

        # ==================================================
        # SUBMISSION KEY
        # ==================================================

        # --------------------------------------------------
        # Duplicate protection is generation-aware.
        #
        # Same Qbit + same generation:
        #     duplicate -> suppress
        #
        # Same lineage + new generation:
        #     valid -> admit
        # --------------------------------------------------

        track_id = getattr(
            qbit,
            "track_id",
            None,
        )

        submission_key = (
            f"{qbit_id}:"
            f"{generation}:"
            f"{track_id or ''}"
        )

        if submission_key in (
            self._submitted_qbit_ids
        ):

            logger.debug(
                "[HeartbeatEmitter] "
                "Duplicate Qbit generation suppressed | "
                "qbit=%s | generation=%s | track_id=%s",
                qbit_id,
                generation,
                track_id,
            )

            return True

        # ==================================================
        # QUEUE LOOP
        # ==================================================

        queue_loop = self.queue_loop

        if queue_loop is None:

            logger.warning(
                "[HeartbeatEmitter] "
                "QbitQueueLoop unavailable | "
                "Qbit retained locally | id=%s | generation=%s",
                qbit_id,
                generation,
            )

            return False

        # ==================================================
        # PREFERRED AUTHORITATIVE QUEUELOOP API
        # ==================================================

        receive_qbit = getattr(
            queue_loop,
            "receive_qbit",
            None,
        )

        if callable(
            receive_qbit
        ):

            try:

                result = receive_qbit(
                    qbit
                )

                # --------------------------------------------------
                # Only count/admit the Qbit after the QueueLoop
                # accepted the submission call.
                # --------------------------------------------------

                self.queue_put_count += 1
                self.queue_receive_count += 1
                self.last_queue_result = result

                self._submitted_qbit_ids.add(
                    submission_key
                )

                # --------------------------------------------------
                # Async QueueLoop receiver.
                #
                # Never invoke QbitDialer directly.
                # QueueLoop owns the continuation.
                # --------------------------------------------------

                if inspect.isawaitable(
                    result
                ):

                    self.queue_async_count += 1

                    if not self._schedule_awaitable(
                        result
                    ):

                        self.queue_error_count += 1

                        self._submitted_qbit_ids.discard(
                            submission_key
                        )

                        return False

                logger.debug(
                    "[HeartbeatEmitter] "
                    "Qbit entered QueueLoop.receive_qbit() | "
                    "qbit=%s | generation=%s | "
                    "feedback=%s | tick=%s",
                    qbit_id,
                    generation,
                    feedback,
                    payload.get(
                        "tick",
                        None,
                    ),
                )

                return True

            except TypeError:

                logger.debug(
                    "[HeartbeatEmitter] "
                    "QueueLoop.receive_qbit() "
                    "signature mismatch; trying "
                    "compatibility API"
                )

            except Exception:

                self.queue_error_count += 1

                logger.exception(
                    "[HeartbeatEmitter] "
                    "QueueLoop.receive_qbit() failed | "
                    "qbit=%s | generation=%s",
                    qbit_id,
                    generation,
                )

                return False

        # ==================================================
        # COMPATIBILITY QUEUELOOP APIs
        # ==================================================

        methods = (
            "put",
            "enqueue",
            "submit",
        )

        for method_name in methods:

            method = getattr(
                queue_loop,
                method_name,
                None,
            )

            if not callable(
                method
            ):

                continue

            try:

                result = method(
                    qbit
                )

                self.queue_put_count += 1
                self.queue_compat_count += 1
                self.last_queue_result = result

                self._submitted_qbit_ids.add(
                    submission_key
                )

                if inspect.isawaitable(
                    result
                ):

                    self.queue_async_count += 1

                    if not self._schedule_awaitable(
                        result
                    ):

                        self.queue_error_count += 1

                        self._submitted_qbit_ids.discard(
                            submission_key
                        )

                        return False

                logger.debug(
                    "[HeartbeatEmitter] "
                    "Qbit queued through "
                    "compatibility API | "
                    "method=%s | "
                    "qbit=%s | "
                    "generation=%s | "
                    "feedback=%s | tick=%s",
                    method_name,
                    qbit_id,
                    generation,
                    feedback,
                    payload.get(
                        "tick",
                        None,
                    ),
                )

                return True

            except TypeError:

                continue

            except Exception:

                self.queue_error_count += 1

                logger.exception(
                    "[HeartbeatEmitter] "
                    "QueueLoop.%s failed | "
                    "qbit=%s | generation=%s",
                    method_name,
                    qbit_id,
                    generation,
                )

                return False

        # ==================================================
        # NO QUEUE API
        # ==================================================

        logger.error(
            "[HeartbeatEmitter] "
            "QbitQueueLoop has no supported "
            "submission API | expected "
            "receive_qbit/put/enqueue/submit"
        )

        return False

    # ======================================================
    # PROCESS QBIT
    # ======================================================

    def process_qbit(
        self,
        qbit,
        metadata=None,
    ):

        try:

            qbit = Qbit.ensure(
                qbit
            )

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Qbit.ensure failed"
            )

            return None

        if qbit is None:

            logger.warning(
                "[HeartbeatEmitter] "
                "process_qbit received None"
            )

            return None
        # ==================================================
        # METADATA
        # ==================================================

        if metadata is None:

            metadata = getattr(
                qbit,
                "metadata",
                {},
            )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {
                "value": metadata
            }

        metadata = dict(
            metadata
        )
        # ==================================================
        # NEURAL PROCESSING
        # ==================================================

        if self.neural is not None:

            try:

                neural_result = (
                    self.neural.process_qbit(
                        qbit
                    )
                )

                if inspect.isawaitable(
                    neural_result
                ):

                    self._schedule_awaitable(
                        neural_result
                    )

                elif neural_result is not None:

                    logger.debug(
                        "[HeartbeatEmitter] "
                        "Neural observation completed | "
                        "qbit_id=%s | track_id=%s | "
                        "result_type=%s",
                        getattr(
                            qbit,
                            "id",
                            None,
                        ),
                        getattr(
                            qbit,
                            "track_id",
                            None,
                        ),
                        type(
                            neural_result
                        ).__name__,
                    )

            except Exception:

                logger.warning(
                    "[HeartbeatEmitter] "
                    "Neural Qbit processing failed; "
                    "original Qbit retained",
                    exc_info=True,
                )

        # --------------------------------------------------
        # Preserve the canonical Qbit.
        # --------------------------------------------------

        processed_qbit = qbit
        # ==================================================
        # CANONICAL RETURN
        #
        # Do NOT call _queue_qbit() here.
        #
        # QbitQueueLoop remains the authoritative transport.
        # ==================================================

        return qbit

    # ======================================================
    # START
    # ======================================================

    def start(
        self,
    ):

        if self._running:

            logger.debug(
                "[HeartbeatEmitter] "
                "%s already running",
                self.module_name,
            )

            return True

        # --------------------------------------------------
        # Establish runtime state FIRST.
        # --------------------------------------------------

        self._running = True

        # --------------------------------------------------
        # Capture active asyncio loop when available.
        # --------------------------------------------------

        try:

            self._async_loop = (
                asyncio.get_running_loop()
            )

        except RuntimeError:

            self._async_loop = None

        # --------------------------------------------------
        # Wait briefly for infrastructure.
        # --------------------------------------------------

        self._wait_for_modules()

        # --------------------------------------------------
        # First heartbeat payload.
        # --------------------------------------------------

        payload = {
            "module": self.module_name,
            "tick": self._tick,
            "timestamp": time.time(),
            "source": self.module_name,
            "type": self.HEARTBEAT_EVENT,
        }

        # --------------------------------------------------
        # Create exactly ONE initial Qbit.
        # --------------------------------------------------

        try:

            new_qbit = self.create_qbit(
                payload
            )

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Initial Qbit creation failed"
            )

            self._running = False

            return False

        if new_qbit is None:

            logger.error(
                "[HeartbeatEmitter] "
                "Initial Qbit is None; "
                "startup aborted safely"
            )

            self._running = False

            return False

        self.qbit = new_qbit
        self.new_qbit = new_qbit
        self.last_qbit = new_qbit

        # --------------------------------------------------
        # Ensure payload.
        # --------------------------------------------------

        qbit_payload = getattr(
            new_qbit,
            "payload",
            None,
        )

        if not isinstance(
            qbit_payload,
            dict,
        ):

            qbit_payload = dict(
                payload
            )

            try:

                new_qbit.payload = (
                    qbit_payload
                )

            except Exception:

                logger.warning(
                    "[HeartbeatEmitter] "
                    "Unable to attach "
                    "fallback payload",
                    exc_info=True,
                )

        # --------------------------------------------------
        # Preserve existing TrackID.
        # --------------------------------------------------

        track = getattr(
            new_qbit,
            "track",
            None,
        )

        if isinstance(
            track,
            dict,
        ):

            current_track_id = (
                track.get(
                    "track_id"
                )
            )

        else:

            current_track_id = getattr(
                new_qbit,
                "track_id",
                None,
            )

        if current_track_id is not None:

            qbit_payload.setdefault(
                "track_id",
                current_track_id,
            )

        self.last_track_id = (
            current_track_id
        )

        # ==================================================
        # INITIAL QUEUE HANDOFF
        #
        # QueueLoop is the primary path.
        #
        # Do NOT additionally call QbitDialer when QueueLoop
        # is attached.
        # ==================================================

        queued = self._queue_qbit(
            new_qbit
        )

        if queued:

            logger.info(
                "[HeartbeatEmitter] "
                "Initial Qbit entered "
                "QbitQueueLoop | qbit=%s | "
                "track_id=%s",
                getattr(
                    new_qbit,
                    "id",
                    None,
                ),
                current_track_id,
            )

        elif self.queue_loop is None:

            # ------------------------------------------------
            # Controlled compatibility fallback ONLY because
            # there is no QueueLoop at all.
            # ------------------------------------------------

            if self.qbit_dialer is not None:

                logger.warning(
                    "[HeartbeatEmitter] "
                    "QueueLoop unavailable; "
                    "using direct QbitDialer "
                    "compatibility path"
                )

                self._handoff_to_dialer(
                    new_qbit
                )

            else:

                logger.warning(
                    "[HeartbeatEmitter] "
                    "No QueueLoop or QbitDialer "
                    "attached; initial Qbit retained"
                )

        else:

            # ------------------------------------------------
            # QueueLoop exists but rejected the Qbit.
            #
            # DO NOT bypass the QueueLoop with Dialer.
            # ------------------------------------------------

            logger.error(
                "[HeartbeatEmitter] "
                "QueueLoop rejected initial Qbit. "
                "Direct Dialer bypass blocked."
            )

        # --------------------------------------------------
        # Local Qbit observation/processing.
        #
        # This MUST NOT queue the Qbit again.
        # --------------------------------------------------

        try:

            self._run_async_process_qbit(
                new_qbit,
                metadata=qbit_payload,
            )

        except Exception:

            logger.warning(
                "[HeartbeatEmitter] "
                "Initial Qbit preprocessing failed",
                exc_info=True,
            )

        # --------------------------------------------------
        # Feedback.
        # --------------------------------------------------

        try:

            self.qbit_feedback_loop(
                new_qbit
            )

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Initial feedback failed"
            )

        # --------------------------------------------------
        # Post check.
        # --------------------------------------------------

        try:

            self.post_check()

        except Exception:

            logger.warning(
                "[HeartbeatEmitter] "
                "post_check failed",
                exc_info=True,
            )

        # --------------------------------------------------
        # Start heartbeat worker.
        # --------------------------------------------------

        try:

            self._thread = threading.Thread(
                target=self._loop,
                daemon=True,
                name=(
                    f"HeartbeatEmitter-"
                    f"{self.module_name}"
                ),
            )

            self._thread.start()

        except Exception:

            self._running = False

            logger.exception(
                "[HeartbeatEmitter] "
                "Failed to start "
                "heartbeat worker"
            )

            return False

        logger.info(
            "[HeartbeatEmitter] "
            "%s STARTED | interval=%.3fs | "
            "queue=%s | dialer=%s",
            self.module_name,
            self.interval,
            bool(self.queue_loop),
            bool(self.qbit_dialer),
        )

        return True

    # ======================================================
    # AUTHORITATIVE QBIT HANDOFF
    #
    # HEARTBEAT EMITTER
    #
    # Heartbeat
    #     |
    #     v
    # HeartbeatEmitter
    #     |
    #     v
    # EXISTING QbitQueueLoop
    #     |
    #     v
    # submit_qbit_command()
    #     |
    #     v
    # QbitDialer._process_received_qbit()
    #     |
    #     +----> TrackSystem
    #     |
    #     +----> ComputeBrain
    #     |
    #     +----> TransformerBrain
    #     |
    #     v
    # submit_command()
    #
    # RULES:
    #
    # - QueueLoop is the authoritative Qbit transport.
    # - HeartbeatEmitter does not create a Qbit.
    # - HeartbeatEmitter does not create a queue.
    # - HeartbeatEmitter does not create a second command path.
    # - Raw Qbit remains DATA.
    # - QbitDialer remains command authority.
    # - submit_command() remains the sole executable handoff.
    #
    # DIRECT DIALER HANDOFF:
    #
    # - Allowed ONLY when QueueLoop is unavailable.
    # - Compatibility fallback only.
    # - Never preferred over QueueLoop.
    # ======================================================

    def _handoff_to_dialer(
        self,
        qbit,
    ):

        # ==================================================
        # HARD INPUT VALIDATION
        # ==================================================

        if qbit is None:

            logger.warning(
                "[HeartbeatEmitter] "
                "Qbit handoff rejected | "
                "reason=qbit_unavailable"
            )

            return False

        # ==================================================
        # EXISTING AUTHORITATIVE QUEUE LOOP
        #
        # THIS MUST BE FIRST.
        #
        # Do not bypass QbitQueueLoop when it is attached.
        # ==================================================

        queue_loop = getattr(
            self,
            "queue_loop",
            None,
        )

        if queue_loop is not None:

            submit_qbit = getattr(
                queue_loop,
                "submit_qbit_command",
                None,
            )

            if not callable(
                submit_qbit
            ):

                submit_qbit = getattr(
                    queue_loop,
                    "submit_qbit",
                    None,
                )

            if not callable(
                submit_qbit
            ):

                logger.error(
                    "[HeartbeatEmitter] "
                    "QbitQueueLoop attached but has no "
                    "supported Qbit submission API"
                )

                return False

            # --------------------------------------------------
            # Preserve existing Qbit payload metadata.
            #
            # Do NOT manufacture a new Qbit identity.
            # --------------------------------------------------

            payload = getattr(
                qbit,
                "payload",
                None,
            )

            if payload is None:

                payload = getattr(
                    qbit,
                    "data",
                    {},
                )

            if not isinstance(
                payload,
                dict,
            ):

                payload = {
                    "value": payload,
                }

            payload = dict(
                payload
            )

            payload = self._sanitize_signal_metadata(
                payload
            )

            # --------------------------------------------------
            # Preserve authoritative Track ID if present.
            # --------------------------------------------------

            track_id = payload.get(
                "track_id"
            )

            if track_id is None:

                track_id = getattr(
                    qbit,
                    "track_id",
                    None,
                )

            # --------------------------------------------------
            # Preserve existing Qbit identity.
            #
            # Do NOT create a qbit_id.
            # --------------------------------------------------

            qbit_id = getattr(
                qbit,
                "qbit_id",
                None,
            )

            if qbit_id is None:

                qbit_id = getattr(
                    qbit,
                    "id",
                    None,
                )

            logger.debug(
                "[HeartbeatEmitter] "
                "Qbit -> QbitQueueLoop | "
                "qbit=%s | track=%s",
                qbit_id,
                track_id,
            )

            # ==================================================
            # AUTHORITATIVE QUEUELOOP SUBMISSION
            #
            # Prefer the complete Qbit object.
            #
            # QueueLoop owns delivery into:
            #
            # submit_qbit_command()
            #       |
            #       v
            # QbitDialer._process_received_qbit()
            #
            # No direct command admission occurs here.
            # ==================================================

            try:

                signature = inspect.signature(
                    submit_qbit
                )

                parameters = (
                    signature.parameters
                )

                kwargs = {}

                if "qbit" in parameters:

                    kwargs[
                        "qbit"
                    ] = qbit

                if "track_id" in parameters:

                    kwargs[
                        "track_id"
                    ] = track_id

                if "payload" in parameters:

                    kwargs[
                        "payload"
                    ] = payload

                if "metadata" in parameters:

                    kwargs[
                        "metadata"
                    ] = payload

                # --------------------------------------------------
                # If the API explicitly accepts qbit by keyword,
                # use the authoritative Qbit object directly.
                # --------------------------------------------------

                if "qbit" in parameters:

                    result = submit_qbit(
                        **kwargs
                    )

                else:

                    result = submit_qbit(
                        qbit,
                        **kwargs,
                    )

                if inspect.isawaitable(
                    result
                ):

                    if not self._schedule_awaitable(
                        result
                    ):

                        logger.error(
                            "[HeartbeatEmitter] "
                            "QbitQueueLoop submission scheduling failed | "
                            "qbit=%s | track=%s",
                            qbit_id,
                            track_id,
                        )

                        return False

                logger.debug(
                    "[HeartbeatEmitter] "
                    "Qbit accepted by authoritative QueueLoop | "
                    "qbit=%s | track=%s",
                    qbit_id,
                    track_id,
                )

                return True

            except asyncio.CancelledError:

                raise

            except Exception as exc:

                logger.exception(
                    "[HeartbeatEmitter] "
                    "QbitQueueLoop submission failed | "
                    "qbit=%s | track=%s | error=%s",
                    qbit_id,
                    track_id,
                    exc,
                )

                return False

        # ==================================================
        # DIRECT DIALER COMPATIBILITY FALLBACK
        #
        # Reached ONLY when QueueLoop is unavailable.
        #
        # This is NOT a second primary pipeline.
        # ==================================================

        dialer = getattr(
            self,
            "qbit_dialer",
            None,
        )

        if dialer is None:

            logger.debug(
                "[HeartbeatEmitter] "
                "QbitDialer unavailable | "
                "handoff deferred"
            )

            return False

        self.dialer_fallback_count += 1

        logger.warning(
            "[HeartbeatEmitter] "
            "DIRECT DIALER COMPATIBILITY FALLBACK | "
            "QueueLoop unavailable"
        )

        # ==================================================
        # PREFERRED FALLBACK:
        # receive_qbit()
        #
        # This still enters the authoritative QbitDialer
        # receive pipeline.
        #
        # receive_qbit()
        #       |
        #       v
        # _process_received_qbit()
        # ==================================================

        receive_qbit = getattr(
            dialer,
            "receive_qbit",
            None,
        )

        if callable(
            receive_qbit
        ):

            try:

                payload = getattr(
                    qbit,
                    "payload",
                    None,
                )

                if payload is None:

                    payload = getattr(
                        qbit,
                        "data",
                        {},
                    )

                if not isinstance(
                    payload,
                    dict,
                ):

                    payload = {
                        "value": payload,
                    }

                payload = dict(
                    payload
                )

                payload = self._sanitize_signal_metadata(
                    payload
                )

                try:

                    result = receive_qbit(
                        qbit,
                        metadata=payload,
                    )

                except TypeError as exc:

                    # Only retry for a signature mismatch.
                    if (
                        "metadata" not in str(exc)
                        and "unexpected keyword" not in str(exc)
                    ):

                        raise

                    result = receive_qbit(
                        qbit
                    )

                if inspect.isawaitable(
                    result
                ):

                    if not self._schedule_awaitable(
                        result
                    ):

                        self.dialer_fallback_error_count += 1

                        return False

                logger.debug(
                    "[HeartbeatEmitter] "
                    "Compatibility Qbit receive accepted"
                )

                return True

            except asyncio.CancelledError:

                raise

            except Exception:

                self.dialer_fallback_error_count += 1

                logger.exception(
                    "[HeartbeatEmitter] "
                    "Compatibility dialer receive_qbit failed"
                )

                return False

        # ==================================================
        # LEGACY push_data() FALLBACK
        #
        # Last-resort compatibility only.
        #
        # NEVER executes when QueueLoop exists.
        # ==================================================

        push_data = getattr(
            dialer,
            "push_data",
            None,
        )

        if callable(
            push_data
        ):

            try:

                payload = getattr(
                    qbit,
                    "payload",
                    None,
                )

                if payload is None:

                    payload = getattr(
                        qbit,
                        "data",
                        {},
                    )

                if not isinstance(
                    payload,
                    dict,
                ):

                    payload = {
                        "value": payload,
                    }

                payload = dict(
                    payload
                )

                payload = self._sanitize_signal_metadata(
                    payload
                )

                track_id = payload.get(
                    "track_id"
                )

                signature = inspect.signature(
                    push_data
                )

                parameters = (
                    signature.parameters
                )

                kwargs = {}

                if "track_id" in parameters:

                    kwargs[
                        "track_id"
                    ] = track_id

                if "qbit" in parameters:

                    kwargs[
                        "qbit"
                    ] = qbit

                result = push_data(
                    payload,
                    **kwargs,
                )

                if inspect.isawaitable(
                    result
                ):

                    if not self._schedule_awaitable(
                        result
                    ):

                        self.dialer_fallback_error_count += 1

                        return False

                logger.debug(
                    "[HeartbeatEmitter] "
                    "Legacy dialer push_data accepted"
                )

                return True

            except asyncio.CancelledError:

                raise

            except Exception:

                self.dialer_fallback_error_count += 1

                logger.exception(
                    "[HeartbeatEmitter] "
                    "Legacy dialer push_data failed"
                )

                return False

        # ==================================================
        # NO SUPPORTED HANDOFF
        # ==================================================

        self.dialer_fallback_error_count += 1

        logger.error(
            "[HeartbeatEmitter] "
            "No supported Qbit handoff path | "
            "QueueLoop unavailable | "
            "QbitDialer has no receive_qbit() or push_data()"
        )

        return False


    # ======================================================
    # ASYNC SCHEDULER
    # ======================================================

    def _schedule_awaitable(
        self,
        awaitable,
    ):

        if awaitable is None:

            return True

        # --------------------------------------------------
        # Current running loop.
        # --------------------------------------------------

        try:

            loop = (
                asyncio.get_running_loop()
            )

            self._async_loop = loop

            loop.create_task(
                awaitable
            )

            return True

        except RuntimeError:

            pass

        # --------------------------------------------------
        # Previously captured runtime loop.
        # --------------------------------------------------

        loop = self._async_loop

        if loop is not None:

            try:

                if loop.is_running():

                    asyncio.run_coroutine_threadsafe(
                        awaitable,
                        loop,
                    )

                    return True

            except Exception:

                logger.debug(
                    "[HeartbeatEmitter] "
                    "Captured async loop scheduling failed",
                    exc_info=True,
                )

        # --------------------------------------------------
        # Last compatibility execution path.
        #
        # Only used when there is no runtime loop available.
        # --------------------------------------------------

        try:

            asyncio.run(
                awaitable
            )

            return True

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Awaitable execution failed"
            )

            return False

    # ======================================================
    # INITIAL ASYNC PROCESSING
    # ======================================================

    def _run_async_process_qbit(
        self,
        qbit,
        metadata=None,
    ):

        if qbit is None:

            logger.warning(
                "[HeartbeatEmitter] "
                "Async Qbit processing rejected | "
                "qbit=None"
            )

            return False

        # --------------------------------------------------
        # Try the currently running asyncio loop first.
        # --------------------------------------------------

        try:

            loop = asyncio.get_running_loop()

            self._async_loop = loop

            result = self.process_qbit(
                qbit,
                metadata=metadata,
            )

            # --------------------------------------------------
            # process_qbit() may be synchronous or asynchronous.
            # If it returns an awaitable, schedule it on the
            # already-running loop rather than calling asyncio.run().
            # --------------------------------------------------

            if inspect.isawaitable(result):

                loop.create_task(
                    result
                )

            return True

        except RuntimeError:

            # --------------------------------------------------
            # No running asyncio loop exists in this thread.
            # Fall through to compatibility execution below.
            # --------------------------------------------------

            pass

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Qbit processing failed"
            )

            return False

        # ------------------------------------------------------
        # Compatibility execution when no asyncio loop exists.
        #
        # process_qbit() is normally synchronous. Only invoke
        # asyncio.run() when the returned value is actually
        # awaitable.
        # ------------------------------------------------------

        try:

            result = self.process_qbit(
                qbit,
                metadata=metadata,
            )

            if inspect.isawaitable(result):

                result = asyncio.run(
                    result
                )

            return True

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Async Qbit processing failed"
            )

            return False
    # ======================================================
    # HEARTBEAT WORKER
    # ======================================================

    def _loop(
        self,
    ):

        self._wait_for_modules()

        while self._running:

            cycle_start = time.time()

            try:

                self.emit()

            except Exception:

                logger.exception(
                    "[HeartbeatEmitter] "
                    "Heartbeat cycle failed"
                )

            # ------------------------------------------------
            # Maintain approximate heartbeat cadence without
            # uncontrolled rapid-fire cycles.
            # ------------------------------------------------

            elapsed = (
                time.time()
                - cycle_start
            )

            sleep_for = max(
                0.01,
                self.interval
                - elapsed,
            )

            end_time = (
                time.time()
                + sleep_for
            )

            while self._running:

                remaining = (
                    end_time
                    - time.time()
                )

                if remaining <= 0:

                    break

                time.sleep(
                    min(
                        0.05,
                        remaining,
                    )
                )

    # ======================================================
    # STOP
    # ======================================================

    def stop(
        self,
    ):

        if not self._running:

            return

        logger.info(
            "[HeartbeatEmitter] "
            "Stopping %s",
            self.module_name,
        )

        self._running = False

        if (
            self._thread is not None
            and self._thread.is_alive()
            and self._thread
            is not threading.current_thread()
        ):

            self._thread.join(
                timeout=2.0
            )

        self._thread = None

        logger.info(
            "[HeartbeatEmitter] "
            "%s stopped",
            self.module_name,
        )

    # ======================================================
    # EMIT ONE HEARTBEAT
    # ======================================================

    def emit(
        self,
        **kwargs,
    ):

        now = time.time()

        # --------------------------------------------------
        # Delta
        # --------------------------------------------------

        delta = (
            now - self._last
            if self._last
            else self.interval
        )

        # --------------------------------------------------
        # Protect against pathological timing.
        # --------------------------------------------------

        if delta < 0:

            delta = self.interval

        # --------------------------------------------------
        # Tick
        # --------------------------------------------------

        self._tick += 1
        self._last = now

        # --------------------------------------------------
        # Runtime signal math.
        #
        # SIGNAL ONLY.
        # NO COMMAND DECISIONS.
        # --------------------------------------------------

        uptime = (
            now
            - self._start_time
        )

        tick_density = (
            self._tick
            / max(
                uptime,
                0.0001,
            )
        )

        self._avg_delta = (
            (
                self._avg_delta * 0.9
            )
            + (
                delta * 0.1
            )
            if self._avg_delta
            else delta
        )

        self._drift = (
            delta
            - self._avg_delta
        )

        tempo_multiplier = max(
            0.1,
            min(
                4.0,
                self.interval
                / max(
                    delta,
                    0.0001,
                ),
            ),
        )

        # --------------------------------------------------
        # Build one signal frame per channel.
        #
        # These are frames inside ONE canonical Qbit.
        # They do NOT create individual Qbits.
        # --------------------------------------------------

        channel_payloads = []

        for channel in self.channels:

            # ----------------------------------------------
            # Channel name/path normalization.
            # ----------------------------------------------

            channel_name = getattr(
                channel,
                "name",
                None,
            )

            if channel_name is None:

                channel_name = str(
                    channel
                )

            channel_path = getattr(
                channel,
                "path",
                None,
            )

            # ----------------------------------------------
            # Track context.
            #
            # TrackSystem/TrackContext owns context.
            # HeartbeatEmitter only reads/writes the
            # current lineage marker where supported.
            # ----------------------------------------------

            parent_id_val = None

            try:

                current = getattr(
                    TrackContext,
                    "current",
                    None,
                )

                if callable(
                    current
                ):

                    parent_id_val = current()

                elif current is not None:

                    parent_id_val = str(
                        current
                    )

            except Exception:

                parent_id_val = None

            # ----------------------------------------------
            # TrackID.
            # ----------------------------------------------

            try:

                track_id = (
                    TrackIDManager.generate(
                        channel=channel_name,
                        skill="heartbeat",
                        parent_id=parent_id_val,
                        priority=5,
                    )
                )

            except TypeError:

                # ------------------------------------------
                # Compatibility with alternate
                # TrackIDManager signatures.
                # ------------------------------------------

                try:

                    track_id = (
                        TrackIDManager.generate(
                            payload={
                                "module": self.module_name,
                                "tick": self._tick,
                                "channel": channel_name,
                            },
                            channel=channel_name,
                        )
                    )

                except Exception:

                    track_id = (
                        f"heartbeat_"
                        f"{channel_name}_"
                        f"{self._tick}"
                    )

            except Exception:

                track_id = (
                    f"heartbeat_"
                    f"{channel_name}_"
                    f"{self._tick}"
                )

            # ----------------------------------------------
            # TrackContext update.
            # ----------------------------------------------

            try:

                writer = getattr(
                    TrackContext,
                    "write",
                    None,
                )

                if callable(
                    writer
                ):

                    writer(
                        key="track_id",
                        value=track_id,
                    )

            except Exception:

                logger.debug(
                    "[HeartbeatEmitter] "
                    "TrackContext write failed",
                    exc_info=True,
                )

            # ----------------------------------------------
            # Machine-first signal payload.
            # ----------------------------------------------

            payload = {
                "module": self.module_name,

                "tick": self._tick,

                "timestamp": now,

                "source": self.module_name,

                "type": self.HEARTBEAT_EVENT,

                "channel": channel_name,

                "channel_path": channel_path,

                "track_id": track_id,

                "parent_id": parent_id_val,

                "signal_only": True,

                "qbit_frame": {
                    "tick": self._tick,
                    "delta": delta,
                    "avg_delta": self._avg_delta,
                    "drift": self._drift,
                    "density": tick_density,
                    "uptime": uptime,
                },

                "multiplier": {
                    "tempo": tempo_multiplier,
                    "interval": self.interval,
                },
            }

            channel_payloads.append(
                payload
            )

        # ==================================================
        # CANONICAL QBIT PAYLOAD
        # ==================================================
        #
        # ONE heartbeat = ONE Qbit.
        #
        # Multiple channel signals live inside that ONE Qbit.
        #
        # ==================================================

        qbit_payload = {
            "module": self.module_name,

            "tick": self._tick,

            "timestamp": now,

            "source": self.module_name,

            "type": self.HEARTBEAT_EVENT,

            "signal_only": True,

            "channels": channel_payloads,

            "qbit_frame": {
                "tick": self._tick,
                "delta": delta,
                "avg_delta": self._avg_delta,
                "drift": self._drift,
                "density": tick_density,
                "uptime": uptime,
            },

            "multiplier": {
                "tempo": tempo_multiplier,
                "interval": self.interval,
            },

            "routing": {
                "origin": "HeartbeatEmitter",
                "transport": "Qbit",
                "handoff": "QbitQueueLoop",
                "command_authority": "QbitDialer",
            },
        }

        # --------------------------------------------------
        # External runtime metadata.
        #
        # Filter command fields because heartbeat is signal-only.
        # --------------------------------------------------

        if kwargs:

            runtime = (
                self._sanitize_signal_metadata(
                    dict(kwargs)
                )
            )

            if runtime:

                qbit_payload[
                    "runtime"
                ] = runtime

        # ==================================================
        # CREATE EXACTLY ONE QBIT
        # ==================================================

        qbit = self.create_qbit(
            qbit_payload
        )

        if qbit is None:

            logger.error(
                "[HeartbeatEmitter] "
                "Tick %s produced no Qbit",
                self._tick,
            )

            return None

        self.qbit = qbit
        self.new_qbit = qbit
        self.last_qbit = qbit
        self.last_payload = qbit_payload

        # --------------------------------------------------
        # Preserve primary TrackID.
        # --------------------------------------------------

        primary_track_id = None

        if channel_payloads:

            primary_track_id = (
                channel_payloads[0].get(
                    "track_id"
                )
            )

        if primary_track_id is not None:

            qbit_payload[
                "track_id"
            ] = primary_track_id

            self.last_track_id = (
                primary_track_id
            )

        # ==================================================
        # QUEUE LOOP — PRIMARY PATH
        # ==================================================
        #
        # This is the ONLY normal handoff.
        #
        # The same Qbit object goes forward.
        # ==================================================

        queued = self._queue_qbit(
            qbit
        )

        # --------------------------------------------------
        # Direct Dialer fallback ONLY when QueueLoop DOES NOT
        # EXIST.
        # --------------------------------------------------

        if (
            not queued
            and self.queue_loop is None
        ):

            if self.qbit_dialer is not None:

                self._handoff_to_dialer(
                    qbit
                )

        elif (
            not queued
            and self.queue_loop is not None
        ):

            logger.error(
                "[HeartbeatEmitter] "
                "QbitQueueLoop handoff failed | "
                "DIRECT DIALER BYPASS BLOCKED | "
                "qbit=%s | tick=%s",
                getattr(
                    qbit,
                    "id",
                    None,
                ),
                self._tick,
            )

        # ==================================================
        # KERNEL / SNAPSHOT PROCESSING
        # ==================================================
        #
        # IMPORTANT:
        # _run_async_process_qbit() does NOT queue qbit.
        #
        # It is local observation/compilation only.
        # ==================================================

        self._run_async_process_qbit(
            qbit,
            metadata=qbit_payload,
        )

        # ==================================================
        # EVENTBUS RETURN / ANNOUNCEMENT
        # ==================================================
        #
        # EventBus is transport/telemetry.
        #
        # It does NOT receive another Qbit from Dialer here.
        #
        # ==================================================

        self._publish_heartbeat(
            qbit,
            channel_payloads,
        )

        # ==================================================
        # FEEDBACK
        # ==================================================

        try:

            self.qbit_feedback_loop(
                qbit
            )

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Qbit feedback failed"
            )

        # ==================================================
        # AUXILIARY CALLBACKS
        # ==================================================

        try:

            self.pulse()

        except Exception:

            logger.exception(
                "[HeartbeatEmitter] "
                "Auxiliary pulse failed"
            )

        # ==================================================
        # EXTERNAL EMIT CALLBACK
        # ==================================================
        #
        # Callback receives completed heartbeat signal.
        #
        # It does NOT replace emit().
        # ==================================================

        if (
            self._external_emit is not None
            and self._external_emit
            is not self.emit
        ):

            try:

                result = (
                    self._external_emit(
                        qbit
                    )
                )

                if inspect.isawaitable(
                    result
                ):

                    self._schedule_awaitable(
                        result
                    )

            except TypeError:

                # ------------------------------------------------
                # Compatibility with callbacks expecting no
                # positional arguments.
                # ------------------------------------------------

                try:

                    result = (
                        self._external_emit()
                    )

                    if inspect.isawaitable(
                        result
                    ):

                        self._schedule_awaitable(
                            result
                        )

                except Exception:

                    logger.warning(
                        "[HeartbeatEmitter] "
                        "External emit callback failed",
                        exc_info=True,
                    )

            except Exception:

                logger.warning(
                    "[HeartbeatEmitter] "
                    "External emit callback failed",
                    exc_info=True,
                )

        logger.debug(
            "[HeartbeatEmitter] "
            "HEARTBEAT | tick=%s | "
            "qbit=%s | queue=%s | track=%s",
            self._tick,
            getattr(
                qbit,
                "id",
                None,
            ),
            queued,
            primary_track_id,
        )

        return qbit

    # ======================================================
    # EVENTBUS PUBLISH
    # ======================================================

    def _publish_heartbeat(
        self,
        qbit,
        channel_payloads,
    ):

        if self.event_bus is None:

            return False

        publish = getattr(
            self.event_bus,
            "publish",
            None,
        )

        if not callable(
            publish
        ):

            logger.warning(
                "[HeartbeatEmitter] "
                "EventBus has no publish()"
            )

            return False

        # --------------------------------------------------
        # Publish once per heartbeat.
        # --------------------------------------------------

        payload = getattr(
            qbit,
            "payload",
            {},
        )

        if not isinstance(
            payload,
            dict,
        ):

            payload = {
                "value": payload
            }

        payload = self._sanitize_signal_metadata(
            payload
        )

        track_id = payload.get(
            "track_id"
        )

        try:

            result = publish(
                self.HEARTBEAT_EVENT,
                payload=payload,
                source=self.module_name,
                channel="HEARTBEAT",
                track_id=track_id,
                parent_id=payload.get(
                    "parent_id"
                ),
                priority=5,
            )

            if inspect.isawaitable(
                result
            ):

                self._schedule_awaitable(
                    result
                )

            self.event_log.append(
                {
                    "event": self.HEARTBEAT_EVENT,
                    "tick": self._tick,
                    "timestamp": time.time(),
                    "qbit_id": getattr(
                        qbit,
                        "id",
                        None,
                    ),
                    "track_id": track_id,
                }
            )

            # --------------------------------------------------
            # Keep history bounded.
            # --------------------------------------------------

            if len(
                self.event_log
            ) > 1000:

                del self.event_log[
                    :-1000
                ]

            return True

        except TypeError:

            # ------------------------------------------------
            # Compatibility with simpler EventBus.publish()
            # signatures.
            # ------------------------------------------------

            try:

                result = publish(
                    self.HEARTBEAT_EVENT,
                    payload,
                )

                if inspect.isawaitable(
                    result
                ):

                    self._schedule_awaitable(
                        result
                    )

                return True

            except Exception:

                logger.warning(
                    "[HeartbeatEmitter] "
                    "EventBus publish "
                    "compatibility call failed",
                    exc_info=True,
                )

                return False

        except Exception:

            logger.warning(
                "[HeartbeatEmitter] "
                "EventBus publish failed",
                exc_info=True,
            )

            return False

    # ======================================================
    # QBIT FEEDBACK / SELF-LEARNING
    # ======================================================

    def qbit_feedback_loop(
        self,
        new_qbit: "Qbit",
    ):

        if new_qbit is None:

            return False

        self.feedback_count += 1

        payload = getattr(
            new_qbit,
            "payload",
            {},
        )

        if not isinstance(
            payload,
            dict,
        ):

            payload = {}

        q_val = payload.get(
            "tick",
            1,
        )

        # --------------------------------------------------
        # Qbit state update.
        # --------------------------------------------------

        try:

            state = getattr(
                new_qbit,
                "state",
                None,
            )

            if (
                isinstance(
                    state,
                    (tuple, list),
                )
                and len(state) >= 2
            ):

                alpha = state[0]
                beta = state[1]

                delta = (
                    (
                        q_val % 10
                    )
                    / 50.0
                ) + (
                    random.random()
                    * 0.05
                )

                if random.random() > 0.5:

                    alpha += complex(
                        delta,
                        delta,
                    )

                else:

                    beta += complex(
                        delta,
                        delta,
                    )

                setter = getattr(
                    new_qbit,
                    "set_state",
                    None,
                )

                if callable(
                    setter
                ):

                    setter(
                        (
                            alpha,
                            beta,
                        )
                    )

        except Exception as exc:

            self.feedback_error_count += 1

            try:

                flags = getattr(
                    new_qbit,
                    "flags",
                    None,
                )

                if isinstance(
                    flags,
                    dict,
                ):

                    flags[
                        "feedback_error"
                    ] = str(exc)

            except Exception:

                pass

            logger.warning(
                "[QbitFeedbackLoop] "
                "State update failed: %s",
                exc,
            )

        # --------------------------------------------------
        # Qbit energy.
        # --------------------------------------------------

        try:

            state = getattr(
                new_qbit,
                "state",
                None,
            )

            if (
                isinstance(
                    state,
                    (tuple, list),
                )
                and len(state) >= 2
            ):

                qbit_energy = (
                    abs(state[0]) ** 2
                    + abs(state[1]) ** 2
                )

            else:

                qbit_energy = 0.0

        except Exception:

            qbit_energy = 0.0

        # --------------------------------------------------
        # Adaptive heartbeat timing.
        #
        # Timing is a heartbeat concern, not a command
        # decision.
        # --------------------------------------------------

        self.adaptive_interval(
            qbit_value=qbit_energy
        )

        # --------------------------------------------------
        # Memory.
        # --------------------------------------------------

        if self.memory_crystallizer:

            try:

                self.memory_crystallizer.record(
                    {
                        "tick": self._tick,
                        "qbit_id": getattr(
                            new_qbit,
                            "id",
                            None,
                        ),
                        "qbit_energy": qbit_energy,
                        "qbit_state": getattr(
                            new_qbit,
                            "state",
                            None,
                        ),
                        "payload": getattr(
                            new_qbit,
                            "payload",
                            None,
                        ),
                    }
                )

            except Exception:

                logger.warning(
                    "[HeartbeatEmitter] "
                    "MemoryCrystallizer "
                    "feedback failed",
                    exc_info=True,
                )

        # --------------------------------------------------
        # Constraint Guardian.
        # --------------------------------------------------

        if self.constraint_guardian:

            try:

                monitor = getattr(
                    self.constraint_guardian,
                    "monitor_qbit_energy",
                    None,
                )

                if callable(
                    monitor
                ):

                    monitor(
                        qbit_energy
                    )

            except Exception:

                logger.warning(
                    "[HeartbeatEmitter] "
                    "ConstraintGuardian "
                    "feedback failed",
                    exc_info=True,
                )

        return qbit_energy

    # ======================================================
    # ADAPTIVE INTERVAL
    # ======================================================

    def adaptive_interval(
        self,
        qbit_value=None,
        cpu_load=None,
        mem_load=None,
    ):

        base_interval = 1.0

        interval = base_interval

        # --------------------------------------------------
        # Qbit influence.
        # --------------------------------------------------

        if qbit_value is not None:

            try:

                interval *= max(
                    0.05,
                    1.0
                    - (
                        float(
                            qbit_value
                        ) % 256
                    )
                    / 512.0,
                )

            except Exception:

                pass

        # --------------------------------------------------
        # CPU influence.
        # --------------------------------------------------

        if cpu_load is not None:

            try:

                interval *= max(
                    0.05,
                    min(
                        2.0,
                        50.0
                        / max(
                            float(
                                cpu_load
                            ),
                            1.0,
                        ),
                    ),
                )

            except Exception:

                pass

        # --------------------------------------------------
        # Memory influence.
        # --------------------------------------------------

        if mem_load is not None:

            try:

                interval *= max(
                    0.05,
                    min(
                        2.0,
                        50.0
                        / max(
                            float(
                                mem_load
                            ),
                            1.0,
                        ),
                    ),
                )

            except Exception:

                pass

        # --------------------------------------------------
        # Smooth.
        # --------------------------------------------------

        self.interval = max(
            0.05,
            (
                self.interval * 0.7
            )
            + (
                interval * 0.3
            ),
        )

        return self.interval

    # ======================================================
    # QUEUE STATUS
    # ======================================================

    def queue_status(
        self,
    ):

        queue_loop = self.queue_loop

        if queue_loop is None:

            return {
                "attached": False,
                "type": None,
                "authoritative_path": (
                    "UNAVAILABLE"
                ),
            }

        status = {
            "attached": True,

            "type": type(
                queue_loop
            ).__name__,

            "authoritative_path": (
                "HeartbeatEmitter"
                " -> Qbit"
                " -> QbitQueueLoop"
                " -> QbitDialer"
            ),

            "heartbeat_queue_puts": (
                self.queue_put_count
            ),

            "heartbeat_queue_errors": (
                self.queue_error_count
            ),

            "receive_qbit_count": (
                self.queue_receive_count
            ),

            "compatibility_queue_count": (
                self.queue_compat_count
            ),

            "async_queue_count": (
                self.queue_async_count
            ),

            "direct_dialer_fallback_count": (
                self.dialer_fallback_count
            ),
        }

        # --------------------------------------------------
        # Common status methods.
        # --------------------------------------------------

        for method_name in (
            "status",
            "get_status",
            "snapshot",
        ):

            method = getattr(
                queue_loop,
                method_name,
                None,
            )

            if callable(
                method
            ):

                try:

                    result = method()

                    if isinstance(
                        result,
                        dict,
                    ):

                        status[
                            "queue"
                        ] = result

                    break

                except Exception:

                    pass

        return status

    # ======================================================
    # RUNTIME SYNCHRONIZATION STATUS
    # ======================================================

    def synchronization_status(
        self,
    ):

        queue_loop = self.queue_loop
        dialer = self.qbit_dialer

        queue_receiver = False
        queue_processor = False
        dialer_receiver = False

        if queue_loop is not None:

            queue_receiver = callable(
                getattr(
                    queue_loop,
                    "receive_qbit",
                    None,
                )
            )

            queue_processor = any(
                callable(
                    getattr(
                        queue_loop,
                        name,
                        None,
                    )
                )
                for name in (
                    "process_qbit",
                    "_process_qbit",
                    "run",
                    "start",
                )
            )

        if dialer is not None:

            dialer_receiver = callable(
                getattr(
                    dialer,
                    "receive_qbit",
                    None,
                )
            )

        return {
            "heartbeat": {
                "attached": True,
                "running": self._running,
                "tick": self._tick,
            },

            "qbit": {
                "present": (
                    self.last_qbit is not None
                ),
                "qbit_id": getattr(
                    self.last_qbit,
                    "id",
                    None,
                ),
                "track_id": self.last_track_id,
            },

            "queue_loop": {
                "attached": (
                    queue_loop is not None
                ),
                "receive_qbit": (
                    queue_receiver
                ),
                "processor_detected": (
                    queue_processor
                ),
            },

            "qbit_dialer": {
                "attached": (
                    dialer is not None
                ),
                "receive_qbit": (
                    dialer_receiver
                ),
            },

            "routing": {
                "normal_path": (
                    "HEARTBEAT"
                    " -> QBIT"
                    " -> QBITLEQUEUELOOP"
                    " -> QBIT DIALER"
                ),
                "direct_dialer_allowed": (
                    queue_loop is None
                ),
                "command_authority": (
                    "QbitDialer"
                ),
                "command_admission": (
                    "QbitDialer.submit_command"
                ),
            },

            "safety": {
                "command_field_rejections": (
                    self.command_field_rejection_count
                ),
                "duplicate_dispatches": (
                    self.duplicate_dispatch_count
                ),
                "direct_dialer_fallbacks": (
                    self.dialer_fallback_count
                ),
            },
        }

    # ======================================================
    # RUNTIME STATUS
    # ======================================================

    def status(
        self,
    ):

        return {
            "module": self.module_name,

            "running": self._running,

            "tick": self._tick,

            "interval": self.interval,

            "qbit_id": getattr(
                self.last_qbit,
                "id",
                None,
            ),

            "track_id": self.last_track_id,

            "queue_loop_attached": (
                self.queue_loop is not None
            ),

            "qbit_dialer_attached": (
                self.qbit_dialer is not None
            ),

            "event_bus_attached": (
                self.event_bus is not None
            ),

            "kernel_bus_attached": (
                self.kernel_bus is not None
            ),

            "queue_put_count": (
                self.queue_put_count
            ),

            "queue_error_count": (
                self.queue_error_count
            ),

            "queue_receive_count": (
                self.queue_receive_count
            ),

            "queue_compat_count": (
                self.queue_compat_count
            ),

            "queue_async_count": (
                self.queue_async_count
            ),

            "dialer_fallback_count": (
                self.dialer_fallback_count
            ),

            "dialer_fallback_error_count": (
                self.dialer_fallback_error_count
            ),

            "feedback_count": (
                self.feedback_count
            ),

            "feedback_error_count": (
                self.feedback_error_count
            ),

            "command_field_rejection_count": (
                self.command_field_rejection_count
            ),

            "duplicate_dispatch_count": (
                self.duplicate_dispatch_count
            ),

            "avg_delta": self._avg_delta,

            "drift": self._drift,

            "uptime": (
                time.time()
                - self._start_time
            ),

            "synchronization": (
                self.synchronization_status()
            ),
        }

    # ======================================================
    # GET
    # ======================================================

    def get(
        self,
        key,
        default=None,
    ):

        qbit = self.qbit

        if qbit is None:

            return default

        payload = getattr(
            qbit,
            "payload",
            None,
        )

        if isinstance(
            payload,
            dict,
        ):

            return payload.get(
                key,
                default,
            )

        return default

# ==========================================================
# END HEARTBEAT EMITTER
# ==========================================================
#
# FINAL RUNTIME CONTRACT
#
# HeartbeatEmitter
#       │
#       ├── creates ONE Qbit
#       │
#       ├── preserves TrackID
#       │
#       ├── compiles KernelBus signal
#       │
#       ├── writes Qbit snapshot
#       │
#       ▼
# QbitQueueLoop
#       │
#       ▼
# QbitDialer
#       │
#       ▼
# EventBus
#       │
#       ▼
# Feedback
#       │
#       ▼
# Next heartbeat
#
# NO:
#   duplicate Qbits
#   duplicate Dialer submission
#   dynamic emit monkey-patching
#   undefined locals
#   recursive EventBus bounce
#   unsupported track_id keyword assumptions
#
# ==========================================================