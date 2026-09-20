# ========================================================================
# FILE: device_modem_integration.py
# PATH: SEED_ROOT/seed/core/device_modem_integration.py
# STABLE v2.2 (UPGRADE)
# ========================================================================

import asyncio
import logging
from typing import Any, Optional, Dict

from seed.core.device import Device
from seed.core.modem_controller import ModemController
from seed.core.audio_modem_manager import audio_modem_manager
from seed.core.track_context import TrackContext

logger = logging.getLogger("DeviceModemIntegration")
logger.setLevel(logging.INFO)

# ========================================================================
# Device Modem Manager
# ========================================================================
class DeviceModemManager:
    def __init__(self, storage_root = "./SEED_ROOT", event_bus=None, modem_controller=ModemController): 
        from seed.core.event_bus import SEEDEventBus
        self.storage_root = storage_root
        self.devices = {}
        self.event_bus = event_bus or SEEDEventBus()
        self.modem_controller = ModemController(storage_root=storage_root, event_bus=event_bus)
        self._running = False
        self._tasks = {}

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        logger.info("[DeviceModemManager] Initialized")

    # ======================================================
    # Device Registration
    # ======================================================
    def register_device(self, device: Device):
        self.devices[device.device_id] = device
        logger.info(f"[DeviceModemManager] Registered device {device.device_id}")

        # Audio-capable device → real modem object
        if device.has_capability("audio_output") and device.device_id not in audio_modem_manager.modems:
            modem = self.modem_controller.create_modem(
                modem_id=device.device_id,
                channels=["AUDIO"],
                owner="device"
            )
            audio_modem_manager.register_modem(modem_id=device.device_id, modem=modem)
            device.add_channel("AUDIO")

        # IoT / Bluetooth routing
        if device.iot_capable or device.smart_device or device.bluetooth_id:
            device.add_channel("IOT")
            if device.bluetooth_id:
                device.add_channel("BT")

    # ======================================================
    # Lifecycle
    # ======================================================
    async def start(self):
        if self._running:
            return
        self._running = True

        self.modem_controller.start()
        await audio_modem_manager.start_all()
        logger.info("[DeviceModemManager] Started")

    async def stop(self):
        if not self._running:
            return
        self._running = False

        self.modem_controller.stop()
        await audio_modem_manager.stop_all()

        # Cancel all device monitoring tasks
        for task in self._tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        logger.info("[DeviceModemManager] Stopped")

    # ======================================================
    # Device Event Push
    # ======================================================
    def push_device_event(self, device_id: str, payload: Dict[str, Any], channel: Optional[str] = None):
        device = self.devices.get(device_id)
        if not device:
            logger.warning(f"[DeviceModemManager] Unknown device {device_id}")
            return

        channel = channel or (device.channels[0] if device.channels else "DEVICE")
        track_id = device.generate_track_id(category="DeviceEvent", stream_type="OUT")

        # Core routing
        try:
            self.modem_controller.push(payload=payload, channel=channel, parent_id=track_id)
        except Exception as e:
            logger.warning(f"[DeviceModemManager] ModemController push error: {e}")

        # Audio mirror routing
        if "AUDIO" in device.channels:
            try:
                audio_modem_manager.push(payload={"type": "audio_qbit", **payload}, channel="AUDIO", parent_id=track_id)
            except Exception as e:
                logger.warning(f"[DeviceModemManager] AudioModem push error: {e}")

        logger.debug(f"[DeviceModemManager] Event routed device={device_id} TrackID={track_id}")

    # ======================================================
    # Device Event Pull
    # ======================================================
    async def pull_device_event(self, device_id: str, qbit_type: str = "generic") -> Optional[Dict[str, Any]]:
        device = self.devices.get(device_id)
        if not device:
            return None
        try:
            frame = await self.modem_controller.pull(qbit_type=qbit_type, device_id=device_id)
            if not frame:
                return None
            return {
                "device_id": device.device_id,
                "track_id": getattr(frame, "track_id", None),
                "payload": getattr(frame, "payload", None)
            }
        except Exception as e:
            logger.warning(f"[DeviceModemManager] Pull error for device {device_id}: {e}")
            return None

    # ======================================================
    # Heartbeat
    # ======================================================
    def heartbeat_device(self, device_id: str):
        device = self.devices.get(device_id)
        if device:
            device.heartbeat()

    # ======================================================
    # Async Device Monitor
    # ======================================================
    def monitor_device(self, device_id: str, interval: float = 0.1):
        if device_id not in self.devices:
            return

        async def _monitor_loop():
            device = self.devices[device_id]
            while self._running:
                try:
                    device.heartbeat()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    device.set_error(f"Monitor error: {e}")

        task = self.loop.create_task(_monitor_loop())
        self._tasks[device_id] = task


# ========================================================================
# Singleton Instance
# ========================================================================
# device_modem_manager = DeviceModemManager()
