# ==========================================================
# FILE: modem.py
# PATH: SEED_ROOT/seed/core/modem.py
# MODULE: SEED Connector - Modem v0.5 (SYSTEM-STABLE)
# PURPOSE: SEEDModem base with dynamic channel handling, direct AudioModemManager integration
# UPDATED: 2026-01-03
# ==========================================================

import asyncio
from typing import Optional, Dict, Any, Callable
import logging
from uuid import uuid4

logger = logging.getLogger("SEEDModem")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)


# ==========================================================
# SEED Modem Base
# ==========================================================
class SEEDModem:
    def __init__(self, name: str = "base_modem"):
        self.name = name
        self.channels: Dict[str, Any] = {}
        self.active_channel: Optional[str] = None
        self._lock = asyncio.Lock()
        self._running = False
        self.on_qbit_frame: Optional[Callable[[dict], Any]] = None

    # ------------------------------------------------------
    # Lifecycle Methods
    # ------------------------------------------------------
    def start(self):
        self._running = True
        logger.info(f"[{self.name}] Started")

    def stop(self):
        self._running = False
        logger.info(f"[{self.name}] Stopped")

    def pause(self):
        self._running = False
        logger.info(f"[{self.name}] Paused")

    def resume(self):
        self._running = True
        logger.info(f"[{self.name}] Resumed")

    async def initialize(self):
        """Async initialization for modem hardware or virtual connections."""
        await asyncio.sleep(0.01)
        self.active_channel = "default"
        if "default" not in self.channels:
            self.channels["default"] = "dummy_connection"
        logger.info(f"[{self.name}] Initialized on channel: default")

    # ------------------------------------------------------
    # Channel Management
    # ------------------------------------------------------
    async def add_channel(self, name: str, connection: Any):
        async with self._lock:
            if name not in self.channels:
                self.channels[name] = connection
                logger.info(f"[{self.name}] Channel '{name}' added")
            else:
                logger.warning(f"[{self.name}] Channel '{name}' already exists")

    async def switch_channel(self, name: str):
        async with self._lock:
            if name not in self.channels:
                raise ValueError(f"Channel '{name}' not found")
            self.active_channel = name
            logger.info(f"[{self.name}] Active channel switched to '{name}'")

    # ------------------------------------------------------
    # Data Transmission
    # ------------------------------------------------------
    async def send(self, data: bytes, channel: Optional[str] = None):
        async with self._lock:
            if not self._running:
                raise RuntimeError(f"{self.name} not running")
            ch = channel or self.active_channel
            if ch not in self.channels:
                raise ValueError(f"Channel '{ch}' not found")
            logger.info(f"[{self.name}] Sending {len(data)} bytes on channel '{ch}'")

            # Build Qbit frame
            frame = {
                "source": self.name,
                "channel": ch,
                "payload_size": len(data),
                "frame_id": uuid4().hex
            }
            # Push frame to callback safely
            if callable(self.on_qbit_frame):
                try:
                    if asyncio.iscoroutinefunction(self.on_qbit_frame):
                        await self.on_qbit_frame(frame)
                    else:
                        self.on_qbit_frame(frame)
                except Exception as e:
                    logger.warning(f"[{self.name}] Qbit frame callback failed: {e}")
            return True

    async def receive(self, channel: Optional[str] = None) -> bytes:
        async with self._lock:
            ch = channel or self.active_channel
            if ch not in self.channels:
                raise ValueError(f"Channel '{ch}' not found")
            logger.info(f"[{self.name}] Receiving data on channel '{ch}'")
            # Placeholder for actual receive
            return b""

    # ------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------
    async def shutdown(self):
        async with self._lock:
            self._running = False
            self.channels.clear()
            self.active_channel = None
            logger.info(f"[{self.name}] Shutdown complete")

    # ------------------------------------------------------
    # Sync wrappers
    # ------------------------------------------------------
    def send_sync(self, data: bytes, channel: Optional[str] = None):
        return asyncio.run(self.send(data, channel))

    def receive_sync(self, channel: Optional[str] = None) -> bytes:
        return asyncio.run(self.receive(channel))


# ==========================================================
# SEED Modem Controller
# ==========================================================
class SEEDModemController:
    def __init__(self, name: str = "main_modem"):
        self.name = name
        self.modems: Dict[str, SEEDModem] = {}
        self.active_modem: Optional[SEEDModem] = None
        self._lock = asyncio.Lock()

    async def add_modem(self, modem: SEEDModem, key: Optional[str] = None):
        k = key or modem.name
        async with self._lock:
            self.modems[k] = modem
            if not self.active_modem:
                self.active_modem = modem
            await modem.initialize()
            logger.info(f"[{self.name}] Added modem '{k}'")

    async def send(self, data: bytes, *, channel: Optional[str] = None, modem_key: Optional[str] = None):
        async with self._lock:
            modem = self.active_modem if not modem_key else self.modems.get(modem_key)
            if not modem:
                raise RuntimeError(f"Modem '{modem_key or 'active'}' not available")
            return await modem.send(data, channel)

    async def receive(self, channel: Optional[str] = None, modem_key: Optional[str] = None) -> bytes:
        async with self._lock:
            modem = self.active_modem if not modem_key else self.modems.get(modem_key)
            if not modem:
                raise RuntimeError(f"Modem '{modem_key or 'active'}' not available")
            return await modem.receive(channel)

    async def switch_active_modem(self, modem_key: str):
        async with self._lock:
            modem = self.modems.get(modem_key)
            if not modem:
                raise ValueError(f"Modem '{modem_key}' not found")
            self.active_modem = modem
            logger.info(f"[{self.name}] Active modem switched to '{modem_key}'")

    async def shutdown(self):
        async with self._lock:
            for k, modem in self.modems.items():
                await modem.shutdown()
                logger.info(f"[{self.name}] Shutdown modem '{k}'")
            self.modems.clear()
            self.active_modem = None

    # Sync wrappers
    def send_sync(self, data: bytes, channel: Optional[str] = None, modem_key: Optional[str] = None):
        return asyncio.run(self.send(data, channel=channel, modem_key=modem_key))

    def receive_sync(self, channel: Optional[str] = None, modem_key: Optional[str] = None) -> bytes:
        return asyncio.run(self.receive(channel=channel, modem_key=modem_key))
