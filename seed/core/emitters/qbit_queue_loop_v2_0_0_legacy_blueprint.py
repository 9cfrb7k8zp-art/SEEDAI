# ============================================================================
# SEED AI OS
# FILE: qbit_queue_loop.py
# PATH: C:\SEED_ROOT\seed\core\emitters\qbit_queue_loop.py
#
# VERSION: 2.0.0
# BUILD: QBIT-FULL-CYCLE-ASYNC-FEEDBACK-STABILIZATION
# UPDATED: 2026-08-16
#
# ROLE:
#   SYSTEM QBIT TRANSPORT / PRIORITY / TEMPORAL EXECUTION LOOP
#
# AUTHORITY MODEL:
#
#   HeartbeatEmitter
#          |
#          v
#      Qbit / QbitDialer
#          |
#          v
#   QbitQueueLoop
#          |
#          +----> QbitDialer handler
#          |
#          +----> Intent / Action layers
#          |
#          +----> QbitDialer feedback / result path
#          +----> TimeTravelEngine
#          +----> Cognition / Memory
#
# IMPORTANT:
#   QbitQueueLoop does NOT become the Qbit brain.
#
#   QbitDialer remains the command authority.
#   QbitQueueLoop transports, prioritizes, records, and dispatches.
#   QbitDialer may return explicitly marked feedback through submit_feedback().
#   Empty queues are normal wait states and MUST NOT kill async consumers.
#
# FIXES INCLUDED:
#   - startup race
#   - inactive queue dropping items
#   - dead batch logic
#   - duplicate KeyboardInterrupt block
#   - dict / tuple / Qbit compatibility
#   - priority normalization
#   - adaptive priority compatibility
#   - command-list discovery
#   - Qbit task discovery
#   - temporal recording
#   - replay safety
#   - rewind safety
#   - watchdog support
#   - governor support
#   - cognition support
#   - memory support
#   - feed broadcasting
#   - thread-safe lifecycle
#   - graceful shutdown
#   - handler compatibility
#   - synchronous + asynchronous handler support
#   - diagnostic counters
#   - EventBus telemetry
#
# NO EXTERNAL DEPENDENCIES.
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
# CONSTANTS
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
# SMALL INTERNAL HELPERS
# ============================================================================

def _safe_get(obj: Any, name: str, default: Any = None) -> Any:
    try:
        if isinstance(obj, dict):
            return obj.get(name, default)

        return getattr(obj, name, default)

    except Exception:
        return default


def _is_qbit_like(item: Any) -> bool:

    if item is None:
        return False

    cls_name = type(item).__name__.lower()

    if cls_name == "qbit":
        return True

    # Qbit-like objects normally expose one or more of these.
    return any(
        hasattr(item, attr)
        for attr in (
            "command_list",
            "commands",
            "task",
            "qbit_id",
            "upstream_track",
        )
    )


def _extract_command_list(item: Any) -> list:

    candidates = []

    # ------------------------------------------------------------------
    # Direct Qbit/object fields
    # ------------------------------------------------------------------

    for field in ("command_list", "commands"):
        value = _safe_get(item, field, None)

        if value:
            candidates.append(value)

    # ------------------------------------------------------------------
    # Task-owned commands
    # ------------------------------------------------------------------

    task = _safe_get(item, "task", None)

    if isinstance(task, dict):
        value = task.get("commands")

        if value:
            candidates.append(value)

    # ------------------------------------------------------------------
    # Dictionary payload
    # ------------------------------------------------------------------

    if isinstance(item, dict):

        for field in ("command_list", "commands"):
            value = item.get(field)

            if value:
                candidates.append(value)

        task = item.get("task")

        if isinstance(task, dict):
            value = task.get("commands")

            if value:
                candidates.append(value)

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------

    for value in candidates:

        if isinstance(value, (list, tuple, deque)):
            return list(value)

        if isinstance(value, str):
            return [value]

        if isinstance(value, dict):
            return [value]

    return []


def _extract_task(item: Any) -> Optional[dict]:

    task = _safe_get(item, "task", None)

    if isinstance(task, dict):
        return task

    if isinstance(item, dict):

        task = item.get("task")

        if isinstance(task, dict):
            return task

    return None


def _extract_metadata(item: Any) -> dict:
    """Return metadata without mutating the source object."""
    metadata = _safe_get(item, "metadata", None)
    if isinstance(metadata, dict):
        return dict(metadata)
    return {}


def _extract_track_id(item: Any) -> Optional[str]:
    return _safe_get(item, "track_id", _safe_get(item, "track", None))


def _extract_channel_id(item: Any) -> Optional[str]:
    return _safe_get(item, "channel_id", _safe_get(item, "channel", None))


# ============================================================================
# QBIT QUEUE LOOP
# ============================================================================

class QbitQueueLoop:

    # ------------------------------------------------------------------------
    # CONSTRUCTION
    # ------------------------------------------------------------------------

    def __init__(
        self,
        event_bus=None,
        qbit_queue=None,
        handler: Optional[Callable] = None,
        queue=None,
        boot_cycle=None,
        throttle_hz=DEFAULT_THROTTLE_HZ,
        replay_buffer_size=DEFAULT_REPLAY_BUFFER,
        time_travel_engine=None,
        loop=None,
        priority_engine=None,
        cognition_map=None,
        watchdog=None,
        governor=None,
        memory_graph=None,
        memory_system=None,
        batch_size=DEFAULT_BATCH_SIZE,
        auto_activate=True,
    ):

        self.event_bus = event_bus

        # ------------------------------------------------------------------
        # External compatibility queue
        # ------------------------------------------------------------------

        self.qbit_queue = qbit_queue if qbit_queue is not None else queue

        # ------------------------------------------------------------------
        # Handler
        # ------------------------------------------------------------------

        self.handler = handler

        # ------------------------------------------------------------------
        # System references
        # ------------------------------------------------------------------

        self.boot_cycle = boot_cycle

        self.priority_engine = priority_engine
        self.cognition_map = cognition_map
        self.watchdog = watchdog
        self.governor = governor
        self.memory_graph = memory_graph
        self.memory_system = memory_system

        # ------------------------------------------------------------------
        # Priority queues
        # ------------------------------------------------------------------

        self.priority_queues: Dict[str, pyqueue.Queue] = {
            PRIORITY_CRITICAL: pyqueue.Queue(),
            PRIORITY_NORMAL: pyqueue.Queue(),
            PRIORITY_BACKGROUND: pyqueue.Queue(),
        }

        # Legacy compatibility.
        self.queue = self.priority_queues[PRIORITY_NORMAL]

        # ------------------------------------------------------------------
        # Runtime configuration
        # ------------------------------------------------------------------

        self.throttle_hz = float(throttle_hz or 0.0)

        if self.throttle_hz > 0:
            self.throttle_delay = 1.0 / self.throttle_hz
        else:
            self.throttle_delay = 0.0

        self.batch_size = max(1, int(batch_size))

        # ------------------------------------------------------------------
        # Lifecycle
        # ------------------------------------------------------------------

        self.active = False
        self.running = False
        self.paused = False

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._state_lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None

        # ------------------------------------------------------------------
        # Async owner
        # ------------------------------------------------------------------

        self.loop = loop

        # ------------------------------------------------------------------
        # Feeds
        # ------------------------------------------------------------------

        self.feeds: Dict[str, Any] = {}

        # ------------------------------------------------------------------
        # Temporal memory
        # ------------------------------------------------------------------

        self.replay_buffer = deque(
            maxlen=max(1, int(replay_buffer_size))
        )

        self.time_travel_engine = time_travel_engine

        # ------------------------------------------------------------------
        # Diagnostics
        # ------------------------------------------------------------------

        self.stats = {
            "puts": 0,
            "gets": 0,
            "processed": 0,
            "commands_seen": 0,
            "tasks_seen": 0,
            "qbits_seen": 0,
            "dicts_seen": 0,
            "replays": 0,
            "rewinds": 0,
            "handler_success": 0,
            "handler_failures": 0,
            "dropped": 0,
            "feed_failures": 0,
            "feedback_submitted": 0,
            "feedback_routed": 0,
            "feedback_rejected": 0,
            "async_gets": 0,
            "async_waits": 0,
            "empty_polls": 0,
            "priority_critical": 0,
            "priority_normal": 0,
            "priority_background": 0,
        }

        log.info(
            "[QbitQueueLoop] initialized | temporal=True | "
            "batch=%s | throttle_hz=%s",
            self.batch_size,
            self.throttle_hz,
        )

        # ------------------------------------------------------------------
        # IMPORTANT STARTUP FIX
        #
        # The old implementation allowed QbitDialer to call:
        #
        #     queue_loop.start()
        #     queue_loop.put(qbit)
        #
        # while active was still False.
        #
        # That silently discarded the Qbit.
        #
        # The queue is now ready immediately.
        # ------------------------------------------------------------------

        if auto_activate:
            self._activate_sync()


    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def _activate_sync(self):

        with self._state_lock:

            self.active = True
            self.running = True
            self._stop_event.clear()

        log.info("[QbitQueueLoop] Ready")


    async def activate(self):


        if self.active and self.running:
            return True

        if self.boot_cycle:

            try:
                await self.boot_cycle.wait_for(
                    "CORE_READY",
                    "EVENT_BUS_READY",
                )
            except Exception as exc:
                log.debug(
                    "[QbitQueueLoop] boot_cycle wait skipped: %s",
                    exc,
                )

        self._activate_sync()

        self._emit(
            "QBIT_QUEUE_READY",
            {
                "active": True,
                "running": self.running,
            },
        )

        return True


    def schedule_activate(self):

        if self.active:
            return True

        if self.loop is None:
            self._activate_sync()
            return True

        try:

            future = asyncio.run_coroutine_threadsafe(
                self.activate(),
                self.loop,
            )

            return future

        except Exception as exc:

            log.warning(
                "[QbitQueueLoop] schedule_activate failed: %s",
                exc,
            )

            self._activate_sync()

            return False


    # ========================================================================
    # FEEDS
    # ========================================================================

    def register_feed(self, name: str, q: Any):

        if q is None:
            raise TypeError("Feed cannot be None")

        if not hasattr(q, "put") and not hasattr(q, "put_nowait"):
            raise TypeError(
                "Feed must expose put() or put_nowait()"
            )

        self.feeds[str(name)] = q

        log.info(
            "[QbitQueueLoop] Feed registered: %s",
            name,
        )


    def unregister_feed(self, name: str):

        self.feeds.pop(str(name), None)


    # ========================================================================
    # PRIORITY
    # ========================================================================

    def auto_priority(self, item: Any) -> str:

        # --------------------------------------------------------------
        # Explicit priority
        # --------------------------------------------------------------

        explicit = _safe_get(item, "priority", None)

        if explicit is None and isinstance(item, dict):
            explicit = item.get("priority")

        if explicit:

            value = str(explicit).upper()

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

        # --------------------------------------------------------------
        # Intent
        # --------------------------------------------------------------

        intent = _safe_get(item, "intent", None)

        if intent is None:

            task = _extract_task(item)

            if task:
                intent = task.get("intent")

        intent = str(intent or "").upper()

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

        return PRIORITY_BACKGROUND


    def _resolve_priority(self, item: Any, priority=None) -> str:

        if priority:
            value = str(priority).upper()

            if value in self.priority_queues:
                return value

        engine = self.priority_engine

        if engine:

            try:

                if hasattr(engine, "learn"):
                    engine.learn(item)

            except Exception as exc:
                log.debug(
                    "[QbitQueueLoop] priority learn failed: %s",
                    exc,
                )

            try:

                if hasattr(engine, "get_priority"):
                    result = engine.get_priority(item)

                    if result:
                        result = str(result).upper()

                        if result in self.priority_queues:
                            return result

            except Exception as exc:
                log.debug(
                    "[QbitQueueLoop] priority calculation failed: %s",
                    exc,
                )

        return self.auto_priority(item)


    # ========================================================================
    # QUEUE INPUT
    # ========================================================================

    async def async_put(self, item, priority=None):

        return self.put(item, priority=priority)


    def put(self, item, priority=None):

        if item is None:
            self.stats["dropped"] += 1
            return False

        # --------------------------------------------------------------
        # STARTUP SAFETY
        #
        # NEVER silently drop a Qbit because activation is slightly late.
        # --------------------------------------------------------------

        if not self.active:
            self._activate_sync()

        selected = self._resolve_priority(
            item,
            priority,
        )

        target_queue = self.priority_queues[
            selected
        ]

        try:

            target_queue.put(item)

            self.stats["puts"] += 1

            self.stats[
                f"priority_{selected.lower()}"
            ] += 1

            # ----------------------------------------------------------
            # Observability
            # ----------------------------------------------------------

            if _is_qbit_like(item):
                self.stats["qbits_seen"] += 1

            if isinstance(item, dict):
                self.stats["dicts_seen"] += 1

            commands = _extract_command_list(item)

            if commands:
                self.stats["commands_seen"] += len(commands)

            task = _extract_task(item)

            if task:
                self.stats["tasks_seen"] += 1

            # ----------------------------------------------------------
            # Broadcast
            # ----------------------------------------------------------

            self._broadcast(item)

            # ----------------------------------------------------------
            # Wake worker
            # ----------------------------------------------------------

            self._wake_event.set()

            return True

        except Exception as exc:

            self.stats["dropped"] += 1

            log.exception(
                "[QbitQueueLoop] queue insertion failed: %s",
                exc,
            )

            return False


    # ========================================================================
    # BROADCAST
    # ========================================================================

    def _broadcast(self, item):

        for name, feed in list(self.feeds.items()):

            try:

                if hasattr(feed, "put_nowait"):
                    feed.put_nowait(item)

                else:
                    feed.put(item)

            except Exception as exc:

                self.stats["feed_failures"] += 1

                log.debug(
                    "[QbitQueueLoop] feed '%s' rejected item: %s",
                    name,
                    exc,
                )


    # ========================================================================
    # QUEUE OUTPUT / SYNC + ASYNC BRIDGE
    # ========================================================================

    def _get_next(self, block=True, timeout=None):
        """Synchronously retrieve the highest-priority available item."""
        if not block:
            for level in PRIORITY_ORDER:
                try:
                    item = self.priority_queues[level].get_nowait()
                    self.stats["gets"] += 1
                    return item
                except pyqueue.Empty:
                    continue
            self.stats["empty_polls"] += 1
            raise pyqueue.Empty

        deadline = None
        if timeout is not None:
            try:
                timeout = max(0.0, float(timeout))
                deadline = time.monotonic() + timeout
            except (TypeError, ValueError):
                timeout = None

        poll = 0.05
        while self.running or self.active:
            for level in PRIORITY_ORDER:
                try:
                    item = self.priority_queues[level].get_nowait()
                    self.stats["gets"] += 1
                    return item
                except pyqueue.Empty:
                    continue

            self.stats["empty_polls"] += 1
            if self._stop_event.is_set():
                raise pyqueue.Empty

            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise pyqueue.Empty
                wait_for = min(poll, remaining)
            else:
                wait_for = poll

            self._wake_event.wait(wait_for)
            self._wake_event.clear()

        raise pyqueue.Empty

    def get_sync(self, block=True, timeout=None):
        """Synchronous API retained for threaded/legacy consumers."""
        item = self._get_next(block=block, timeout=timeout)
        self._record(item)
        return item

    async def async_get(self, block=True, timeout=None):
        """Async-safe API used by QbitDialer.

        The underlying queues remain ``queue.Queue`` instances for thread
        safety. Retrieval is moved to a worker thread so an empty queue never
        blocks the asyncio event loop and never kills the QbitDialer task.
        """
        self.stats["async_gets"] += 1

        if not block:
            return self.get_sync(block=False)

        while True:
            if self._stop_event.is_set() and self.depth() == 0:
                raise asyncio.CancelledError("QbitQueueLoop stopped")

            self.stats["async_waits"] += 1
            try:
                return await asyncio.to_thread(
                    self.get_sync,
                    True,
                    timeout if timeout is not None else 0.25,
                )
            except pyqueue.Empty:
                if timeout is not None:
                    raise
                if self._stop_event.is_set() and self.depth() == 0:
                    raise asyncio.CancelledError("QbitQueueLoop stopped")
                await asyncio.sleep(0)

    async def get(self, block=True, timeout=None):
        """Public async contract: ``await queue.get()``."""
        return await self.async_get(block=block, timeout=timeout)

    def get_nowait(self):
        return self.get_sync(block=False)

    def depth(self) -> int:
        return sum(q.qsize() for q in self.priority_queues.values())

    def qsize(self) -> int:
        return self.depth()

    # Explicit alias for callers that prefer the name to document intent.
    sync_get = get_sync

    # ========================================================================
    # FEEDBACK / FULL-CYCLE ROUTING
    # ========================================================================

    def submit_feedback(self, feedback, source_item=None, priority=None):
        """Re-enter an explicit QbitDialer feedback result safely.

        Arbitrary handler return values are NOT automatically requeued. Only
        explicitly submitted feedback re-enters the command transport path,
        preventing accidental self-feeding loops.
        """
        if feedback is None:
            self.stats["feedback_rejected"] += 1
            return False

        payload = feedback
        if isinstance(feedback, dict):
            payload = dict(feedback)
            metadata = dict(payload.get("metadata") or {})
            metadata.update({
                "feedback": True,
                "feedback_source": "QbitDialer",
            })
            if source_item is not None:
                track_id = _extract_track_id(source_item)
                channel_id = _extract_channel_id(source_item)
                if track_id is not None:
                    payload.setdefault("track_id", track_id)
                    metadata.setdefault("track_id", track_id)
                if channel_id is not None:
                    payload.setdefault("channel_id", channel_id)
                    metadata.setdefault("channel_id", channel_id)
            payload["metadata"] = metadata
            payload["feedback"] = True
            payload.setdefault("feedback_source", "QbitDialer")
        else:
            try:
                setattr(payload, "feedback", True)
                setattr(payload, "feedback_source", "QbitDialer")
                if source_item is not None:
                    track_id = _extract_track_id(source_item)
                    channel_id = _extract_channel_id(source_item)
                    if track_id is not None:
                        setattr(payload, "track_id", track_id)
                    if channel_id is not None:
                        setattr(payload, "channel_id", channel_id)
            except Exception:
                self.stats["feedback_rejected"] += 1
                return False

        selected = self._resolve_priority(payload, priority)
        accepted = self.put(payload, priority=selected)
        if accepted:
            self.stats["feedback_submitted"] += 1
            self.stats["feedback_routed"] += 1
            self._emit("QBIT_FEEDBACK_ROUTED", self._cycle_payload(payload))
        else:
            self.stats["feedback_rejected"] += 1
        return accepted

    def _cycle_payload(self, item):
        metadata = _extract_metadata(item)
        return {
            "qbit_id": _safe_get(item, "id", _safe_get(item, "qbit_id")),
            "track_id": _extract_track_id(item),
            "channel_id": _extract_channel_id(item),
            "feedback": bool(_safe_get(item, "feedback", False) or metadata.get("feedback", False)),
            "feedback_source": _safe_get(item, "feedback_source", metadata.get("feedback_source")),
            "intent": _safe_get(item, "intent"),
            "action": _safe_get(item, "action"),
        }

    # ========================================================================
    # TEMPORAL RECORDING
    # ========================================================================

    def _record(self, item):

        if item is None:
            return

        # --------------------------------------------------------------
        # Do not record replayed objects again.
        # --------------------------------------------------------------

        replayed = _safe_get(item, "_replayed", False)
        if isinstance(item, dict):
            replayed = bool(item.get("_replayed", False))
        if replayed:
            try:
                setattr(item, "_replayed", False)
            except Exception:
                if isinstance(item, dict):
                    item.pop("_replayed", None)
            return

        # --------------------------------------------------------------
        # Replay memory
        # --------------------------------------------------------------

        self.replay_buffer.append(item)

        # --------------------------------------------------------------
        # Memory graph
        # --------------------------------------------------------------

        if self.memory_graph:

            try:

                if hasattr(
                    self.memory_graph,
                    "add_qbit",
                ):
                    self.memory_graph.add_qbit(item)

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] MemoryGraph failed: %s",
                    exc,
                )

        # --------------------------------------------------------------
        # Cognition
        # --------------------------------------------------------------

        if self.cognition_map:

            try:

                if hasattr(
                    self.cognition_map,
                    "observe",
                ):
                    self.cognition_map.observe(item)

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] CognitionMap failed: %s",
                    exc,
                )

        # --------------------------------------------------------------
        # Memory system
        # --------------------------------------------------------------

        if self.memory_system:

            try:

                if hasattr(
                    self.memory_system,
                    "update",
                ):
                    self.memory_system.update(item)

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] MemorySystem failed: %s",
                    exc,
                )

        # --------------------------------------------------------------
        # TimeTravel
        # --------------------------------------------------------------

        if self.time_travel_engine:

            try:

                payload = self._temporal_payload(item)

                self.time_travel_engine.record(
                    event_type="QBIT_QUEUE_ITEM",
                    payload=payload,
                )

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] TimeTravel record failed: %s",
                    exc,
                )


    def _temporal_payload(self, item):

        commands = _extract_command_list(item)
        task = _extract_task(item)

        return {
            "qbit_id": _safe_get(
                item,
                "id",
                _safe_get(item, "qbit_id"),
            ),
            "track_id": _safe_get(
                item,
                "track_id",
                _safe_get(item, "track", None),
            ),
            "intent": _safe_get(
                item,
                "intent",
            ),
            "action": _safe_get(
                item,
                "action",
            ),
            "commands": list(commands),
            "task": task,
            "type": type(item).__name__,
        }


    # ========================================================================
    # REPLAY
    # ========================================================================

    def replay(self, steps=1):

        try:
            steps = max(0, int(steps))
        except Exception:
            steps = 1

        if steps == 0:
            return []

        items = list(
            self.replay_buffer
        )[-steps:]

        self.stats["replays"] += len(items)

        log.warning(
            "[QbitQueueLoop] replay requested | steps=%s | returned=%s",
            steps,
            len(items),
        )

        return items


    def rewind(self, steps=1):

        items = self.replay(steps)

        for item in reversed(items):

            try:
                setattr(item, "_replayed", True)
            except Exception:
                if isinstance(item, dict):
                    item["_replayed"] = True

            # ----------------------------------------------------------
            # Put back into the normal transport path.
            # ----------------------------------------------------------

            self.put(
                item,
                priority=self.auto_priority(item),
            )

        self.stats["rewinds"] += len(items)

        log.warning(
            "[QbitQueueLoop] rewind complete | items=%s",
            len(items),
        )

        return items


    # ========================================================================
    # COMMAND DISCOVERY
    # ========================================================================

    def inspect_qbit(self, item) -> Dict[str, Any]:

        task = _extract_task(item)
        commands = _extract_command_list(item)

        return {
            "is_qbit": _is_qbit_like(item),
            "qbit_id": _safe_get(
                item,
                "id",
                _safe_get(item, "qbit_id"),
            ),
            "track_id": _safe_get(
                item,
                "track_id",
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
            "command_count": len(commands),
            "task": task,
            "task_id": (
                task.get("task_id")
                if task
                else None
            ),
            "task_state": (
                task.get("state")
                if task
                else None
            ),
        }


    # ========================================================================
    # EVENTBUS
    # ========================================================================

    def _emit(self, event_name, payload=None):

        if not self.event_bus:
            return False

        try:

            return self.event_bus.emit(
                event_name,
                payload,
            )

        except Exception as exc:

            log.debug(
                "[QbitQueueLoop] EventBus emit failed "
                "| event=%s | error=%s",
                event_name,
                exc,
            )

            return False


    # ========================================================================
    # CONTROL
    # ========================================================================

    def pause(self, reason=None):

        with self._state_lock:
            self.paused = True

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


    def resume(self):

        with self._state_lock:
            self.paused = False

        self._wake_event.set()

        log.info("[QbitQueueLoop] resumed")

        self._emit(
            "QBIT_RESUME",
            {},
        )


    def stop(self, join=True, timeout=3.0):

        with self._state_lock:

            self.running = False
            self.active = False

            self._stop_event.set()
            self._wake_event.set()

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
            and thread is not threading.current_thread()
        ):

            thread.join(
                timeout=max(0.0, float(timeout))
            )

        log.info(
            "[QbitQueueLoop] stopped"
        )


    # ========================================================================
    # START
    # ========================================================================

    def start(self, threaded=True):

        # --------------------------------------------------------------
        # Always activate before accepting data.
        # --------------------------------------------------------------

        self._activate_sync()

        if not threaded:

            self._run_loop()

            return self

        with self._state_lock:

            if (
                self._thread
                and self._thread.is_alive()
            ):
                return self

            self.running = True
            self.active = True

            self._stop_event.clear()

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

            # ----------------------------------------------------------
            # Build actual batch.
            #
            # OLD BUG:
            #
            #     item = queue.get()
            #     ...
            #     if not batch:
            #
            # but item was never appended to batch.
            #
            # That made the batch-processing section unreachable.
            # ----------------------------------------------------------

            for _ in range(self.batch_size):

                item = None

                for level in PRIORITY_ORDER:

                    try:

                        item = (
                            self.priority_queues[level]
                            .get_nowait()
                        )

                        break

                    except pyqueue.Empty:
                        continue

                if item is None:
                    break

                self._record(item)

                batch.append(item)

            # ----------------------------------------------------------
            # Nothing to process.
            # ----------------------------------------------------------

            if not batch:

                self._wake_event.wait(
                    timeout=0.05
                )

                self._wake_event.clear()

                continue

            # ----------------------------------------------------------
            # Yield actual items.
            # ----------------------------------------------------------

            for item in batch:

                yield item

            # ----------------------------------------------------------
            # Throttle.
            # ----------------------------------------------------------

            if self.throttle_delay:

                time.sleep(
                    self.throttle_delay
                )


    # ========================================================================
    # EXECUTION LOOP
    # ========================================================================

    def _run_loop(self):

        log.debug(
            "[QbitQueueLoop] execution loop starting"
        )

        try:

            for item in self:

                if not self.running:
                    break

                self._dispatch(item)

        except KeyboardInterrupt:

            log.info(
                "[QbitQueueLoop] interrupted"
            )

        except Exception:

            log.exception(
                "[QbitQueueLoop] fatal execution-loop error"
            )

        finally:

            with self._state_lock:

                self.running = False
                self.active = False

            log.info(
                "[QbitQueueLoop] execution loop offline"
            )


    # ========================================================================
    # DISPATCH
    # ========================================================================

    def _dispatch(self, item):

        self.stats["processed"] += 1

        # --------------------------------------------------------------
        # Watchdog
        # --------------------------------------------------------------

        if self.watchdog:

            try:

                if hasattr(
                    self.watchdog,
                    "tick",
                ):
                    self.watchdog.tick()

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] watchdog tick failed: %s",
                    exc,
                )

        # --------------------------------------------------------------
        # Governor
        # --------------------------------------------------------------

        if self.governor:

            try:

                if hasattr(
                    self.governor,
                    "tick",
                ):
                    self.governor.tick()

            except Exception as exc:

                log.debug(
                    "[QbitQueueLoop] governor tick failed: %s",
                    exc,
                )

        # --------------------------------------------------------------
        # Command telemetry
        # --------------------------------------------------------------

        commands = _extract_command_list(item)

        if commands:

            self._emit(
                "QBIT_COMMANDS_DETECTED",
                {
                    "qbit_id": _safe_get(
                        item,
                        "id",
                        _safe_get(item, "qbit_id"),
                    ),
                    "count": len(commands),
                    "commands": commands,
                },
            )

        # --------------------------------------------------------------
        # Main handler
        #
        # QbitDialer should be supplied here.
        # --------------------------------------------------------------

        if not self.handler:

            log.debug(
                "[QbitQueueLoop] no handler | item=%r",
                item,
            )

            return

        try:

            result = self.handler(item)

            # ----------------------------------------------------------
            # Async handler compatibility.
            # ----------------------------------------------------------

            if inspect.isawaitable(result):
                result = self._run_awaitable(result)

            # Only explicitly marked feedback is reintroduced into the
            # transport path. Normal command results remain telemetry/result
            # values and cannot accidentally recurse into QbitDialer.
            if self._is_feedback(result):
                self.submit_feedback(result, source_item=item)

            self.stats["handler_success"] += 1

        except Exception as exc:

            self.stats["handler_failures"] += 1

            log.exception(
                "[QbitQueueLoop] handler failure: %s",
                exc,
            )

            self._emit(
                "QBIT_QUEUE_HANDLER_ERROR",
                {
                    "error": str(exc),
                    "qbit_id": _safe_get(
                        item,
                        "id",
                        _safe_get(item, "qbit_id"),
                    ),
                },
            )


    def _is_feedback(self, item) -> bool:
        if item is None:
            return False
        if bool(_safe_get(item, "feedback", False)):
            return True
        metadata = _extract_metadata(item)
        if bool(metadata.get("feedback", False)):
            return True
        return str(_safe_get(item, "route", "")).upper() == "FEEDBACK"

    # ========================================================================
    # ASYNC HANDLER SUPPORT
    # ========================================================================

    def _run_awaitable(self, awaitable):

        # --------------------------------------------------------------
        # If no loop is currently running in this worker thread,
        # asyncio.run() is safe.
        # --------------------------------------------------------------

        try:
            running_loop = asyncio.get_running_loop()

        except RuntimeError:

            running_loop = None

        if running_loop is None:

            try:

                return asyncio.run(
                    awaitable
                )

            except Exception:

                # Close coroutine if possible.
                try:
                    awaitable.close()
                except Exception:
                    pass

                raise

        # --------------------------------------------------------------
        # A loop already owns this thread.
        #
        # Do not call asyncio.run() inside it.
        # --------------------------------------------------------------

        if self.loop and self.loop.is_running():

            future = asyncio.run_coroutine_threadsafe(
                awaitable,
                self.loop,
            )

            return future.result()

        # Last-resort task creation.
        return running_loop.create_task(
            awaitable
        )


    # ========================================================================
    # DIAGNOSTICS
    # ========================================================================

    def status(self) -> Dict[str, Any]:

        return {
            "active": self.active,
            "running": self.running,
            "paused": self.paused,

            "thread_alive": bool(
                self._thread
                and self._thread.is_alive()
            ),

            "queue_depth": {
                level: self.priority_queues[level].qsize()
                for level in PRIORITY_ORDER
            },

            "replay_buffer": len(
                self.replay_buffer
            ),
            "queue_depth_total": self.depth(),
            "feedback_enabled": True,

            "feeds": list(
                self.feeds.keys()
            ),

            "handler": (
                getattr(
                    self.handler,
                    "__name__",
                    type(self.handler).__name__,
                )
                if self.handler
                else None
            ),

            "stats": dict(
                self.stats
            ),
        }


    def command_count(self) -> int:

        return int(
            self.stats.get(
                "commands_seen",
                0,
            )
        )


    def task_count(self) -> int:

        return int(
            self.stats.get(
                "tasks_seen",
                0,
            )
        )


    def qbit_count(self) -> int:

        return int(
            self.stats.get(
                "qbits_seen",
                0,
            )
        )


    # ========================================================================
    # REPRESENTATION
    # ========================================================================

    def __repr__(self):

        status = self.status()

        return (
            "<QbitQueueLoop "
            f"active={status['active']} "
            f"running={status['running']} "
            f"processed={status['stats']['processed']} "
            f"commands={status['stats']['commands_seen']} "
            f"tasks={status['stats']['tasks_seen']}>"
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