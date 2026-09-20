# ==========================================================
# FILE: neural_bridge.py
# PATH: SEED_ROOT/seed/core/cognition/neural_bridge.py
#
# SYSTEM: SEED AI OS
# COMPONENT: Cognition NeuralBridge
# VERSION: 4.0.0
# BUILD: PASSIVE / LIFECYCLE-AWARE / QBIT-COMPATIBLE
#
# ROLE:
#   COGNITION TRANSLATION + REPRESENTATION BRIDGE
#
# IMPORTANT:
#   This is NOT the SRegistry/registry bridge.
#
#   This bridge operates in the cognition path and connects
#   existing authoritative SEED systems to cognitive
#   representation/encoding.
#
# AUTHORITY:
#   NeuralBridge is PASSIVE.
#
#   It does NOT:
#       - own system lifecycle
#       - create QbitDialer
#       - create QbitQueueLoop
#       - create EventBus
#       - create TrackSystem
#       - create ComputeBrain
#       - create TransformerBrain
#       - create FATHUDAdapter
#       - create registry_runtime
#       - create threads
#       - create timers
#       - create asyncio loops
#       - create private execution queues
#       - execute commands
#       - call submit_command()
#       - subscribe itself to EventBus
#
#   Existing authoritative objects are injected/bound.
#
# COGNITIVE PATH:
#
#   Qbit
#      |
#      v
#   normalize_qbit()
#      |
#      +--> identity / lineage / generation
#      |
#      v
#   NeuralBridge
#      |
#      +--> vector representation
#      |
#      +--> encoder
#      |
#      +--> ComputeBrain
#      |
#      +--> TransformerBrain
#      |
#      v
#   cognitive packet
#      |
#      v
#   QbitDialer
#      |
#      v
#   submit_command()
#
# ==========================================================

from __future__ import annotations

import logging
from collections.abc import Mapping
from numbers import Number
from uuid import uuid4


log = logging.getLogger("NeuralBridge")


# ==========================================================
# LIFECYCLE
# ==========================================================

LIFECYCLE_DISCOVER = "DISCOVER"
LIFECYCLE_REGISTER = "REGISTER"
LIFECYCLE_LOAD = "LOAD"
LIFECYCLE_VALIDATE = "VALIDATE"
LIFECYCLE_WAIT = "WAIT"
LIFECYCLE_AVAILABLE = "AVAILABLE"
LIFECYCLE_DELIVER = "DELIVER"
LIFECYCLE_BOUND = "BOUND"
LIFECYCLE_READY = "READY"
LIFECYCLE_RUNNING = "RUNNING"
LIFECYCLE_FAILED = "FAILED"


# ==========================================================
# DEPENDENCY NAMES
# ==========================================================

DEPENDENCY_NAMES = (
    "SRegistry",
    "registry_runtime",
    "QbitQueueLoop",
    "EventBus",
    "TrackSystem",
    "ComputeBrain",
    "TransformerBrain",
    "QbitDialer",
    "FATHUDAdapter",
)


# ==========================================================
# TRACK ID
# ==========================================================

def gen_track_id(prefix="Dialer_NeuralBridge"):
    return f"{prefix}-{uuid4().hex[:8]}"


# ==========================================================
# NEURAL BRIDGE
# ==========================================================

class NeuralBridge:

    VERSION = "4.0.0"
    COMPONENT = "NeuralBridge"
    ROLE = "COGNITION_TRANSLATION"

    # ------------------------------------------------------
    # CONSTRUCTION
    # ------------------------------------------------------

    def __init__(
        self,
        encoder=None,
        kernel_bus=None,
        registry=None,
        registry_runtime=None,
        qbit_queue_loop=None,
        event_bus=None,
        track_system=None,
        compute_brain=None,
        transformer_brain=None,
        qbit_dialer=None,
        fathud=None,
        fat_layer=None,
    ):
        self.encoder = encoder
        self.kernel_bus = kernel_bus

        self.registry = registry
        self.registry_runtime = registry_runtime

        self.qbit_queue_loop = qbit_queue_loop
        self.event_bus = event_bus
        self.track_system = track_system

        self.compute_brain = compute_brain
        self.transformer_brain = transformer_brain
        self.qbit_dialer = qbit_dialer

        self.fathud = fathud
        self.fat_layer = fat_layer

        # --------------------------------------------------
        # Passive state
        # --------------------------------------------------

        self.initialized = True
        self.enabled = True

        self.lifecycle = LIFECYCLE_DISCOVER

        # --------------------------------------------------
        # Telemetry
        # --------------------------------------------------

        self.process_count = 0
        self.success_count = 0
        self.failure_count = 0

        self.vector_count = 0
        self.encode_count = 0
        self.kernel_write_count = 0

        self.last_error = None
        self.last_track_id = None
        self.last_qbit_id = None
        self.last_generation = None

        # --------------------------------------------------
        # Dependency state
        # --------------------------------------------------

        self.dependencies = {
            name: {
                "required": False,
                "available": False,
                "bound": False,
                "same_instance": None,
                "state": LIFECYCLE_DISCOVER,
            }
            for name in DEPENDENCY_NAMES
        }

        self._refresh_dependency_state()

    # ======================================================
    # BASIC STATE
    # ======================================================

    def enable(self):
        self.enabled = True

        if self.lifecycle == LIFECYCLE_FAILED:
            self.lifecycle = LIFECYCLE_AVAILABLE

        return True

    def disable(self):
        self.enabled = False
        return True

    # ======================================================
    # LIFECYCLE
    # ======================================================

    def set_lifecycle(self, state):
        if state not in {
            LIFECYCLE_DISCOVER,
            LIFECYCLE_REGISTER,
            LIFECYCLE_LOAD,
            LIFECYCLE_VALIDATE,
            LIFECYCLE_WAIT,
            LIFECYCLE_AVAILABLE,
            LIFECYCLE_DELIVER,
            LIFECYCLE_BOUND,
            LIFECYCLE_READY,
            LIFECYCLE_RUNNING,
            LIFECYCLE_FAILED,
        }:
            raise ValueError(
                f"[NeuralBridge] Invalid lifecycle state: {state!r}"
            )

        self.lifecycle = state
        return self.lifecycle

    def _refresh_dependency_state(self):
        """
        Refresh dependency availability without creating,
        starting, or subscribing to anything.
        """

        bindings = {
            "SRegistry": self.registry,
            "registry_runtime": self.registry_runtime,
            "QbitQueueLoop": self.qbit_queue_loop,
            "EventBus": self.event_bus,
            "TrackSystem": self.track_system,
            "ComputeBrain": self.compute_brain,
            "TransformerBrain": self.transformer_brain,
            "QbitDialer": self.qbit_dialer,
            "FATHUDAdapter": self.fathud,
        }

        for name, obj in bindings.items():

            state = self.dependencies[name]

            state["available"] = obj is not None
            state["bound"] = obj is not None
            state["same_instance"] = (
                True if obj is not None else None
            )

            if obj is not None:
                state["state"] = LIFECYCLE_BOUND
            else:
                state["state"] = LIFECYCLE_WAIT

        if self.lifecycle not in {
            LIFECYCLE_RUNNING,
            LIFECYCLE_FAILED,
        }:
            if all(
                state["available"]
                for name, state in self.dependencies.items()
                if state["required"]
            ):
                self.lifecycle = LIFECYCLE_READY
            elif any(
                state["available"]
                for state in self.dependencies.values()
            ):
                self.lifecycle = LIFECYCLE_AVAILABLE

        return True

    def declare_dependency(self, name, required=True):

        if name not in self.dependencies:
            self.dependencies[name] = {
                "required": False,
                "available": False,
                "bound": False,
                "same_instance": None,
                "state": LIFECYCLE_DISCOVER,
            }

        self.dependencies[name]["required"] = bool(required)

        self._refresh_dependency_state()

        return True

    def dependency_status(self):
        self._refresh_dependency_state()

        return {
            name: dict(state)
            for name, state in self.dependencies.items()
        }

    # ======================================================
    # AUTHORITATIVE BINDING
    # ======================================================

    def bind_systems(
        self,
        *,
        registry=None,
        registry_runtime=None,
        qbit_queue_loop=None,
        event_bus=None,
        track_system=None,
        compute_brain=None,
        transformer_brain=None,
        qbit_dialer=None,
        fathud=None,
        fat_layer=None,
    ):
        """
        Bind existing authoritative objects.

        None means:
            preserve the currently bound object.

        No component is constructed here.
        """

        self.set_lifecycle(LIFECYCLE_DELIVER)

        replacements = {
            "registry": registry,
            "registry_runtime": registry_runtime,
            "qbit_queue_loop": qbit_queue_loop,
            "event_bus": event_bus,
            "track_system": track_system,
            "compute_brain": compute_brain,
            "transformer_brain": transformer_brain,
            "qbit_dialer": qbit_dialer,
            "fathud": fathud,
            "fat_layer": fat_layer,
        }

        for attribute, value in replacements.items():
            if value is not None:
                setattr(self, attribute, value)

        self._refresh_dependency_state()

        self.set_lifecycle(LIFECYCLE_BOUND)

        return self.verify_bindings()

    def verify_bindings(self):
        """
        Verify that bound references are usable.

        This method does not instantiate or start anything.
        """

        self._refresh_dependency_state()

        checks = {}

        checks["registry"] = self.registry is not None
        checks["registry_runtime"] = (
            self.registry_runtime is not None
        )
        checks["qbit_queue_loop"] = (
            self.qbit_queue_loop is not None
        )
        checks["event_bus"] = self.event_bus is not None
        checks["track_system"] = self.track_system is not None
        checks["compute_brain"] = self.compute_brain is not None
        checks["transformer_brain"] = (
            self.transformer_brain is not None
        )
        checks["qbit_dialer"] = self.qbit_dialer is not None
        checks["fathud"] = self.fathud is not None

        # --------------------------------------------------
        # EventBus capability
        # --------------------------------------------------

        if self.event_bus is not None:
            checks["event_bus_usable"] = (
                callable(
                    getattr(
                        self.event_bus,
                        "emit",
                        None,
                    )
                )
                or callable(
                    getattr(
                        self.event_bus,
                        "_emit",
                        None,
                    )
                )
            )
        else:
            checks["event_bus_usable"] = False

        # --------------------------------------------------
        # QueueLoop capability
        # --------------------------------------------------

        if self.qbit_queue_loop is not None:
            checks["qbit_queue_loop_usable"] = any(
                callable(
                    getattr(
                        self.qbit_queue_loop,
                        name,
                        None,
                    )
                )
                for name in (
                    "put",
                    "enqueue",
                    "submit",
                    "submit_qbit",
                )
            )
        else:
            checks["qbit_queue_loop_usable"] = False

        # --------------------------------------------------
        # QbitDialer capability
        # --------------------------------------------------

        if self.qbit_dialer is not None:
            checks["qbit_dialer_usable"] = callable(
                getattr(
                    self.qbit_dialer,
                    "submit_command",
                    None,
                )
            )
        else:
            checks["qbit_dialer_usable"] = False

        required_failures = []

        for name, state in self.dependencies.items():
            if state["required"] and not state["available"]:
                required_failures.append(name)

        if required_failures:
            self.lifecycle = LIFECYCLE_WAIT
        else:
            self.lifecycle = LIFECYCLE_READY

        return {
            "valid": not bool(required_failures),
            "lifecycle": self.lifecycle,
            "required_missing": required_failures,
            "checks": checks,
        }

    # ======================================================
    # STATUS
    # ======================================================

    def status(self):
        self._refresh_dependency_state()

        return {
            "component": self.COMPONENT,
            "role": self.ROLE,
            "version": self.VERSION,
            "initialized": self.initialized,
            "enabled": self.enabled,
            "lifecycle": self.lifecycle,

            "encoder_attached": self.encoder is not None,
            "kernel_bus_attached": (
                self.kernel_bus is not None
            ),

            "process_count": self.process_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,

            "vector_count": self.vector_count,
            "encode_count": self.encode_count,
            "kernel_write_count": (
                self.kernel_write_count
            ),

            "last_error": self.last_error,
            "last_qbit_id": self.last_qbit_id,
            "last_track_id": self.last_track_id,
            "last_generation": self.last_generation,

            "dependencies": self.dependency_status(),
        }

    def health(self):
        verification = self.verify_bindings()

        return {
            "component": self.COMPONENT,
            "version": self.VERSION,
            "healthy": (
                self.initialized
                and self.enabled
                and self.lifecycle
                in {
                    LIFECYCLE_AVAILABLE,
                    LIFECYCLE_BOUND,
                    LIFECYCLE_READY,
                    LIFECYCLE_RUNNING,
                }
                and verification["valid"]
            ),
            "lifecycle": self.lifecycle,
            "verification": verification,
        }

    # ======================================================
    # QBIT NORMALIZATION
    # ======================================================

    @staticmethod
    def _is_mapping(value):
        return isinstance(value, Mapping)

    @staticmethod
    def _is_callable_qbit(value):
        return (
            callable(value)
            and not isinstance(value, Mapping)
        )

    def _normalize_qbit(self, qbit):

        if qbit is None:
            return None

        if self._is_callable_qbit(qbit):
            raise TypeError(
                "[NeuralBridge] qbit is callable; "
                "expected Qbit/data object."
            )

        if self._is_mapping(qbit):
            normalized = dict(qbit)
        else:

            normalized = None

            for method_name in (
                "to_dict",
                "as_dict",
            ):
                converter = getattr(
                    qbit,
                    method_name,
                    None,
                )

                if callable(converter):
                    try:
                        converted = converter()

                        if isinstance(
                            converted,
                            Mapping,
                        ):
                            normalized = dict(
                                converted
                            )
                            break

                    except Exception as exc:
                        log.debug(
                            "[NeuralBridge] %s() failed: %s",
                            method_name,
                            exc,
                        )

            if normalized is None:

                payload = getattr(
                    qbit,
                    "payload",
                    None,
                )

                if isinstance(
                    payload,
                    Mapping,
                ):
                    normalized = dict(payload)

            if normalized is None:

                data = getattr(
                    qbit,
                    "data",
                    None,
                )

                if isinstance(
                    data,
                    Mapping,
                ):
                    normalized = dict(data)

            if normalized is None:

                try:
                    attributes = vars(qbit)

                    if isinstance(
                        attributes,
                        dict,
                    ):
                        normalized = dict(
                            attributes
                        )

                except TypeError:
                    pass

        if normalized is None:
            return None

        # --------------------------------------------------
        # Preserve source identity
        # --------------------------------------------------

        self._preserve_qbit_identity(
            qbit,
            normalized,
        )

        return normalized

    # ======================================================
    # IDENTITY / LINEAGE
    # ======================================================

    def _preserve_qbit_identity(
        self,
        source,
        normalized,
    ):
        """
        Preserve Qbit identity and lineage.

        Never replace an existing value.
        """

        # --------------------------------------------------
        # Qbit ID
        # --------------------------------------------------

        qbit_id = None

        for key in (
            "qbit_id",
            "id",
            "uuid",
        ):
            value = normalized.get(key)

            if value is not None:
                qbit_id = value
                break

        if qbit_id is None:
            for key in (
                "qbit_id",
                "id",
                "uuid",
            ):
                value = getattr(
                    source,
                    key,
                    None,
                )

                if value is not None:
                    qbit_id = value
                    break

        if qbit_id is not None:
            normalized.setdefault(
                "qbit_id",
                qbit_id,
            )

        # --------------------------------------------------
        # Track ID
        # --------------------------------------------------

        track_id = normalized.get(
            "track_id"
        )

        if track_id is None:
            track_id = getattr(
                source,
                "track_id",
                None,
            )

        if track_id is None:
            track_id = gen_track_id()

        normalized.setdefault(
            "track_id",
            track_id,
        )

        # --------------------------------------------------
        # Generation
        # --------------------------------------------------

        generation = normalized.get(
            "generation"
        )

        if generation is None:
            generation = getattr(
                source,
                "generation",
                None,
            )

        if generation is None:
            generation = 0

        normalized.setdefault(
            "generation",
            generation,
        )

        # --------------------------------------------------
        # Parent lineage
        # --------------------------------------------------

        parent_id = normalized.get(
            "parent_id"
        )

        if parent_id is None:
            parent_id = getattr(
                source,
                "parent_id",
                None,
            )

        if parent_id is not None:
            normalized.setdefault(
                "parent_id",
                parent_id,
            )

        # --------------------------------------------------
        # Source lineage
        # --------------------------------------------------

        normalized.setdefault(
            "lineage",
            normalized.get(
                "lineage",
                {},
            ),
        )

        lineage = normalized["lineage"]

        if not isinstance(
            lineage,
            Mapping,
        ):
            lineage = {}

        lineage = dict(lineage)

        lineage.setdefault(
            "track_id",
            track_id,
        )

        lineage.setdefault(
            "generation",
            generation,
        )

        if qbit_id is not None:
            lineage.setdefault(
                "qbit_id",
                qbit_id,
            )

        if parent_id is not None:
            lineage.setdefault(
                "parent_id",
                parent_id,
            )

        lineage.setdefault(
            "bridge",
            self.COMPONENT,
        )

        normalized["lineage"] = lineage

        self.last_qbit_id = qbit_id
        self.last_track_id = track_id
        self.last_generation = generation

        return normalized

    # ======================================================
    # QBIT ACCESS
    # ======================================================

    def get(self, key, default=None, qbit=None):
        """
        Compatibility accessor.

        If qbit is supplied, read from it.

        Otherwise read from the most recently represented
        Qbit metadata when available.
        """

        if qbit is not None:
            return self.get_qbit_value(
                qbit,
                key,
                default,
            )

        if hasattr(
            self,
            "_last_normalized_qbit",
        ):
            return self._last_normalized_qbit.get(
                key,
                default,
            )

        return default

    @staticmethod
    def get_qbit_value(
        qbit,
        key,
        default=None,
    ):

        if qbit is None:
            return default

        if isinstance(
            qbit,
            Mapping,
        ):
            return qbit.get(
                key,
                default,
            )

        return getattr(
            qbit,
            key,
            default,
        )

    # ======================================================
    # VECTOR
    # ======================================================

    def qbit_to_vector(self, qbit):

        if qbit is None:
            return []

        if self._is_callable_qbit(qbit):
            raise TypeError(
                f"[NeuralBridge] qbit is a function: {qbit!r}"
            )

        normalized = self._normalize_qbit(qbit)

        if normalized is None:
            log.warning(
                "[NeuralBridge] Unable to normalize Qbit "
                "of type %s",
                type(qbit).__name__,
            )
            return []

        self._last_normalized_qbit = normalized

        # --------------------------------------------------
        # Existing vector
        # --------------------------------------------------

        for key in (
            "vector",
            "embedding",
            "features",
        ):
            value = normalized.get(key)

            if isinstance(
                value,
                (list, tuple),
            ):
                vector = [
                    float(item)
                    for item in value
                    if isinstance(
                        item,
                        Number,
                    )
                ]

                if vector:
                    self.vector_count += 1
                    return vector

        # --------------------------------------------------
        # Explicit numeric state
        # --------------------------------------------------

        vector = []

        preferred_numeric_fields = (
            "amplitude",
            "phase",
            "probability",
            "confidence",
            "weight",
            "strength",
            "priority",
            "score",
            "energy",
            "value",
        )

        for key in preferred_numeric_fields:
            value = normalized.get(key)

            if isinstance(
                value,
                Number,
            ):
                vector.append(
                    float(value)
                )

        if vector:
            self.vector_count += 1
            return vector

        # --------------------------------------------------
        # Intent representation
        # --------------------------------------------------

        intent = normalized.get(
            "intent",
            "",
        )

        if intent is None:
            intent = ""

        if not isinstance(
            intent,
            str,
        ):
            intent = str(intent)

        intent = intent.strip()

        if intent:
            vector = [
                round(
                    ord(character) / 255.0,
                    6,
                )
                for character in intent[:64]
            ]

            self.vector_count += 1

            return vector

        # --------------------------------------------------
        # Generic numeric extraction
        # --------------------------------------------------

        ignored_keys = {
            "timestamp",
            "created_at",
            "updated_at",
            "generation",
        }

        for key, value in normalized.items():

            if key in ignored_keys:
                continue

            if isinstance(
                value,
                Number,
            ):
                vector.append(
                    float(value)
                )

        self.vector_count += 1

        return vector

    # ======================================================
    # ENCODER
    # ======================================================

    def _encode(self, qbit):

        if self.encoder is None:
            return qbit

        encode = getattr(
            self.encoder,
            "encode",
            None,
        )

        if callable(encode):
            self.encode_count += 1
            return encode(qbit)

        process = getattr(
            self.encoder,
            "process",
            None,
        )

        if callable(process):
            self.encode_count += 1
            return process(qbit)

        if callable(self.encoder):
            self.encode_count += 1
            return self.encoder(qbit)

        raise TypeError(
            "[NeuralBridge] Attached encoder has no "
            "supported encode/process interface."
        )

    # ======================================================
    # KERNEL BUS
    # ======================================================

    def _write_kernel_bus(self, packet):

        if self.kernel_bus is None:
            return False

        write = getattr(
            self.kernel_bus,
            "write",
            None,
        )

        if callable(write):
            write(packet)
            self.kernel_write_count += 1
            return True

        put = getattr(
            self.kernel_bus,
            "put",
            None,
        )

        if callable(put):
            put(packet)
            self.kernel_write_count += 1
            return True

        emit = getattr(
            self.kernel_bus,
            "emit",
            None,
        )

        if callable(emit):
            emit(packet)
            self.kernel_write_count += 1
            return True

        raise TypeError(
            "[NeuralBridge] Attached kernel_bus has no "
            "supported write/put/emit interface."
        )

    # ======================================================
    # COGNITIVE REPRESENTATION
    # ======================================================

    def build_neural_packet(self, qbit):

        if qbit is None:
            return None

        try:

            normalized = self._normalize_qbit(qbit)

            if normalized is None:
                return None

            self._last_normalized_qbit = normalized

            vector = self.qbit_to_vector(
                normalized
            )

            packet = {
                "component": self.COMPONENT,
                "version": self.VERSION,

                "intent": normalized.get(
                    "intent",
                    "",
                ),

                "vector": vector,

                "qbit": normalized,

                "qbit_id": normalized.get(
                    "qbit_id"
                ),

                "track_id": normalized.get(
                    "track_id"
                ),

                "generation": normalized.get(
                    "generation",
                    0,
                ),

                "parent_id": normalized.get(
                    "parent_id"
                ),

                "lineage": dict(
                    normalized.get(
                        "lineage",
                        {},
                    )
                ),
            }

            return packet

        except Exception as exc:

            self.failure_count += 1
            self.last_error = str(exc)

            log.exception(
                "[NeuralBridge] Packet construction failure: %s",
                exc,
            )

            return None

    # ======================================================
    # PRIMARY PROCESS
    # ======================================================

    def process(self, qbit):

        if not self.enabled:
            log.debug(
                "[NeuralBridge] Processing disabled."
            )
            return None

        if qbit is None:
            return None

        self.process_count += 1

        self.set_lifecycle(
            LIFECYCLE_RUNNING
        )

        try:

            normalized = self._normalize_qbit(
                qbit
            )

            if normalized is None:
                raise TypeError(
                    "[NeuralBridge] Unsupported Qbit type: "
                    f"{type(qbit).__name__}"
                )

            self._last_normalized_qbit = normalized

            # ------------------------------------------------
            # Build representation
            # ------------------------------------------------

            packet = self.build_neural_packet(
                normalized
            )

            if packet is None:
                raise RuntimeError(
                    "[NeuralBridge] Failed to build "
                    "neural packet."
                )

            # ------------------------------------------------
            # External encoder
            # ------------------------------------------------

            encoded_packet = self._encode(
                packet
            )

            if encoded_packet is None:
                log.debug(
                    "[NeuralBridge] Encoder returned None."
                )
                return None

            # ------------------------------------------------
            # Optional KernelBus forwarding
            #
            # This is transport only.
            # It is NOT command execution.
            # ------------------------------------------------

            if self.kernel_bus is not None:
                self._write_kernel_bus(
                    encoded_packet
                )

            self.success_count += 1

            return encoded_packet

        except Exception as exc:

            self.failure_count += 1
            self.last_error = str(exc)

            self.set_lifecycle(
                LIFECYCLE_FAILED
            )

            log.exception(
                "[NeuralBridge] Processing failure: %s",
                exc,
            )

            return None

        finally:

            if self.lifecycle == LIFECYCLE_RUNNING:
                self.set_lifecycle(
                    LIFECYCLE_READY
                )

    # ======================================================
    # QBIT COMPATIBILITY
    # ======================================================

    def process_qbit(self, qbit):
        return self.process(qbit)

    # ======================================================
    # VECTOR PROCESSING
    # ======================================================

    def process_vector(self, qbit):

        if not self.enabled:
            return []

        try:
            return self.qbit_to_vector(qbit)

        except Exception as exc:

            self.failure_count += 1
            self.last_error = str(exc)

            log.exception(
                "[NeuralBridge] Vector processing failure: %s",
                exc,
            )

            return []

    # ======================================================
    # EXPLICIT BUS SEND
    # ======================================================

    def send(self, packet):

        if packet is None:
            return False

        if not self.enabled:
            return False

        try:
            return self._write_kernel_bus(
                packet
            )

        except Exception as exc:

            self.failure_count += 1
            self.last_error = str(exc)

            log.exception(
                "[NeuralBridge] Send failure: %s",
                exc,
            )

            return False

    # ======================================================
    # RESET TELEMETRY
    # ======================================================

    def reset_counters(self):

        self.process_count = 0
        self.success_count = 0
        self.failure_count = 0

        self.vector_count = 0
        self.encode_count = 0
        self.kernel_write_count = 0

        self.last_error = None

        return True


# ==========================================================
# MODULE-LEVEL COMPATIBILITY HELPERS
# ==========================================================

def qbit_to_vector(qbit):

    bridge = NeuralBridge()

    return bridge.qbit_to_vector(qbit)


def process_qbit(
    qbit,
    encoder=None,
    kernel_bus=None,
):

    bridge = NeuralBridge(
        encoder=encoder,
        kernel_bus=kernel_bus,
    )

    return bridge.process_qbit(qbit)


# ==========================================================
# EXPORTS
# ==========================================================

__all__ = [
    "NeuralBridge",
    "gen_track_id",
    "qbit_to_vector",
    "process_qbit",
]