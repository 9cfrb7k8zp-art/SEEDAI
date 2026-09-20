# ==========================================================
# FILE: sensor_trust_manager.py
# PATH: SEED_ROOT/seed/core/sensor_trust_manager.py
# VERSION: 0.6
# UPDATED: 2026-01-02
# SENSOR TRUST MANAGER – Level 2 Reliability & Decay Engine
# Full integration with ManagedDevice + DeviceManager
# ==========================================================

import time
import threading
import logging
from typing import Optional

logger = logging.getLogger("SensorTrustManager")
logger.setLevel(logging.INFO)


class SensorTrustManager:

    _global_instance = None

    def __init__(
        self,
        device_manager=None,
        decay_rate = 0.85,
        recovery_rate = 0.05,
        min_trust = 0.1,
        max_trust = 1.0,
        stale_timeout = 5.0,
        log_changes = False,
    ):
        self.device_manager = None
        self.decay_rate = decay_rate
        self.recovery_rate = recovery_rate
        self.min_trust = min_trust
        self.max_trust = max_trust
        self.stale_timeout = stale_timeout
        self.log_changes = log_changes

        self._trust = {}        # channel -> trust
        self._last_seen = {}    # channel -> timestamp
        self._lock = threading.Lock()

        # Set as global singleton instance
        SensorTrustManager._global_instance = self

    @classmethod
    def get_global(cls):
        if cls._global_instance is None:
            cls._global_instance = SensorTrustManager()
        return cls._global_instance

    # --------------------------------------------------
    # Update trust for a channel
    # --------------------------------------------------
    def update(self, channel: str, valid: bool = True) -> float:
        now = time.time()
        with self._lock:
            trust = self._trust.get(channel, self.max_trust)

            if valid:
                trust += self.recovery_rate * (self.max_trust - trust)
            else:
                trust *= self.decay_rate

            trust = max(self.min_trust, min(self.max_trust, trust))

            self._trust[channel] = trust
            self._last_seen[channel] = now

            if self.log_changes:
                action = "RECOVERY" if valid else "DECAY"
                logger.debug(f"[SensorTrustManager] {action} | {channel} -> {trust:.3f}")

            return trust

    # --------------------------------------------------
    # Get current trust without updating
    # --------------------------------------------------
    def get_trust(self, channel: str) -> float:
        with self._lock:
            return self._trust.get(channel, self.max_trust)

    # --------------------------------------------------
    # Remove stale sensors
    # --------------------------------------------------
    def prune(self):
        now = time.time()
        with self._lock:
            stale_channels = [ch for ch, ts in self._last_seen.items() if now - ts > self.stale_timeout]
            for ch in stale_channels:
                self._trust.pop(ch, None)
                self._last_seen.pop(ch, None)
                logger.warning(f"[SensorTrustManager] Pruned stale sensor channel: {ch}")

    # --------------------------------------------------
    # Snapshot for debugging
    # --------------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._trust)

    # --------------------------------------------------
    # DeviceManager / ManagedDevice helper
    # --------------------------------------------------
    def track_device_read(self, device_id: str, valid: bool = True, capability: str = None):
        channel_key = f"device.{device_id}"
        if capability:
            channel_key += f".{capability}"
        return self.update(channel_key, valid)

    def verify_devices(self):
        if not self.device_manager:
            return
        for device in self.device_manager.devices.values():
            device["trusted"] = True
        if self.device_manager.event_bus:
            self.device_manager.event_bus.emit("TRUST_CHECK", {"devices": self.device_manager.devices})



# ==========================================================
# Automatic integration with ManagedDevice
# ==========================================================
from seed.core.device_manager import ManagedDevice

original_read = ManagedDevice.read

async def read_with_trust(self, parent_track_id: Optional[str] = None, trust_mgr: Optional[SensorTrustManager] = None):
    try:
        data = await original_read(self, parent_track_id=parent_track_id)

        valid = data is not None
        mgr = trust_mgr or SensorTrustManager.get_global()

        # Update trust for each capability
        for cap in getattr(self.device, "capabilities", []):
            mgr.track_device_read(self.id, valid=valid, capability=cap)

        return data
    except Exception as e:
        logger.warning(f"[ManagedDevice] Read error (with trust): {e}")
        mgr = trust_mgr or SensorTrustManager.get_global()
        for cap in getattr(self.device, "capabilities", []):
            mgr.track_device_read(self.id, valid=False, capability=cap)
        return None

ManagedDevice.read = read_with_trust

# ============= Just Added ====================

def verify_devices(self):
    for device in self.device_manager.devices.values():
        device["trusted"] = True  # default for now
    # Optionally report status to event bus
    self.device_manager.event_bus.emit("TRUST_CHECK", {"devices": self.device_manager.devices})

# ==========================================================
# Inject trust manager into DeviceManager polling = old =look here first
# ==========================================================
from seed.core.device_manager import DeviceManager

original_poll_loop = DeviceManager._poll_loop

async def poll_loop_with_trust(self, qbit=None):
    trust_mgr = SensorTrustManager.get_global()
    try:
        while not self._stop_polling:
            tasks = [dev.read(trust_mgr=trust_mgr) for dev in list(self.devices.values())]
            if tasks:
                await asyncio.gather(*tasks)
            await asyncio.sleep(0.05)
    except asyncio.CancelledError:
        logger.info("[DeviceManager] Polling cancelled (with trust)")
    except Exception as e:
        logger.warning(f"[DeviceManager] Polling loop error (with trust): {e}")


logger.info("[SensorTrustManager v0.6] Loaded and integrated with ManagedDevice & DeviceManager")
