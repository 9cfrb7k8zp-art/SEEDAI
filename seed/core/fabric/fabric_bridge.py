
# =====================================================================
# FILE: fabric_bridge.py
# PATH: C:\SEED_ROOT\seed\core\fabric\fabric_bridge.py
#
# SEED CORE FABRIC BRIDGE
#
# PURPOSE
# -------
# Bridge between the SEED Fabric subsystem and the existing SEED
# runtime/cognitive/control infrastructure.
#
# ARCHITECTURE
# ------------
# This bridge:
#
#   Fabric
#      |
#      v
#   FabricBridge
#      |
#      +--> QbitQueueLoop       transport
#      +--> TrackSystem        lineage/telemetry
#      +--> SRegistry          node/registry state
#      +--> registry_runtime   lifecycle/dependency state
#      +--> NeuralBridge       cognition translation
#      +--> EventBus           event transport
#      +--> Oracle             governance/observation
#      +--> QbitDialer         command authority
#
# IMPORTANT:
#
# - Existing system objects are injected.
# - Nothing authoritative is instantiated here.
# - No second Qbit queue is created.
# - No second runtime loop is created.
# - No EventBus is created.
# - No NeuralBridge is created.
# - No QbitDialer is created.
# - This bridge never bypasses QbitDialer.submit_command().
# - Fabric observations/recommendations remain non-authoritative.
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


log = logging.getLogger("FabricBridge")


# =====================================================================
# SHARED TRACK ID
# =====================================================================

def gen_track_id(prefix: str = "SEEDFabric_Bridge") -> str:

    return f"{prefix}-{uuid4().hex[:8]}"


# =====================================================================
# FABRIC BRIDGE
# =====================================================================

class FabricBridge:

    name = "fabric_bridge"
    role = "fabric-bridge"
    version = "2.0.0"
    node_type = "fabric_bridge"

    capabilities = (
        "fabric_transport",
        "qbit_transport",
        "qbit_serialization",
        "track_lineage",
        "registry_observation",
        "registry_runtime_observation",
        "neural_bridge_integration",
        "event_bus_integration",
        "oracle_governance_link",
        "dialer_control_link",
        "fabric_health",
        "fabric_telemetry",
    )

    def __init__(
        self,
        queue_loop=None,
        fabric_node=None,
        *,
        track_system=None,
        registry=None,
        registry_runtime=None,
        neural_bridge=None,
        event_bus=None,
        oracle=None,
        qbit_dialer=None,
    ):
        # -------------------------------------------------------------
        # AUTHORITATIVE EXISTING OBJECTS ONLY
        # -------------------------------------------------------------

        self.queue_loop = queue_loop
        self.fabric = fabric_node

        self.track_system = track_system
        self.registry = registry
        self.registry_runtime = registry_runtime
        self.neural_bridge = neural_bridge
        self.event_bus = event_bus
        self.oracle = oracle
        self.qbit_dialer = qbit_dialer

        # -------------------------------------------------------------
        # LOCAL STATE
        # -------------------------------------------------------------

        self.node_id = (
            f"FABRIC_BRIDGE.{uuid4().hex[:12]}"
        )

        self._lock = threading.RLock()

        self._running = False
        self._ready = False

        self._sent_count = 0
        self._failed_count = 0
        self._observed_count = 0

        self._last_track_id = None
        self._last_qbit_id = None
        self._last_error = None
        self._last_send_time = None

        self._history = []

    # =================================================================
    # LIFECYCLE
    # =================================================================

    def start(self):

        with self._lock:
            if self._running:
                return self.status()

            self._running = True
            self._ready = self._dependencies_available()

        log.info(
            "[%s] Started | ready=%s",
            self.name,
            self._ready,
        )

        return self.status()

    def stop(self):

        with self._lock:
            self._running = False
            self._ready = False

        log.info("[%s] Stopped", self.name)

        return self.status()

    # =================================================================
    # DEPENDENCY BINDING
    # =================================================================

    def bind(self, name, obj):

        if not name:
            raise ValueError("binding name is required")

        with self._lock:
            setattr(self, name, obj)

            if name == "queue_loop":
                self.queue_loop = obj
            elif name == "fabric":
                self.fabric = obj
            elif name == "track_system":
                self.track_system = obj
            elif name in ("registry", "sregistry"):
                self.registry = obj
            elif name == "registry_runtime":
                self.registry_runtime = obj
            elif name == "neural_bridge":
                self.neural_bridge = obj
            elif name == "event_bus":
                self.event_bus = obj
            elif name == "oracle":
                self.oracle = obj
            elif name == "qbit_dialer":
                self.qbit_dialer = obj

            self._ready = self._dependencies_available()

        return True

    def _dependencies_available(self):

        return bool(
            self.queue_loop is not None
            or self.fabric is not None
        )

    # =================================================================
    # QBIT NORMALIZATION
    # =================================================================

    @staticmethod
    def _qbit_to_payload(qbit):

        if qbit is None:
            raise ValueError("qbit cannot be None")

        if isinstance(qbit, dict):
            payload = deepcopy(qbit)

        elif hasattr(qbit, "to_dict"):
            payload = qbit.to_dict()

        elif hasattr(qbit, "model_dump"):
            payload = qbit.model_dump()

        elif hasattr(qbit, "__dict__"):
            payload = deepcopy(vars(qbit))

        else:
            raise TypeError(
                f"Unsupported qbit type: {type(qbit).__name__}"
            )

        if not isinstance(payload, dict):
            payload = {"value": payload}

        return FabricBridge._json_safe(payload)

    @staticmethod
    def _json_safe(value):

        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, dict):
            return {
                str(key): FabricBridge._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [
                FabricBridge._json_safe(item)
                for item in value
            ]

        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass

        try:
            json.dumps(value)
            return value
        except Exception:
            return repr(value)

    # =================================================================
    # QBIT ID / TRACK ID
    # =================================================================

    @staticmethod
    def _get_qbit_id(payload):
        for key in (
            "qbit_id",
            "id",
            "task_id",
            "signal_id",
        ):
            value = payload.get(key)

            if value:
                return str(value)

        return None

    # =================================================================
    # OBSERVATION RECORD
    # =================================================================

    def _build_observation(
        self,
        payload,
        host=None,
        port=None,
    ):

        track_id = (
            payload.get("track_id")
            or gen_track_id()
        )

        qbit_id = self._get_qbit_id(payload)

        observation = {
            "type": "fabric_qbit_observation",
            "observation_id": (
                f"FABOBS.{uuid4().hex[:12]}"
            ),
            "track_id": track_id,
            "qbit_id": qbit_id,
            "timestamp": time.time(),

            "source": {
                "node_id": self.node_id,
                "node_type": self.node_type,
                "fabric": self.name,
            },

            "transport": {
                "host": host,
                "port": port,
                "queue_loop_bound": (
                    self.queue_loop is not None
                ),
            },

            "bindings": {
                "fabric": self.fabric is not None,
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
                "oracle": self.oracle is not None,
                "qbit_dialer": (
                    self.qbit_dialer is not None
                ),
            },

            "authority": {
                "command_authority": "QbitDialer",
                "execution_allowed": False,
                "command_submitted": False,
            },

            "qbit": payload,
        }

        return observation

    # =================================================================
    # SYSTEM OBSERVATION / INTEGRATION
    # =================================================================

    def observe_qbit(
        self,
        qbit,
        *,
        host=None,
        port=None,
    ):

        payload = self._qbit_to_payload(qbit)

        observation = self._build_observation(
            payload,
            host=host,
            port=port,
        )

        with self._lock:
            self._observed_count += 1
            self._last_track_id = observation["track_id"]
            self._last_qbit_id = observation["qbit_id"]

            self._history.append(
                deepcopy(observation)
            )

            if len(self._history) > 256:
                self._history.pop(0)

        self._publish_track(observation)
        self._publish_registry(observation)
        self._publish_registry_runtime(observation)
        self._publish_neural_bridge(observation)
        self._publish_event_bus(observation)
        self._publish_oracle(observation)

        return observation

    # =================================================================
    # EVENTBUS
    # =================================================================

    def _publish_event_bus(self, observation):

        bus = self.event_bus

        if bus is None:
            return False

        for method_name in (
            "emit",
            "publish",
            "dispatch",
        ):
            method = getattr(bus, method_name, None)

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

    def _publish_track(self, observation):

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
            method = getattr(tracker, method_name, None)

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

    def _publish_registry(self, observation):

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
            method = getattr(registry, method_name, None)

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

    def _publish_registry_runtime(self, observation):

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
            method = getattr(runtime, method_name, None)

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

    def _publish_neural_bridge(self, observation):


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
            method = getattr(bridge, method_name, None)

            if not callable(method):
                continue

            try:
                result = method(observation)

                # Do not execute an awaitable here.
                #
                # The authoritative runtime owns async execution.
                if inspect.isawaitable(result):
                    log.debug(
                        "[%s] NeuralBridge returned awaitable; "
                        "authoritative runtime must await it",
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

    def _publish_oracle(self, observation):

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
            method = getattr(oracle, method_name, None)

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
    # QBIT QUEUE LOOP
    # =================================================================

    def _queue_existing_qbit(self, qbit):

        queue_loop = self.queue_loop

        if queue_loop is None:
            return False

        for method_name in (
            "put",
            "enqueue",
            "submit",
            "submit_qbit",
            "queue_qbit",
        ):
            method = getattr(queue_loop, method_name, None)

            if not callable(method):
                continue

            try:
                result = method(qbit)

                if inspect.isawaitable(result):
                    log.debug(
                        "[%s] QbitQueueLoop returned awaitable; "
                        "authoritative runtime owns awaiting",
                        self.name,
                    )

                return True

            except TypeError:
                continue

            except Exception:
                log.debug(
                    "[%s] QbitQueueLoop delivery failed",
                    self.name,
                    exc_info=True,
                )
                return False

        return False

    # =================================================================
    # EXTERNAL TCP FABRIC TRANSPORT
    # =================================================================

    def send_qbit(
        self,
        qbit,
        host,
        port,
        *,
        timeout=5.0,
        observe=True,
        queue_existing=True,
    ):

        payload = self._qbit_to_payload(qbit)

        if observe:
            observation = self.observe_qbit(
                payload,
                host=host,
                port=port,
            )
        else:
            observation = None

        if queue_existing:
            try:
                self._queue_existing_qbit(qbit)
            except Exception:
                log.debug(
                    "[%s] Existing queue delivery failed",
                    self.name,
                    exc_info=True,
                )

        try:
            wire_data = json.dumps(
                payload,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")

            with socket.create_connection(
                (host, port),
                timeout=timeout,
            ) as sock:
                sock.sendall(wire_data)

            with self._lock:
                self._sent_count += 1
                self._last_send_time = time.time()
                self._last_error = None

            log.debug(
                "[%s] Qbit sent | host=%s | port=%s | qbit_id=%s | track_id=%s",
                self.name,
                host,
                port,
                self._last_qbit_id,
                self._last_track_id,
            )

            return {
                "status": "sent",
                "track_id": (
                    observation.get("track_id")
                    if observation
                    else payload.get("track_id")
                ),
                "qbit_id": self._get_qbit_id(payload),
                "host": host,
                "port": port,
                "bytes": len(wire_data),
                "queued": bool(
                    queue_existing
                    and self.queue_loop is not None
                ),
            }

        except Exception as exc:
            with self._lock:
                self._failed_count += 1
                self._last_error = repr(exc)

            log.debug(
                "[%s] Fabric send failed: %s",
                self.name,
                exc,
                exc_info=True,
            )

            return {
                "status": "failed",
                "track_id": (
                    observation.get("track_id")
                    if observation
                    else payload.get("track_id")
                ),
                "qbit_id": self._get_qbit_id(payload),
                "host": host,
                "port": port,
                "error": repr(exc),
            }

    # =================================================================
    # DIALER CONTROL LINK
    # =================================================================

    def build_dialer_observation(self, qbit):

        payload = self._qbit_to_payload(qbit)

        return {
            "type": "fabric_control_observation",
            "track_id": (
                payload.get("track_id")
                or gen_track_id()
            ),
            "qbit_id": self._get_qbit_id(payload),
            "source_node": self.node_id,

            "fabric": {
                "name": self.name,
                "role": self.role,
            },

            "authority": {
                "owner": "QbitDialer",
                "submit_command_required": True,
                "command_submitted": False,
                "executed": False,
            },

            "qbit": payload,
        }

    # =================================================================
    # HEALTH / STATUS
    # =================================================================

    def health(self):
        with self._lock:
            if not self._running:
                state = "STOPPED"
            elif self._failed_count > self._sent_count:
                state = "DEGRADED"
            elif self._ready:
                state = "HEALTHY"
            else:
                state = "WAITING"

            return {
                "node_id": self.node_id,
                "name": self.name,
                "state": state,
                "running": self._running,
                "ready": self._ready,

                "bindings": {
                    "queue_loop": (
                        self.queue_loop is not None
                    ),
                    "fabric": self.fabric is not None,
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
                    "oracle": self.oracle is not None,
                    "qbit_dialer": (
                        self.qbit_dialer is not None
                    ),
                },

                "telemetry": {
                    "observed": self._observed_count,
                    "sent": self._sent_count,
                    "failed": self._failed_count,
                    "last_track_id": (
                        self._last_track_id
                    ),
                    "last_qbit_id": (
                        self._last_qbit_id
                    ),
                    "last_send_time": (
                        self._last_send_time
                    ),
                },

                "authority": {
                    "command_authority": "QbitDialer",
                    "execution_allowed": False,
                },
            }

    def status(self):
        return self.health()

    # =================================================================
    # HISTORY
    # =================================================================

    def history(self):
        with self._lock:
            return deepcopy(self._history)

    # =================================================================
    # REPRESENTATION
    # =================================================================

    def __repr__(self):
        return (
            f"<FabricBridge "
            f"name={self.name!r} "
            f"node_id={self.node_id!r} "
            f"running={self._running} "
            f"ready={self._ready}>"
        )


# =====================================================================
# PACKAGE METADATA
# =====================================================================

TOOL_NAME = "fabric_bridge"
TOOL_ROLE = "fabric-bridge"
TOOL_VERSION = "2.0.0"

TOOL_CAPABILITIES = (
    "fabric_transport",
    "qbit_transport",
    "track_lineage",
    "registry_observation",
    "registry_runtime_observation",
    "neural_bridge_integration",
    "event_bus_integration",
    "oracle_governance_link",
    "dialer_control_link",
)

TOOL_DEPENDENCIES = (
    "QbitQueueLoop",
    "FabricNode",
    "TrackSystem",
    "SRegistry",
    "registry_runtime",
    "NeuralBridge",
    "EventBus",
    "Oracle",
    "QbitDialer",
)
