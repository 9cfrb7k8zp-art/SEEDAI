"""
FILE: seed_runtime_full.py
PATH: seed/core/seed_runtime_full.py

SEED MODULE: Runtime + HostDevice Integrated
VERSION: 6.9.7 + 3.5.2 (Full Production, Full Autonomy)
"""

import os
import json
import time
import uuid
import socket
import platform
import hashlib
import threading
import asyncio
import logging
import random
import ssl
from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Awaitable, Optional, List

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from flask import Flask, jsonify, request, abort

# ==========================================================
# Logging
# ==========================================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ==========================================================
# HostDevice Module
# ==========================================================
@dataclass
class HostDevice:
    platform_system: str = field(default_factory=lambda: platform.system())
    platform_release: str = field(default_factory=lambda: platform.release())
    platform_version: str = field(default_factory=lambda: platform.version())
    hostname: str = field(default_factory=lambda: socket.gethostname())
    ip_address: str = field(default_factory=lambda: HostDevice._detect_ip())
    role: str = field(default="generic")
    node_id: str = field(default_factory=lambda: f"SEED-{uuid.uuid4().hex[:8].upper()}")
    extra_info: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _detect_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @classmethod
    def auto_detect(cls, role: str = "generic") -> "HostDevice":
        device = cls(role=role)
        identity_path = os.path.join(os.getcwd(), "seed_storage", f"{device.node_id}_host.json")
        os.makedirs(os.path.dirname(identity_path), exist_ok=True)
        try:
            with open(identity_path, "w") as f:
                json.dump(device.as_dict(), f, indent=4)
        except Exception:
            pass
        return device

    def as_dict(self) -> Dict[str, Any]:
        return {
            "platform_system": self.platform_system,
            "platform_release": self.platform_release,
            "platform_version": self.platform_version,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "role": self.role,
            "node_id": self.node_id,
            "extra_info": self.extra_info
        }

    def fingerprint(self) -> str:
        data = f"{self.hostname}-{self.ip_address}-{self.platform_system}-{self.platform_release}-{self.node_id}"
        return hashlib.sha256(data.encode()).hexdigest()

    def update_role(self, new_role: str):
        self.role = new_role
        return self.role

    def add_extra_info(self, key: str, value: Any):
        self.extra_info[key] = value

    def refresh_identity(self):
        self.platform_system = platform.system()
        self.platform_release = platform.release()
        self.platform_version = platform.version()
        self.hostname = socket.gethostname()
        self.ip_address = self._detect_ip()
        self.node_id = f"SEED-{uuid.uuid4().hex[:8].upper()}"

# ==========================================================
# SEED Runtime Module
# ==========================================================
class SEEDRuntime:
    def __init__(
        self,
        qbit_dialer=None,
        seed_identity: dict = None,
        private_key_bytes: bytes = None,
        storage_root: str = None,
        host_device: HostDevice = None,
        event_bus: Optional[Any] = None,
        remote_port: int = 5001,
        web_port: int = 8080,
        auth_token: str = None,
        federation_peers: Optional[List[Dict[str, Any]]] = None
    ):
        self.qbit_dialer = qbit_dialer
        self.host_device = host_device or HostDevice.auto_detect()
        self.node_id = self.host_device.node_id
        self.storage_root = os.path.join(storage_root or os.getcwd(), self.node_id)
        os.makedirs(self.storage_root, exist_ok=True)

        self.auth_token = auth_token or hashlib.sha256(os.urandom(32)).hexdigest()
        logging.info(f"[SEEDRuntime] Remote/Web auth token: {self.auth_token}")

        # Event bus
        if event_bus:
            self.event_bus = event_bus
        else:
            class SimpleEventBus:
                def emit(self, event_name, payload):
                    logging.info(f"[EventBus] {event_name}: {payload}")
            self.event_bus = SimpleEventBus()

        logging.info(f"[SEEDRuntime] Host device: {self.host_device.as_dict()}")

        # Thread control
        self._stop_event = threading.Event()
        self._runtime_thread = None

        # Initialize SEED core (simplified)
        self.init_event = seed_identity or {}

        # Integration flags
        self.DEVHUD_ACTIVE = False
        self.TASK_MANAGER_ACTIVE = True
        self.QBIT_ACTIVE = True
        self.PROJECT4_ACTIVE = True

        # Announce host
        try:
            self.event_bus.emit(
                "host.joined",
                {"node_id": self.node_id, "host": self.host_device.as_dict()}
            )
        except Exception:
            logging.warning("Failed to emit host.joined event")

        # Bind Qbit dialer if available
        if self.qbit_dialer and hasattr(self.qbit_dialer, "bind_host"):
            try:
                self.qbit_dialer.bind_host(self.host_device)
            except Exception:
                logging.warning("Qbit binding failed")

        # Start runtime thread
        self._start()

        # Heartbeat
        self.start_heartbeat()

        # Secure remote command server
        self._remote_port = remote_port
        self._start_secure_remote_server()

        # Web dashboard
        self._web_port = web_port
        self._start_web_dashboard()

        # Dynamic federation + task auto redistribution
        self.federation_peers = federation_peers or []
        self.dynamic_peer_list: Dict[str, Dict[str, Any]] = {}
        self._start_dynamic_federation_loop()
        self._start_task_redistribution_loop()

    # ======================================================
    # Thread + Event Loop
    # ======================================================
    def _start(self):
        self._runtime_thread = threading.Thread(target=self._thread_entry, daemon=True)
        self._runtime_thread.start()
        logging.info("[SEEDRuntime] Runtime thread started.")

    def _thread_entry(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.task_queue: asyncio.Queue[Callable[[], Awaitable]] = asyncio.Queue()
        try:
            self.loop.run_until_complete(self._orchestration_loop())
        except Exception:
            logging.error("Orchestration loop crashed")
        finally:
            self.loop.close()
            logging.info("[SEEDRuntime] Event loop closed.")

    async def _orchestration_loop(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(1)  # placeholder for real tasks

    async def _enqueue(self, coro_fn: Callable[[dict], Awaitable]):
        await self.task_queue.put(coro_fn)

    # ======================================================
    # Heartbeat
    # ======================================================
    def start_heartbeat(self, interval=5.0):
        def beat():
            while not self._stop_event.is_set():
                try:
                    self.event_bus.emit(
                        "runtime.heartbeat",
                        {"node_id": self.node_id, "timestamp": time.time()}
                    )
                except Exception:
                    pass
                time.sleep(interval)
        thread = threading.Thread(target=beat, daemon=True)
        thread.start()

    # ======================================================
    # Remote Server
    # ======================================================
    def _start_secure_remote_server(self):
        def server():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', self._remote_port))
            s.listen(5)
            while not self._stop_event.is_set():
                try:
                    s.settimeout(1.0)
                    conn, addr = s.accept()
                    with conn:
                        data = conn.recv(1024).decode().strip()
                        if data.startswith(self.auth_token):
                            cmd = data[len(self.auth_token):].strip()
                            response = f"Command received: {cmd}"
                        else:
                            response = "Authentication failed"
                        conn.sendall(response.encode())
                except Exception:
                    continue
            s.close()
        thread = threading.Thread(target=server, daemon=True)
        thread.start()

    # ======================================================
    # Web Dashboard
    # ======================================================
    def _start_web_dashboard(self):
        app = Flask(__name__)

        @app.route("/status", methods=["GET"])
        def dashboard_status():
            token = request.args.get("token", "")
            if token != self.auth_token:
                abort(403)
            return jsonify(self.status())

        def run_flask():
            app.run(host="0.0.0.0", port=self._web_port, threaded=True)

        thread = threading.Thread(target=run_flask, daemon=True)
        thread.start()

    # ======================================================
    # Federation
    # ======================================================
    def _start_dynamic_federation_loop(self):
        def loop():
            while not self._stop_event.is_set():
                for peer in self.federation_peers:
                    self.dynamic_peer_list[peer.get("host", "unknown")] = peer
                time.sleep(5)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()

    # ======================================================
    # Task Redistribution
    # ======================================================
    def _start_task_redistribution_loop(self):
        def loop():
            while not self._stop_event.is_set():
                time.sleep(3)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()

    # ======================================================
    # Control API
    # ======================================================
    def stop(self):
        self._stop_event.set()
        if hasattr(self, 'loop') and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self._runtime_thread:
            self._runtime_thread.join(timeout=5)

    def restart(self):
        self.stop()
        self._stop_event.clear()
        self._start()

    def status(self):
        return {
            "node_id": self.node_id,
            "role": self.host_device.role,
            "platform": self.host_device.platform_system,
            "ip_address": self.host_device.ip_address,
            "queued_tasks": getattr(self, 'task_queue', asyncio.Queue()).qsize(),
            "dynamic_peers_count": len(self.dynamic_peer_list)
        }

# ==========================================================
# Standalone Launch
# ==========================================================
if __name__ == "__main__":
    host_device = HostDevice.auto_detect(role="primary")
    private_key_bytes = Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    seed_identity = {"seed_id": f"{host_device.node_id}"}

    runtime = SEEDRuntime(
        seed_identity=seed_identity,
        private_key_bytes=private_key_bytes,
        storage_root=os.path.join(os.getcwd(), "seed_storage"),
        host_device=host_device,
        remote_port=5001,
        web_port=8080,
        federation_peers=[{"host": "127.0.0.1", "port": 5002, "token": "exampletoken123"}]
    )

    try:
        while True:
            logging.info(runtime.status())
            time.sleep(5)
    except KeyboardInterrupt:
        runtime.stop()
        logging.info("SEED Runtime fully stopped")
