# ============================================================================
# SEED AI OS
# FILE: qbit_queue_loop.py
# PATH: C:\SEED_ROOT\seed\core\emitters\qbit_queue_loop.py
#
# VERSION: 3.1.0
# BUILD: QBIT-AUTHORITY-ROUTING / FULL-CYCLE / LIFECYCLE-SAFE /
#        TRACK-AWARE / ASYNC-SAFE
# UPDATED: 2026-08-23
#
# ROLE:
#   SYSTEM QBIT TRANSPORT / PRIORITY / TEMPORAL EXECUTION LOOP
#
# AUTHORITY:
#
#   HeartbeatEmitter
#          |
#          v
#      EventBus
#          |
#          v
#      QbitDialer
#          |
#          v
#   QbitQueueLoop
#          |
#          +----> QbitDialer.execute_command()
#          |
#          +----> Intent / Action transport
#          |
#          +----> Feedback / result routing
#          |
#          +----> Cognition / Memory / TimeTravel
#
# IMPORTANT:
#
#   QbitQueueLoop is NOT the Qbit brain.
#   QbitQueueLoop is NOT a second command registry.
#   QbitQueueLoop does NOT manufacture Qbits.
#   QbitQueueLoop does NOT replace TrackID.
#
#   QbitDialer remains the command authority.
#
# LIFECYCLE:
#
#   CONSTRUCTED
#       |
#       v
#   TRANSPORT READY
#       |
#       v
#   CORE READY
#       |
#       v
#   STARTED
#       |
#       v
#   DISPATCHING
#       |
#       v
#   STOPPED
#
# DESIGN RULE:
#
#   Queue = transport.
#   Dialer = command authority.
#   Heartbeat = control signal source.
#   EventBus = system event transport.
#   TrackID = identity continuity.
#
# ============================================================================

from __future__ import annotations

import asyncio
import inspect
import logging
import queue as pyqueue
import threading
import time

from collections import deque
from typing import Any, Callable, Dict, Optional


log = logging.getLogger("QbitQueueLoop")


# ============================================================================
# PRIORITY
# ============================================================================

PRIORITY_CRITICAL = "CRITICAL"
PRIORITY_NORMAL = "NORMAL"
PRIORITY_BACKGROUND = "BACKGROUND"

PRIORITY_ORDER = (
    PRIORITY_CRITICAL,
    PRIORITY_NORMAL,
    PRIORITY_BACKGROUND,
)


DEFAULT_REPLAY_BUFFER = 256
DEFAULT_BATCH_SIZE = 16
DEFAULT_THROTTLE_HZ = 60.0


# ============================================================================
# SAFE HELPERS
# ============================================================================

def _safe_get(
    obj: Any,
    name: str,
    default: Any = None,
) -> Any:

    try:

        if isinstance(obj, dict):
            return obj.get(name, default)

        return getattr(obj, name, default)

    except Exception:
        return default


def _is_qbit_like(
    item: Any,
) -> bool:

    if item is None:
        return False

    if type(item).__name__.lower() == "qbit":
        return True

    return any(
        hasattr(item, attr)
        for attr in (
            "command_list",
            "commands",
            "task",
            "qbit_id",
            "upstream_track",
            "qbit_state",
        )
    )


def _extract_command_list(
    item: Any,
) -> list:

    # ==========================================================
    # RAW QBIT = DATA
    #
    # Never extract command vocabulary from a raw Qbit here.
    # The Qbit goes through the Dialer's cognitive receive path.
    # ==========================================================

    if _is_qbit_like(
        item
    ):

        value = _safe_get(
            item,
            "command_list",
            None,
        )

        # A Qbit command_list can contain actual downstream
        # command/control data, but the Qbit itself remains DATA.
        if value is None:
            return []

        if isinstance(
            value,
            (list, tuple, deque),
        ):

            return list(
                value
            )

        if isinstance(
            value,
            str,
        ):

            return [
                value
            ]

        if isinstance(
            value,
            dict,
        ):

            return [
                value
            ]

        return []

    # ==========================================================
    # DICTIONARY / COMMAND ENVELOPE
    # ==========================================================

    value = _safe_get(
        item,
        "command_list",
        None,
    )

    if value is not None:

        if isinstance(
            value,
            (list, tuple, deque),
        ):

            return list(
                value
            )

        if isinstance(
            value,
            str,
        ):

            return [
                value
            ]

        if isinstance(
            value,
            dict,
        ):

            return [
                value
            ]

    # ==========================================================
    # IMPORTANT:
    #
    # DO NOT read task["commands"] here.
    #
    # create_task() uses:
    #
    #     task["commands"]
    #
    # as the capability/vocabulary contract.
    #
    # Those names must NOT automatically become execution
    # requests.
    # ==========================================================

    return []

def _extract_task(
    item: Any,
) -> Optional[dict]:

    task = _safe_get(
        item,
        "task",
        None,
    )

    if isinstance(task, dict):
        return task

    return None


def _extract_metadata(
    item: Any,
) -> dict:

    metadata = _safe_get(
        item,
        "metadata",
        None,
    )

    if isinstance(metadata, dict):
        return dict(metadata)

    return {}


def _extract_track_id(
    item: Any,
) -> Optional[str]:

    value = _safe_get(
        item,
        "track_id",
        None,
    )

    if value is None:
        value = _safe_get(
            item,
            "track",
            None,
        )

    return value


def _extract_channel_id(
    item: Any,
) -> Optional[str]:

    value = _safe_get(
        item,
        "channel_id",
        None,
    )

    if value is None:
        value = _safe_get(
            item,
            "channel",
            None,
        )

    return value


def _extract_parent_id(
    item: Any,
) -> Optional[str]:

    value = _safe_get(
        item,
        "parent_id",
        None,
    )

    if value is None:
        value = _safe_get(
            item,
            "parent_track_id",
            None,
        )

    return value


def _has_command_marker(
    item: Any,
) -> bool:

    return any(
        _safe_get(
            item,
            field,
            None,
        ) is not None
        for field in (
            "name",
            "command",
            "action",
            "cmd",
        )
    )


def _is_empty_command_value(
    value: Any,
) -> bool:

    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    return False


# ============================================================================
# QBIT QUEUE LOOP
# ============================================================================

class QbitQueueLoop:

    # ========================================================================
    # CONSTRUCTION
    # ========================================================================

    def __init__(
        self,
        qbit=None,
        event_bus=None,
        qbit_queue=None,
        handler: Optional[Callable] = None,
        queue=None,
        boot_cycle=None,
        throttle_hz=DEFAULT_THROTTLE_HZ,
        qbitqueueloop=None,
        time_travel_engine=None,
        loop=None,
        priority_engine=None,
        cognition_map=None,
        watchdog=None,
        governor=None,
        track_system=None,
        heartbeatemitter=None,
        memory_graph=None,
        memory_system=None,
        replay_buffer_size=1000,
        batch_size=DEFAULT_BATCH_SIZE,
        auto_activate=True,
        qbit_dialer=None,
    ):

        # --------------------------------------------------------------------
        # EVENT BUS
        # --------------------------------------------------------------------

        self.event_bus = event_bus
        self.qbit = qbit
        # --------------------------------------------------------------------
        # EXTERNAL COMPATIBILITY QUEUE
        #
        # This remains an external source/reference.
        #
        # It is NOT treated as the command authority.
        # --------------------------------------------------------------------

        self.qbit_queue = (
            qbit_queue
            if qbit_queue is not None
            else queue
        )

        # --------------------------------------------------------------------
        # COMMAND AUTHORITY
        # --------------------------------------------------------------------

        self.qbit_dialer = None

        # Handler is retained for legacy/non-command processing.
        self.handler = handler

        # ================================================================
        # QBIT ADMISSION LEDGER
        #
        # One canonical Qbit/track lineage is admitted to QbitDialer
        # only once by this QueueLoop.
        #
        # This does NOT create, copy, or replace the Qbit.
        # It only prevents duplicate transport admission.
        # ================================================================

        self._admitted_qbits = set()

        self._qbit_admission_lock = threading.RLock()

        # --------------------------------------------------------------------
        # SYSTEM REFERENCES
        # --------------------------------------------------------------------

        self.boot_cycle = boot_cycle

        self.priority_engine = priority_engine
        self.cognition_map = cognition_map
        self.watchdog = watchdog
        self.governor = governor
        self.memory_graph = memory_graph
        self.memory_system = memory_system
        self.time_travel_engine = time_travel_engine

        self.qbit_dialer = qbit_dialer
        self.heartbeatemitter = heartbeatemitter
        self.track_system = track_system
        self.event_bus = event_bus

        # --------------------------------------------------------------------
        # PRIORITY QUEUES
        # --------------------------------------------------------------------

        self.priority_queues: Dict[
            str,
            pyqueue.Queue,
        ] = {
            PRIORITY_CRITICAL: pyqueue.Queue(),
            PRIORITY_NORMAL: pyqueue.Queue(),
            PRIORITY_BACKGROUND: pyqueue.Queue(),
        }

        # Legacy compatibility.
        self.queue = self.priority_queues[
            PRIORITY_NORMAL
        ]

        # --------------------------------------------------------------------
        # RUNTIME CONFIG
        # --------------------------------------------------------------------

        try:
            self.throttle_hz = float(
                throttle_hz or 0.0
            )
        except (
            TypeError,
            ValueError,
        ):
            self.throttle_hz = DEFAULT_THROTTLE_HZ

        self.throttle_delay = (
            1.0 / self.throttle_hz
            if self.throttle_hz > 0
            else 0.0
        )

        try:
            self.batch_size = max(
                1,
                int(batch_size),
            )
        except (
            TypeError,
            ValueError,
        ):
            self.batch_size = DEFAULT_BATCH_SIZE

        # --------------------------------------------------------------------
        # LIFECYCLE
        #
        # auto_activate means transport-ready.
        # It does NOT mean worker-running.
        # --------------------------------------------------------------------

        self.active = False
        self.running = False
        self.paused = False
        self.core_ready = False
        self.shutdown_requested = False

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

        self._state_lock = threading.RLock()

        self._thread: Optional[
            threading.Thread
        ] = None

        # Worker identity.
        self._worker_thread_id = None

        # --------------------------------------------------------------------
        # ASYNC OWNER
        # --------------------------------------------------------------------

        self.loop = loop

        # --------------------------------------------------------------------
        # FEEDS
        # --------------------------------------------------------------------

        self.feeds: Dict[
            str,
            Any,
        ] = {}

        # --------------------------------------------------------------------
        # TEMPORAL MEMORY
        # --------------------------------------------------------------------

        try:
            replay_size = max(
                1,
                int(replay_buffer_size),
            )
        except (
            TypeError,
            ValueError,
        ):
            replay_size = DEFAULT_REPLAY_BUFFER

        self.replay_buffer = deque(
            maxlen=replay_size
        )

        # --------------------------------------------------------------------
        # DIAGNOSTICS
        # --------------------------------------------------------------------

        self.stats = {

            # Transport.
            "puts": 0,
            "gets": 0,
            "processed": 0,
            "dropped": 0,

            # Objects.
            "commands_seen": 0,
            "tasks_seen": 0,
            "qbits_seen": 0,
            "dicts_seen": 0,

            # Command execution.
            "commands_dispatched": 0,
            "commands_completed": 0,
            "commands_failed": 0,
            "commands_cancelled": 0,
            "commands_rejected": 0,

            # Temporal.
            "replays": 0,
            "rewinds": 0,

            # Handler.
            "handler_success": 0,
            "handler_failures": 0,

            # Feedback.
            "feedback_submitted": 0,
            "feedback_routed": 0,
            "feedback_rejected": 0,

            # Async.
            "async_gets": 0,
            "async_waits": 0,
            "empty_polls": 0,

            # Feeds.
            "feed_failures": 0,

            # Priority.
            "priority_critical": 0,
            "priority_normal": 0,
            "priority_background": 0,

            # Lifecycle.
            "starts": 0,
            "stops": 0,
            "pauses": 0,
            "resumes": 0,

            # Errors.
            "dispatch_errors": 0,

            # Authority.
            "authority_bind_attempts": 0,
            "authority_bind_failures": 0,

            # External transport.
            "external_queue_reads": 0,
            "external_queue_failures": 0,
        }

        self.last_command = None
        self.last_command_result = None
        self.last_error = None
        self.last_dispatch_time = None

        # --------------------------------------------------------------------
        # COMMAND AUTHORITY BINDING
        # --------------------------------------------------------------------

        if qbit_dialer is not None:
            self.bind_qbit_dialer(
                qbit_dialer
            )

        # --------------------------------------------------------------------
        # TRANSPORT READY
        # --------------------------------------------------------------------

        if auto_activate:
            self._prepare_transport()

        log.info(
            "[QbitQueueLoop] initialized | "
            "transport_ready=%s | running=%s | "
            "dialer_bound=%s | batch=%s | throttle_hz=%s",
            self.active,
            self.running,
            self.qbit_dialer is not None,
            self.batch_size,
            self.throttle_hz,
        )

    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    # ========================================================================
    # QBIT RECEIVE / LINEAGE
    #
    # HEARTBEAT -> QUEUE LOOP
    #
    # A Qbit is an existing data carrier.
    #
    # DO NOT:
    #   - manufacture a replacement Qbit
    #   - convert the Qbit into a command
    #   - execute the Qbit here
    #   - bypass QbitDialer
    #
    # QueueLoop owns transport.
    # QbitDialer owns command admission/execution.
    # ========================================================================

    def _record_qbit_lineage(
        self,
        qbit,
        track_id=None,
        source="QbitQueueLoop",
    ):

        if qbit is None:
            return False

        qbit_id = getattr(
            qbit,
            "qbit_id",
            None,
        )

        lineage_entry = {
            "source": source,
            "qbit_id": qbit_id,
            "track_id": track_id,
            "timestamp": time.time(),
        }

        # ------------------------------------------------------------
        # Prefer the Qbit's own lineage API when available.
        # ------------------------------------------------------------

        for method_name in (
            "record_lineage",
            "add_lineage",
            "append_lineage",
        ):

            method = getattr(
                qbit,
                method_name,
                None,
            )

            if callable(method):

                try:
                    method(
                        lineage_entry
                    )

                    return True

                except TypeError:

                    try:
                        method(
                            source
                        )

                        return True

                    except Exception:
                        pass

                except Exception:
                    pass

        # ------------------------------------------------------------
        # Otherwise maintain QueueLoop-local lineage.
        #
        # This does NOT alter Qbit identity.
        # ------------------------------------------------------------

        if not hasattr(
            self,
            "_qbit_lineage",
        ):

            self._qbit_lineage = deque(
                maxlen=DEFAULT_REPLAY_BUFFER
            )

        self._qbit_lineage.append(
            lineage_entry
        )

        return True


    def _enqueue_qbit(
        self,
        qbit,
        priority=None,
    ):


        if qbit is None:
            return False

        # ------------------------------------------------------------
        # Preserve Qbit identity.
        # ------------------------------------------------------------

        try:

            attach = getattr(
                qbit,
                "attach_queue_loop",
                None,
            )

            if callable(attach):

                attach(
                    self
                )

        except Exception as exc:

            self.last_error = str(
                exc
            )

            log.exception(
                "[QbitQueueLoop] "
                "Qbit queue attachment failed | qbit=%s",
                getattr(
                    qbit,
                    "qbit_id",
                    "UNKNOWN",
                ),
            )

            return False

        # ------------------------------------------------------------
        # Authoritative QueueLoop admission.
        #
        # put() handles:
        #   priority
        #   accounting
        #   broadcast
        #   wake-up
        #
        # It does NOT execute commands.
        # ------------------------------------------------------------

        return self.put(
            qbit,
            priority=priority,
        )
    # ========================================================================
    # RUNTIME AUTHORITY BINDING
    #
    # Runtime dependencies are attached AFTER construction.
    #
    # IMPORTANT:
    #
    # QbitQueueLoop does not discover or manufacture authorities.
    # The boot/runtime layer supplies the authoritative objects.
    #
    # Authority:
    #
    #     QbitDialer       = command authority
    #     HeartbeatEmitter = control signal source
    #     TrackSystem      = track/context authority
    #     EventBus         = event transport
    #
    # ========================================================================

    def bind_runtime(
        self,
        qbit_dialer=None,
        heartbeatemitter=None,
        track_system=None,
        event_bus=None,
    ):

        if event_bus is not None:
            self.event_bus = event_bus

        if qbit_dialer is not None:
            self.bind_qbit_dialer(
                qbit_dialer
            )

        if heartbeatemitter is not None:
            self.heartbeatemitter = (
                heartbeatemitter
            )

        if track_system is not None:
            self.track_system = (
                track_system
            )

        log.info(
            "[QbitQueueLoop] runtime bindings updated | "
            "dialer=%s | heartbeat=%s | "
            "track_system=%s | event_bus=%s",
            self.qbit_dialer is not None,
            self.heartbeatemitter is not None,
            self.track_system is not None,
            self.event_bus is not None,
        )

        return True

    def receive_qbit(self, qbit):

        if qbit is None:
            return False

        # ==========================================================
        # PRESERVE THE QBIT
        #
        # Do NOT manufacture, copy, or replace the Qbit here.
        #
        # A processed Qbit may legitimately return to the QueueLoop
        # as a new generation / feedback cycle. Identity continuity
        # is preserved through lineage metadata.
        # ==========================================================

        track_id = getattr(
            qbit,
            "track_id",
            None,
        )

        channel_id = getattr(
            qbit,
            "channel_id",
            None,
        )

        parent_id = getattr(
            qbit,
            "parent_id",
            None,
        )

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

        # ----------------------------------------------------------
        # GENERATION / CYCLE IDENTITY
        #
        # Same lineage is allowed to re-enter the loop when it
        # represents a new processing generation or feedback cycle.
        #
        # The QueueLoop does not invent a new Qbit ID.
        # It only preserves identity supplied by the Qbit.
        # ----------------------------------------------------------

        generation = metadata.get(
            "generation",
            getattr(
                qbit,
                "generation",
                0,
            ),
        )

        cycle_id = metadata.get(
            "cycle_id",
            getattr(
                qbit,
                "cycle_id",
                None,
            ),
        )

        feedback = bool(
            metadata.get(
                "feedback",
                getattr(
                    qbit,
                    "feedback",
                    False,
                ),
            )
        )

        self._record_qbit_lineage(
            qbit=qbit,
            track_id=track_id,
            source="QbitQueueLoop",
        )

        # ----------------------------------------------------------
        # ADMISSION IDENTITY
        #
        # Duplicate protection belongs to the exact admission
        # event, not the permanent Qbit lineage.
        #
        # Therefore:
        #
        #   same qbit + same generation + same cycle
        #       = duplicate
        #
        #   same qbit + new generation
        #       = valid re-entry
        #
        #   same lineage + new feedback cycle
        #       = valid re-entry
        # ----------------------------------------------------------

        qbit_id = getattr(
            qbit,
            "qbit_id",
            None,
        )

        admission_key = (
            qbit_id,
            track_id,
            parent_id,
            generation,
            cycle_id,
            feedback,
        )

        with self._qbit_admission_lock:

            if admission_key in self._admitted_qbits:
                self.stats[
                    "dropped"
                ] += 1

                log.debug(
                    "[QbitQueueLoop] duplicate admission blocked | "
                    "qbit_id=%s | track_id=%s | generation=%s | "
                    "cycle_id=%s | feedback=%s",
                    qbit_id,
                    track_id,
                    generation,
                    cycle_id,
                    feedback,
                )

                return False

            self._admitted_qbits.add(
                admission_key
            )

        # ==========================================================
        # AUTHORITATIVE TRANSPORT
        #
        # QueueLoop owns transport only.
        # QbitDialer remains command authority.
        # ==========================================================

        accepted = self._enqueue_qbit(
            qbit
        )

        if not accepted:
            # The Qbit was not successfully admitted to transport.
            # Remove the ledger entry so a later valid retry is not
            # incorrectly classified as a duplicate.
            with self._qbit_admission_lock:
                self._admitted_qbits.discard(
                    admission_key
                )

            return False

        return True

    def _prepare_transport(self):

        with self._state_lock:

            self.active = True

            # Transport-ready is NOT execution-ready.
            self.running = False

            self.shutdown_requested = False

            self._stop_event.clear()

        log.info(
            "[QbitQueueLoop] transport ready | execution stopped"
        )

    async def activate(self):

        if self.active:
            return True

        if self.boot_cycle:

            try:

                await self.boot_cycle.wait_for(
                    "CORE_READY",
                    "EVENT_BUS_READY",
                )

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] boot wait skipped: %s",
                    exc,
                )

        self._prepare_transport()

        self._emit(
            "QBIT_QUEUE_READY",
            {
                "active": self.active,
                "running": self.running,
                "core_ready": self.core_ready,
                "dialer_bound": (
                    self.qbit_dialer is not None
                ),
            },
        )

        return True

    def mark_core_ready(self):

        with self._state_lock:
            self.core_ready = True

        log.info(
            "[QbitQueueLoop] CORE_READY"
        )

        self._emit(
            "QBIT_QUEUE_CORE_READY",
            self.status(),
        )

        return True

    def schedule_activate(self):

        if self.active:
            return True

        if self.loop is None:

            self._prepare_transport()

            return True

        try:

            return asyncio.run_coroutine_threadsafe(
                self.activate(),
                self.loop,
            )

        except Exception as exc:

            log.warning(
                "[QbitQueueLoop] schedule_activate failed: %s",
                exc,
            )

            self._prepare_transport()

            return False
# ========================================================================
# QBIT DIALER AUTHORITY
# ========================================================================

    def bind_qbit_dialer(
        self,
        dialer,
    ):
        self.stats[
            "authority_bind_attempts"
        ] += 1

        if dialer is None:

            self.stats[
                "authority_bind_failures"
            ] += 1

            raise TypeError(
                "QbitDialer cannot be None"
            )

        execute = self._resolve_qbit_dialer_executor(
            dialer
        )

        if not callable(execute):

            self.stats[
                "authority_bind_failures"
            ] += 1

            raise TypeError(
                "QbitDialer must expose a callable "
                "command executor"
            )

        self.qbit_dialer = dialer

        # IMPORTANT:
        #
        # Do NOT automatically make execute_command()
        # the generic handler.
        #
        # The dialer is command authority only.
        #
        # Legacy handler remains separate.

        if getattr(
            dialer,
            "execute_command",
            None,
        ) is execute:

            handler_name = "execute_command"

        elif getattr(
            dialer,
            "_execute_qbit_command",
            None,
        ) is execute:

            handler_name = "_execute_qbit_command"

        else:

            handler_name = type(execute).__name__

        log.info(
            "[QbitQueueLoop] QbitDialer command authority bound | %s | handler=%s",
            type(dialer).__name__,
            handler_name,
        )

        self._emit(
            "QBIT_COMMAND_AUTHORITY_BOUND",
            {
                "authority": "QbitDialer",
                "handler": handler_name,
                "queue_role": "transport",
            },
        )
        self._drain_pending_qbits()

    def _drain_pending_qbits(self):
        pending = getattr(
            self,
            "_pending_qbits",
            None,
        )

        if not pending:
            return 0

        self._pending_qbits = []

        drained = 0

        for qbit in pending:

            try:
                self._dispatch(
                    qbit
                )
                drained += 1

            except Exception:
                log.exception(
                    "[QbitQueueLoop] Pending Qbit replay failed | "
                    "qbit_id=%s",
                    _safe_get(
                        qbit,
                        "qbit_id",
                        _safe_get(
                            qbit,
                            "id",
                            None,
                        ),
                    ),
                )

        log.info(
            "[QbitQueueLoop] Pending Qbits drained | count=%s",
            drained,
        )

        return drained

    def _resolve_qbit_dialer_executor(
        self,
        dialer,
    ):
        execute = getattr(
            dialer,
            "execute_command",
            None,
        )

        if callable(execute):
            return execute

        execute = getattr(
            dialer,
            "_execute_qbit_command",
            None,
        )

        if callable(execute):
            return execute

        return None

    def unbind_qbit_dialer(self):

        previous = self.qbit_dialer

        self.qbit_dialer = None

        self._emit(
            "QBIT_COMMAND_AUTHORITY_UNBOUND",
            {
                "authority": (
                    type(previous).__name__
                    if previous is not None
                    else None
                ),
            },
        )

        log.warning(
            "[QbitQueueLoop] QbitDialer authority unbound"
        )

        return True

    def set_handler(
        self,
        handler,
    ):

        if handler is not None and not callable(handler):
            raise TypeError(
                "QbitQueueLoop handler must be callable"
            )

        # Never silently replace QbitDialer authority.
        if (
            handler is not None
            and self.qbit_dialer is not None
            and handler
            is getattr(
                self.qbit_dialer,
                "execute_command",
                None,
            )
        ):
            log.warning(
                "[QbitQueueLoop] refusing to install "
                "QbitDialer.execute_command as generic handler"
            )

            return False

        self.handler = handler

        return True

    # ========================================================================
    # COMMAND IDENTIFICATION
    # ========================================================================

    def is_command_item(
        self,
        item,
    ) -> bool:

        if item is None:
            return False

        # ======================================================
        # RAW QBIT IS DATA
        #
        # A Qbit may contain command vocabulary, task metadata,
        # or downstream commands, but the Qbit object itself is
        # NOT a command item.
        # ======================================================

        if _is_qbit_like(
            item
        ):

            return False

        # ======================================================
        # EXPLICIT COMMAND LIST
        #
        # Only an actual command_list on the item is treated as
        # executable command input here.
        #
        # Do NOT infer commands from task["commands"].
        #
        # create_task() uses task["commands"] as the command
        # vocabulary/capability contract.
        # ======================================================

        command_list = _safe_get(
            item,
            "command_list",
            None,
        )

        if command_list:

            return True

        # ======================================================
        # DIRECT COMMAND ENVELOPE
        # ======================================================

        return _has_command_marker(
            item
        )

    def dispatch_command(
        self,
        command,
        source_item=None,
    ):

        return self._dispatch_command(
            command,
            source_item=source_item,
        )

    # ========================================================================
    # FEEDS
    # ========================================================================

    def register_feed(
        self,
        name: str,
        q: Any,
    ):

        if q is None:
            raise TypeError(
                "Feed cannot be None"
            )

        if not hasattr(q, "put") and not hasattr(
            q,
            "put_nowait",
        ):
            raise TypeError(
                "Feed must expose put() or put_nowait()"
            )

        self.feeds[str(name)] = q

        log.info(
            "[QbitQueueLoop] Feed registered: %s",
            name,
        )

        return True

    def unregister_feed(
        self,
        name: str,
    ):

        self.feeds.pop(
            str(name),
            None,
        )

    # ========================================================================
    # PRIORITY
    # ========================================================================

    def auto_priority(
        self,
        item: Any,
    ) -> str:

        explicit = _safe_get(
            item,
            "priority",
            None,
        )

        if explicit:

            value = str(
                explicit
            ).upper()

            aliases = {
                "HIGH": PRIORITY_CRITICAL,
                "URGENT": PRIORITY_CRITICAL,
                "CRITICAL": PRIORITY_CRITICAL,
                "NORMAL": PRIORITY_NORMAL,
                "MEDIUM": PRIORITY_NORMAL,
                "LOW": PRIORITY_BACKGROUND,
                "BACKGROUND": PRIORITY_BACKGROUND,
            }

            if value in aliases:
                return aliases[value]

        intent = _safe_get(
            item,
            "intent",
            None,
        )

        if intent is None:

            task = _extract_task(
                item
            )

            if task:
                intent = task.get(
                    "intent"
                )

        intent = str(
            intent or ""
        ).upper()

        if intent in {
            "HANDLE_ERROR",
            "REPAIR",
            "SYSTEM_ALERT",
            "SHUTDOWN",
            "EMERGENCY",
            "RECOVERY",
        }:
            return PRIORITY_CRITICAL

        if intent in {
            "RESPOND",
            "EXECUTE",
            "COMMAND",
            "CONTROL",
            "QBIT",
            "SYSTEM",
        }:
            return PRIORITY_NORMAL

        if _has_command_marker(
            item
        ):
            return PRIORITY_NORMAL

        return PRIORITY_BACKGROUND

    def _resolve_priority(
        self,
        item: Any,
        priority=None,
    ) -> str:

        if priority:

            value = str(
                priority
            ).upper()

            aliases = {
                "HIGH": PRIORITY_CRITICAL,
                "URGENT": PRIORITY_CRITICAL,
                "CRITICAL": PRIORITY_CRITICAL,
                "NORMAL": PRIORITY_NORMAL,
                "MEDIUM": PRIORITY_NORMAL,
                "LOW": PRIORITY_BACKGROUND,
                "BACKGROUND": PRIORITY_BACKGROUND,
            }

            value = aliases.get(
                value,
                value,
            )

            if value in self.priority_queues:
                return value

        engine = self.priority_engine

        if engine:

            try:

                if hasattr(
                    engine,
                    "learn",
                ):
                    engine.learn(
                        item
                    )

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] priority learn failed: %s",
                    exc,
                )

            try:

                if hasattr(
                    engine,
                    "get_priority",
                ):

                    result = engine.get_priority(
                        item
                    )

                    if result:

                        result = str(
                            result
                        ).upper()

                        aliases = {
                            "HIGH": PRIORITY_CRITICAL,
                            "URGENT": PRIORITY_CRITICAL,
                            "CRITICAL": PRIORITY_CRITICAL,
                            "NORMAL": PRIORITY_NORMAL,
                            "MEDIUM": PRIORITY_NORMAL,
                            "LOW": PRIORITY_BACKGROUND,
                            "BACKGROUND": PRIORITY_BACKGROUND,
                        }

                        result = aliases.get(
                            result,
                            result,
                        )

                        if result in self.priority_queues:
                            return result

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] priority calculation failed: %s",
                    exc,
                )

        return self.auto_priority(
            item
        )

    # ========================================================================
    # QUEUE INPUT
    # ========================================================================

    async def async_put(
        self,
        item,
        priority=None,
    ):

        return self.put(
            item,
            priority=priority,
        )

    def put(
        self,
        item,
        priority=None,
    ):

        if item is None:

            self.stats[
                "dropped"
            ] += 1

            return False

        if self.shutdown_requested:

            self.stats[
                "dropped"
            ] += 1

            log.warning(
                "[QbitQueueLoop] rejected item "
                "because shutdown is requested"
            )

            self._emit(
                "QBIT_QUEUE_REJECTED",
                {
                    "reason": "shutdown_requested",
                },
            )

            return False

        # Transport may accept items before execution begins.
        if not self.active:
            self._prepare_transport()

        selected = self._resolve_priority(
            item,
            priority,
        )

        target_queue = self.priority_queues[
            selected
        ]

        try:

            target_queue.put(
                item
            )

            self.stats[
                "puts"
            ] += 1

            self.stats[
                f"priority_{selected.lower()}"
            ] += 1

            if _is_qbit_like(item):

                self.stats[
                    "qbits_seen"
                ] += 1

            if isinstance(
                item,
                dict,
            ):

                self.stats[
                    "dicts_seen"
                ] += 1

            commands = _extract_command_list(
                item
            )

            if commands:

                self.stats[
                    "commands_seen"
                ] += len(
                    commands
                )

            elif _has_command_marker(
                item
            ):

                self.stats[
                    "commands_seen"
                ] += 1

            task = _extract_task(
                item
            )

            if task:

                self.stats[
                    "tasks_seen"
                ] += 1

            self._broadcast(
                item
            )

            self._wake_event.set()

            self._emit(
                "QBIT_QUEUE_ACCEPTED",
                self._cycle_payload(
                    item
                ),
            )

            return True

        except Exception as exc:

            self.stats[
                "dropped"
            ] += 1

            self.last_error = str(
                exc
            )

            log.exception(
                "[QbitQueueLoop] queue insertion failed: %s",
                exc,
            )

            return False

    # ========================================================================
    # EXTERNAL QUEUE COMPATIBILITY
    #
    # AUTHORITATIVE TRANSPORT BRIDGE
    #
    # External queue -> QbitQueueLoop internal queue.
    #
    # IMPORTANT:
    #
    #   This method DOES NOT:
    #       - create a Qbit
    #       - create a command
    #       - create a processing loop
    #       - create a QbitDialer
    #       - execute a command
    #
    #   It ONLY transports an already-existing carrier.
    #
    # FLOW:
    #
    #   external qbit_queue
    #           |
    #           v
    #      pull_external()
    #           |
    #           v
    #      Qbit.ensure()
    #           |
    #           v
    #      self.put(Qbit)
    #           |
    #           v
    #      internal queue
    #           |
    #           v
    #      processing loop
    #
    # ========================================================================

    def pull_external(
        self,
        block=False,
        timeout=None,
        priority=None,
    ):

        external = self.qbit_queue

        if external is None:

            self.stats[
                "external_queue_unavailable"
            ] = (
                self.stats.get(
                    "external_queue_unavailable",
                    0,
                )
                + 1
            )

            return None

        try:

            # ---------------------------------------------------------------
            # READ FROM EXTERNAL QUEUE
            # ---------------------------------------------------------------

            if hasattr(
                external,
                "get",
            ):

                if block:

                    item = external.get(
                        block=True,
                        timeout=timeout,
                    )

                else:

                    item = external.get_nowait()

            else:

                raise TypeError(
                    "External qbit_queue does not expose get()"
                )

            self.stats[
                "external_queue_reads"
            ] += 1

            if item is None:

                self.stats[
                    "external_queue_null_items"
                ] = (
                    self.stats.get(
                        "external_queue_null_items",
                        0,
                    )
                    + 1
                )

                return None

            # ---------------------------------------------------------------
            # NORMALIZE THE CARRIER
            #
            # Existing Qbit objects pass through unchanged.
            # Dict payloads may be converted into Qbits.
            #
            # Qbit.ensure() does NOT execute anything.
            # ---------------------------------------------------------------

            try:

                from seed.core.qbit.qbit import Qbit

                qbit = Qbit.ensure(
                    item
                )

            except Exception as exc:

                self.stats[
                    "external_queue_invalid_items"
                ] = (
                    self.stats.get(
                        "external_queue_invalid_items",
                        0,
                    )
                    + 1
                )

                self.last_error = (
                    f"invalid_external_qbit: {exc}"
                )

                log.exception(
                    "[QbitQueueLoop] "
                    "External item could not be normalized | "
                    "type=%s",
                    type(item).__name__,
                )

                return None

            # ---------------------------------------------------------------
            # PRESERVE AUTHORITATIVE QUEUE BINDING
            #
            # Do not replace an existing queue.
            # This only records the current transport owner.
            # ---------------------------------------------------------------

            try:

                qbit.attach_queue_loop(
                    self
                )

            except Exception:

                log.exception(
                    "[QbitQueueLoop] "
                    "Failed to attach queue loop | "
                    "qbit=%s",
                    getattr(
                        qbit,
                        "qbit_id",
                        "UNKNOWN",
                    ),
                )

                return None

            # ---------------------------------------------------------------
            # TRANSPORT INTO INTERNAL QUEUE
            # ---------------------------------------------------------------
            #
            # IMPORTANT:
            #
            # self.put() is the authoritative internal admission point.
            #
            # It must be the method responsible for:
            #     - priority handling
            #     - sequence/tie-breaking
            #     - queue accounting
            #     - lifecycle transition
            #
            # It must NOT execute the Qbit.
            # ---------------------------------------------------------------

            queued = self.put(
                qbit,
                priority=priority,
            )

            # ---------------------------------------------------------------
            # VERIFY INTERNAL ADMISSION
            # ---------------------------------------------------------------

            if queued is False:

                self.stats[
                    "external_queue_put_failures"
                ] = (
                    self.stats.get(
                        "external_queue_put_failures",
                        0,
                    )
                    + 1
                )

                self.last_error = (
                    "external_qbit_internal_put_failed"
                )

                log.error(
                    "[QbitQueueLoop] "
                    "External Qbit read but internal admission failed | "
                    "qbit=%s",
                    getattr(
                        qbit,
                        "qbit_id",
                        "UNKNOWN",
                    ),
                )

                return None

            # ---------------------------------------------------------------
            # TRANSPORT DIAGNOSTICS
            # ---------------------------------------------------------------

            self.stats[
                "external_qbits_admitted"
            ] = (
                self.stats.get(
                    "external_qbits_admitted",
                    0,
                )
                + 1
            )

            log.debug(
                "[QbitQueueLoop] "
                "External Qbit admitted | "
                "qbit=%s | "
                "track=%s | "
                "priority=%s",
                getattr(
                    qbit,
                    "qbit_id",
                    "UNKNOWN",
                ),
                getattr(
                    qbit,
                    "track_id",
                    "UNKNOWN",
                ),
                priority,
            )

            return qbit

        except pyqueue.Empty:

            # ---------------------------------------------------------------
            # EMPTY IS NORMAL.
            #
            # Do not mark the queue failed merely because a non-blocking
            # poll found nothing.
            # ---------------------------------------------------------------

            return None

        except Exception as exc:

            self.stats[
                "external_queue_failures"
            ] += 1

            self.last_error = str(
                exc
            )

            log.exception(
                "[QbitQueueLoop] "
                "External queue read failed"
            )

            return None

    def drain_external(
        self,
        max_items=None,
    ) -> int:

        count = 0

        if max_items is not None:

            try:
                max_items = max(
                    0,
                    int(max_items),
                )
            except Exception:
                max_items = None

        while (
            max_items is None
            or count < max_items
        ):

            item = self.pull_external(
                block=False
            )

            if item is None:
                break

            count += 1

        if count:
            self._emit(
                "QBIT_EXTERNAL_QUEUE_DRAINED",
                {
                    "count": count,
                },
            )

        return count

    # ========================================================================
    # BROADCAST
    # ========================================================================

    def _broadcast(
        self,
        item,
    ):

        for name, feed in list(
            self.feeds.items()
        ):

            try:

                if hasattr(
                    feed,
                    "put_nowait",
                ):

                    feed.put_nowait(
                        item
                    )

                else:

                    feed.put(
                        item
                    )

            except Exception as exc:

                self.stats[
                    "feed_failures"
                ] += 1

                log.debug(
                    "[QbitQueueLoop] feed '%s' rejected item: %s",
                    name,
                    exc,
                )

    # ========================================================================
    # QUEUE OUTPUT
    # ========================================================================

    def _get_next(
        self,
        block=True,
        timeout=None,
    ):

        if not block:

            for level in PRIORITY_ORDER:

                try:

                    item = (
                        self.priority_queues[
                            level
                        ].get_nowait()
                    )

                    self.stats[
                        "gets"
                    ] += 1

                    return item

                except pyqueue.Empty:
                    continue

            self.stats[
                "empty_polls"
            ] += 1

            raise pyqueue.Empty

        deadline = None

        if timeout is not None:

            try:

                timeout = max(
                    0.0,
                    float(timeout),
                )

                deadline = (
                    time.monotonic()
                    + timeout
                )

            except (
                TypeError,
                ValueError,
            ):

                timeout = None

        poll = 0.05

        while (
            self.running
            or self.depth() > 0
        ):

            for level in PRIORITY_ORDER:

                try:

                    item = (
                        self.priority_queues[
                            level
                        ].get_nowait()
                    )

                    self.stats[
                        "gets"
                    ] += 1

                    return item

                except pyqueue.Empty:
                    continue

            self.stats[
                "empty_polls"
            ] += 1

            if self._stop_event.is_set():
                raise pyqueue.Empty

            if deadline is not None:

                remaining = (
                    deadline
                    - time.monotonic()
                )

                if remaining <= 0:
                    raise pyqueue.Empty

                wait_for = min(
                    poll,
                    remaining,
                )

            else:

                wait_for = poll

            self._wake_event.wait(
                wait_for
            )

            self._wake_event.clear()

        raise pyqueue.Empty

    def get_sync(
        self,
        block=True,
        timeout=None,
    ):

        item = self._get_next(
            block=block,
            timeout=timeout,
        )

        self._record(
            item
        )

        return item

    async def async_get(
        self,
        block=True,
        timeout=None,
    ):

        self.stats[
            "async_gets"
        ] += 1

        if not block:

            return self.get_sync(
                block=False
            )

        while True:

            if (
                self._stop_event.is_set()
                and self.depth() == 0
            ):

                raise asyncio.CancelledError(
                    "QbitQueueLoop stopped"
                )

            self.stats[
                "async_waits"
            ] += 1

            try:

                return await asyncio.to_thread(
                    self.get_sync,
                    True,
                    timeout
                    if timeout is not None
                    else 0.25,
                )

            except pyqueue.Empty:

                if timeout is not None:
                    raise

                if (
                    self._stop_event.is_set()
                    and self.depth() == 0
                ):

                    raise asyncio.CancelledError(
                        "QbitQueueLoop stopped"
                    )

                await asyncio.sleep(
                    0
                )

    async def get(
        self,
        block=True,
        timeout=None,
    ):

        return await self.async_get(
            block=block,
            timeout=timeout,
        )

    def get_nowait(
        self,
    ):

        return self.get_sync(
            block=False
        )

    def depth(
        self,
    ) -> int:

        return sum(
            q.qsize()
            for q in self.priority_queues.values()
        )

    def qsize(
        self,
    ) -> int:

        return self.depth()

    sync_get = get_sync

    # ========================================================================
    # COMMAND NORMALIZATION
    # ========================================================================

    def _command_frame(
        self,
        command,
        source_item=None,
    ):

        # ==========================================================
        # RAW QBIT PROTECTION
        # ==========================================================

        if _is_qbit_like(
            command
        ):

            raise TypeError(
                "[QbitQueueLoop] Raw Qbit cannot be converted "
                "into a command frame"
            )

        # ==========================================================
        # STRING COMMAND
        # ==========================================================

        if isinstance(
            command,
            str,
        ):

            frame = {
                "name": command.strip().upper(),
                "source": "QBIT_QUEUE",
            }

        # ==========================================================
        # DICTIONARY COMMAND
        # ==========================================================

        elif isinstance(
            command,
            dict,
        ):

            frame = dict(
                command
            )

        # ==========================================================
        # OTHER OBJECT
        # ==========================================================

        else:

            raise TypeError(
                "[QbitQueueLoop] Unsupported command object | "
                f"type={type(command).__name__}"
            )

        # ==========================================================
        # SOURCE ITEM IDENTITY
        # ==========================================================

        if source_item is not None:

            for field, extractor in (
                (
                    "track_id",
                    _extract_track_id,
                ),
                (
                    "channel_id",
                    _extract_channel_id,
                ),
                (
                    "parent_id",
                    _extract_parent_id,
                ),
            ):

                value = extractor(
                    source_item
                )

                if value is not None:

                    frame.setdefault(
                        field,
                        value,
                    )

        # ==========================================================
        # QBIT IDENTITY / DATA
        # ==========================================================

        if source_item is not None:

            qbit = _safe_get(
                source_item,
                "qbit",
                None,
            )

            qbit_payload = _safe_get(
                source_item,
                "qbit_payload",
                None,
            )

            if qbit is not None:

                frame.setdefault(
                    "qbit",
                    qbit,
                )

                frame.setdefault(
                    "qbit_id",
                    _safe_get(
                        qbit,
                        "qbit_id",
                        _safe_get(
                            qbit,
                            "id",
                            None,
                        ),
                    ),
                )

                frame.setdefault(
                    "task_id",
                    _safe_get(
                        qbit,
                        "task_id",
                        None,
                    ),
                )

                frame.setdefault(
                    "pipeline_id",
                    _safe_get(
                        qbit,
                        "pipeline_id",
                        None,
                    ),
                )

            if qbit_payload is not None:

                frame.setdefault(
                    "qbit_payload",
                    qbit_payload,
                )

        # ==========================================================
        # METADATA
        # ==========================================================

        source_metadata = (
            _extract_metadata(
                source_item
            )
            if source_item is not None
            else {}
        )

        if source_metadata:

            existing_metadata = dict(
                frame.get(
                    "metadata"
                ) or {}
            )

            merged_metadata = dict(
                source_metadata
            )

            merged_metadata.update(
                existing_metadata
            )

            frame[
                "metadata"
            ] = merged_metadata

        frame.setdefault(
            "source",
            "QBIT_QUEUE",
        )

        return frame

    # ========================================================================
    # COMMAND DISPATCH
    # ========================================================================

    def _dispatch_command(
        self,
        command,
        source_item=None,
    ):

        dialer = self.qbit_dialer

        if dialer is None:

            self.stats[
                "commands_rejected"
            ] += 1

            self._emit(
                "QBIT_COMMAND_REJECTED",
                {
                    "reason": "QbitDialer not bound",
                    "command": repr(command),
                    "track_id": _extract_track_id(
                        source_item
                    ) if source_item is not None else None,
                },
            )

            return {
                "status": "rejected",
                "reason": "qbit_dialer_not_bound",
                "command": repr(command),
            }

        execute = getattr(
            dialer,
            "execute_command",
            None,
        )

        if not callable(execute):

            self.stats[
                "commands_rejected"
            ] += 1

            self._emit(
                "QBIT_COMMAND_REJECTED",
                {
                    "reason": "QbitDialer execute_command unavailable",
                    "command": repr(command),
                },
            )

            return {
                "status": "rejected",
                "reason": "execute_command_unavailable",
            }

        frame = self._command_frame(
            command,
            source_item=source_item,
        )

        self.stats[
            "commands_dispatched"
        ] += 1

        command_name = (
            frame.get("name")
            or frame.get("command")
            or frame.get("action")
            or frame.get("cmd")
        )

        self.last_command = command_name

        self._emit(
            "QBIT_COMMAND_DISPATCHED",
            {
                "command": command_name,
                "track_id": frame.get(
                    "track_id"
                ),
                "channel_id": frame.get(
                    "channel_id"
                ),
                "parent_id": frame.get(
                    "parent_id"
                ),
                "source": frame.get(
                    "source"
                ),
            },
        )

        try:

            result = execute(
                frame
            )

            if inspect.isawaitable(
                result
            ):

                result = self._run_awaitable(
                    result
                )

            self.last_command_result = result

            status = str(
                _safe_get(
                    result,
                    "status",
                    "",
                )
            ).lower()

            if status in {
                "completed",
                "complete",
                "success",
                "succeeded",
            }:

                self.stats[
                    "commands_completed"
                ] += 1

                self._emit(
                    "QBIT_COMMAND_COMPLETED",
                    result,
                )

            elif status in {
                "failed",
                "failure",
                "error",
            }:

                self.stats[
                    "commands_failed"
                ] += 1

                self._emit(
                    "QBIT_COMMAND_FAILED",
                    result,
                )

            elif status == "rejected":

                self.stats[
                    "commands_rejected"
                ] += 1

                self._emit(
                    "QBIT_COMMAND_REJECTED",
                    result,
                )

            return result

        except asyncio.CancelledError:

            self.stats[
                "commands_cancelled"
            ] += 1

            self._emit(
                "QBIT_COMMAND_CANCELLED",
                {
                    "command": command_name,
                    "track_id": frame.get(
                        "track_id"
                    ),
                    "channel_id": frame.get(
                        "channel_id"
                    ),
                },
            )

            raise

        except Exception as exc:

            self.stats[
                "commands_failed"
            ] += 1

            self.last_error = str(
                exc
            )

            self._emit(
                "QBIT_COMMAND_FAILED",
                {
                    "command": command_name,
                    "error": str(exc),
                    "track_id": frame.get(
                        "track_id"
                    ),
                    "channel_id": frame.get(
                        "channel_id"
                    ),
                },
            )

            raise

    def _dispatch_commands(
        self,
        item,
    ):

        # ==========================================================
        # RAW QBIT
        #
        # A Qbit goes to the Dialer's cognitive pipeline.
        # It is NOT command-dispatched.
        # ==========================================================

        if _is_qbit_like(
            item
        ):

            dialer = self.qbit_dialer

            if dialer is None:

                self.stats[
                    "commands_rejected"
                ] += 1

                return [
                    {
                        "status": "rejected",
                        "reason": "qbit_dialer_not_bound",
                        "qbit_id": _safe_get(
                            item,
                            "qbit_id",
                            _safe_get(
                                item,
                                "id",
                                None,
                            ),
                        ),
                    }
                ]

            receive = getattr(
                dialer,
                "submit_qbit_command",
                None,
            )

            if not callable(
                receive
            ):

                receive = getattr(
                    dialer,
                    "_process_received_qbit",
                    None,
                )

            if not callable(
                receive
            ):

                return [
                    {
                        "status": "rejected",
                        "reason": "qbit_receive_path_unavailable",
                    }
                ]

            try:

                result = receive(
                    item
                )

                if inspect.isawaitable(
                    result
                ):

                    result = self._run_awaitable(
                        result
                    )

                return [
                    result
                ]

            except asyncio.CancelledError:

                raise

            except Exception as exc:

                self.stats[
                    "commands_rejected"
                ] += 1

                raise RuntimeError(
                    "[QbitQueueLoop] Qbit cognitive "
                    "dispatch failed"
                ) from exc

        # ==========================================================
        # ACTUAL EXPLICIT COMMAND LIST
        # ==========================================================

        commands = _extract_command_list(
            item
        )

        if not commands:

            if _has_command_marker(
                item
            ):

                return [
                    self._dispatch_command(
                        item,
                        source_item=item,
                    )
                ]

            return None

        results = []

        for command in commands:

            # ------------------------------------------------------
            # A command list may itself contain a Qbit.
            # ------------------------------------------------------

            if _is_qbit_like(
                command
            ):

                dialer = self.qbit_dialer

                if dialer is None:

                    results.append(
                        {
                            "status": "rejected",
                            "reason": "qbit_dialer_not_bound",
                        }
                    )

                    continue

                receive = getattr(
                    dialer,
                    "submit_qbit_command",
                    None,
                )

                if not callable(
                    receive
                ):

                    receive = getattr(
                        dialer,
                        "_process_received_qbit",
                        None,
                    )

                if not callable(
                    receive
                ):

                    results.append(
                        {
                            "status": "rejected",
                            "reason": (
                                "qbit_receive_path_unavailable"
                            ),
                        }
                    )

                    continue

                result = receive(
                    command
                )

                if inspect.isawaitable(
                    result
                ):

                    result = self._run_awaitable(
                        result
                    )

                results.append(
                    result
                )

                continue

            # ------------------------------------------------------
            # Ignore genuinely empty commands.
            # ------------------------------------------------------

            if _is_empty_command_value(
                command
            ):

                continue

            # ------------------------------------------------------
            # Only strings/dicts are legitimate command frames.
            # ------------------------------------------------------

            if not isinstance(
                command,
                (
                    str,
                    dict,
                ),
            ):

                log.debug(
                    "[QbitQueueLoop] ignoring non-command item "
                    "inside command_list | type=%s",
                    type(command).__name__,
                )

                continue

            result = self._dispatch_command(
                command,
                source_item=item,
            )

            results.append(
                result
            )

        return results
    # ========================================================================
    # FEEDBACK
    # ========================================================================

    def submit_feedback(
        self,
        feedback,
        source_item=None,
        priority=None,
    ):

        if feedback is None:

            self.stats[
                "feedback_rejected"
            ] += 1

            return False

        if isinstance(
            feedback,
            dict,
        ):

            payload = dict(
                feedback
            )

            metadata = dict(
                payload.get(
                    "metadata"
                ) or {}
            )

            metadata.update(
                {
                    "feedback": True,
                    "feedback_source": "QbitDialer",
                }
            )

            if source_item is not None:

                track_id = _extract_track_id(
                    source_item
                )

                channel_id = _extract_channel_id(
                    source_item
                )

                parent_id = _extract_parent_id(
                    source_item
                )

                if track_id is not None:

                    payload.setdefault(
                        "track_id",
                        track_id,
                    )

                    metadata.setdefault(
                        "track_id",
                        track_id,
                    )

                if channel_id is not None:

                    payload.setdefault(
                        "channel_id",
                        channel_id,
                    )

                    metadata.setdefault(
                        "channel_id",
                        channel_id,
                    )

                if parent_id is not None:

                    payload.setdefault(
                        "parent_id",
                        parent_id,
                    )

                    metadata.setdefault(
                        "parent_id",
                        parent_id,
                    )

            payload[
                "metadata"
            ] = metadata

            payload[
                "feedback"
            ] = True

            payload.setdefault(
                "feedback_source",
                "QbitDialer",
            )

        else:

            try:

                setattr(
                    feedback,
                    "feedback",
                    True,
                )

                setattr(
                    feedback,
                    "feedback_source",
                    "QbitDialer",
                )

            except Exception:

                self.stats[
                    "feedback_rejected"
                ] += 1

                return False

            payload = feedback

        selected = self._resolve_priority(
            payload,
            priority,
        )

        accepted = self.put(
            payload,
            priority=selected,
        )

        if accepted:

            self.stats[
                "feedback_submitted"
            ] += 1

            self.stats[
                "feedback_routed"
            ] += 1

            self._emit(
                "QBIT_FEEDBACK_ROUTED",
                self._cycle_payload(
                    payload
                ),
            )

        else:

            self.stats[
                "feedback_rejected"
            ] += 1

        return accepted

    def _is_feedback(
        self,
        item,
    ):

        if item is None:
            return False

        if bool(
            _safe_get(
                item,
                "feedback",
                False,
            )
        ):
            return True

        metadata = _extract_metadata(
            item
        )

        if bool(
            metadata.get(
                "feedback",
                False,
            )
        ):
            return True

        return (
            str(
                _safe_get(
                    item,
                    "route",
                    "",
                )
            ).upper()
            == "FEEDBACK"
        )

    # ========================================================================
    # CYCLE PAYLOAD
    # ========================================================================

    def _cycle_payload(
        self,
        item,
    ):

        metadata = _extract_metadata(
            item
        )

        return {
            "qbit_id": _safe_get(
                item,
                "id",
                _safe_get(
                    item,
                    "qbit_id",
                ),
            ),

            "track_id": _extract_track_id(
                item
            ),

            "channel_id": _extract_channel_id(
                item
            ),

            "parent_id": _extract_parent_id(
                item
            ),

            "feedback": bool(
                _safe_get(
                    item,
                    "feedback",
                    False,
                )
                or metadata.get(
                    "feedback",
                    False,
                )
            ),

            "feedback_source": _safe_get(
                item,
                "feedback_source",
                metadata.get(
                    "feedback_source"
                ),
            ),

            "intent": _safe_get(
                item,
                "intent",
            ),

            "action": _safe_get(
                item,
                "action",
            ),

            "priority": _safe_get(
                item,
                "priority",
            ),

            "timestamp": time.time(),
        }

    # ========================================================================
    # TEMPORAL RECORDING
    # ========================================================================

    def _record(
        self,
        item,
    ):

        if item is None:
            return

        replayed = bool(
            _safe_get(
                item,
                "_replayed",
                False,
            )
        )

        if replayed:

            try:

                setattr(
                    item,
                    "_replayed",
                    False,
                )

            except Exception:

                if isinstance(
                    item,
                    dict,
                ):

                    item.pop(
                        "_replayed",
                        None,
                    )

            return

        self.replay_buffer.append(
            item
        )

        if self.memory_graph:

            try:

                if hasattr(
                    self.memory_graph,
                    "add_qbit",
                ):

                    self.memory_graph.add_qbit(
                        item
                    )

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] MemoryGraph failed: %s",
                    exc,
                )

        if self.cognition_map:

            try:

                if hasattr(
                    self.cognition_map,
                    "observe",
                ):

                    self.cognition_map.observe(
                        item
                    )

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] CognitionMap failed: %s",
                    exc,
                )

        if self.memory_system:

            try:

                if hasattr(
                    self.memory_system,
                    "update",
                ):

                    self.memory_system.update(
                        item
                    )

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] MemorySystem failed: %s",
                    exc,
                )

        if self.time_travel_engine:

            try:

                self.time_travel_engine.record(
                    event_type="QBIT_QUEUE_ITEM",
                    payload=self._temporal_payload(
                        item
                    ),
                )

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] TimeTravel record failed: %s",
                    exc,
                )

    def _temporal_payload(
        self,
        item,
    ):

        return {
            "qbit_id": _safe_get(
                item,
                "id",
                _safe_get(
                    item,
                    "qbit_id",
                ),
            ),

            "track_id": _extract_track_id(
                item
            ),

            "channel_id": _extract_channel_id(
                item
            ),

            "parent_id": _extract_parent_id(
                item
            ),

            "intent": _safe_get(
                item,
                "intent",
            ),

            "action": _safe_get(
                item,
                "action",
            ),

            "commands": _extract_command_list(
                item
            ),

            "task": _extract_task(
                item
            ),

            "type": type(
                item
            ).__name__,

            "timestamp": time.time(),
        }

    # ========================================================================
    # REPLAY
    # ========================================================================

    def replay(
        self,
        steps=1,
    ):

        try:

            steps = max(
                0,
                int(steps),
            )

        except Exception:

            steps = 1

        if steps == 0:
            return []

        items = list(
            self.replay_buffer
        )[-steps:]

        self.stats[
            "replays"
        ] += len(
            items
        )

        self._emit(
            "QBIT_REPLAY",
            {
                "steps": steps,
                "returned": len(items),
            },
        )

        return items

    def rewind(
        self,
        steps=1,
    ):

        items = self.replay(
            steps
        )

        for item in reversed(
            items
        ):

            try:

                setattr(
                    item,
                    "_replayed",
                    True,
                )

            except Exception:

                if isinstance(
                    item,
                    dict,
                ):

                    item[
                        "_replayed"
                    ] = True

            self.put(
                item,
                priority=self.auto_priority(
                    item
                ),
            )

        self.stats[
            "rewinds"
        ] += len(
            items
        )

        self._emit(
            "QBIT_REWIND",
            {
                "steps": steps,
                "items": len(items),
            },
        )

        return items

    # ========================================================================
    # QBIT INSPECTION
    # ========================================================================

    def inspect_qbit(
        self,
        item,
    ) -> Dict[str, Any]:

        task = _extract_task(
            item
        )

        commands = _extract_command_list(
            item
        )

        return {

            "is_qbit": _is_qbit_like(
                item
            ),

            "is_command": self.is_command_item(
                item
            ),

            "qbit_id": _safe_get(
                item,
                "id",
                _safe_get(
                    item,
                    "qbit_id",
                ),
            ),

            "track_id": _extract_track_id(
                item
            ),

            "channel_id": _extract_channel_id(
                item
            ),

            "parent_id": _extract_parent_id(
                item
            ),

            "intent": _safe_get(
                item,
                "intent",
            ),

            "action": _safe_get(
                item,
                "action",
            ),

            "commands": commands,

            "command_count": len(
                commands
            ),

            "task": task,

            "task_id": (
                task.get(
                    "task_id"
                )
                if task
                else None
            ),

            "task_state": (
                task.get(
                    "state"
                )
                if task
                else None
            ),
        }

    # ========================================================================
    # EVENT BUS
    # ========================================================================

    def _emit(
        self,
        event_name,
        payload=None,
    ):

        bus = self.event_bus

        if bus is None:
            return False

        try:

            if hasattr(
                bus,
                "emit",
            ):

                return bus.emit(
                    event_name,
                    payload,
                )

            if hasattr(
                bus,
                "publish",
            ):

                return bus.publish(
                    event_name,
                    payload,
                )

        except Exception as exc:

            log.debug(
                "[QbitQueueLoop] EventBus emit failed | "
                "event=%s | error=%s",
                event_name,
                exc,
            )

        return False

    # ========================================================================
    # CONTROL
    # ========================================================================

    def pause(
        self,
        reason=None,
    ):

        with self._state_lock:

            if self.paused:
                return True

            self.paused = True

            self.stats[
                "pauses"
            ] += 1

        log.warning(
            "[QbitQueueLoop] paused | reason=%s",
            reason,
        )

        self._emit(
            "QBIT_PAUSE",
            {
                "reason": reason,
            },
        )

        return True

    def resume(self):

        with self._state_lock:

            if not self.paused:
                return True

            self.paused = False

            self.stats[
                "resumes"
            ] += 1

        self._wake_event.set()

        log.info(
            "[QbitQueueLoop] resumed"
        )

        self._emit(
            "QBIT_RESUME",
            {},
        )

        return True

    def stop(
        self,
        join=True,
        timeout=3.0,
    ):

        with self._state_lock:

            if (
                not self.running
                and not self.active
                and self.shutdown_requested
            ):
                return True

            self.running = False
            self.active = False
            self.shutdown_requested = True

            self._stop_event.set()
            self._wake_event.set()

            self.stats[
                "stops"
            ] += 1

        self._emit(
            "QBIT_STOP",
            {
                "reason": "shutdown",
            },
        )

        thread = self._thread

        if (
            join
            and thread
            and thread.is_alive()
            and thread
            is not threading.current_thread()
        ):

            thread.join(
                timeout=max(
                    0.0,
                    float(timeout),
                )
            )

        if (
            thread is not None
            and not thread.is_alive()
        ):

            self._thread = None
            self._worker_thread_id = None

        log.info(
            "[QbitQueueLoop] stopped"
        )

        return True

    # ========================================================================
    # START
    # ========================================================================

    def start(
        self,
        threaded=True,
    ):

        with self._state_lock:

            if (
                self._thread
                and self._thread.is_alive()
            ):

                return self

            # Starting a previously stopped transport reopens transport.
            self.active = True
            self.running = True
            self.paused = False
            self.shutdown_requested = False

            self._stop_event.clear()
            self._wake_event.clear()

            self.stats[
                "starts"
            ] += 1

        self._emit(
            "QBIT_QUEUE_STARTED",
            self.status(),
        )

        if not threaded:

            self._worker_thread_id = (
                threading.get_ident()
            )

            self._run_loop()

            return self

        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="QbitQueueLoop",
        )

        self._thread.start()

        log.info(
            "[QbitQueueLoop] execution loop online"
        )

        return self

    # ========================================================================
    # ITERATOR
    # ========================================================================

    def __iter__(self):

        while self.running:

            if self.paused:

                self._wake_event.wait(
                    timeout=0.05
                )

                self._wake_event.clear()

                continue

            batch = []

            for _ in range(
                self.batch_size
            ):

                item = None

                for level in PRIORITY_ORDER:

                    try:

                        item = (
                            self.priority_queues[
                                level
                            ].get_nowait()
                        )

                        self.stats[
                            "gets"
                        ] += 1

                        break

                    except pyqueue.Empty:
                        continue

                if item is None:
                    break

                self._record(
                    item
                )

                batch.append(
                    item
                )

            if not batch:

                self._wake_event.wait(
                    timeout=0.05
                )

                self._wake_event.clear()

                continue

            for item in batch:

                yield item

            if self.throttle_delay:

                time.sleep(
                    self.throttle_delay
                )

    # ========================================================================
    # EXECUTION LOOP
    # ========================================================================

    def _run_loop(self):

        self._worker_thread_id = (
            threading.get_ident()
        )

        log.info(
            "[QbitQueueLoop] execution loop starting | "
            "thread=%s",
            self._worker_thread_id,
        )

        self._emit(
            "QBIT_QUEUE_DISPATCHING",
            {
                "thread_id": self._worker_thread_id,
            },
        )

        try:

            for item in self:

                if not self.running:
                    break

                self._dispatch(
                    item
                )

        except KeyboardInterrupt:

            log.info(
                "[QbitQueueLoop] interrupted"
            )

        except Exception:

            log.exception(
                "[QbitQueueLoop] fatal execution-loop error"
            )

            self.last_error = (
                "fatal execution-loop error"
            )

        finally:

            with self._state_lock:

                self.running = False

            worker_id = self._worker_thread_id

            self._emit(
                "QBIT_QUEUE_DISPATCHING_STOPPED",
                {
                    "thread_id": worker_id,
                    "queue_depth": self.depth(),
                },
            )

            log.info(
                "[QbitQueueLoop] execution loop offline"
            )

    # ========================================================================
    # DISPATCH
    #
    # QBIT QUEUE LOOP TRANSPORT DISPATCH
    #
    # AUTHORITATIVE ARCHITECTURE
    #
    #     Qbit
    #       |
    #       v
    #     QbitQueueLoop
    #       |
    #       v
    #     QbitDialer
    #       |
    #       v
    #     TrackSystem
    #       |
    #       v
    #     ComputeBrain
    #       |
    #       v
    #     ThoughtPacket
    #       |
    #       v
    #     TransformerBrain
    #       |
    #       v
    #     Command Proposal
    #       |
    #       v
    #     QbitDialer.submit_command()
    #
    # IMPORTANT:
    #
    # QbitQueueLoop is TRANSPORT.
    #
    # QbitQueueLoop does NOT:
    #
    #     - execute Qbits
    #     - interpret Qbit payload as commands
    #     - become command authority
    #     - call execute_command()
    #     - call _dispatch_commands() for raw Qbits
    #
    # QbitDialer is the sole command authority.
    #
    # ========================================================================

    def _dispatch(
        self,
        item,
    ):

        self.stats[
            "processed"
        ] += 1

        self.last_dispatch_time = time.time()

        # ====================================================================
        # WATCHDOG
        # ====================================================================

        if self.watchdog:

            try:

                tick = getattr(
                    self.watchdog,
                    "tick",
                    None,
                )

                if callable(tick):

                    tick()

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] watchdog tick failed: %s",
                    exc,
                )

        # ====================================================================
        # GOVERNOR
        # ====================================================================

        if self.governor:

            try:

                tick = getattr(
                    self.governor,
                    "tick",
                    None,
                )

                if callable(tick):

                    tick()

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] governor tick failed: %s",
                    exc,
                )

        # ====================================================================
        # QBIT DATA PLANE
        #
        # THIS MUST REMAIN BEFORE COMMAND DETECTION.
        #
        # A Qbit is DATA.
        #
        # It is not automatically an executable command merely because
        # its payload contains fields named "command" or "commands".
        # ====================================================================

        if _is_qbit_like(
            item
        ):

            qbit_id = _safe_get(
                item,
                "qbit_id",
                _safe_get(
                    item,
                    "id",
                    None,
                ),
            )

            track_id = _extract_track_id(
                item
            )

            channel_id = _extract_channel_id(
                item
            )

            parent_id = _extract_parent_id(
                item
            )

            # ================================================================
            # QBIT DIALER AUTHORITY
            #
            # QueueLoop may receive a Qbit before boot has finished attaching
            # the Dialer.
            #
            # This is NOT a command rejection.
            #
            # It is a synchronization state.
            #
            # Do not increment command rejection counters.
            # Do not execute the Qbit.
            # Do not interpret its payload.
            # ================================================================

            dialer = getattr(
                self,
                "qbit_dialer",
                None,
            )

            if dialer is None:

                log.debug(
                    "[QbitQueueLoop] Qbit held pending "
                    "QbitDialer authority | "
                    "qbit_id=%s | track_id=%s",
                    qbit_id,
                    track_id,
                )

                # ------------------------------------------------------------
                # Preserve the Qbit for later admission.
                # ------------------------------------------------------------

                pending = getattr(
                    self,
                    "_pending_qbits",
                    None,
                )

                if pending is None:

                    pending = []

                    self._pending_qbits = pending

                pending.append(
                    item
                )

                self._emit(
                    "QBIT_PENDING_AUTHORITY",
                    {
                        "qbit_id": qbit_id,
                        "track_id": track_id,
                        "channel_id": channel_id,
                        "parent_id": parent_id,
                        "reason": (
                            "QbitDialer not attached"
                        ),
                    },
                )

                return

            # ================================================================
            # AUTHORITATIVE QBIT RECEIVE PATH
            # ================================================================

            receive = getattr(
                dialer,
                "submit_qbit_command",
                None,
            )

            if not callable(
                receive
            ):

                receive = getattr(
                    dialer,
                    "_process_received_qbit",
                    None,
                )

            if not callable(
                receive
            ):

                self.stats[
                    "dispatch_errors"
                ] += 1

                self.last_error = (
                    "QbitDialer has no "
                    "authoritative Qbit receive path"
                )

                log.error(
                    "[QbitQueueLoop] QbitDialer has no "
                    "authoritative Qbit receive path | "
                    "qbit_id=%s",
                    qbit_id,
                )

                self._emit(
                    "QBIT_QUEUE_AUTHORITY_ERROR",
                    {
                        "qbit_id": qbit_id,
                        "track_id": track_id,
                        "channel_id": channel_id,
                        "parent_id": parent_id,
                    },
                )

                return
            # ================================================================
            # CANONICAL QBIT ADMISSION GUARD
            #
            # One Qbit + one Track lineage = one QueueLoop admission.
            #
            # IMPORTANT:
            #
            # This does NOT create another Qbit.
            # This does NOT modify the Qbit.
            # This does NOT execute anything.
            #
            # It prevents the same canonical Qbit from being transported
            # into QbitDialer more than once.
            # ================================================================

            admission_key = (
                str(qbit_id),
                str(track_id),
            )

            try:

                with self._qbit_admission_lock:

                    if admission_key in self._admitted_qbits:

                        self.duplicate_dispatch_count = (
                            getattr(
                                self,
                                "duplicate_dispatch_count",
                                0,
                            )
                            + 1
                        )

                        log.warning(
                            "[QbitQueueLoop] Duplicate Qbit admission "
                            "blocked | "
                            "qbit_id=%s | "
                            "track_id=%s",
                            qbit_id,
                            track_id,
                        )

                        self._emit(
                            "QBIT_DUPLICATE_BLOCKED",
                            {
                                "qbit_id": qbit_id,
                                "track_id": track_id,
                                "channel_id": channel_id,
                                "parent_id": parent_id,
                            },
                        )

                        return

                    # --------------------------------------------------------
                    # Mark BEFORE Dialer receive.
                    #
                    # This prevents concurrent QueueLoop paths from both
                    # admitting the same Qbit.
                    # --------------------------------------------------------

                    self._admitted_qbits.add(
                        admission_key
                    )

            except Exception as exc:

                log.error(
                    "[QbitQueueLoop] "
                    "Qbit admission guard failed | "
                    "qbit_id=%s | track_id=%s | error=%s",
                    qbit_id,
                    track_id,
                    exc,
                )

                return
            # ================================================================
            # SEND QBIT TO DIALER
            #
            # QueueLoop transports.
            # Dialer processes.
            # ================================================================

            try:

                result = receive(
                    item
                )

                if inspect.isawaitable(
                    result
                ):

                    result = self._run_awaitable(
                        result
                    )

                self.last_command_result = result

                self._emit(
                    "QBIT_RECEIVED",
                    {
                        "qbit_id": qbit_id,
                        "track_id": track_id,
                        "channel_id": channel_id,
                        "parent_id": parent_id,
                        "result": result,
                    },
                )

                return

            except asyncio.CancelledError:

                raise

            except Exception as exc:

                self.stats[
                    "dispatch_errors"
                ] += 1

                self.last_error = str(
                    exc
                )

                log.exception(
                    "[QbitQueueLoop] Qbit cognitive receive failed | "
                    "qbit_id=%s | track_id=%s",
                    qbit_id,
                    track_id,
                )

                self._emit(
                    "QBIT_QUEUE_COGNITIVE_ERROR",
                    {
                        "error": str(
                            exc
                        ),
                        "qbit_id": qbit_id,
                        "track_id": track_id,
                        "channel_id": channel_id,
                        "parent_id": parent_id,
                    },
                )

                return

        # ====================================================================
        # NON-QBIT COMMAND DETECTION
        #
        # This path is ONLY for items that are NOT raw Qbits.
        #
        # ====================================================================

        commands = _extract_command_list(
            item
        )

        is_direct_command = (
            _has_command_marker(
                item
            )
        )

        # ====================================================================
        # COMMAND PATH
        #
        # Commands detected outside the raw-Qbit data plane are admitted
        # through the queue's command dispatcher.
        #
        # This does NOT apply to raw Qbits.
        # ====================================================================

        if commands or is_direct_command:

            if commands:

                self._emit(
                    "QBIT_COMMANDS_DETECTED",
                    {
                        "qbit_id": _safe_get(
                            item,
                            "id",
                            _safe_get(
                                item,
                                "qbit_id",
                            ),
                        ),
                        "track_id": _extract_track_id(
                            item
                        ),
                        "channel_id": _extract_channel_id(
                            item
                        ),
                        "parent_id": _extract_parent_id(
                            item
                        ),
                        "count": len(
                            commands
                        ),
                        "commands": commands,
                    },
                )

            else:

                self._emit(
                    "QBIT_COMMAND_DETECTED",
                    {
                        "qbit_id": _safe_get(
                            item,
                            "id",
                            _safe_get(
                                item,
                                "qbit_id",
                            ),
                        ),
                        "track_id": _extract_track_id(
                            item
                        ),
                        "channel_id": _extract_channel_id(
                            item
                        ),
                        "parent_id": _extract_parent_id(
                            item
                        ),
                    },
                )

            # ================================================================
            # COMMAND ADMISSION
            # ================================================================

            try:

                command_result = (
                    self._dispatch_commands(
                        item
                    )
                )

                if command_result is None:

                    return

                self.stats[
                    "handler_success"
                ] += 1

                # ------------------------------------------------------------
                # Feedback only.
                # ------------------------------------------------------------

                if isinstance(
                    command_result,
                    list,
                ):

                    for result in command_result:

                        if self._is_feedback(
                            result
                        ):

                            self.submit_feedback(
                                result,
                                source_item=item,
                            )

                elif self._is_feedback(
                    command_result
                ):

                    self.submit_feedback(
                        command_result,
                        source_item=item,
                    )

                return

            except asyncio.CancelledError:

                raise

            except Exception as exc:

                self.stats[
                    "handler_failures"
                ] += 1

                self.stats[
                    "dispatch_errors"
                ] += 1

                self.last_error = str(
                    exc
                )

                log.exception(
                    "[QbitQueueLoop] command dispatch failure: %s",
                    exc,
                )

                self._emit(
                    "QBIT_QUEUE_COMMAND_ERROR",
                    {
                        "error": str(
                            exc
                        ),
                        "qbit_id": _safe_get(
                            item,
                            "id",
                            _safe_get(
                                item,
                                "qbit_id",
                            ),
                        ),
                        "track_id": _extract_track_id(
                            item
                        ),
                        "channel_id": _extract_channel_id(
                            item
                        ),
                    },
                )

                return

        # ====================================================================
        # NON-COMMAND DATA
        #
        # Compatibility path for ordinary data that is not a Qbit and not
        # an explicit command.
        #
        # ====================================================================

        if not self.handler:

            log.debug(
                "[QbitQueueLoop] no non-command handler | item=%r",
                item,
            )

            return

        # ====================================================================
        # NEVER ALLOW QbitDialer.execute_command TO BECOME THE GENERIC
        # HANDLER.
        # ====================================================================

        if (
            self.qbit_dialer is not None
            and self.handler
            is getattr(
                self.qbit_dialer,
                "execute_command",
                None,
            )
        ):

            log.warning(
                "[QbitQueueLoop] blocked generic handler dispatch "
                "because handler is QbitDialer.execute_command"
            )

            return

        # ====================================================================
        # GENERIC DATA HANDLER
        # ====================================================================

        try:

            result = self.handler(
                item
            )

            if inspect.isawaitable(
                result
            ):

                result = self._run_awaitable(
                    result
                )

            if self._is_feedback(
                result
            ):

                self.submit_feedback(
                    result,
                    source_item=item,
                )

            self.stats[
                "handler_success"
            ] += 1

        except asyncio.CancelledError:

            raise

        except Exception as exc:

            self.stats[
                "handler_failures"
            ] += 1

            self.stats[
                "dispatch_errors"
            ] += 1

            self.last_error = str(
                exc
            )

            log.exception(
                "[QbitQueueLoop] handler failure: %s",
                exc,
            )

            self._emit(
                "QBIT_QUEUE_HANDLER_ERROR",
                {
                    "error": str(
                        exc
                    ),
                    "qbit_id": _safe_get(
                        item,
                        "id",
                        _safe_get(
                            item,
                            "qbit_id",
                        ),
                    ),
                    "track_id": _extract_track_id(
                        item
                    ),
                    "channel_id": _extract_channel_id(
                        item
                    ),
                },
            )

    # ========================================================================
    # ASYNC HANDLER SUPPORT
    # ========================================================================

    def _run_awaitable(
        self,
        awaitable,
    ):

        if not inspect.isawaitable(
            awaitable
        ):
            return awaitable

        # --------------------------------------------------------------------
        # Identify current running loop.
        # --------------------------------------------------------------------

        try:

            running_loop = (
                asyncio.get_running_loop()
            )

        except RuntimeError:

            running_loop = None

        # --------------------------------------------------------------------
        # No running loop in this thread.
        #
        # Normal QbitQueueLoop worker path.
        # --------------------------------------------------------------------

        if running_loop is None:

            try:

                return asyncio.run(
                    awaitable
                )

            except Exception:

                try:

                    close = getattr(
                        awaitable,
                        "close",
                        None,
                    )

                    if callable(close):
                        close()

                except Exception:
                    pass

                raise

        # --------------------------------------------------------------------
        # A Future/Task is already attached to this running loop.
        #
        # Blocking here would deadlock the loop.
        # --------------------------------------------------------------------

        if isinstance(
            awaitable,
            (
                asyncio.Future,
            ),
        ):

            raise RuntimeError(
                "QbitQueueLoop cannot synchronously resolve "
                "an asyncio.Future/Task owned by the current "
                "running event loop"
            )

        # --------------------------------------------------------------------
        # A coroutine is being dispatched while an event loop is already
        # running in this thread.
        #
        # Execute it in a helper thread instead of blocking the current loop.
        # --------------------------------------------------------------------

        result_box = []
        error_box = []

        def runner():

            try:

                result_box.append(
                    asyncio.run(
                        awaitable
                    )
                )

            except BaseException as exc:

                error_box.append(
                    exc
                )

        thread = threading.Thread(
            target=runner,
            daemon=True,
            name="QbitQueueLoopAwaitable",
        )

        thread.start()
        thread.join()

        if error_box:
            raise error_box[0]

        return (
            result_box[0]
            if result_box
            else None
        )

    # ========================================================================
    # STATUS
    # ========================================================================

    def command_status(
        self,
    ):

        handler_name = None

        if self.handler:

            handler_name = getattr(
                self.handler,
                "__name__",
                type(
                    self.handler
                ).__name__,
            )

        return {

            "authority": (
                "QbitDialer"
                if self.qbit_dialer
                else None
            ),

            "authority_bound": (
                self.qbit_dialer
                is not None
            ),

            "handler": handler_name,

            "handler_is_command_authority": (
                self.qbit_dialer is not None
                and self.handler
                is getattr(
                    self.qbit_dialer,
                    "execute_command",
                    None,
                )
            ),

            "last_command":
                self.last_command,

            "last_result":
                self.last_command_result,

            "commands_seen":
                self.stats[
                    "commands_seen"
                ],

            "commands_dispatched":
                self.stats[
                    "commands_dispatched"
                ],

            "commands_completed":
                self.stats[
                    "commands_completed"
                ],

            "commands_failed":
                self.stats[
                    "commands_failed"
                ],

            "commands_rejected":
                self.stats[
                    "commands_rejected"
                ],

            "commands_cancelled":
                self.stats[
                    "commands_cancelled"
                ],
        }

    def qbit_status(
        self,
    ):

        dialer = self.qbit_dialer

        if dialer is None:

            return {
                "bound": False,
                "authority": None,
            }

        try:

            if hasattr(
                dialer,
                "command_status",
            ):

                return {
                    "bound": True,
                    "authority": "QbitDialer",
                    "dialer": dialer.command_status(),
                }

        except Exception as exc:

            return {
                "bound": True,
                "authority": "QbitDialer",
                "error": str(
                    exc
                ),
            }

        return {
            "bound": True,
            "authority": "QbitDialer",
        }

    def health_status(
        self,
    ):

        return {

            "transport":
                self.active,

            "running":
                self.running,

            "paused":
                self.paused,

            "core_ready":
                self.core_ready,

            "shutdown_requested":
                self.shutdown_requested,

            "queue_depth":
                self.depth(),

            "dialer_bound":
                self.qbit_dialer is not None,

            "thread_alive":
                bool(
                    self._thread
                    and self._thread.is_alive()
                ),

            "worker_thread_id":
                self._worker_thread_id,

            "current_thread_id":
                threading.get_ident(),

            "last_dispatch":
                self.last_dispatch_time,

            "last_error":
                self.last_error,
        }

    def get_stats(
        self,
    ):

        return dict(
            self.stats
        )

    def status(
        self,
    ) -> Dict[str, Any]:

        return {

            "active":
                self.active,

            "running":
                self.running,

            "paused":
                self.paused,

            "core_ready":
                self.core_ready,

            "shutdown_requested":
                self.shutdown_requested,

            "thread_alive":
                bool(
                    self._thread
                    and self._thread.is_alive()
                ),

            "authority":
                "QbitDialer"
                if self.qbit_dialer
                else None,

            "qbit_dialer_bound":
                self.qbit_dialer is not None,

            "queue_depth": {
                level:
                    self.priority_queues[
                        level
                    ].qsize()
                for level in PRIORITY_ORDER
            },

            "queue_depth_total":
                self.depth(),

            "replay_buffer":
                len(
                    self.replay_buffer
                ),

            "feedback_enabled":
                True,

            "feeds":
                list(
                    self.feeds.keys()
                ),

            "handler":
                (
                    getattr(
                        self.handler,
                        "__name__",
                        type(
                            self.handler
                        ).__name__,
                    )
                    if self.handler
                    else None
                ),

            "command_plane":
                self.command_status(),

            "qbit":
                self.qbit_status(),

            "health":
                self.health_status(),

            "stats":
                dict(
                    self.stats
                ),
        }

    # ========================================================================
    # COUNTERS
    # ========================================================================

    def command_count(
        self,
    ) -> int:

        return int(
            self.stats.get(
                "commands_seen",
                0,
            )
        )

    def task_count(
        self,
    ) -> int:

        return int(
            self.stats.get(
                "tasks_seen",
                0,
            )
        )

    def qbit_count(
        self,
    ) -> int:

        return int(
            self.stats.get(
                "qbits_seen",
                0,
            )
        )

    # ========================================================================
    # REPRESENTATION
    # ========================================================================

    def __repr__(
        self,
    ):

        status = self.status()

        return (
            "<QbitQueueLoop "
            f"active={status['active']} "
            f"running={status['running']} "
            f"core_ready={status['core_ready']} "
            f"authority={status['authority']} "
            f"processed={status['stats']['processed']} "
            f"commands={status['stats']['commands_seen']} "
            f"completed={status['stats']['commands_completed']} "
            f"failed={status['stats']['commands_failed']} "
            f"depth={status['queue_depth_total']}>"
        )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "QbitQueueLoop",
    "PRIORITY_CRITICAL",
    "PRIORITY_NORMAL",
    "PRIORITY_BACKGROUND",
]