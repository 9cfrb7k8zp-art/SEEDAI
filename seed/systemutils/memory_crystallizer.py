# ==========================================================
# FILE: memory_crystallizer.py
# PATH: SEED_ROOT/seed/systemutils/memory_crystallizer.py
# VERSION: 5.6 (FULL QBIT + VECTOR | LIMPMODE | ASYNC-SAFE | EVENTBUS-DEFERRED)
# UPDATED: 2026-01-04
# ==========================================================

from __future__ import annotations

import asyncio
import time
import threading
import logging
from typing import Any, Dict, Optional
from collections import deque

logger = logging.getLogger("MemoryCrystallizer")
logger.setLevel(logging.INFO)

# ==========================================================
# MEMORY STATE ENUM (SOFT CONTROL)
# ==========================================================

class MemoryState:
    TRANSIENT = "transient"
    CANDIDATE = "candidate"
    CRYSTALLIZED = "crystallized"
    DISCARDED = "discarded"


# ==========================================================
# MEMORY CRYSTALLIZER
# ==========================================================

class Memory_Crystallizer:
    def __init__(
        self,
        *,
        qbit,
        emit,
        track, 
        track_id,
        task,
        max_history=1024,
        event_bus=None,
        limp_mode = False,
        buffer_limit = 256,
        crystallization_threshold = 0.75,
        storage_root="./SEED_ROOT",
    ):
        self.event_bus = event_bus
        self.limp_mode = limp_mode
        self.storage_root = storage_root
        self.lock = threading.Lock()
        self.qbit = qbit
        self.emit = emit
        self.track = track
        self.track_id = track_id
        self.tack = task

        self.buffer_limit = buffer_limit
        self.crystallization_threshold = crystallization_threshold

        # short-term memory buffer
        self._memory_buffer: deque = deque(maxlen=buffer_limit)

        # crystallized memory store (can be swapped later)
        self._long_term_memory: Dict[str, Dict[str, Any]] = {}

        self._lock = asyncio.Lock()

        logger.info("[MemoryCrystallizer] Initialized")

    # ------------------------------------------------------
    # ENTRY POINT
    # ------------------------------------------------------

    async def observe(self, qbit) -> None:
        if self.limp_mode:
            return

        if not qbit or not hasattr(qbit, "payload"):
            return

        async with self._lock:
            record = self._build_record(qbit)
            self._memory_buffer.append(record)

            self._evaluate(record)


    def record(self, event):
        with self.lock:
            self.history.append({
                "timestamp": time.time(),
                "event": event
            })

    def replay(self, last_n=None):
        with self.lock:
            return list(self.history)[-last_n:] if last_n else list(self.history)

    # ------------------------------------------------------
    # RECORD BUILD
    # ------------------------------------------------------

    def _build_record(self, qbit) -> Dict[str, Any]:
        return {
            "timestamp": time.time(),
            "track_id": getattr(qbit, "track", {}).get("track_id"),
            "payload": qbit.payload,
            "state": qbit.state if hasattr(qbit, "state") else None,
            "weight": getattr(qbit, "weight", 1.0),
            "flags": getattr(qbit, "flags", {}),
            "state_tag": MemoryState.TRANSIENT,
            "origin": qbit.upstream_track.get("origin") if hasattr(qbit, "upstream_track") else None,
        }

    # ------------------------------------------------------
    # EVALUATION LOGIC (SOFT, NON-BINARY)
    # ------------------------------------------------------

    def _evaluate(self, record: Dict[str, Any]) -> None:
        weight = record.get("weight", 1.0)
        repetition = self._repetition_score(record)

        crystallization_score = (weight + repetition) / 2

        if crystallization_score >= self.crystallization_threshold:
            record["state_tag"] = MemoryState.CRYSTALLIZED
            self._crystallize(record)
        elif crystallization_score >= 0.4:
            record["state_tag"] = MemoryState.CANDIDATE
        else:
            record["state_tag"] = MemoryState.DISCARDED

    # ------------------------------------------------------
    # REPETITION AWARENESS
    # ------------------------------------------------------

    def _repetition_score(self, record: Dict[str, Any]) -> float:
        payload = record.get("payload")
        if payload is None:
            return 0.0

        count = 0
        for r in self._memory_buffer:
            if r.get("payload") == payload:
                count += 1

        return min(count / self.buffer_limit, 1.0)

    # ------------------------------------------------------
    # CRYSTALLIZATION
    # ------------------------------------------------------

    def _crystallize(self, record: Dict[str, Any]) -> None:
        track_id = record.get("track_id")
        if not track_id:
            return

        self._long_term_memory[track_id] = record

        self._emit(
            "MEMORY_CRYSTALLIZED",
            {
                "track_id": track_id,
                "payload": record.get("payload"),
                "origin": record.get("origin"),
            },
        )

    # ------------------------------------------------------
    # SAFE EMIT (NEVER BLOCKS CORE)
    # ------------------------------------------------------

    def _emit(self, event: str, payload: Optional[dict] = None) -> None:
        if not self.event_bus:
            return

        try:
            self.event_bus.publish(
                event,
                payload=payload or {},
                source="MemoryCrystallizer",
            )
        except Exception as e:
            logger.debug(f"[MemoryCrystallizer] emit failed: {e}")

    # ------------------------------------------------------
    # SEED CONTROLLED MEMORY ACCESS
    # ------------------------------------------------------

    def recall(self, track_id: str) -> Optional[Dict[str, Any]]:
        return self._long_term_memory.get(track_id)

    def forget(self, track_id: str) -> None:
        self._long_term_memory.pop(track_id, None)

    def all_memories(self):
        return dict(self._long_term_memory)

    # ------------------------------------------------------

    def __repr__(self):
        return (
            f"Memory_Crystallizer("
            f"short_term={len(self._memory_buffer)}, "
            f"long_term={len(self._long_term_memory)}"
            f")"
        )
