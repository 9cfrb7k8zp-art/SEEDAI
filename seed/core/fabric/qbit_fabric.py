
# =====================================================================
# FILE: qbit_fabric.py
# PATH: C:\SEED_ROOT\seed\core\fabric\qbit_fabric.py
#
# SEED CORE QBIT FABRIC NODE
#
# PURPOSE
# -------
# Network-facing Qbit Fabric node.
#
# Receives serialized Qbits from Fabric peers, validates and records
# their lineage, then hands the EXISTING Qbit to the authoritative
# SEED QbitQueueLoop.
#
# ARCHITECTURE
# ------------
#
#                    EXTERNAL FABRIC PEER
#                              |
#                              v
#                       QbitFabricNode
#                              |
#             +----------------+----------------+
#             |                |                |
#             v                v                v
#        TrackSystem       SRegistry       NeuralBridge
#        lineage          discovery       cognition
#             |                |                |
#             +----------------+----------------+
#                              |
#                              v
#                          EventBus
#                              |
#                              v
#                            Oracle
#                              |
#                              v
#                       QbitQueueLoop
#                              |
#                              v
#                         QbitDialer
#
# QbitFabricNode is NOT command authority.
#
# QbitDialer remains the command authority.
# QbitQueueLoop remains the authoritative Qbit transport/execution loop.
#
# This node does NOT:
#
# - create Qbits
# - create QbitQueueLoop
# - create QbitDialer
# - create EventBus
# - create NeuralBridge
# - create TrackSystem
# - create SRegistry
# - create Oracle
# - create a second SEED runtime loop
# - call QbitDialer.submit_command()
# =====================================================================

from __future__ import annotations

import inspect
import json
import logging
import socket
import threading
import time
from copy import deepcopy
from uuid import uuid4


log = logging.getLogger("QbitFabric")


# =====================================================================
# TRACK ID
# =====================================================================

def gen_track_id(prefix: str = "SEEDQbit_Fabric") -> str:

    return f"{prefix}-{uuid4().hex[:8]}"


# =====================================================================
# QBIT FABRIC NODE
# =====================================================================

class QbitFabricNode:

    name = "qbit_fabric"
    role = "qbit-fabric"
    version = "2.0.0"
    node_type = "fabric_node"

    capabilities = (
        "qbit_fabric",
        "qbit_receive",
        "qbit_transport",
        "qbit_decode",
        "qbit_validation",
        "track_lineage",
        "registry_observation",
        "registry_runtime_observation",
        "neural_bridge_integration",
        "event_bus_integration",
        "oracle_governance_link",
        "dialer_control_link",
        "peer_transport",
        "fabric_health",
    )

    # -----------------------------------------------------------------
    # Network defaults
    # -----------------------------------------------------------------

    DEFAULT_HOST = "0.0.0.0"
    DEFAULT_PORT = 5555

    RECEIVE_SIZE = 65536
    SOCKET_TIMEOUT = 1.0
    BACKLOG = 32

    def __init__(
        self,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        *,
        queue_loop=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        neural_bridge=None,
        event_bus=None,
        oracle=None,
        qbit_dialer=None,
        fabric_bridge=None,
    ):

        # -------------------------------------------------------------
        # CONFIGURATION
        # -------------------------------------------------------------

        self.host = host
        self.port = int(port)

        # -------------------------------------------------------------
        # AUTHORITATIVE EXISTING SYSTEM REFERENCES
        # -------------------------------------------------------------

        self.queue_loop = queue_loop
        self.track_system = track_system
        self.registry = registry
        self.registry_runtime = registry_runtime
        self.neural_bridge = neural_bridge
        self.event_bus = event_bus
        self.oracle = oracle
        self.qbit_dialer = qbit_dialer
        self.fabric_bridge = fabric_bridge

        # -------------------------------------------------------------
        # PEERS
        # -------------------------------------------------------------

        self.peers = []

        # -------------------------------------------------------------
        # LOCAL LIFECYCLE
        # -------------------------------------------------------------

        self.running = False
        self.ready = False

        self.node_id = (
            f"QBIT_FABRIC.{uuid4().hex[:12]}"
        )

        self._lock = threading.RLock()
        self._server_socket = None
        self._server_thread = None

        # -------------------------------------------------------------
        # TELEMETRY
        # -------------------------------------------------------------

        self.received_count = 0
        self.accepted_count = 0
        self.rejected_count = 0
        self.decode_errors = 0
        self.queue_errors = 0

        self._last_qbit_id = None
        self._last_track_id = None
        self._last_receive_time = None
        self._last_error = None

        self._history = []

    # =================================================================
    # BINDING
    # =================================================================

    def bind(self, name, obj):

        if not name:
            raise ValueError("binding name is required")

        with self._lock:

            if name in (
                "queue_loop",
                "track_system",
                "registry",
                "registry_runtime",
                "neural_bridge",
                "event_bus",
                "oracle",
                "qbit_dialer",
                "fabric_bridge",
            ):
                setattr(self, name, obj)

            else:
                setattr(self, name, obj)

            self.ready = self._calculate_ready()

        return True

    def attach_queue(self, queue_loop):

        self.queue_loop = queue_loop

        with self._lock:
            self.ready = self._calculate_ready()

        return self.queue_loop

    # =================================================================
    # READINESS
    # =================================================================

    def _calculate_ready(self):

        return self.queue_loop is not None

    # =================================================================
    # START
    # =================================================================

    def start(self):
        """
        Start the network-facing Fabric receiver.

        This creates only the node's local socket/thread.
        It does NOT create or start the SEED runtime.
        """

        with self._lock:

            if self.running:
                return self.status()

            self.running = True
            self.ready = self._calculate_ready()

        self._server_thread = threading.Thread(
            target=self._server,
            daemon=True,
            name="QbitFabricServer",
        )

        self._server_thread.start()

        log.info(
            "[%s] Started | host=%s | port=%s | ready=%s",
            self.name,
            self.host,
            self.port,
            self.ready,
        )

        return self.status()

    # =================================================================
    # STOP
    # =================================================================

    def stop(self):
        """
        Stop the Fabric receiver.

        Does not stop QbitQueueLoop, QbitDialer, or SEED runtime.
        """

        with self._lock:
            self.running = False

            sock = self._server_socket
            self._server_socket = None

        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

        log.info("[%s] Stopped", self.name)

        return self.status()

    # =================================================================
    # SERVER
    # =================================================================

    def _server(self):

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        try:
            sock.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1,
            )

            sock.bind(
                (self.host, self.port)
            )

            sock.listen(self.BACKLOG)

            sock.settimeout(
                self.SOCKET_TIMEOUT
            )

            with self._lock:
                self._server_socket = sock

            log.info(
                "[%s] QbitFabric listening on %s:%s",
                self.name,
                self.host,
                self.port,
            )

            while self.running:

                try:
                    conn, addr = sock.accept()

                except socket.timeout:
                    continue

                except OSError:

                    if not self.running:
                        break

                    log.debug(
                        "[%s] Fabric accept failed",
                        self.name,
                        exc_info=True,
                    )

                    continue

                thread = threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr),
                    daemon=True,
                    name="QbitFabricClient",
                )

                thread.start()

        except Exception as exc:

            with self._lock:
                self._last_error = repr(exc)
                self.running = False
                self.ready = False

            log.error(
                "[%s] Fabric server failed: %s",
                self.name,
                exc,
                exc_info=True,
            )

        finally:

            try:
                sock.close()
            except Exception:
                pass

            with self._lock:
                if self._server_socket is sock:
                    self._server_socket = None

    # =================================================================
    # CLIENT HANDLER
    # =================================================================

    def _handle_client(
        self,
        conn,
        addr=None,
    ):

        try:
            conn.settimeout(
                self.SOCKET_TIMEOUT
            )

            chunks = []
            remaining = self.RECEIVE_SIZE

            while remaining > 0:

                try:
                    chunk = conn.recv(
                        min(
                            16384,
                            remaining,
                        )
                    )

                except socket.timeout:
                    break

                if not chunk:
                    break

                chunks.append(chunk)

                remaining -= len(chunk)

                # -----------------------------------------------------
                # Current Fabric protocol is one JSON payload.
                #
                # Once valid JSON is decoded, stop reading.
                # -----------------------------------------------------

                try:
                    data = b"".join(chunks)
                    json.loads(data.decode("utf-8"))
                    break
                except Exception:
                    continue

            data = b"".join(chunks)

            if not data:
                self._reject(
                    "empty_payload",
                    addr,
                )
                return

            try:
                qbit = json.loads(
                    data.decode("utf-8")
                )

            except Exception as exc:

                with self._lock:
                    self.decode_errors += 1
                    self.rejected_count += 1
                    self._last_error = repr(exc)

                log.debug(
                    "[%s] Fabric decode error: %s",
                    self.name,
                    exc,
                )

                return

            self.on_qbit(
                qbit,
                peer=addr,
            )

        finally:

            try:
                conn.close()
            except Exception:
                pass

    # =================================================================
    # QBIT VALIDATION
    # =================================================================

    def _validate_qbit(self, qbit):

        if qbit is None:
            return False, "qbit_none"

        if not isinstance(qbit, dict):
            return False, (
                f"unsupported_type:"
                f"{type(qbit).__name__}"
            )

        return True, None

    # =================================================================
    # QBIT ID
    # =================================================================

    @staticmethod
    def _qbit_id(qbit):

        for key in (
            "qbit_id",
            "id",
            "task_id",
            "signal_id",
        ):

            value = qbit.get(key)

            if value:
                return str(value)

        return None

    # =================================================================
    # QBIT OBSERVATION
    # =================================================================

    def _build_observation(
        self,
        qbit,
        peer=None,
    ):

        track_id = (
            qbit.get("track_id")
            or gen_track_id()
        )

        qbit_id = self._qbit_id(qbit)

        return {
            "type": "qbit_fabric_observation",

            "observation_id": (
                f"QFABOBS.{uuid4().hex[:12]}"
            ),

            "track_id": track_id,
            "qbit_id": qbit_id,
            "timestamp": time.time(),

            "source": {
                "node_id": self.node_id,
                "node_type": self.node_type,
                "fabric": self.name,
            },

            "peer": {
                "host": (
                    peer[0]
                    if peer
                    else None
                ),
                "port": (
                    peer[1]
                    if peer
                    else None
                ),
            },

            "authority": {
                "command_authority": "QbitDialer",
                "transport_authority": "QbitQueueLoop",
                "execution_allowed": False,
                "command_submitted": False,
                "executed": False,
            },

            "bindings": {
                "queue_loop": (
                    self.queue_loop is not None
                ),
                "track_system": (
                    self.track_system is not None
                ),
                "registry": (
                    self.registry is not None
                ),
                "registry_runtime": (
                    self.registry_runtime is not None
                ),
                "neural_bridge": (
                    self.neural_bridge is not None
                ),
                "event_bus": (
                    self.event_bus is not None
                ),
                "oracle": (
                    self.oracle is not None
                ),
                "qbit_dialer": (
                    self.qbit_dialer is not None
                ),
                "fabric_bridge": (
                    self.fabric_bridge is not None
                ),
            },

            "qbit": deepcopy(qbit),
        }

    # =================================================================
    # RECEIVE QBIT
    # =================================================================

    def on_qbit(
        self,
        qbit,
        *,
        peer=None,
    ):

        valid, reason = self._validate_qbit(
            qbit
        )

        if not valid:

            self._reject(
                reason,
                peer,
            )

            return {
                "status": "rejected",
                "reason": reason,
            }

        observation = self._build_observation(
            qbit,
            peer=peer,
        )

        with self._lock:

            self.received_count += 1

            self._last_qbit_id = (
                observation["qbit_id"]
            )

            self._last_track_id = (
                observation["track_id"]
            )

            self._last_receive_time = (
                observation["timestamp"]
            )

            self._last_error = None

            self._history.append(
                deepcopy(observation)
            )

            if len(self._history) > 256:
                self._history.pop(0)

        # -------------------------------------------------------------
        # Publish passive evidence first.
        # -------------------------------------------------------------

        self._publish_track(
            observation
        )

        self._publish_registry(
            observation
        )

        self._publish_registry_runtime(
            observation
        )

        self._publish_neural_bridge(
            observation
        )

        self._publish_event_bus(
            observation
        )

        self._publish_oracle(
            observation
        )

        # -------------------------------------------------------------
        # Deliver the EXISTING Qbit to the authoritative queue.
        # -------------------------------------------------------------

        queued = self._queue_qbit(
            qbit
        )

        if not queued:

            with self._lock:
                self.queue_errors += 1
                self._last_error = (
                    "QbitQueueLoop unavailable "
                    "or incompatible"
                )

            log.warning(
                "[%s] Qbit received but authoritative "
                "QbitQueueLoop was not available",
                self.name,
            )

            return {
                "status": "observed_waiting",
                "track_id": (
                    observation["track_id"]
                ),
                "qbit_id": (
                    observation["qbit_id"]
                ),
                "queued": False,
            }

        with self._lock:
            self.accepted_count += 1

        return {
            "status": "accepted",
            "track_id": (
                observation["track_id"]
            ),
            "qbit_id": (
                observation["qbit_id"]
            ),
            "queued": True,
        }

    # =================================================================
    # QUEUE DELIVERY
    # =================================================================

    def _queue_qbit(self, qbit):
        """
        Deliver the existing Qbit to the authoritative QbitQueueLoop.

        No queue is created here.
        """

        queue_loop = self.queue_loop

        if queue_loop is None:
            return False

        # -------------------------------------------------------------
        # Prefer the explicit Qbit submission methods.
        # -------------------------------------------------------------

        for method_name in (
            "put",
            "enqueue",
            "submit_qbit",
            "queue_qbit",
            "submit",
        ):

            method = getattr(
                queue_loop,
                method_name,
                None,
            )

            if not callable(method):
                continue

            # ---------------------------------------------------------
            # First attempt: Qbit only.
            # ---------------------------------------------------------

            try:
                result = method(qbit)

                if inspect.isawaitable(result):
                    log.debug(
                        "[%s] QueueLoop returned awaitable; "
                        "authoritative runtime owns awaiting",
                        self.name,
                    )

                return True

            except TypeError:
                pass

            except Exception:
                log.debug(
                    "[%s] QueueLoop delivery failed via %s",
                    self.name,
                    method_name,
                    exc_info=True,
                )

                return False

            # ---------------------------------------------------------
            # Compatibility attempt for existing priority-aware
            # queue implementations.
            # ---------------------------------------------------------

            try:
                result = method(
                    qbit,
                    priority="NORMAL",
                )

                if inspect.isawaitable(result):
                    log.debug(
                        "[%s] QueueLoop returned awaitable; "
                        "authoritative runtime owns awaiting",
                        self.name,
                    )

                return True

            except TypeError:
                continue

            except Exception:
                log.debug(
                    "[%s] QueueLoop priority delivery failed "
                    "via %s",
                    self.name,
                    method_name,
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # REJECTION
    # =================================================================

    def _reject(
        self,
        reason,
        peer=None,
    ):

        with self._lock:
            self.rejected_count += 1
            self._last_error = str(reason)

        log.warning(
            "[%s] Qbit rejected | reason=%s | peer=%s",
            self.name,
            reason,
            peer,
        )

    # =================================================================
    # EVENTBUS
    # =================================================================

    def _publish_event_bus(
        self,
        observation,
    ):

        bus = self.event_bus

        if bus is None:
            return False

        for method_name in (
            "emit",
            "publish",
            "dispatch",
        ):

            method = getattr(
                bus,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(observation)
                return True

            except TypeError:

                try:
                    method(
                        observation.get("type"),
                        observation,
                    )

                    return True

                except Exception:
                    continue

            except Exception:
                log.debug(
                    "[%s] EventBus publication failed",
                    self.name,
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # TRACK SYSTEM
    # =================================================================

    def _publish_track(
        self,
        observation,
    ):

        tracker = self.track_system

        if tracker is None:
            return False

        for method_name in (
            "record",
            "observe",
            "track",
            "record_event",
            "ingest",
        ):

            method = getattr(
                tracker,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(observation)
                return True

            except TypeError:
                continue

            except Exception:
                log.debug(
                    "[%s] TrackSystem publication failed",
                    self.name,
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # REGISTRY
    # =================================================================

    def _publish_registry(
        self,
        observation,
    ):

        registry = self.registry

        if registry is None:
            return False

        for method_name in (
            "record_observation",
            "record",
            "observe",
            "update",
            "publish",
        ):

            method = getattr(
                registry,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(observation)
                return True

            except TypeError:
                continue

            except Exception:
                log.debug(
                    "[%s] Registry publication failed",
                    self.name,
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # REGISTRY RUNTIME
    # =================================================================

    def _publish_registry_runtime(
        self,
        observation,
    ):

        runtime = self.registry_runtime

        if runtime is None:
            return False

        for method_name in (
            "record_observation",
            "record",
            "observe",
            "update",
            "publish",
        ):

            method = getattr(
                runtime,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(observation)
                return True

            except TypeError:
                continue

            except Exception:
                log.debug(
                    "[%s] registry_runtime publication failed",
                    self.name,
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # NEURAL BRIDGE
    # =================================================================

    def _publish_neural_bridge(
        self,
        observation,
    ):

        bridge = self.neural_bridge

        if bridge is None:
            return False

        for method_name in (
            "observe",
            "ingest",
            "process_observation",
            "translate",
            "receive",
        ):

            method = getattr(
                bridge,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    observation
                )

                # -----------------------------------------------------
                # Do not call asyncio.run().
                #
                # The authoritative runtime must own awaiting.
                # -----------------------------------------------------

                if inspect.isawaitable(result):
                    log.debug(
                        "[%s] NeuralBridge returned awaitable; "
                        "authoritative runtime owns awaiting",
                        self.name,
                    )

                return True

            except TypeError:
                continue

            except Exception:
                log.debug(
                    "[%s] NeuralBridge publication failed",
                    self.name,
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # ORACLE
    # =================================================================

    def _publish_oracle(
        self,
        observation,
    ):

        oracle = self.oracle

        if oracle is None:
            return False

        for method_name in (
            "observe",
            "record_observation",
            "record",
            "ingest",
            "evaluate_observation",
        ):

            method = getattr(
                oracle,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(observation)
                return True

            except TypeError:
                continue

            except Exception:
                log.debug(
                    "[%s] Oracle publication failed",
                    self.name,
                    exc_info=True,
                )

                return False

        return False

    # =================================================================
    # DIALER OBSERVATION
    # =================================================================

    def build_dialer_observation(
        self,
        qbit,
    ):

        if not isinstance(qbit, dict):
            raise TypeError(
                "qbit must be a dict"
            )

        return {
            "type": "qbit_fabric_control_observation",

            "track_id": (
                qbit.get("track_id")
                or gen_track_id()
            ),

            "qbit_id": self._qbit_id(
                qbit
            ),

            "source_node": self.node_id,

            "authority": {
                "owner": "QbitDialer",
                "submit_command_required": True,
                "command_submitted": False,
                "executed": False,
            },

            "qbit": deepcopy(qbit),
        }

    # =================================================================
    # PEERS
    # =================================================================

    def add_peer(
        self,
        host,
        port,
    ):

        peer = (
            str(host),
            int(port),
        )

        with self._lock:

            if peer not in self.peers:
                self.peers.append(peer)

        return peer

    def remove_peer(
        self,
        host,
        port,
    ):

        peer = (
            str(host),
            int(port),
        )

        with self._lock:

            if peer in self.peers:
                self.peers.remove(peer)

        return peer

    def list_peers(self):

        with self._lock:
            return list(self.peers)

    # =================================================================
    # SNAPSHOT
    # =================================================================

    def snapshot(self):

        with self._lock:

            return {
                "node_id": self.node_id,
                "name": self.name,
                "role": self.role,
                "version": self.version,

                "host": self.host,
                "port": self.port,

                "running": self.running,
                "ready": self.ready,

                "peers": list(
                    self.peers
                ),

                "bindings": {
                    "queue_loop": (
                        self.queue_loop is not None
                    ),
                    "track_system": (
                        self.track_system is not None
                    ),
                    "registry": (
                        self.registry is not None
                    ),
                    "registry_runtime": (
                        self.registry_runtime is not None
                    ),
                    "neural_bridge": (
                        self.neural_bridge is not None
                    ),
                    "event_bus": (
                        self.event_bus is not None
                    ),
                    "oracle": (
                        self.oracle is not None
                    ),
                    "qbit_dialer": (
                        self.qbit_dialer is not None
                    ),
                    "fabric_bridge": (
                        self.fabric_bridge is not None
                    ),
                },

                "telemetry": {
                    "received": self.received_count,
                    "accepted": self.accepted_count,
                    "rejected": self.rejected_count,
                    "decode_errors": (
                        self.decode_errors
                    ),
                    "queue_errors": (
                        self.queue_errors
                    ),
                    "last_qbit_id": (
                        self._last_qbit_id
                    ),
                    "last_track_id": (
                        self._last_track_id
                    ),
                    "last_receive_time": (
                        self._last_receive_time
                    ),
                    "last_error": (
                        self._last_error
                    ),
                },

                "authority": {
                    "command_authority": "QbitDialer",
                    "transport_authority": "QbitQueueLoop",
                    "execution_allowed": False,
                },
            }

    # =================================================================
    # HISTORY
    # =================================================================

    def history(self):

        with self._lock:
            return deepcopy(
                self._history
            )

    # =================================================================
    # HEALTH
    # =================================================================

    def health(self):

        snapshot = self.snapshot()

        if not snapshot["running"]:
            state = "STOPPED"

        elif self.queue_loop is None:
            state = "WAITING"

        elif self.queue_errors > 0:
            state = "DEGRADED"

        else:
            state = "HEALTHY"

        snapshot["health"] = state

        return snapshot

    def status(self):
        return self.health()

    # =================================================================
    # REPRESENTATION
    # =================================================================

    def __repr__(self):

        return (
            f"<QbitFabricNode "
            f"name={self.name!r} "
            f"node_id={self.node_id!r} "
            f"host={self.host!r} "
            f"port={self.port!r} "
            f"running={self.running} "
            f"ready={self.ready}>"
        )


# =====================================================================
# PACKAGE METADATA
# =====================================================================

TOOL_NAME = "qbit_fabric"
TOOL_ROLE = "qbit-fabric"
TOOL_VERSION = "2.0.0"

TOOL_CAPABILITIES = (
    "qbit_fabric",
    "qbit_receive",
    "qbit_transport",
    "qbit_decode",
    "qbit_validation",
    "track_lineage",
    "registry_observation",
    "registry_runtime_observation",
    "neural_bridge_integration",
    "event_bus_integration",
    "oracle_governance_link",
    "dialer_control_link",
    "peer_transport",
)

TOOL_DEPENDENCIES = (
    "QbitQueueLoop",
    "TrackSystem",
    "SRegistry",
    "registry_runtime",
    "NeuralBridge",
    "EventBus",
    "Oracle",
    "QbitDialer",
    "FabricBridge",
)
