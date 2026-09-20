# ==========================================================
# FILE: modem_controller.py
# PATH: SEED_ROOT/seed/core/modem_controller.py
# VERSION: 2.9
#
# PURPOSE:
#   User-facing modem controller
#   - Owns ModemLayer + AudioModem
#   - NEVER masquerades as a modem itself
#   - Dynamic channel routing (audio/light/generic/network)
#   - TrackID-native
#   - Qbit + EventBus aware
# UPDATED: 2025-12-31
# ==========================================================

import asyncio
import logging
import socket
from typing import Optional, Dict

from seed.core.modem_layer import ModemLayer, SignalFrame
from seed.core.audio_modem import SEEDAudioModem
from seed.core.modem import SEEDModem, SEEDModemController
from seed.core.track_context import TrackContext
from seed.core.track_id_manager import TrackIDManager

logger = logging.getLogger("ModemController")
logging.basicConfig(level=logging.INFO)


class ModemController:
    def __init__(self, storage_root = "./SEED_ROOT", event_bus=None):
        from seed.core.event_bus import SEEDEventBus
        self.storage_root = storage_root
        self.event_bus = event_bus

        # Core layers
        self.modem_layer = ModemLayer(storage_root=storage_root, event_bus=event_bus)
        self.audio_modem = SEEDAudioModem(modem_layer=self.modem_layer)

        # Queues for routing
        self._push_queue = asyncio.Queue()
        self._pull_queue = asyncio.Queue()
        self._channels: Dict[str, asyncio.Queue] = {
            "audio": asyncio.Queue(),
            "light": asyncio.Queue(),
            "network": asyncio.Queue(),
            "generic": asyncio.Queue(),
        }

        # Modem registry (dynamic)
        self.modem_registry: Dict[str, SEEDModem] = {}

        self._running = False

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        logger.info("[ModemController] Initialized (layer-correct)")

    # ======================================================
    # MODES / ROUTING
    # ======================================================
    def register_modem(self, name: str, modem: SEEDModem):
        """Register a SEEDModem dynamically at controller level."""
        if name in self.modem_registry:
            raise KeyError(f"Modem '{name}' already registered")
        if not all(hasattr(modem, attr) for attr in ("start", "stop", "send")):
            raise TypeError(f"Invalid modem '{name}', missing required method")
        self.modem_registry[name] = modem
        logger.info(f"[ModemController] Registered modem '{name}'")

    async def send_via_modem(self, data: bytes, modem_name: str, channel: str = None):
        """Send data via a specific registered modem."""
        modem = self.modem_registry.get(modem_name)
        if not modem:
            raise ValueError(f"Modem '{modem_name}' not found")
        return await modem.send(data, channel)

    # ======================================================
    # START / STOP
    # ======================================================
    def start(self):
        if self._running:
            return
        self._running = True
        self.modem_layer.start()
        self.audio_modem.start()
        for modem in self.modem_registry.values():
            modem.start()
        self.loop.create_task(self._push_loop())
        self.loop.create_task(self._pull_loop())
        self.loop.create_task(self._route_loop())
        logger.info("[ModemController] Started")

    def stop(self):
        self._running = False
        self.modem_layer.stop()
        self.audio_modem.stop()
        for modem in self.modem_registry.values():
            modem.stop()
        logger.info("[ModemController] Stopped")

    # ======================================================
    # PUSH / PULL LOOPS
    # ======================================================
    async def _push_loop(self):
        while self._running:
            frame: SignalFrame = await self._push_queue.get()
            if not frame:
                continue
            try:
                TrackContext.set(frame.track_id)
                qtype = frame.payload.get("type", "generic")
                # Dynamic routing
                if qtype == "audio":
                    await self.audio_modem.send(frame)
                elif qtype in self.modem_registry:
                    await self.modem_registry[qtype].send(frame)
                else:
                    await self.modem_layer.send(frame)
                if self.event_bus:
                    self.event_bus.emit("MODEM_PUSH", {"track_id": frame.track_id, "type": qtype})
            except Exception as e:
                logger.error(f"[ModemController] Push error: {e}")
            await asyncio.sleep(0)

    async def _pull_loop(self):
        while self._running:
            try:
                frame = await self.modem_layer.receive()
                if not frame:
                    continue
                TrackContext.set(frame.track_id)
                await self._pull_queue.put(frame)
                if self.event_bus:
                    self.event_bus.emit("MODEM_PULL", {"track_id": frame.track_id})
            except Exception as e:
                logger.error(f"[ModemController] Pull error: {e}")
            await asyncio.sleep(0)

    async def _route_loop(self):
        while self._running:
            frame: SignalFrame = await self._pull_queue.get()
            qtype = frame.payload.get("type", "generic")
            queue = self._channels.get(qtype, self._channels["generic"])
            await queue.put(frame)
            await asyncio.sleep(0)

    # ======================================================
    # PUBLIC PUSH / PULL API
    # ======================================================
    def push(self, payload: dict, *, channel: str = "MODEM", skill: str = "PUSH", parent_id: Optional[str] = None, priority: int = 5):
        """Public push entry with TrackID generation."""
        track = TrackIDManager.generate(channel=channel, skill=skill, parent_id=parent_id, priority=priority)
        frame = SignalFrame(
            frequency=payload.get("frequency", 0.0),
            amplitude=payload.get("amplitude", 0.0),
            phase=payload.get("phase", 0.0),
            payload=payload,
            track_id=track.track_id,
        )
        self.loop.call_soon_threadsafe(self._push_queue.put_nowait, frame)

    async def pull(self, qtype: str = "generic") -> Optional[SignalFrame]:
        queue = self._channels.get(qtype, self._channels["generic"])
        try:
            return await queue.get()
        except Exception as e:
            logger.warning(f"[ModemController] Pull failed: {e}")
            return None

    # ======================================================
    # NETWORK / DNS CONTROL
    # ======================================================
    async def network_protocol_control(self, address: str, port: int, data: bytes, timeout: float = 2.0) -> bytes:
        try:
            reader, writer = await asyncio.open_connection(address, port)
            writer.write(data)
            await writer.drain()
            received = await asyncio.wait_for(reader.read(4096), timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return received
        except Exception as e:
            logger.warning(f"[ModemController] Network error: {e}")
            return b""

    def dns_query_operator(self, domain: str) -> Optional[str]:
        try:
            ip = socket.gethostbyname(domain)
            TrackContext.set(f"DNS:{domain}")
            logger.info(f"[DNS] {domain} -> {ip}")
            return ip
        except Exception as e:
            logger.warning(f"[DNS] Failed: {e}")
            return None
