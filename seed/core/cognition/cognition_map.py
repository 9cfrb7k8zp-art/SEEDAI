# ==========================================================
# FILE: cognition_map.py
# PATH: SEED_ROOT/seed/core/cognition/cognition_map.py
#
# SYSTEM: SEED AI OS
# COMPONENT: CognitionMap
# VERSION: 2.0.0
# UPDATED: 2026-08-18
#
# SYSTEM LAYER:
#   COGNITION / OBSERVATION / QBIT FLOW ANALYTICS
#
# PURPOSE:
#   - Observe Qbit items flowing through the existing queue
#   - Track intent/node frequency
#   - Track intent-to-intent transitions
#   - Detect repeated loops
#   - Detect hot paths
#   - Provide safe cognition statistics
#   - Optionally wrap an EXISTING queue handler
#
# LIFECYCLE CONTRACT:
#
#   CONSTRUCTED != ACTIVE
#
#   CognitionMap is PASSIVE when instantiated.
#
#   It MUST NOT:
#       - start a thread
#       - start QbitQueueLoop
#       - start QbitDialer
#       - create a queue
#       - create a handler
#       - create a second execution path
#       - execute Qbit work by itself
#
#   It MAY:
#       - observe data
#       - maintain cognition statistics
#       - attach to an existing callable queue handler
#       - detach from an existing queue
#
# ARCHITECTURE:
#
#       QbitDialer
#            |
#            v
#       QbitQueueLoop
#            |
#            v
#       CognitionMap
#            |
#            v
#       EXISTING queue handler
#
# IMPORTANT:
#   CognitionMap is an OBSERVER / WRAPPER.
#
#   It does NOT become the authoritative queue executor.
#
# SAFETY:
#   - never call None as a handler
#   - never replace a missing handler
#   - never create a duplicate handler chain
#   - safe repeated attach
#   - safe detach
#   - supports synchronous handlers
#   - supports asynchronous handlers
#   - preserves original handler ownership
#   - construction is passive
# ==========================================================

import inspect
import logging
import threading
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple


log = logging.getLogger("CognitionMap")


# ==========================================================
# COGNITION MAP
# ==========================================================

class CognitionMap:
    

    VERSION = "2.0.0"

    def __init__(
        self,
        *,
        loop_threshold: int = 10,
        hot_threshold: int = 50,
    ):
        # --------------------------------------------------
        # Internal state
        # --------------------------------------------------

        self.nodes = defaultdict(int)
        self.edges = defaultdict(int)

        self.last_qbit = None

        self.loop_threshold = max(
            1,
            int(loop_threshold),
        )

        self.hot_threshold = max(
            1,
            int(hot_threshold),
        )

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        self._lock = threading.RLock()

        self._attached = False
        self._active = False

        self._queue_loop = None

        # The handler that existed BEFORE CognitionMap
        # attached to the queue.
        self._original_handler = None

        # Our installed wrapper.
        self._wrapped_handler = None

        # --------------------------------------------------
        # Statistics
        # --------------------------------------------------

        self._observations = 0
        self._last_observation_time = 0.0

        log.debug(
            "[CognitionMap] Constructed PASSIVE | version=%s",
            self.VERSION,
        )

    # ======================================================
    # NORMALIZATION
    # ======================================================

    @staticmethod
    def _normalize_qbit(
        qbit: Any,
    ) -> Dict[str, Any]:
       

        if isinstance(qbit, dict):
            return qbit

        # --------------------------------------------------
        # Objects exposing a payload/data dictionary
        # --------------------------------------------------

        payload = getattr(
            qbit,
            "payload",
            None,
        )

        if isinstance(payload, dict):
            return payload

        data = getattr(
            qbit,
            "data",
            None,
        )

        if isinstance(data, dict):
            return data

        # --------------------------------------------------
        # Unknown payload.
        #
        # Keep observation safe without modifying the
        # original object.
        # --------------------------------------------------

        return {
            "value": qbit,
            "intent": "UNKNOWN",
        }

    # ======================================================
    # OBSERVE
    # ======================================================

    def observe(
        self,
        qbit: Any,
    ) -> Dict[str, Any]:
       
        data = self._normalize_qbit(qbit)

        intent = str(
            data.get(
                "intent",
                "UNKNOWN",
            )
            or "UNKNOWN"
        )

        with self._lock:

            # --------------------------------------------------
            # Track node frequency
            # --------------------------------------------------

            self.nodes[intent] += 1

            # --------------------------------------------------
            # Track transitions
            # --------------------------------------------------

            if self.last_qbit is not None:

                previous = self._normalize_qbit(
                    self.last_qbit
                )

                prev_intent = str(
                    previous.get(
                        "intent",
                        "UNKNOWN",
                    )
                    or "UNKNOWN"
                )

                edge_key = (
                    prev_intent,
                    intent,
                )

                self.edges[edge_key] += 1

            # --------------------------------------------------
            # Preserve the observed object.
            # --------------------------------------------------

            self.last_qbit = qbit

            self._observations += 1

            self._last_observation_time = time.time()

        return data

    # ======================================================
    # LOOP DETECTION
    # ======================================================

    def detect_loops(
        self,
    ) -> List[Tuple[str, int]]:
       

        loops = []

        with self._lock:

            for (
                edge,
                count,
            ) in self.edges.items():

                if not isinstance(
                    edge,
                    tuple,
                ):
                    continue

                if len(edge) != 2:
                    continue

                a, b = edge

                if (
                    a == b
                    and count > self.loop_threshold
                ):
                    loops.append(
                        (
                            a,
                            count,
                        )
                    )

        return loops

    # ======================================================
    # HOT PATH DETECTION
    # ======================================================

    def detect_hot_paths(
        self,
    ) -> List[Tuple[Tuple[str, str], int]]:
      

        hot = []

        with self._lock:

            for (
                edge,
                count,
            ) in self.edges.items():

                if count > self.hot_threshold:

                    hot.append(
                        (
                            edge,
                            count,
                        )
                    )

        return hot

    # ======================================================
    # STATS
    # ======================================================

    def stats(
        self,
    ) -> Dict[str, Any]:
    

        with self._lock:

            return {
                "version":
                    self.VERSION,

                "active":
                    self._active,

                "attached":
                    self._attached,

                "observations":
                    self._observations,

                "last_observation_time":
                    self._last_observation_time,

                "loop_threshold":
                    self.loop_threshold,

                "hot_threshold":
                    self.hot_threshold,

                "nodes":
                    dict(self.nodes),

                "edges":
                    dict(self.edges),

                "loops":
                    self.detect_loops(),

                "hot_paths":
                    self.detect_hot_paths(),
            }

    # ======================================================
    # RESET
    # ======================================================

    def reset(
        self,
    ):
        

        with self._lock:

            self.nodes.clear()
            self.edges.clear()

            self.last_qbit = None

            self._observations = 0
            self._last_observation_time = 0.0

        log.debug(
            "[CognitionMap] Statistics reset"
        )

        return True

    # ======================================================
    # HANDLER WRAPPER
    # ======================================================

    def _build_wrapper(
        self,
        original_handler: Callable,
    ):
      
        if not callable(
            original_handler
        ):
            return None

        def wrapped_handler(
            qbit,
        ):
            # --------------------------------------------------
            # Observe before forwarding.
            # --------------------------------------------------

            try:
                self.observe(qbit)

            except Exception as exc:
                # Cognition must NEVER break queue execution merely
                # because observation failed.
                log.debug(
                    "[CognitionMap] observation failed: %s",
                    exc,
                    exc_info=True,
                )

            # --------------------------------------------------
            # Defensive lifecycle check.
            #
            # This should normally never be false because the
            # wrapper is only installed around a callable handler.
            # --------------------------------------------------

            handler = self._original_handler

            if not callable(handler):
                log.warning(
                    "[CognitionMap] Original queue handler "
                    "is unavailable; dispatch deferred"
                )
                return None

            # --------------------------------------------------
            # Forward to the original handler.
            #
            # Do NOT call the result here.
            #
            # If the original handler returns a coroutine,
            # QbitQueueLoop remains responsible for awaiting it.
            # --------------------------------------------------

            try:
                result = handler(qbit)

                if inspect.isawaitable(result):
                    return result

                return result

            except Exception:
                # Preserve queue-handler exceptions.
                #
                # The queue owns execution/error handling.
                raise

        # Preserve useful debugging metadata.
        try:
            wrapped_handler.__name__ = (
                getattr(
                    original_handler,
                    "__name__",
                    "queue_handler",
                )
                + "_cognition_wrapped"
            )

        except Exception:
            pass

        return wrapped_handler

    # ======================================================
    # ATTACH
    # ======================================================

    def attach_to_queue(
        self,
        queue_loop: Any,
    ) -> bool:
     

        if queue_loop is None:
            log.debug(
                "[CognitionMap] Queue attachment deferred: "
                "queue_loop is None"
            )
            return False

        with self._lock:

            # --------------------------------------------------
            # Already attached to this queue.
            # --------------------------------------------------

            if (
                self._attached
                and self._queue_loop is queue_loop
            ):
                return True

            # --------------------------------------------------
            # If attached elsewhere, detach first.
            # --------------------------------------------------

            if self._attached:
                self._detach_locked()

            # --------------------------------------------------
            # Locate the existing handler.
            # --------------------------------------------------

            handler = getattr(
                queue_loop,
                "handler",
                None,
            )

            # --------------------------------------------------
            # NEVER wrap None.
            # --------------------------------------------------

            if not callable(handler):

                self._queue_loop = queue_loop
                self._original_handler = None
                self._wrapped_handler = None
                self._attached = False
                self._active = False

                log.info(
                    "[CognitionMap] Attachment deferred | "
                    "queue handler is not ready"
                )

                return False

            # --------------------------------------------------
            # Avoid wrapping our own wrapper.
            # --------------------------------------------------

            if (
                self._wrapped_handler is not None
                and handler is self._wrapped_handler
            ):
                self._queue_loop = queue_loop
                self._attached = True
                self._active = True

                return True

            # --------------------------------------------------
            # Store original handler.
            # --------------------------------------------------

            self._queue_loop = queue_loop
            self._original_handler = handler

            wrapper = self._build_wrapper(
                handler
            )

            if not callable(wrapper):

                self._queue_loop = None
                self._original_handler = None
                self._wrapped_handler = None
                self._attached = False
                self._active = False

                log.warning(
                    "[CognitionMap] Handler wrapper creation failed"
                )

                return False

            # --------------------------------------------------
            # Install wrapper.
            #
            # We are replacing ONLY the queue's handler
            # reference. We do not start or stop the queue.
            # --------------------------------------------------

            try:

                queue_loop.handler = wrapper

            except Exception as exc:

                self._queue_loop = None
                self._original_handler = None
                self._wrapped_handler = None
                self._attached = False
                self._active = False

                log.warning(
                    "[CognitionMap] Queue handler attachment failed: %s",
                    exc,
                )

                return False

            self._wrapped_handler = wrapper

            self._attached = True
            self._active = True

            log.info(
                "[CognitionMap] ACTIVE | "
                "attached to existing queue handler"
            )

            return True

    # ======================================================
    # RETRY ATTACHMENT
    # ======================================================

    def try_attach(
        self,
        queue_loop: Any = None,
    ) -> bool:
      

        with self._lock:

            target = (
                queue_loop
                if queue_loop is not None
                else self._queue_loop
            )

        if target is None:
            return False

        return self.attach_to_queue(
            target
        )

    # ======================================================
    # DETACH
    # ======================================================

    def _detach_locked(
        self,
    ) -> bool:
      

        queue = self._queue_loop
        original = self._original_handler
        wrapper = self._wrapped_handler

        # --------------------------------------------------
        # Restore original handler only if our wrapper is
        # still installed.
        #
        # This prevents CognitionMap from overwriting a newer
        # handler installed by the queue/control layer.
        # --------------------------------------------------

        if queue is not None:

            try:

                current = getattr(
                    queue,
                    "handler",
                    None,
                )

                if (
                    wrapper is not None
                    and current is wrapper
                ):

                    queue.handler = original

            except Exception as exc:

                log.debug(
                    "[CognitionMap] Handler restoration failed: %s",
                    exc,
                )

        self._queue_loop = None
        self._original_handler = None
        self._wrapped_handler = None

        self._attached = False
        self._active = False

        return True

    def detach_from_queue(
        self,
    ) -> bool:
       
        with self._lock:

            result = self._detach_locked()

        log.info(
            "[CognitionMap] DETACHED | queue lifecycle unchanged"
        )

        return result

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def activate(
        self,
        queue_loop: Any = None,
    ) -> bool:
      

        return self.attach_to_queue(
            queue_loop
        )

    def deactivate(
        self,
    ) -> bool:
    

        return self.detach_from_queue()

    # ======================================================
    # STATUS
    # ======================================================

    @property
    def attached(self) -> bool:
        with self._lock:
            return bool(
                self._attached
            )

    @property
    def active(self) -> bool:
        with self._lock:
            return bool(
                self._active
            )

    @property
    def queue_loop(self):
        with self._lock:
            return self._queue_loop

    @property
    def original_handler(self):
        with self._lock:
            return self._original_handler

    def status(
        self,
    ) -> Dict[str, Any]:
       

        with self._lock:

            return {
                "component":
                    "CognitionMap",

                "version":
                    self.VERSION,

                "active":
                    self._active,

                "attached":
                    self._attached,

                "queue_attached":
                    self._queue_loop is not None,

                "handler_ready":
                    callable(
                        self._original_handler
                    ),

                "observations":
                    self._observations,

                "last_observation_time":
                    self._last_observation_time,
            }

    # ======================================================
    # SAFE CLOSE
    # ======================================================

    def close(
        self,
    ) -> bool:
     
        return self.detach_from_queue()


# ==========================================================
# MODULE-LEVEL COMPATIBILITY
# ==========================================================

def start_cognition_map(
    queue_loop,
):
#    """
#    Backward-compatible constructor/attachment helper.

#    IMPORTANT:

#    This function does NOT start QbitQueueLoop.

#    It creates CognitionMap and attempts to attach it to the
#    queue's EXISTING handler.

#    If the handler is not ready yet, CognitionMap remains
#    passive and can later be activated with:

#       cmap.try_attach(queue_loop)

#   This prevents the historical failure:

#       original_process = None
#        original_process(qbit)
#   """

    cmap = CognitionMap()

    if queue_loop is None:

        log.warning(
            "[CognitionMap] start requested without queue_loop; "
            "created PASSIVE map"
        )

        return cmap

    attached = cmap.attach_to_queue(
        queue_loop
    )

    if not attached:

        log.info(
            "[CognitionMap] Queue handler not ready; "
            "map remains PASSIVE"
        )

    return cmap