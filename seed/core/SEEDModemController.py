# ==========================================================
# FILE: SEEDModemController.py
# PATH: SEED_ROOT/seed/core/SEEDModemController.py
# MODULE: Unified Modem Controller v2.2 (STABLE)
#
# DESCRIPTION:
#   - Unified controller for ModemLayer + AudioModem
#   - Async-safe multi-channel Qbit routing
#   - TrackID system: User / System / SEEDCore AI
#   - Push/Pull integration with SEEDEMQbit, AudioModem
#   - EventBus aware
#   - AudioModemManager compatible (Modem interface)
#
# UPDATED: 2025-12-31
# ==========================================================

import asyncio
import logging
from typing import Any, Dict, Optional, Protocol

from seed.core.modem_layer import ModemLayer, SignalFrame
from seed.core.audio_modem import SEEDAudioModem
from seed.core.track_id_manager import TrackIDManager

logger = logging.getLogger("SEEDModemController")
logger.setLevel(logging.INFO)

# ==========================================================
# MODEM INTERFACE (REAL, NOT FAKE)
# ==========================================================

class Modem(Protocol):
    """
    Minimal modem interface required by AudioModemManager.
    """
    def start(self) -> None: ...
    def stop(self) -> None: ...
    async def pull(self, qbit_type: str = "generic") -> Optional[Dict[str, Any]]: ...
    def push(self, payload: Dict[str, Any], parent_id: Optional[str] = None, origin: str = "System") -> None: ...


# ==========================================================
# SEED MODEM CONTROLLER
# ==========================================================

class SEEDModemController:
    """
    Unified controller for ModemLayer + AudioModem.

    L-4 Responsibilities:
      - Accept structured payloads
      - Assign TrackID ONLY if missing
      - Route frames to ModemLayer or AudioModem
      - Route pulled payloads by qbit type
    """

    def __init__(self, storage_root: str = "./SEED_ROOT", event_bus=None):
        self.storage_root = storage_root
        self.event_bus = event_bus

        # Core layers
        self.modem_layer = ModemLayer(
            storage_root=storage_root,
            event_bus=event_bus
        )

        self.audio_modem = SEEDAudioModem(
            modem_layer=self.modem_layer
        )

        # Queues
        self._push_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._pull_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._light_queue: asyncio.Queue = asyncio.Queue()
        self._generic_queue: asyncio.Queue = asyncio.Queue()

        self._running = False

        # Loop handling
        try:
            self.loop = asyncio.get_running_loop()
            logger.info("[SEEDModemController] Using existing asyncio loop")
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            logger.info("[SEEDModemController] Created new asyncio loop")

    # ---------------------------------------------------------------

    # Existing code ...

    # Add these to satisfy AudioModemManager
    def start(self):
        logger.info(f"[{self.name}] Controller start called")

    def stop(self):
        logger.info(f"[{self.name}] Controller stop called")

    async def send(self, data: bytes, *, channel: Optional[str] = None, modem_key: Optional[str] = None):
        # Use the internal routing logic
        return await self.send(data, channel=channel, modem_key=modem_key)


    # ======================================================
    # START / STOP
    # ======================================================
    def start(self):
        if self._running:
            return

        self._running = True
        self.modem_layer.start()
        self.audio_modem.start()

        self.loop.create_task(self._push_loop())
        self.loop.create_task(self._pull_loop())
        self.loop.create_task(self._route_pull_loop())

        logger.info("[SEEDModemController] Controller started")

    def stop(self):
        self._running = False
        self.modem_layer.stop()
        self.audio_modem.stop()
        logger.info("[SEEDModemController] Controller stopped")

    # ======================================================
    # PUSH LOOP (SINGLE SOURCE OF TRUTH)
    # ======================================================
    async def _push_loop(self):
        while self._running:
            payload = await self._push_queue.get()
            if not payload:
                continue

            try:
                # ---- TrackID ownership (ONLY HERE)
                if "track_id" not in payload:
                    payload["track_id"] = TrackIDManager.generate(
                        channel_marker="MODEM_PUSH",
                        parent_id=payload.get("parent_id"),
                        origin=payload.get("origin", "System")
                    )

                qtype = payload.get("type", "generic")

                # ---- Audio path
                if qtype == "audio_qbit":
                    frame = SignalFrame(
                        frequency=payload.get("frequency", 0.0),
                        amplitude=payload.get("amplitude", 1.0),
                        phase=payload.get("phase", 0.0),
                        payload=payload,
                        track_id=payload["track_id"]
                    )
                    self.audio_modem.send(frame)

                # ---- ModemLayer path
                else:
                    frame = SignalFrame(
                        frequency=payload.get("frequency", 0.0),
                        amplitude=payload.get("amplitude", 1.0),
                        phase=payload.get("phase", 0.0),
                        payload=payload,
                        track_id=payload["track_id"]
                    )
                    await self.modem_layer.send(frame)

                if self.event_bus:
                    self.event_bus.publish("MODEM_PUSH", payload=payload)

            except Exception as e:
                logger.error(f"[SEEDModemController] Push loop error: {e}")

            await asyncio.sleep(0)

    # ======================================================
    # PULL LOOP
    # ======================================================
    async def _pull_loop(self):
        while self._running:
            try:
                frame = await self.modem_layer.receive()
                if not frame:
                    continue

                payload = frame.payload

                if "track_id" not in payload:
                    payload["track_id"] = TrackIDManager.generate(
                        channel_marker="MODEM_PULL",
                        parent_id=payload.get("parent_id"),
                        origin=payload.get("origin", "System")
                    )

                await self._pull_queue.put(payload)

                if self.event_bus:
                    self.event_bus.publish("MODEM_PULL", payload=payload)

            except Exception as e:
                logger.error(f"[SEEDModemController] Pull loop error: {e}")

            await asyncio.sleep(0)

    # ======================================================
    # ROUTING LOOP
    # ======================================================
    async def _route_pull_loop(self):
        while self._running:
            payload = await self._pull_queue.get()
            qtype = payload.get("type", "generic")

            if qtype == "audio_qbit":
                await self._audio_queue.put(payload)
            elif qtype == "light_qbit":
                await self._light_queue.put(payload)
            else:
                await self._generic_queue.put(payload)

            await asyncio.sleep(0)

    # ======================================================
    # PUBLIC API (AudioModemManager SAFE)
    # ======================================================
    def push(
        self,
        payload: Dict[str, Any],
        parent_id: Optional[str] = None,
        origin: str = "System"
    ):
        """
        Thread-safe push into modem system.
        """
        if "track_id" not in payload:
            payload["track_id"] = TrackIDManager.generate(
                channel_marker="MODEM_PUSH",
                parent_id=parent_id,
                origin=origin
            )

        self.loop.call_soon_threadsafe(
            self._push_queue.put_nowait,
            payload
        )

    async def pull(self, qbit_type: str = "generic") -> Optional[Dict[str, Any]]:
        """
        Pull routed payload by qbit type.
        """
        try:
            if qbit_type == "audio_qbit":
                return await self._audio_queue.get()
            elif qbit_type == "light_qbit":
                return await self._light_queue.get()
            return await self._generic_queue.get()
        except Exception as e:
            logger.warning(f"[SEEDModemController] Pull failed: {e}")
            return None
