# ==========================================================
# FILE: hud_qbit_per_device.py
# PATH: SEED_ROOT/seed/core/hud_qbit_per_device.py
# HUDQbitPerDevice – tracks per-device contributions to Qbit channels
# ==========================================================

import time
import logging

logger = logging.getLogger("HUDQbitPerDevice")


# ==========================================================
# FILE: hud_qbit_per_device.py
# PATH: SEED_ROOT/seed/core/hud_qbit_per_device.py
# HUD per-device Qbit traffic visualization with pipeline integration
# ==========================================================

import time

class HUDQbitPerDevice:
    """
    Tracks and visualizes per-device contributions to each Qbit channel.
    Fully integrates with HUD overlay and optional modules for control.
    """

    def __init__(self, hud_overlay, channels=None, device_manager=None, modem=None, qbit_dialer=None):
        """
        hud_overlay: HUDMemoryOverlayQbitDynamic instance
        channels: list of Qbit channels to monitor (optional)
        device_manager: optional DeviceManager instance
        modem: optional modem instance
        qbit_dialer: optional QbitDialer instance
        """
        self.hud_overlay = hud_overlay
        self.channels = channels or getattr(hud_overlay, "channels", [1, 2, 3])
        self.device_manager = device_manager
        self.modem = modem
        self.qbit_dialer = qbit_dialer

        self.device_channel_log = {}  # {device_id: {channel: weighted_value}}
        self.last_update = time.time()

    # -----------------------------
    # Update per-device contributions
    # -----------------------------
    def update(self):
        """
        Pulls latest HUD overlay state and computes per-device channel weights.
        """
        try:
            _, channel_snapshot, device_events = self.hud_overlay.get_current_state()
        except Exception:
            # Fallback if overlay state is unavailable
            channel_snapshot = {ch: 0 for ch in self.channels}
            device_events = {}

        for dev_id in device_events.keys():
            if dev_id not in self.device_channel_log:
                self.device_channel_log[dev_id] = {ch: 0 for ch in self.channels}

            # Example contribution: evenly divide channel weight among devices
            for ch in self.channels:
                total_weight = channel_snapshot.get(ch, 0)
                num_devices = max(1, len(device_events))
                self.device_channel_log[dev_id][ch] = total_weight / num_devices

        # Remove devices no longer active
        inactive_devices = set(self.device_channel_log.keys()) - set(device_events.keys())
        for dev in inactive_devices:
            del self.device_channel_log[dev]

        self.last_update = time.time()

    # -----------------------------
    # Get per-device channel weights
    # -----------------------------
    def get_device_channel_snapshot(self):
        """
        Returns {device_id: {channel: weight}}
        """
        return self.device_channel_log

    # -----------------------------
    # Optional: send Qbit frames per device
    # -----------------------------
    def push_to_qbit_dialer(self):
        """
        If qbit_dialer is connected, push the latest device contributions as Qbit frames.
        """
        if not self.qbit_dialer:
            return

        for dev_id, channels in self.device_channel_log.items():
            frame = {
                "device_id": dev_id,
                "channels": channels,
                "timestamp": time.time()
            }
            self.qbit_dialer.push_data({"type": "per_device_qbit", "frame": frame})

    # -----------------------------
    # Optional: HUD command integration
    # -----------------------------
    def push_to_hud(self):
        """
        Push current snapshot to HUD overlay if connected
        """
        if self.hud_overlay:
            self.hud_overlay.push_per_device_snapshot(self.device_channel_log)


    # -----------------------------
    # Update per-device contributions
    # -----------------------------
    def update(self):
        """
        Recalculate per-device contributions based on the current HUD overlay state.
        Distributes channel weights evenly among active devices.
        """
        try:
            _, channel_snapshot, device_events = self.hud_overlay.get_current_state()
        except Exception as e:
            self.logger.warning(f"Failed to get HUD overlay state: {e}")
            return

        # Update or initialize device entries
        for dev_id in device_events.keys():
            if dev_id not in self.device_channel_log:
                self.device_channel_log[dev_id] = {ch: 0.0 for ch in self.channels}

            # Evenly divide channel weight among devices
            for ch in self.channels:
                total_weight = channel_snapshot.get(ch, 0.0)
                num_devices = max(1, len(device_events))
                self.device_channel_log[dev_id][ch] = total_weight / num_devices

        # Remove inactive devices
        inactive_devices = set(self.device_channel_log.keys()) - set(device_events.keys())
        for dev in inactive_devices:
            del self.device_channel_log[dev]

        self.last_update = time.time()

    # -----------------------------
    # Get snapshot for HUD or pipeline
    # -----------------------------
    def get_device_channel_snapshot(self):
        """
        Returns a copy of the device channel log:
        {device_id: {channel: weight}}
        """
        return {dev: dict(channels) for dev, channels in self.device_channel_log.items()}

    # -----------------------------
    # Add a device dynamically
    # -----------------------------
    def add_device(self, device_id):
        if device_id not in self.device_channel_log:
            self.device_channel_log[device_id] = {ch: 0.0 for ch in self.channels}
            self.logger.info(f"Added new device: {device_id}")

    # -----------------------------
    # Remove a device dynamically
    # -----------------------------
    def remove_device(self, device_id):
        if device_id in self.device_channel_log:
            del self.device_channel_log[device_id]
            self.logger.info(f"Removed device: {device_id}")

    # -----------------------------
    # Force manual recalculation
    # -----------------------------
    def recalc(self):
        self.update()
