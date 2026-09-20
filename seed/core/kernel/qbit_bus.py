# ==========================================================
# FILE: qbit_bus.py
# PATH: C:\SEED_ROOT\seed\core\kernel\qbit_bus.py
# VERSION: 2.0
# ROLE: Kernel-level Qbit packet transport
# AUTHORITY: SEED kernel / Qbit communication layer
# PURPOSE:
#   - Provide a thread-safe bounded ring buffer
#   - Transport Qbit/kernel packets
#   - Support controlled dispatcher lifecycle
#   - Preserve legacy write/read/start_kernel_bus API
# ==========================================================

import threading
import logging
import time
from typing import Any, Optional

log = logging.getLogger("QbitKernelBus")


class QbitKernelBus:
    """
    Thread-safe bounded ring buffer for Qbit/kernel packets.

    Legacy API preserved:
        bus.write(packet)
        bus.read()

    Added:
        start()
        stop()
        is_running()
        stats()
    """

    def __init__(self, size=10000):

        if not isinstance(size, int) or size < 2:
            raise ValueError("QbitKernelBus size must be an integer >= 2")

        self.buffer = [None] * size
        self.size = size

        self.write_ptr = 0
        self.read_ptr = 0

        self.lock = threading.Lock()

        # Lifecycle
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self.dialer = None

        # Diagnostics
        self.total_writes = 0
        self.total_reads = 0
        self.total_drops = 0
        self.total_dispatch_errors = 0

        self.created_at = time.time()

    def bind_dialer(self, dialer):

        if dialer is None:
            raise ValueError("QbitKernelBus requires a dialer")

        self.dialer = dialer
        return dialer

    # ======================================================
    # WRITE
    # ======================================================

    def write(self, packet):

        if packet is None:
            return False

        with self.lock:

            next_ptr = (self.write_ptr + 1) % self.size

            if next_ptr == self.read_ptr:

                self.total_drops += 1

                log.warning(
                    "[KernelBus] overflow | drops=%s",
                    self.total_drops,
                )

                return False

            self.buffer[self.write_ptr] = packet
            self.write_ptr = next_ptr

            self.total_writes += 1

            return True

    # ======================================================
    # READ
    # ======================================================

    def read(self) -> Optional[Any]:

        with self.lock:

            if self.read_ptr == self.write_ptr:
                return None

            packet = self.buffer[self.read_ptr]

            self.buffer[self.read_ptr] = None

            self.read_ptr = (
                self.read_ptr + 1
            ) % self.size

            self.total_reads += 1

            return packet

    # ======================================================
    # STATUS
    # ======================================================

    def is_empty(self):

        with self.lock:
            return self.read_ptr == self.write_ptr

    def is_running(self):

        return self._running

    def stats(self):

        with self.lock:

            if self.write_ptr >= self.read_ptr:
                depth = self.write_ptr - self.read_ptr
            else:
                depth = (
                    self.size
                    - self.read_ptr
                    + self.write_ptr
                )

            return {
                "size": self.size,
                "depth": depth,
                "write_ptr": self.write_ptr,
                "read_ptr": self.read_ptr,
                "total_writes": self.total_writes,
                "total_reads": self.total_reads,
                "total_drops": self.total_drops,
                "total_dispatch_errors": (
                    self.total_dispatch_errors
                ),
                "running": self._running,
            }

    # ======================================================
    # DISPATCHER
    # ======================================================

    def start(self, dialer=None):

        if dialer is None:
            dialer = self.dialer

        self.bind_dialer(dialer)

        if self._running:
            return self._thread

        self._stop_event.clear()
        self._running = True

        def loop():

            log.info(
                "[KernelBus] Dispatcher started"
            )

            try:

                while not self._stop_event.is_set():

                    packet = self.read()

                    if packet is None:
                        self._stop_event.wait(0.001)
                        continue

                    try:

                        receiver = getattr(
                            dialer,
                            "receive_qbit",
                            None,
                        )

                        if callable(receiver):
                            receiver(packet)
                        else:
                            emitter = getattr(
                                dialer,
                                "emit",
                                None,
                            )
                            if not callable(emitter):
                                raise RuntimeError(
                                    "QbitDialer exposes neither receive_qbit nor emit"
                                )
                            emitter(packet)

                    except Exception as e:

                        self.total_dispatch_errors += 1

                        log.exception(
                            "[KernelBus] dispatch error: %s",
                            e,
                        )

            finally:

                self._running = False

                log.info(
                    "[KernelBus] Dispatcher stopped"
                )

        self._thread = threading.Thread(
            target=loop,
            daemon=True,
            name="KernelBusDispatcher",
        )

        self._thread.start()

        return self._thread

    # ======================================================
    # STOP
    # ======================================================

    def stop(self, timeout=2.0):

        if not self._running:
            return True

        log.info(
            "[KernelBus] stopping dispatcher"
        )

        self._stop_event.set()

        thread = self._thread

        if thread and thread.is_alive():
            thread.join(timeout=timeout)

        self._running = False

        return True

# ==========================================================
# SEED DEBUG CHECKPOINT
# DATE: 2026-08-10
#
# PREVIOUS FIX:
#   qbit_bus.py / QbitKernelBus
#   STATUS: PASSED
#
# CURRENT FIX:
#   intent_memory.py → TimeTravelEngine
#
# ROOT CAUSE:
#   TimeTravelEngine.__init__ requires `dialer`.
#   IntentMemory already possessed the correct existing
#   QbitDialer as `self.qbit_dialer` but failed to pass it.
#
# CONFIRMED CONTRACT:
#   TimeTravelEngine(
#       dialer,
#       event_bus=...,
#       emit=...,
#       ...
#   )
#
# CORRECT WIRING:
#   dialer=self.qbit_dialer
#
# ARCHITECTURAL RULE:
#   Reuse existing QbitDialer.
#   Do not construct another dialer.
#   Do not invent a new import/module.
#
# PATHS:
#   intent_memory.py:
#       C:\SEED_ROOT\seed\core\intent_memory.py
#
#   time_travel_engine.py:
#       C:\SEED_ROOT\seed\core\time_travel_engine.py
#
# PHASE:
#   Intent Memory → Temporal Replay/Rollback
# ==========================================================
# ==========================================================
# LEGACY COMPATIBILITY API
# ==========================================================

def start_kernel_bus(bus, dialer):

    if bus is None:
        raise ValueError("bus cannot be None")

    if not isinstance(bus, QbitKernelBus):
        raise TypeError(
            "bus must be a QbitKernelBus instance"
        )

    return bus.start(dialer)