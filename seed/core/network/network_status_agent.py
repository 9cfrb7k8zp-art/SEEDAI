"""SEED AI OS network observer.

Authority: observer only. Emits status Qbits toward the authoritative QbitDialer.
"""
from __future__ import annotations
import platform
import socket
import time
from typing import Any


class NetworkStatusAgent:
    """Lightweight network monitor; never executes commands directly."""

    def __init__(self, qbit_dialer=None, event_bus=None, interval=15.0):
        self.qbit_dialer = qbit_dialer
        self.event_bus = event_bus
        self.interval = float(interval)
        self.agent_name = "SEED-V2-NetworkMonitor"
        self.running = False

    def bind_runtime(self, qbit_dialer=None, event_bus=None):
        if qbit_dialer is not None:
            self.qbit_dialer = qbit_dialer
        if event_bus is not None:
            self.event_bus = event_bus
        return self

    def snapshot(self) -> dict[str, Any]:
        hostname = socket.gethostname()
        try:
            socket.gethostbyname(hostname)
            network = "ONLINE"
        except OSError:
            network = "OFFLINE"
        return {
            "agent": self.agent_name,
            "hostname": hostname,
            "platform": platform.platform(),
            "network": network,
            "timestamp": time.time(),
        }

    def emit_status(self):
        payload = self.snapshot()
        dialer = self.qbit_dialer
        if dialer is None:
            return {"status": "DEFERRED", "payload": payload}
        submit = getattr(dialer, "submit_command", None)
        if not callable(submit):
            return {"status": "DEFERRED", "payload": payload}
        return {"status": "OBSERVED", "payload": payload, "authority": "QbitDialer"}

    def status(self):
        return {"agent": self.agent_name, "running": self.running, **self.snapshot()}
