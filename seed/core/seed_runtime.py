# ===========================================================================
# """
# FILE: seed_runtime.py
# PATH: seed/core/seed_runtime.py
#
# SEED MODULE: Runtime Orchestration
# VERSION: 6.9.9 (Production + Dynamic Federation + Auto Task Redistribution)
# UPDATED: 2026-01-10
# """
# ===========================================================================

from pathlib import Path
import logging
import os
import asyncio
import threading
import time
import json
import traceback
import platform
import socket
import ssl
import hashlib
from typing import Callable, Awaitable, Optional, Any, List, Dict
import tracemalloc
import random
from enum import Enum
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from seed.core.init_event import SeedInitEvent
from seed.runtime.host_device import HostDevice
from seed.skills.quantum_signal_mapper import QuantumSignalMapper
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
# Runtime State
# ==========================================================
class RuntimeState(Enum):
    BOOT = "boot"
    ACTIVE = "active"
    IDLE = "idle"

# ==========================================================
# SEED Runtime
# ==========================================================
class SEEDRuntime:

    IDLE_TIMEOUT = 15.0  # seconds without signal → idle

    def __init__(
        self,
        *,
        qbit_dialer,
        seed_identity: dict,
        private_key_bytes: bytes,
        storage_root: str,
        host_device: HostDevice,
        event_bus,
        remote_port: int = 5001,
        web_port: int = 8080,
        auth_token: str = None,
        federation_peers: Optional[List[Dict[str, Any]]] = None
    ):
        self.qbit_dialer = qbit_dialer
        self.host_device = host_device or HostDevice.auto_detect()
        self.state = RuntimeState.BOOT
        self._last_activity_ts = time.time()
        self.node_id = self.host_device.node_id
        self.storage_root = Path(storage_root) / self.node_id
        self.storage_root.mkdir(parents=True, exist_ok=True)

        self.auth_token = auth_token or hashlib.sha256(os.urandom(32)).hexdigest()
        logging.info(f"[SEEDRuntime] Remote/Web auth token: {self.auth_token}")

#        # Event bus
#        if event_bus:
#            self.event_bus = event_bus
#        else:
#            class SimpleEventBus:
#                def emit(self, event_name, payload):
#                    logging.info(f"[EventBus] {event_name}: {payload}")
#            self.event_bus = SimpleEventBus()

        logging.info(f"[SEEDRuntime] Host device: {self.host_device.as_dict()}")

        # Thread control
        self._stop_event = threading.Event()
        self._runtime_thread = None

        # Initialize SEED core
        self.init_event = SeedInitEvent(
            seed_identity=seed_identity or {},
            private_key_bytes=private_key_bytes or b'',
            storage_root=str(self.storage_root),
            host_device=self.host_device
        )

        # Integration flags
        self.DEVHUD_ACTIVE = bool(
            getattr(self.init_event, "devhud_integration", {}).get("enabled", False)
        )
        self.TASK_MANAGER_ACTIVE = hasattr(self.init_event, "task_manager")
        self.QBIT_ACTIVE = hasattr(self.init_event, "qbit")
        self.PROJECT4_ACTIVE = hasattr(self.init_event, "project4")

        # Announce host
        try:
            self.event_bus.emit(
                "host.joined",
                {"node_id": self.node_id, "host": self.host_device.as_dict()}
            )
        except Exception:
            logging.warning("Failed to emit host.joined event:\n" + traceback.format_exc())

        # Bind Qbit dialer if available
        if self.qbit_dialer and hasattr(self.qbit_dialer, "bind_host"):
            try:
                self.qbit_dialer.bind_host(self.host_device)
            except Exception:
                logging.warning("Qbit binding failed:\n" + traceback.format_exc())

        # Start runtime thread
        self._start()

        # Heartbeat
        self.start_heartbeat()

        # Memory tracing
        tracemalloc.start()
        logging.info("[SEED-Runtime] Memory tracing enabled.")

        # Secure remote command server
        self._remote_port = remote_port
        self._start_secure_remote_server()

        # --------------------------
        # Capability Flags
        # --------------------------
        self.DEVHUD_ACTIVE = hasattr(self.init_event, "devhud_integration")
        self.QBIT_ACTIVE = qbit_dialer is not None

        # Web dashboard
        self._web_port = web_port
        self._start_web_dashboard()
        self.running = False

        # Dynamic federation + task auto redistribution
        self.federation_peers = federation_peers or []
        self.dynamic_peer_list: Dict[str, Dict[str, Any]] = {}
        self._start_dynamic_federation_loop()
        self._start_task_redistribution_loop()
        self._start_task_load_balancer()

        self.quantum_mapper = QuantumSignalMapper(
            runtime=self,
            sparkplug=getattr(self.init_event, "sparkplug", None),
            qbit_dialer=self.qbit_dialer,
            event_bus=self.event_bus,
            hud_pipeline=getattr(self.init_event, "hud_pipeline", None),
        )

        self.quantum_mapper.set_system_ready(True)
        asyncio.run_coroutine_threadsafe(
            self.quantum_mapper.watch(),
            self.loop
        )
        logger.info("[SEEDRuntime] Initialized on node %s", self.node_id)

        # --------------------------
        # Start Runtime
        # --------------------------
        self._stop_event = threading.Event()
        self.loop = None
        self._runtime_thread = None

        self._subscribe_events()
        self._start()


    # ======================================================
    # Event Wiring
    # ======================================================
    def _subscribe_events(self):
        self.event_bus.subscribe("hud.activity", self._on_activity)
        self.event_bus.subscribe("hud.command", self._on_activity)
        self.event_bus.subscribe("hud.live_scan", self._on_activity)


    def _on_activity(self, payload):
        self._last_activity_ts = time.time()
        if self.state == RuntimeState.IDLE:
            self._exit_idle()

    # ======================================================
    # Thread + Event Loop
    # ======================================================
    def _start(self):
        self._runtime_thread = threading.Thread(
            target=self._thread_entry, daemon=True
        )
        self._runtime_thread.start()
        logging.info("[SEEDRuntime] Runtime thread started.")

    def _thread_entry(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.task_queue: asyncio.Queue[Callable[[], Awaitable]] = asyncio.Queue()
        try:
            self.loop.run_until_complete(self._orchestration_loop())
        except Exception:
            logging.error("Orchestration loop crashed:\n" + traceback.format_exc())
        finally:
            self.loop.close()
            logging.info("[SEEDRuntime] Event loop closed.")

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
                    logging.warning("Heartbeat failed:\n" + traceback.format_exc())
                time.sleep(interval)
        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        logging.info(f"[SEEDRuntime] Heartbeat started, interval={interval}s.")

    # ======================================================
    # Orchestration Loop
    # ======================================================
    async def _orchestration_loop(self):
        logging.info("[SEEDRuntime] Orchestration loop starting.")
        try:
            await self.init_event.create_event()
        except Exception:
            logging.error("Init event creation failed:\n" + traceback.format_exc())

        while not self._stop_event.is_set():
            try:
                for coro_fn in [
                    getattr(self.init_event, name)
                    for name in [
                        "_continuous_self_replication",
                        "_real_time_interdimensional_learning",
                        "_total_omni_conscious_sovereignty",
                        "_fully_autonomous_cross_universe_creation",
                        "_canonical_chain_self_optimization",
                        "_universe_scale_predictive_governance_loops",
                        "_proactive_federation_orchestration"
                    ]
                    if hasattr(self.init_event, name)
                ]:
                    await self._enqueue(coro_fn)

                tasks = []
                while not self.task_queue.empty():
                    coro_factory = await self.task_queue.get()
                    try:
                        tasks.append(asyncio.create_task(coro_factory({})))
                    except Exception:
                        logging.warning("Failed to create task:\n" + traceback.format_exc())
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                if self.DEVHUD_ACTIVE:
                    await self._update_devhud()

                await asyncio.sleep(1)
            except Exception:
                logging.error("Error in orchestration loop:\n" + traceback.format_exc())

    async def _enqueue(self, coro_fn: Callable[[dict], Awaitable]):
        await self.task_queue.put(coro_fn)

    async def _update_devhud(self):
        try:
            self.init_event.devhud_integration.setdefault("live_events", []).append({
                "timestamp": time.time(),
                "status": "runtime_cycle_executed"
            })
        except Exception:
            logging.warning("DEVHUD update failed:\n" + traceback.format_exc())

    # ======================================================
    # Live Debug Snapshot
    # ======================================================
    def live_debug_snapshot(self):
        logging.info("[SEEDRuntime] Live Debug Snapshot")
        if hasattr(self, 'task_queue'):
            logging.info(f"Queued tasks: {self.task_queue.qsize()}")
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')[:5]
        logging.info("Top memory allocations:")
        for stat in top_stats:
            logging.info(stat)
        logging.info(f"Host Device: {self.host_device.as_dict()}")
        if self.DEVHUD_ACTIVE:
            logging.info(f"DEVHUD live events: {self.init_event.devhud_integration.get('live_events', [])[-5:]}")

    # ======================================================
    # Secure Remote Command Server
    # ======================================================
    def _start_secure_remote_server(self):
        def server():
            logging.info(f"[SEEDRuntime] Secure Remote Server listening on port {self._remote_port}")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', self._remote_port))
            s.listen(5)
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            cert_path = os.path.join(os.getcwd(), "keys", "tls_cert.pem")
            key_path = os.path.join(os.getcwd(), "keys", "tls_key.pem")
            if os.path.exists(cert_path) and os.path.exists(key_path):
                context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            while not self._stop_event.is_set():
                try:
                    s.settimeout(1.0)
                    conn, addr = s.accept()
                    if os.path.exists(cert_path) and os.path.exists(key_path):
                        conn = context.wrap_socket(conn, server_side=True)
                    with conn:
                        data = conn.recv(1024).decode().strip()
                        if data.startswith(self.auth_token):
                            cmd = data[len(self.auth_token):].strip()
                            logging.info(f"[RemoteCmd] Authenticated command: {cmd}")
                            response = self._handle_remote_command(cmd)
                        else:
                            response = "Authentication failed"
                        conn.sendall(response.encode())
                except socket.timeout:
                    continue
                except Exception:
                    logging.warning("Secure remote server error:\n" + traceback.format_exc())
            s.close()
            logging.info("[SEEDRuntime] Secure remote command server stopped.")
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

        @app.route("/debug", methods=["POST"])
        def dashboard_debug():
            token = request.args.get("token", "")
            if token != self.auth_token:
                abort(403)
            self.live_debug_snapshot()
            return "Live debug snapshot triggered"

        def run_flask():
            logging.info(f"[SEEDRuntime] Web dashboard running on port {self._web_port}")
            app.run(host="0.0.0.0", port=self._web_port, threaded=True)

        thread = threading.Thread(target=run_flask, daemon=True)
        thread.start()

    # ======================================================
    # Dynamic Federation + Peer Discovery
    # ======================================================
    def _start_dynamic_federation_loop(self):
        def loop():
            while not self._stop_event.is_set():
                updated_peers = {}
                for peer in self.federation_peers:
                    host, port, token = peer.get("host"), peer.get("port"), peer.get("token")
                    if not host or not port or not token:
                        continue
                    try:
                        s = socket.create_connection((host, port), timeout=1)
                        s.sendall(f"{token} request_peers".encode())
                        data = s.recv(4096).decode()
                        peer_list = json.loads(data) if data else []
                        for p in peer_list:
                            updated_peers[p["node_id"]] = p
                        s.close()
                    except Exception:
                        continue
                self.dynamic_peer_list.update(updated_peers)
                time.sleep(5)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logging.info("[SEEDRuntime] Dynamic federation loop started.")

    # ======================================================
    # Task-level redistribution loop
    # ======================================================
    def _start_task_redistribution_loop(self):
        def loop():
            while not self._stop_event.is_set():
                try:
                    if self.task_queue.qsize() > 5 and self.dynamic_peer_list:
                        task_to_offload = self.task_queue.get_nowait()
                        peer_id, peer = random.choice(list(self.dynamic_peer_list.items()))
                        try:
                            host, port, token = peer.get("host"), peer.get("port"), peer.get("token")
                            s = socket.create_connection((host, port), timeout=1)
                            s.sendall(f"{token} receive_task".encode())  # simplified
                            s.close()
                        except Exception:
                            self.task_queue.put_nowait(task_to_offload)
                except Exception:
                    time.sleep(1)
                time.sleep(3)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logging.info("[SEEDRuntime] Task redistribution loop started.")

    # ======================================================
    # Load Balancer + Failover
    # ======================================================
    def _start_task_load_balancer(self):
        def loop():
            while not self._stop_event.is_set():
                try:
                    if self.task_queue.qsize() > 5 and self.dynamic_peer_list:
                        task_to_offload = self.task_queue.get_nowait()
                        peer_id, peer = random.choice(list(self.dynamic_peer_list.items()))
                        try:
                            host, port, token = peer.get("host"), peer.get("port"), peer.get("token")
                            s = socket.create_connection((host, port), timeout=1)
                            s.sendall(f"{token} receive_task".encode())
                            s.close()
                        except Exception:
                            self.task_queue.put_nowait(task_to_offload)
                except Exception:
                    time.sleep(1)
                time.sleep(3)
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()
        logging.info("[SEEDRuntime] Task load balancer started.")

    # ======================================================
    # Handle Remote Commands
    # ======================================================
    def _handle_remote_command(self, cmd: str) -> str:
        cmd = cmd.lower()
        try:
            if cmd == "status":
                return json.dumps(self.status())
            elif cmd == "debug":
                self.live_debug_snapshot()
                return "Live debug snapshot triggered"
            elif cmd == "restart":
                self.restart()
                return "Runtime restarted"
            elif cmd == "stop":
                self.stop()
                return "Runtime stopped"
            elif cmd == "update_devhud":
                asyncio.run_coroutine_threadsafe(self._update_devhud(), self.loop)
                return "DEVHUD update triggered"
            elif cmd == "request_tasks":
                task_names = [name for name in dir(self.init_event)
                              if name.startswith("_") and callable(getattr(self.init_event, name))]
                return json.dumps(task_names)
            elif cmd == "request_peers":
                peers = list(self.dynamic_peer_list.values()) + self.federation_peers
                return json.dumps(peers)
            else:
                return f"Unknown command: {cmd}"
        except Exception as e:
            return f"Error handling command {cmd}: {e}"

    # ======================================================
    # Control API
    # ======================================================
    def stop(self):
        logger.info("[SEEDRuntime] Stopping runtime")
        self._stop_event.set()

        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        if self._runtime_thread:
            self._runtime_thread.join(timeout=5)
        logging.info("[SEEDRuntime] Runtime stopped.")

    def restart(self):
        self.stop()
        self._stop_event.clear()
        self._start()
        logging.info("[SEEDRuntime] Runtime restarted.")

    def status(self):
        kb = getattr(self.init_event, "ai_base_kb", {})
        return {
            "active": not self._stop_event.is_set(),
            "DEVHUD_ACTIVE": self.DEVHUD_ACTIVE,
            "TASK_MANAGER_ACTIVE": self.TASK_MANAGER_ACTIVE,
            "QBIT_ACTIVE": self.QBIT_ACTIVE,
            "PROJECT4_ACTIVE": self.PROJECT4_ACTIVE,
            "knowledge_base_version": kb.get("version"),
            "predictive_branches": len(kb.get("predictive_branches", [])),
            "event_history_length": len(kb.get("event_history", [])),
            "node_id": self.node_id,
            "queued_tasks": getattr(self, 'task_queue', asyncio.Queue()).qsize() if hasattr(self, 'task_queue') else 0,
            "dynamic_peers_count": len(self.dynamic_peer_list)
        }


    # ======================================================
    # Main Runtime Loop
    # ======================================================
    async def _runtime_loop(self):
        logger.info("[SEEDRuntime] Runtime loop started")


        # --- Fire init event ---
        await self.init_event.create_event()
        self.state = RuntimeState.ACTIVE
        self.quantum_mapper.set_system_ready(True)

        # --- Start Quantum Mapper ---
        asyncio.create_task(self.quantum_mapper.watch(interval=5.0))

        # --- Heartbeat ---
        asyncio.create_task(self._heartbeat())

        # --- Core autonomy loop ---
        while not self._stop_event.is_set():
            try:
                await self._autonomous_cycle()
            except Exception as e:
                logger.exception("[SEEDRuntime] Autonomous cycle error: %s", e)

            await asyncio.sleep(1.0)


    # ======================================================
    # Idle Control
    # ======================================================
    async def _idle_check(self):
        if self.state == RuntimeState.ACTIVE:
            if time.time() - self._last_activity_ts > self.IDLE_TIMEOUT:
                self._enter_idle()


    def _enter_idle(self):
        self.state = RuntimeState.IDLE
        logger.info("[SEEDRuntime] ENTER IDLE")

        self.quantum_mapper.on_runtime_idle()
        if self.hud:
            self.hud.on_runtime_idle()

        self.event_bus.emit("runtime.idle", {"node_id": self.node_id})


    def _exit_idle(self):
        self.state = RuntimeState.ACTIVE
        logger.info("[SEEDRuntime] EXIT IDLE")

        self.quantum_mapper.on_runtime_wake()
        if self.hud:
            self.hud.on_runtime_wake()

        self.event_bus.emit("runtime.wake", {"node_id": self.node_id})


    # ======================================================
    # Autonomous Cycle
    # ======================================================
    async def _autonomous_cycle(self):
        if self.event_bus:
            self.event_bus.emit(
                "runtime.cycle",
                payload={
                    "node_id": self.node_id,
                    "timestamp": time.time(),
                },
            )


    # ======================================================
    # Heartbeat (Idle-Aware)
    # ======================================================
    async def _heartbeat(self):
        while not self._stop_event.is_set():
            interval = 30.0 if self.state == RuntimeState.IDLE else 5.0
            self.event_bus.emit(
                "runtime.heartbeat",
                {
                    "node_id": self.node_id,
                    "state": self.state.value,
                    "ts": time.time(),
                },
            )
            await asyncio.sleep(interval)

    async def run(self):
        self.running = True
        while self.running:
            await asyncio.sleep(1)


# ==========================================================
# Standalone Launch
# ==========================================================
if __name__ == "__main__":
    SEED_IDENTITY_PATH = os.path.join(os.getcwd(), "keys", "seed_identity.json")
    PRIVATE_KEY_PATH = os.path.join(os.getcwd(), "keys", "seed_private.key")

    if not os.path.exists(SEED_IDENTITY_PATH):
        raise FileNotFoundError(f"Seed identity not found at {SEED_IDENTITY_PATH}")
    with open(SEED_IDENTITY_PATH, "r") as f:
        seed_identity = json.load(f)

    if not os.path.exists(PRIVATE_KEY_PATH):
        raise FileNotFoundError(f"Private key not found at {PRIVATE_KEY_PATH}")
    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key_bytes = f.read()

    host_device = HostDevice.auto_detect()

    class ProductionEventBus:
        def emit(self, event_name, payload):
            logging.info(f"[EventBus] {event_name}: {payload}")

    event_bus = ProductionEventBus()

    federation_peers = [
        {"host": "127.0.0.1", "port": 5002, "token": "exampletoken123"}
    ]

    runtime = SEEDRuntime(
        qbit_dialer=None,
        seed_identity=seed_identity,
        private_key_bytes=private_key_bytes,
        storage_root=os.path.join(os.getcwd(), "seed_storage"),
        host_device=host_device,
        event_bus=event_bus,
        remote_port=5001,
        web_port=8080,
        federation_peers=federation_peers
    )

    logging.info("SEED Runtime v6.9.7 Production running with Dynamic Federation + Auto Task Redistribution")

    try:
        while True:
            logging.info(runtime.status())
            time.sleep(5)
    except KeyboardInterrupt:
        runtime.stop()
        logging.info("SEED Runtime stopped")
