# ==========================================================
# FILE: qbit_aggregator.py
# PATH: SEED_ROOT/seed/core/qbit_aggregator.py
# Dynamic multi-source Qbit aggregation engine with auto-balance
# and quantum calculation
# Upgraded to integrate with QbitLayer plug interface
# ==========================================================

### Add This to the bottom Code### Look what this got "from" see how it works. ## fix error, merge to codes#


import tracemalloc
import time
import asyncio
import threading
import logging
import math

from seed.core.hud_qbit_alerts import HUDQbitChannelAlerts
from seed.core.hud_qbit_autobalance import HUDQbitAutoBalance
from seed.core.qbit_layer import QbitLayer

logger = logging.getLogger("QbitAggregator")
logging.basicConfig(level=logging.INFO)


class QbitAggregator:
    """
    Aggregates multiple system signals into Qbit channel weights.
    Supports async FAT pushes, HUD updates, QbitLayer plug integration,
    alerts, auto-balancing, and quantum calculations.
    """

    def __init__(
        self,
        device_manager=None,
        modem=None,
        log_source=None,
        cpu_source=None,
        qbit_dialer=None,
        plugs=None,  # dict of plug_name -> plug_instance
    ):
        self.device_manager = device_manager
        self.modem = modem
        self.log_source = log_source
        self.cpu_source = cpu_source
        self.qbit_dialer = qbit_dialer
        self.plugs = plugs or {}  # {"qbit": QbitLayer instance, ...}

        # HUD overlay, alerts, and FAT queue
        self.hud_overlay = None
        self.hud_alerts = None
        self.hud_autobalance = None
        self.fat_queue = None

        self.weights = {
            "handshake": 1.0,
            "modem": 0.8,
            "memory": 1.2,
            "logs": 0.6,
            "cpu": 0.5,
            "qbit": 1.0
        }

        tracemalloc.start()
        logger.info("[QbitAggregator] Initialized with qbit_dialer=%s, plugs=%s",
                    bool(qbit_dialer), list(self.plugs.keys()))

    # -----------------------------
    # HUD / FAT integration
    # -----------------------------
    def set_hud_overlay(self, hud_overlay):
        self.hud_overlay = hud_overlay
        self.hud_alerts = HUDQbitChannelAlerts(hud_overlay)
        self.hud_autobalance = HUDQbitAutoBalance(hud_overlay)
        logger.info("[QbitAggregator] HUD overlay, alerts, and auto-balance attached")

    def set_fat_queue(self, fat_queue):
        self.fat_queue = fat_queue
        logger.info("[QbitAggregator] FAT queue attached")

    async def push_to_fat(self, entry):
        if self.fat_queue:
            await asyncio.to_thread(self.fat_queue.put_nowait, entry)
        else:
            logger.warning("[QbitAggregator] FAT queue not set, entry dropped")

    # -----------------------------
    # Individual signal collectors
    # -----------------------------
    def handshake_signal(self):
        return len(getattr(self.device_manager, "active_sessions", [])) if self.device_manager else 0

    def modem_signal(self):
        if not self.modem:
            return 0
        return sum(getattr(self.modem, "tx_log", [])) + sum(getattr(self.modem, "rx_log", []))

    def memory_signal(self):
        snapshot = tracemalloc.take_snapshot()
        mem_bytes = sum(stat.size for stat in snapshot.statistics("lineno"))
        return mem_bytes / (1024 * 1024)  # MB

    def log_signal(self, channel):
        if not self.log_source:
            return 0
        return self.log_source(channel)

    def cpu_signal(self):
        if not self.cpu_source:
            return 0
        return self.cpu_source()

    def qbit_signal(self):
        total_nodes = 0
        # From dialer
        if self.qbit_dialer:
            total_nodes += len(getattr(self.qbit_dialer, "active_nodes", []))
        # From plugged layers
        for plug_name, plug in self.plugs.items():
            if isinstance(plug, QbitLayer):
                latest_states = plug.read()
                total_nodes += len(latest_states)
        return total_nodes

    # -----------------------------
    # Quantum calculator
    # -----------------------------
    def quantum_calculator(self, channel_values):
        """
        Computes a derived quantum weight using all channel values
        """
        total = sum(channel_values.values())
        q_sum = sum(math.sin(v) ** 2 + math.cos(v) ** 2 for v in channel_values.values())  # ~1.0
        quantum_value = total * q_sum / max(1, len(channel_values))
        return quantum_value

    # -----------------------------
    # Aggregate into channel weight
    # -----------------------------
    def compute_channel_weight(self, channel):
        value = (
            self.handshake_signal() * self.weights["handshake"] +
            self.modem_signal() * self.weights["modem"] +
            self.memory_signal() * self.weights["memory"] +
            self.log_signal(channel) * self.weights["logs"] +
            self.cpu_signal() * self.weights["cpu"] +
            self.qbit_signal() * self.weights["qbit"]
        )

        # Apply auto-balance if available
        if self.hud_autobalance:
            value = self.hud_autobalance.balance_channel(channel, value)

        # HUD overlay update
        if self.hud_overlay and hasattr(self.hud_overlay, "update_channel"):
            self.hud_overlay.update_channel(channel, value)

        # HUD alerts update
        if self.hud_alerts:
            color = self.hud_alerts.get_channel_color(value)
            if hasattr(self.hud_overlay, "set_channel_color"):
                self.hud_overlay.set_channel_color(channel, color)

        # Push to FAT asynchronously
        if self.fat_queue:
            entry = {
                "timestamp": time.time(),
                "source": "QbitAggregator",
                "channel": channel,
                "value": value
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.push_to_fat(entry))
            except RuntimeError:
                threading.Thread(target=lambda: asyncio.run(self.push_to_fat(entry)), daemon=True).start()

        # Push to QbitLayer plugs automatically
        for plug_name, plug in self.plugs.items():
            if hasattr(plug, "write"):
                plug.write(channel, value)

        return value

    # -----------------------------
    # Aggregate all channels
    # -----------------------------
    def compute_all_channels(self, channels):
        results = {}
        for ch in channels:
            results[ch] = self.compute_channel_weight(ch)

        # Quantum calculation example
        if results:
            q_val = self.quantum_calculator(results)
            logger.debug(f"[QbitAggregator] Quantum value derived: {q_val:.4f}")

        return results

    # -----------------------------
    # Async update loop for periodic computation
    # -----------------------------
    async def async_update_loop(self, channels, interval=0.1):
        while True:
            self.compute_all_channels(channels)
            await asyncio.sleep(interval)
