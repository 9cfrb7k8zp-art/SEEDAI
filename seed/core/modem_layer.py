# ==========================================================
# FILE: modem_layer.py
# PATH: SEED_ROOT/seed/core/modem_layer.py
# VERSION: v2.7.0 (CONTRACT-STABLE | TRACK-SAFE | DEVICE-AGNOSTIC)
#
# DESCRIPTION:
#   Core Modem Transport Layer for SEED AI OS
#
#   - Defines Modem base contract (FIXES type mismatch)
#   - TrackID-native frame transport
#   - Async + thread-safe TX/RX
#   - Unified RX queue for system modules
#   - EventBus + Qbit compatible
#
# UPDATED: 2025-12-31
# ==========================================================

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from threading import Thread, Event
from queue import Queue, Empty

from seed.core.track_context import TrackContext


logger = logging.getLogger("ModemLayer")
logger.setLevel(logging.INFO)

# ==========================================================
# MODEM CONTRACT (CRITICAL)
# ==========================================================
class Modem(Protocol):

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def send(self, frame: "SignalFrame") -> None: ...


# ==========================================================
# SIGNAL FRAME (TRANSPORT ONLY)
# ==========================================================
@dataclass
class SignalFrame:
    frequency = 3.6
    amplitude = 0.9
    phase: float
    payload = ()
    timestamp = None
    noise = 0.3
    track_id = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

        if not isinstance(self.payload, dict):
            raise TypeError("SignalFrame.payload must be a dict")

# ==========================================================
# MODEM LAYER (TRANSPORT CORE)
# ==========================================================
class ModemLayer:

    def __init__(self, storage_root = "./SEED_ROOT", event_bus=None):
        from seed.core.event_bus import SEEDEventBus
        self.storage_root = storage_root
        self.event_bus = SEEDEventBus

        # Async queues (loop-owned)
        self._send_queue: asyncio.Queue[SignalFrame] = asyncio.Queue()
        self._receive_queue: asyncio.Queue[SignalFrame] = asyncio.Queue()

        # Thread-safe RX queue (SYSTEM STANDARD)
        self.rx_queue: Queue[SignalFrame] = Queue()

        self._running = False

        # Event loop control
        self._loop = None
        self._loop_ready = Event()

        self._loop_thread = Thread(
            target=self._loop_worker,
            name="ModemLoopThread",
            daemon=True
        )
        self._loop_thread.start()

        logger.info("[ModemLayer] Initialized")

    # ======================================================
    # LOOP WORKER
    # ======================================================
    def _loop_worker(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._loop.create_task(self._io_pump())
        self._loop_ready.set()

        logger.info("[ModemLayer] Event loop ready")
        self._loop.run_forever()

    # ======================================================
    # START / STOP
    # ======================================================
    def start(self):
        if self._running:
            return
        self._running = True
        logger.info("[ModemLayer] Started")

    def stop(self):
        self._running = False
        logger.info("[ModemLayer] Stopped")

    # ======================================================
    # ASYNC SEND (TRACK REQUIRED)
    # ======================================================
    async def send(self, frame: SignalFrame):
        self._validate_frame(frame)

        await self._send_queue.put(frame)

        if self.event_bus:
            self._emit("MODEM_FRAME_TX", frame)

        logger.info(f"[{frame.track_id}] TX queued")

    # ======================================================
    # THREAD-SAFE SEND
    # ======================================================
    def tx(self, frame: SignalFrame):
        self._validate_frame(frame)
        self._loop_ready.wait()

        try:
            asyncio.run_coroutine_threadsafe(
                self._send_queue.put(frame),
                self._loop
            )

            if self.event_bus:
                self._emit("MODEM_FRAME_TX", frame)

            logger.info(f"[{frame.track_id}] TX sent (thread-safe)")

        except Exception as e:
            logger.error(f"[{frame.track_id}] TX failure: {e}")

    # ======================================================
    # ASYNC RECEIVE
    # ======================================================
    async def receive(self) -> Optional[SignalFrame]:
        if not self._running:
            return None

        frame = await self._receive_queue.get()
        logger.info(f"[{frame.track_id}] RX async")
        return frame

    # ======================================================
    # THREAD-SAFE RECEIVE
    # ======================================================
    def receive_nowait(self) -> Optional[SignalFrame]:
        try:
            frame = self.rx_queue.get_nowait()
            logger.info(f"[{frame.track_id}] RX thread-safe")
            return frame
        except Empty:
            return None

    # ======================================================
    # IO PUMP (TRACK-CONTEXT SAFE)
    # ======================================================
    async def _io_pump(self):
        while True:
            try:
                frame: SignalFrame = await self._send_queue.get()

                # Restore TrackContext during transport
                TrackContext.set(frame.track_id)

                # Transport pass-through
                await self._receive_queue.put(frame)
                self.rx_queue.put(frame)

                if self.event_bus:
                    self._emit("MODEM_FRAME_RX", frame)

                logger.info(f"[{frame.track_id}] Pumped through modem")

            except Exception as e:
                logger.error(f"[ModemLayer] IO pump error: {e}")
                await asyncio.sleep(0.01)

    # ======================================================
    # FRAME VALIDATION (HUMAN ERROR GUARD)
    # ======================================================
    def _validate_frame(self, frame: SignalFrame):
        if not self._running:
            raise RuntimeError("ModemLayer is not running")

        if not isinstance(frame, SignalFrame):
            raise TypeError(f"Expected SignalFrame, got {type(frame)}")

        if not frame.track_id:
            raise ValueError("SignalFrame missing track_id")

    # ======================================================
    # EVENT EMIT (TRACK SAFE)
    # ======================================================
    def _emit(self, event: str, frame: SignalFrame):
        try:
            TrackContext.set(frame.track_id)
            self.event_bus.emit(event, {"frame": frame})
        except Exception as e:
            logger.error(f"[{frame.track_id}] Event emit failed: {e}")

    # ======================================================
    # ENCODING PLACEHOLDER
    # ======================================================
    def encode(self, payload: Any) -> bytes:
        return str(payload).encode("utf-8")
