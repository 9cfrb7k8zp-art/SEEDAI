# =====================================================
# FILE: hud_watchdog_panel.py
# PATH: seed/core/hud_watchdog_panel.py
# HUD Panel for Watchdog / System Health Visualization
# =====================================================

import time
import threading

class HUDWatchdogPanel:
    """
    HUD panel that visualizes watchdog telemetry:
    - module state
    - heartbeat age
    - failure count
    """

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.modules = {}   # module_name -> status dict
        self._lock = threading.Lock()

        # Subscribe to watchdog telemetry
        self.event_bus.on("hud.status", self._on_status)

        print("[HUD][WatchdogPanel] Initialized")

    # -----------------------------
    # Event handler
    # -----------------------------
    def _on_status(self, packet):
        module = packet.get("module")
        if not module:
            return

        with self._lock:
            self.modules[module] = {
                "state": packet.get("state", "unknown"),
                "failures": packet.get("failures", 0),
                "last_heartbeat": packet.get("last_heartbeat"),
                "timestamp": packet.get("timestamp", time.time()),
                "reason": packet.get("reason")
            }

    # -----------------------------
    # Render hook (HUD Overlay calls this)
    # -----------------------------
    def render(self):
        """
        Returns structured HUD data (no UI assumptions).
        """
        now = time.time()
        output = []

        with self._lock:
            for module, data in self.modules.items():
                hb = data.get("last_heartbeat")
                age = round(now - hb, 2) if hb else None

                output.append({
                    "module": module,
                    "state": data["state"],
                    "failures": data["failures"],
                    "heartbeat_age": age,
                    "reason": data.get("reason")
                })

        return output
