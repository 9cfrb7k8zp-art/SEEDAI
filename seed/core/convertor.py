# ==========================================================
# FILE: convertor.py
# PATH: SEED_ROOT/seed/core/convertor.py
# VERSION: 0.1.0 (FULL DATA CONVERSION | QBIT-FEED ONLY)
# UPDATED: 2026-01-05
#
# PURPOSE:
# - Convert ALL incoming system/module/event data into numeric-safe form
# - Act as EventBus adapter BEFORE QbitDialer ingestion
# - Zero control authority (NO decisions, NO limp mode)
# - Async-safe, thread-safe
# ==========================================================

import asyncio
import logging
import threading
import time
import math
from typing import Any, Dict, Optional

logger = logging.getLogger("SEEDConvertor")
logger.setLevel(logging.INFO)


# ==========================================================
# Numeric Conversion Core
# ==========================================================
def _to_number(value: Any) -> float:
    """
    Hard numeric coercion.
    Anything non-representable becomes 0.0
    """
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return float(value)

    if isinstance(value, bool):
        return 1.0 if value else 0.0

    try:
        return float(value)
    except Exception:
        return 0.0


def _convert_recursive(value: Any):
    """
    Recursively convert any structure into numeric-safe form.
    """
    if isinstance(value, dict):
        return {str(k): _convert_recursive(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_convert_recursive(v) for v in value]

    return _to_number(value)


# ==========================================================
# Convertor
# ==========================================================
class DataConvertor:
    """
    Qbit-controlled data convertor.
    This module:
    - Receives raw data from EventBus / HealthMonitor / System
    - Converts to numeric-only structures
    - Emits ONLY to Qbit Dialer
    """

    def __init__(
        self,
        qbit_dialer: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        async_mode: bool = True,
    ):
        self.qbit = qbit_dialer
        self.event_bus = event_bus
        self.async_mode = async_mode

        self._lock = threading.Lock()
        self._running = True

        logger.info("[Convertor] Initialized (numeric-only, Qbit-feed)")

        # Auto-bind to EventBus if provided
        if self.event_bus:
            self._bind_event_bus(self.event_bus)

    # ======================================================
    # EventBus Binding
    # ======================================================
    def _bind_event_bus(self, event_bus):
        """
        Subscribe to all high-level data flow events.
        Convertor does NOT decide routing logic – only adapts data.
        """
        try:
            event_bus.subscribe(
                event_name="*",
                callback=self.ingest_event,
                async_callback=self.async_mode,
            )
            logger.info("[Convertor] Bound to EventBus (wildcard)")
        except Exception as e:
            logger.error(f"[Convertor] EventBus bind failed: {e}")

    # ======================================================
    # Ingest
    # ======================================================
    def ingest_event(self, event):
        """
        Entry point from EventBus.
        Accepts TrackedData or raw payloads.
        """
        if not self._running or not self.qbit:
            return

        try:
            payload = getattr(event, "payload", event)
            track_id = getattr(event, "track_id", None)
            source = getattr(event, "source_id", "unknown")

            converted = self.convert(payload)

            packet = {
                "data": converted,
                "track_id": track_id,
                "source": source,
                "timestamp": time.time(),
            }

            self._emit_to_qbit(packet)

        except Exception as e:
            logger.error(f"[Convertor] Ingest error: {e}")

    # ======================================================
    # Convert
    # ======================================================
    def convert(self, payload: Any) -> Dict[str, Any]:
        """
        Convert arbitrary payload into numeric-only structure.
        """
        try:
            return {
                "vector": _convert_recursive(payload),
                "valid": 1.0,
            }
        except Exception as e:
            logger.error(f"[Convertor] Conversion failed: {e}")
            return {
                "vector": {},
                "valid": 0.0,
            }

    # ======================================================
    # Emit to Qbit
    # ======================================================
    def _emit_to_qbit(self, packet: Dict[str, Any]):
        """
        Single output path.
        Convertor NEVER emits anywhere else.
        """
        try:
            if hasattr(self.qbit, "receive_converted_data"):
                if self.async_mode:
                    self._emit_async(packet)
                else:
                    self.qbit.receive_converted_data(packet)
            else:
                logger.warning("[Convertor] Qbit missing receive_converted_data()")
        except Exception as e:
            logger.error(f"[Convertor] Emit failed: {e}")

    def _emit_async(self, packet: Dict[str, Any]):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.qbit.receive_converted_data(packet))
        except RuntimeError:
            loop = getattr(self.qbit, "_main_loop", None)
            if loop:
                asyncio.run_coroutine_threadsafe(
                    self.qbit.receive_converted_data(packet),
                    loop
                )

    # ======================================================
    # Control
    # ======================================================
    def stop(self):
        self._running = False
        logger.info("[Convertor] Stopped cleanly")
