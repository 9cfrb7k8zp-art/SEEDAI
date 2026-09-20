# ==========================================================
# FILE: relay_queue.py
# PATH: SEED_ROOT/seed/core/relay/relay_queue.py
# VERSION: 2.0.0
# PURPOSE: Deterministic relay task queue
# ==========================================================

from __future__ import annotations

import queue
import threading
import time
from typing import Optional, Tuple

from .relay_protocol import RelayRequest


MODULE_ID = "CORE_RELAY_QUEUE"
MODULE_VERSION = "2.0.0"


class RelayQueue:

    def __init__(self, maxsize: int = 100):
        self._queue = queue.PriorityQueue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._sequence = 0
        self._stopped = False

    def put(self, request: RelayRequest) -> bool:
        if self._stopped:
            return False

        with self._lock:
            self._sequence += 1
            sequence = self._sequence

        priority = max(0, min(100, int(request.priority)))

        # Lower queue priority number runs first.
        queue_item: Tuple[int, int, RelayRequest] = (
            priority,
            sequence,
            request,
        )

        try:
            self._queue.put_nowait(queue_item)
            return True
        except queue.Full:
            return False

    def get(self, timeout: Optional[float] = None) -> Optional[RelayRequest]:
        if self._stopped:
            return None

        try:
            _, _, request = self._queue.get(
                timeout=timeout
            )
            return request
        except queue.Empty:
            return None

    def task_done(self) -> None:
        self._queue.task_done()

    def qsize(self) -> int:
        return self._queue.qsize()

    def stop(self) -> None:
        self._stopped = True

    def start(self) -> None:
        self._stopped = False

    def is_stopped(self) -> bool:
        return self._stopped

    def wait_until_empty(self, timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout

        while self._queue.unfinished_tasks:
            if time.monotonic() >= deadline:
                return False

            time.sleep(0.05)

        return True