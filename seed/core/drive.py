# ==========================================================
# FILE: drive.py
# PATH: SEED_ROOT/seed/core/drive.py
# MODULE: SEED AI OS — Drive (AI Thought Connector)
# PURPOSE: Thread-safe, async, multi-source thought bridge
# AUTHOR: Oracle / Carlos A. Clarke
# UPDATED: 2025-12-31 (Track ID + Qbit + Full System Integration)
# ==========================================================

import asyncio
import threading
import time
import traceback
import uuid
from collections import deque

from seed.core.qbit_dialer import QbitDialer

# ==========================================================
# TrackContext
# ==========================================================
class TrackContext:
    _stack = []

    @classmethod
    def push(cls, prefix="THOUGHT"):
        parent_id = cls._stack[-1] if cls._stack else None
        track_id = f"{prefix}-{str(uuid.uuid4())[:8]}"
        cls._stack.append(track_id)
        return track_id, parent_id

    @classmethod
    def pop(cls):
        if cls._stack:
            return cls._stack.pop()
        return None

    @classmethod
    def current(cls):
        return cls._stack[-1] if cls._stack else None


# ==========================================================
# Drive
# ==========================================================
class Drive:
    """
    Drive: Central thought connector for SEED.
    Handles AI packets, Orchestrator commands, AgentManager tasks,
    and forwards them to UI and QbitDialer asynchronously.
    """

    def __init__(self, ui=None, log_func=None, qbit_dialer: QbitDialer = None):
        self.ui = ui
        self.qbit_dialer = qbit_dialer
        self.queue = asyncio.PriorityQueue()
        self.loop = asyncio.new_event_loop()
        self.running = True
        self.log_func = log_func or (lambda msg: print(f"[Drive] {msg}"))
        self.voice_engine = None  # optional TTS engine
        self.history = deque(maxlen=1024)

        # Start async processing loop in a separate thread
        threading.Thread(target=self._start_loop, daemon=True).start()

    # -------------------- Receive AI thought --------------------
    def receive_ai_thought(self, packet):
        track_id, parent_id = TrackContext.push("THOUGHT")
        packet["track_id"] = track_id
        packet["parent_id"] = parent_id

        try:
            text = packet.get("text", "")
            source = packet.get("source", "AI")
            self._update_voice_display(f"[{track_id}] [{source}] {text}")

            # Optional TTS voice output
            if getattr(self, "voice_engine", None) and packet.get("priority", 1) <= 1:
                try:
                    self.voice_engine.say(text)
                    self.voice_engine.runAndWait()
                except Exception:
                    pass

            # Emit Qbit for monitoring/logging
            if self.qbit_dialer:
                qbit = {
                    "qbit_type": "AI_THOUGHT",
                    "payload": {"text": text, "source": source},
                    "track": {"track_id": track_id, "parent_id": parent_id},
                    "ts": time.time()
                }
                try:
                    self.qbit_dialer.submit_qbit(qbit)
                except Exception:
                    pass

            # Keep history for analytics/debug
            self.history.append(packet)

        finally:
            TrackContext.pop()

    # -------------------- Async loop --------------------
    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._process_queue())

    async def _process_queue(self):
        while self.running:
            try:
                priority, packet = await self.queue.get()
                track_id, parent_id = TrackContext.push("QUEUE")
                packet.setdefault("track_id", track_id)
                packet.setdefault("parent_id", parent_id)

                # Forward to UI asynchronously
                if self.ui and hasattr(self.ui, "receive_ai_thought"):
                    try:
                        self.ui.receive_ai_thought(packet)
                    except Exception:
                        self.log_func(f"[{track_id}] UI thought handling failed:\n{traceback.format_exc()}")

                self.log_func(f"[{track_id}] Thought processed: {packet}")

                # Emit Qbit for queued thought
                if self.qbit_dialer:
                    qbit = {
                        "qbit_type": "QUEUE_THOUGHT",
                        "payload": packet,
                        "track": {"track_id": track_id, "parent_id": parent_id},
                        "ts": time.time()
                    }
                    try:
                        self.qbit_dialer.submit_qbit(qbit)
                    except Exception:
                        pass

            except Exception:
                self.log_func(f"[Drive] Queue processing error:\n{traceback.format_exc()}")
            finally:
                TrackContext.pop()

    # -------------------- Public API --------------------
    def send_thought(self, packet, priority=1):
        """
        Thread-safe enqueue of a single thought packet.
        packet: dict containing keys like 'text', 'intent', 'source'
        priority: 0=critical,1=normal,2=low
        """
        if "track_id" not in packet:
            track_id, parent_id = TrackContext.push("THOUGHT")
            packet["track_id"] = track_id
            packet["parent_id"] = parent_id
            TrackContext.pop()

        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.queue.put_nowait, (priority, packet))

    def send_bulk(self, packets):
        """
        Enqueue multiple thought packets.
        Each packet can optionally contain a 'priority' key.
        """
        for packet in packets:
            self.send_thought(packet, packet.get("priority", 1))

    # -------------------- Shutdown --------------------
    def shutdown(self):
        """
        Gracefully stop Drive processing loop.
        """
        self.running = False
        if self.loop.is_running():
            for task in asyncio.all_tasks(loop=self.loop):
                task.cancel()
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.log_func("Drive shutdown complete")

    # -------------------- UI display helper --------------------
    def _update_voice_display(self, text):
        if self.ui and hasattr(self.ui, "log"):
            self.ui.log(text)
