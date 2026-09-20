# ==========================================================
# FILE: quantum_math_engine.py
# LOCATION: C:\SEED_ROOT\seed\core\dialers\quantum_math_engine.py
# ROLE:
#   Dynamic quantum/state analysis layer.
#
# FLOW:
#
#   HeartbeatEmitter
#          |
#          v
#        Qbit
#          |
#          v
#   QbitQueueLoop
#          |
#          v
#   QuantumMathEngine
#          |
#          v
#      ComputeBrain
#          |
#          v
#     ThoughtPacket
#          |
#          v
#   TransformerBrain
#          |
#          v
#    CognitiveResult
#          |
#          v
#      QbitDialer
#
# IMPORTANT:
#
# QuantumMathEngine DOES NOT:
#   - execute commands
#   - submit commands
#   - become command authority
#   - create another Qbit
#   - create another QbitQueueLoop
#   - create another QbitDialer
#   - create another HeartbeatEmitter
#
# QbitDialer remains the sole command authority.
#
# QuantumMathEngine:
#   - consumes heartbeat/Qbit state
#   - observes the authoritative QbitQueueLoop
#   - calculates resonance/state probability
#   - tracks health
#   - tracks success/failure/pending/degraded states
#   - preserves lineage
#   - connects thoughts to results
#   - carries runtime connection state
#   - dynamically observes runtime components
#   - provides cognitive/quantum results downstream
#
# ==========================================================

import math
import time
import logging
from threading import RLock


logger = logging.getLogger("QuantumMathEngine")

def normalize_qbit_input(
    state_input: any,
) -> tuple[complex, complex]:

    if isinstance(
        state_input,
        (int, float, complex),
    ):
        state_input = (
            complex(state_input),
            0.0 + 0.0j,
        )

    elif isinstance(
        state_input,
        (list, tuple),
    ):
        state_input = tuple(
            complex(x)
            for x in state_input
        )

    elif isinstance(
        state_input,
        dict,
    ):
        if "alpha" in state_input:
            alpha = state_input.get(
                "alpha",
                0.0 + 0.0j,
            )

            beta = state_input.get(
                "beta",
                0.0 + 0.0j,
            )

            state_input = (
                complex(alpha),
                complex(beta),
            )

        elif "state" in state_input:
            return normalize_qbit_input(
                state_input["state"]
            )

        elif "qbit" in state_input:
            return normalize_qbit_input(
                state_input["qbit"]
            )

        else:
            raise ValueError(
                "Dictionary does not contain "
                "a recognizable Qbit state"
            )

    else:
        raise ValueError(
            "Cannot convert "
            f"{type(state_input)!r} "
            "to Qbit state"
        )

    if len(state_input) == 0:
        state_input = (
            1 / math.sqrt(2),
            1 / math.sqrt(2),
        )

    elif len(state_input) != 2:
        state_input = (
            state_input[0],
            (
                state_input[1]
                if len(state_input) > 1
                else 0.0 + 0.0j
            ),
        )

    alpha, beta = (
        complex(state_input[0]),
        complex(state_input[1]),
    )

    norm = math.sqrt(
        abs(alpha) ** 2 +
        abs(beta) ** 2
    ) or 1.0

    return (
        alpha / norm,
        beta / norm,
    )



# ==========================================================
# NORMALIZATION FALLBACK
# ==========================================================
#
# The authoritative normalize_qbit_input() should normally
# come from the SEED Qbit/math layer.
#
# This fallback prevents the engine from becoming unusable
# if the helper is not imported into this module.
#
# ==========================================================

try:
    normalize_qbit_input
except NameError:

    def normalize_qbit_input(state):

        if state is None:
            return (
                complex(1.0, 0.0),
                complex(0.0, 0.0),
            )

        if isinstance(state, dict):

            alpha = (
                state.get("alpha")
                or state.get("amplitude_alpha")
                or state.get("a")
            )

            beta = (
                state.get("beta")
                or state.get("amplitude_beta")
                or state.get("b")
            )

            if alpha is None and beta is None:

                # Support probability-style input.
                alpha = state.get(
                    "alpha_probability",
                    1.0,
                )

                beta = state.get(
                    "beta_probability",
                    0.0,
                )

                try:
                    alpha = math.sqrt(
                        max(
                            0.0,
                            float(alpha),
                        )
                    )

                    beta = math.sqrt(
                        max(
                            0.0,
                            float(beta),
                        )
                    )

                except Exception:

                    alpha = 1.0
                    beta = 0.0

            return (
                complex(alpha or 0.0),
                complex(beta or 0.0),
            )

        if isinstance(
            state,
            (list, tuple),
        ):

            if len(state) >= 2:

                return (
                    complex(state[0]),
                    complex(state[1]),
                )

            if len(state) == 1:

                return (
                    complex(state[0]),
                    complex(0.0),
                )

        try:

            return (
                complex(state),
                complex(0.0),
            )

        except Exception:

            return (
                complex(1.0, 0.0),
                complex(0.0, 0.0),
            )


# ==========================================================
# QUANTUM MATH ENGINE
# ==========================================================

class QuantumMathEngine:

    def __init__(
        self,
        qbit=None,
        qbit_queue_loop=None,
        qbit_dialer=None,
        heartbeat_emitter=None,
        emit=None,
        track_system=None,
        runtime_context=None,
        compute_brain=None,
        transformer_brain=None,
    ):

        self.lock = RLock()

        # --------------------------------------------------
        # AUTHORITATIVE RUNTIME REFERENCES
        # --------------------------------------------------

        self.qbit = qbit
        self.qbit_queue_loop = qbit_queue_loop
        self.qbit_dialer = qbit_dialer
        self.heartbeat_emitter = heartbeat_emitter

        self.track_system = track_system
        self.runtime_context = runtime_context

        self.compute_brain = compute_brain
        self.transformer_brain = transformer_brain

        self.emit = emit

        # --------------------------------------------------
        # Runtime state
        # --------------------------------------------------

        self.running = False

        self.last_heartbeat = None
        self.last_qbit_state = None
        self.last_thought = None
        self.last_result = None

        self.last_resonance = 1.0

        self.last_magnitude = 1.0

        self.last_probability = {
            "alpha_probability": 1.0,
            "beta_probability": 0.0,
        }

        self.last_runtime_signal = None

        # --------------------------------------------------
        # Health
        # --------------------------------------------------

        self.health = {
            "healthy": True,
            "state": "INITIALIZING",

            "success": 0,
            "failure": 0,
            "pending": 0,

            "last_success": None,
            "last_failure": None,
            "last_pending": None,

            "error": None,

            "heartbeat_success": 0,
            "heartbeat_failure": 0,

            "cognitive_success": 0,
            "cognitive_failure": 0,

            "result_success": 0,
            "result_failure": 0,
        }

        # --------------------------------------------------
        # Lineage
        # --------------------------------------------------

        self.current_qbit_id = None
        self.current_task_id = None
        self.current_track_id = None
        self.current_channel_id = None

        self.current_source = None
        self.current_sequence = None
        self.current_generation = None

        # --------------------------------------------------
        # Thought/result relationship
        # --------------------------------------------------

        self.thought_results = []

        self.max_history = 256

        # --------------------------------------------------
        # Runtime signal history
        # --------------------------------------------------

        self.signal_history = []

        self.max_signal_history = 256

    # ======================================================
    # RUNTIME BINDING
    # ======================================================

    def bind_runtime(
        self,
        qbit=None,
        qbit_queue_loop=None,
        qbit_dialer=None,
        heartbeat_emitter=None,
        track_system=None,
        emit=None,
        runtime_context=None,
        compute_brain=None,
        transformer_brain=None,
    ):

        with self.lock:

            if qbit is not None:
                self.qbit = qbit

            if qbit_queue_loop is not None:
                self.qbit_queue_loop = (
                    qbit_queue_loop
                )

            if qbit_dialer is not None:
                self.qbit_dialer = qbit_dialer

            if heartbeat_emitter is not None:
                self.heartbeat_emitter = (
                    heartbeat_emitter
                )

            if track_system is not None:
                self.track_system = track_system

            if emit is not None:
                self.emit = emit

            if runtime_context is not None:
                self.runtime_context = (
                    runtime_context
                )

            if compute_brain is not None:
                self.compute_brain = (
                    compute_brain
                )

            if transformer_brain is not None:
                self.transformer_brain = (
                    transformer_brain
                )

            self._sync_runtime_context()

            self.running = True

            self._set_health(
                state="BOUND",
                success=True,
            )

        return self.get_state()

    # ======================================================
    # DYNAMIC RUNTIME SYNCHRONIZATION
    # ======================================================

    def sync_runtime(
        self,
        runtime_context=None,
    ):

        try:

            if runtime_context is not None:
                self.runtime_context = (
                    runtime_context
                )

            self._sync_runtime_context()

            self._emit(
                "QUANTUM_RUNTIME_SYNCHRONIZED",
                {
                    "type": "QuantumRuntimeSync",
                    "connections": (
                        self._connection_state()
                    ),
                    "lineage": (
                        self._lineage_state()
                    ),
                },
            )

            return self.get_state()

        except Exception as exc:

            self._set_health(
                state="RUNTIME_SYNC_FAILURE",
                success=False,
                error=str(exc),
            )

            return self.get_state()

    # ------------------------------------------------------
    # RUNTIME CONTEXT OBSERVATION
    # ------------------------------------------------------

    def _sync_runtime_context(self):

        context = self.runtime_context

        if context is None:
            return False

        bindings = (
            "qbit",
            "qbit_queue_loop",
            "qbit_dialer",
            "heartbeat_emitter",
            "track_system",
            "compute_brain",
            "transformer_brain",
            "emit",
        )

        changed = False

        for name in bindings:

            try:

                value = getattr(
                    context,
                    name,
                    None,
                )

            except Exception:
                continue

            if value is None:
                continue

            current = getattr(
                self,
                name,
                None,
            )

            # RuntimeContext is authoritative.
            # Adopt only if this engine has no object yet.
            if current is None:

                setattr(
                    self,
                    name,
                    value,
                )

                changed = True

        return changed

    # ======================================================
    # DYNAMIC RUNTIME SIGNAL
    # ======================================================

    def process_runtime_signal(
        self,
        heartbeat=None,
        qbit=None,
        qbit_queue_loop=None,
        qbit_dialer=None,
        heartbeat_emitter=None,
        source=None,
    ):



        try:

            # --------------------------------------------------
            # Late-bind runtime references.
            # --------------------------------------------------

            self.bind_runtime(
                qbit=qbit,
                qbit_queue_loop=(
                    qbit_queue_loop
                ),
                qbit_dialer=qbit_dialer,
                heartbeat_emitter=(
                    heartbeat_emitter
                ),
            )

            # --------------------------------------------------
            # If no heartbeat was explicitly supplied,
            # attempt to obtain the latest authoritative
            # heartbeat from HeartbeatEmitter.
            # --------------------------------------------------

            if heartbeat is None:

                heartbeat = (
                    self._read_latest_heartbeat()
                )

            # --------------------------------------------------
            # If heartbeat exists, process it.
            # --------------------------------------------------

            if heartbeat is not None:

                result = self.receive_heartbeat(
                    heartbeat,
                    qbit=qbit,
                )

            elif self.qbit is not None:

                result = self.receive_qbit(
                    self.qbit
                )

            else:

                result = {
                    "type": (
                        "QuantumRuntimeResult"
                    ),
                    "success": False,
                    "failure": False,
                    "pending": True,
                    "state": "PENDING",
                    "error": (
                        "NO_HEARTBEAT_OR_QBIT"
                    ),
                    "connections": (
                        self._connection_state()
                    ),
                }

                self._set_health(
                    state="PENDING",
                    success=None,
                )

            self.last_runtime_signal = result

            self._record_signal(result)

            return result

        except Exception as exc:

            self._set_health(
                state="RUNTIME_SIGNAL_FAILURE",
                success=False,
                error=str(exc),
            )

            failure = {
                "type": "QuantumRuntimeResult",
                "success": False,
                "failure": True,
                "pending": False,
                "state": "FAILURE",
                "error": str(exc),
                "lineage": (
                    self._lineage_state()
                ),
                "connections": (
                    self._connection_state()
                ),
                "health": self.health.copy(),
            }

            self._emit(
                "QUANTUM_RUNTIME_FAILURE",
                failure,
            )

            return failure

    # ======================================================
    # HEARTBEAT ENTRY
    # ======================================================

    def receive_heartbeat(
        self,
        heartbeat,
        qbit=None,
    ):

        try:

            self.last_heartbeat = heartbeat

            # --------------------------------------------------
            # Prefer explicitly supplied Qbit.
            # --------------------------------------------------

            if qbit is not None:

                self.qbit = qbit

            # --------------------------------------------------
            # Extract Qbit from heartbeat.
            # --------------------------------------------------

            if self.qbit is None:

                if isinstance(
                    heartbeat,
                    dict,
                ):

                    self.qbit = (
                        heartbeat.get("qbit")
                        or heartbeat.get("Qbit")
                    )

                else:

                    self.qbit = getattr(
                        heartbeat,
                        "qbit",
                        None,
                    )

            # --------------------------------------------------
            # Synchronize from runtime context after receiving
            # the heartbeat.
            # --------------------------------------------------

            self._sync_runtime_context()

            state = self._extract_state(
                heartbeat,
                self.qbit,
            )

            self.last_qbit_state = state

            self._capture_lineage(
                heartbeat
            )

            self._capture_lineage(
                state
            )

            # --------------------------------------------------
            # Quantum calculations.
            # --------------------------------------------------

            resonance = self.resonance(
                state
            )

            magnitude = self.state_magnitude(
                state
            )

            probability = self.state_probability(
                state
            )

            self.last_resonance = resonance
            self.last_magnitude = magnitude
            self.last_probability = (
                probability
            )

            # --------------------------------------------------
            # Heartbeat health.
            # --------------------------------------------------

            self._set_health(
                state="HEALTHY",
                success=True,
            )

            self.health[
                "heartbeat_success"
            ] += 1

            result = {
                "type": (
                    "QuantumHeartbeatResult"
                ),

                "source": (
                    self.current_source
                    or "HeartbeatEmitter"
                ),

                # ------------------------------------------
                # Lineage
                # ------------------------------------------

                "qbit_id": (
                    self.current_qbit_id
                ),

                "task_id": (
                    self.current_task_id
                ),

                "track_id": (
                    self.current_track_id
                ),

                "channel_id": (
                    self.current_channel_id
                ),

                "sequence": (
                    self.current_sequence
                ),

                "generation": (
                    self.current_generation
                ),

                # ------------------------------------------
                # Quantum values
                # ------------------------------------------

                "resonance": resonance,

                "magnitude": magnitude,

                "probability": probability,

                "state": state,

                # ------------------------------------------
                # Runtime connections
                # ------------------------------------------

                "connections": (
                    self._connection_state()
                ),

                # ------------------------------------------
                # Health
                # ------------------------------------------

                "success": True,
                "failure": False,
                "pending": False,

                "health": self.health.copy(),
            }

            self._emit(
                "QUANTUM_HEARTBEAT_RESULT",
                result,
            )

            return result

        except Exception as exc:

            self.health[
                "heartbeat_failure"
            ] += 1

            self._set_health(
                state="HEARTBEAT_FAILURE",
                success=False,
                error=str(exc),
            )

            result = {
                "type": (
                    "QuantumHeartbeatResult"
                ),

                "source": (
                    "HeartbeatEmitter"
                ),

                "success": False,
                "failure": True,
                "pending": False,

                "error": str(exc),

                "lineage": (
                    self._lineage_state()
                ),

                "connections": (
                    self._connection_state()
                ),

                "health": self.health.copy(),
            }

            self._emit(
                "QUANTUM_HEARTBEAT_FAILURE",
                result,
            )

            return result

    # ======================================================
    # QBIT ENTRY
    # ======================================================

    def receive_qbit(
        self,
        qbit,
    ):

        if qbit is not None:
            self.qbit = qbit

        return self.receive_heartbeat(
            {
                "type": "QBIT_SIGNAL",
                "source": "QbitQueueLoop",
                "qbit": self.qbit,
            },
            qbit=self.qbit,
        )

    # ======================================================
    # QUEUE LOOP ENTRY
    # ======================================================

    def receive_queue_signal(
        self,
        signal,
    ):


        try:

            self._sync_runtime_context()

            qbit = None

            if isinstance(
                signal,
                dict,
            ):

                qbit = (
                    signal.get("qbit")
                    or signal.get("Qbit")
                )

            if qbit is not None:
                self.qbit = qbit

            result = self.process_runtime_signal(
                heartbeat=signal,
                qbit=qbit,
                qbit_queue_loop=(
                    self.qbit_queue_loop
                ),
                qbit_dialer=(
                    self.qbit_dialer
                ),
                heartbeat_emitter=(
                    self.heartbeat_emitter
                ),
                source="QbitQueueLoop",
            )

            self._emit(
                "QUANTUM_QUEUE_RESULT",
                result,
            )

            return result

        except Exception as exc:

            self._set_health(
                state="QUEUE_SIGNAL_FAILURE",
                success=False,
                error=str(exc),
            )

            failure = {
                "type": "QuantumQueueResult",
                "success": False,
                "failure": True,
                "pending": False,
                "error": str(exc),
                "connections": (
                    self._connection_state()
                ),
                "health": self.health.copy(),
            }

            self._emit(
                "QUANTUM_QUEUE_FAILURE",
                failure,
            )

            return failure

    # ======================================================
    # RESONANCE
    # ======================================================

    def resonance(
        self,
        signals,
    ):

        if signals is None:
            return 1.0

        if isinstance(
            signals,
            dict,
        ):

            values = signals.values()

        elif isinstance(
            signals,
            (list, tuple, set),
        ):

            values = signals

        else:

            values = (signals,)

        total = 0.0
        count = 0

        for value in values:

            try:

                if isinstance(
                    value,
                    complex,
                ):

                    magnitude = abs(value)

                elif isinstance(
                    value,
                    (int, float),
                ):

                    magnitude = abs(
                        float(value)
                    )

                else:

                    continue

                if math.isfinite(
                    magnitude
                ):

                    total += magnitude
                    count += 1

            except Exception:

                continue

        if count == 0:
            return 1.0

        return max(
            0.05,
            min(
                2.50,
                total / count,
            ),
        )

    # ======================================================
    # STATE MAGNITUDE
    # ======================================================

    def state_magnitude(
        self,
        state,
    ):

        alpha, beta = (
            normalize_qbit_input(
                state
            )
        )

        return math.sqrt(
            abs(alpha) ** 2
            +
            abs(beta) ** 2
        )

    # ======================================================
    # STATE PROBABILITY
    # ======================================================

    def state_probability(
        self,
        state,
    ):

        alpha, beta = (
            normalize_qbit_input(
                state
            )
        )

        return {
            "alpha_probability": (
                abs(alpha) ** 2
            ),

            "beta_probability": (
                abs(beta) ** 2
            ),
        }

    # ======================================================
    # COMPUTE BRAIN ENTRY
    # ======================================================

    def process_qbit_to_thought(
        self,
        qbit=None,
        compute_brain=None,
    ):

        try:

            if qbit is not None:
                self.qbit = qbit

            self._sync_runtime_context()

            brain = (
                compute_brain
                or self.compute_brain
            )

            if brain is None:

                failure = {
                    "type": "ThoughtPacket",
                    "success": False,
                    "failure": True,
                    "pending": False,
                    "error": (
                        "COMPUTE_BRAIN_UNAVAILABLE"
                    ),
                    "lineage": (
                        self._lineage_state()
                    ),
                }

                self._set_health(
                    state="COMPUTE_BRAIN_UNAVAILABLE",
                    success=False,
                    error=(
                        "COMPUTE_BRAIN_UNAVAILABLE"
                    ),
                )

                return failure

            source = (
                self.qbit
                if qbit is None
                else qbit
            )

            thought = brain.process(
                source
            )

            self.last_thought = thought

            if isinstance(
                thought,
                dict,
            ):

                self._capture_lineage(
                    thought
                )

                thought.setdefault(
                    "qbit_id",
                    self.current_qbit_id,
                )

                thought.setdefault(
                    "task_id",
                    self.current_task_id,
                )

                thought.setdefault(
                    "track_id",
                    self.current_track_id,
                )

                thought.setdefault(
                    "channel_id",
                    self.current_channel_id,
                )

                thought.setdefault(
                    "quantum",
                    {
                        "resonance": (
                            self.last_resonance
                        ),
                        "magnitude": (
                            self.last_magnitude
                        ),
                        "probability": (
                            self.last_probability
                        ),
                    },
                )

            self._set_health(
                state="THOUGHT_READY",
                success=True,
            )

            self._emit(
                "QUANTUM_THOUGHT_READY",
                {
                    "type": (
                        "QuantumThoughtReady"
                    ),
                    "thought": thought,
                    "lineage": (
                        self._lineage_state()
                    ),
                    "quantum": {
                        "resonance": (
                            self.last_resonance
                        ),
                        "magnitude": (
                            self.last_magnitude
                        ),
                        "probability": (
                            self.last_probability
                        ),
                    },
                    "health": (
                        self.health.copy()
                    ),
                },
            )

            return thought

        except Exception as exc:

            self._set_health(
                state="THOUGHT_FAILURE",
                success=False,
                error=str(exc),
            )

            failure = {
                "type": "ThoughtPacket",

                "success": False,
                "failure": True,
                "pending": False,

                "error": str(exc),

                "lineage": (
                    self._lineage_state()
                ),

                "health": (
                    self.health.copy()
                ),
            }

            self._emit(
                "QUANTUM_THOUGHT_FAILURE",
                failure,
            )

            return failure

    # ======================================================
    # THOUGHT -> RESULT
    # ======================================================

    def process_thought(
        self,
        thought,
        transformer=None,
    ):

        try:

            self.last_thought = thought

            if isinstance(
                thought,
                dict,
            ):

                self._capture_lineage(
                    thought
                )

            transformer = (
                transformer
                or self.transformer_brain
            )

            # --------------------------------------------------
            # Transformer unavailable.
            # --------------------------------------------------

            if transformer is None:

                result = {
                    "type": "CognitiveResult",

                    "thought": thought,

                    "action": None,

                    "confidence": 0.05,

                    "success": False,
                    "failure": True,
                    "pending": False,

                    "error": (
                        "TRANSFORMER_BRAIN_UNAVAILABLE"
                    ),
                }

                self._set_health(
                    state="COGNITION_FAILURE",
                    success=False,
                    error=(
                        "TRANSFORMER_BRAIN_UNAVAILABLE"
                    ),
                )

            else:

                result = transformer.analyze(
                    thought
                )

                if not isinstance(
                    result,
                    dict,
                ):

                    result = {
                        "type": (
                            "CognitiveResult"
                        ),

                        "thought": thought,

                        "result": result,
                    }

                # --------------------------------------------------
                # Do NOT blindly mark every cognitive output
                # as success.
                #
                # A proposal can be valid while still pending
                # downstream execution.
                # --------------------------------------------------

                if (
                    "success" not in result
                    and
                    "failure" not in result
                ):

                    result[
                        "success"
                    ] = True

                    result[
                        "failure"
                    ] = False

                result.setdefault(
                    "pending",
                    False,
                )

                if result.get(
                    "pending"
                ):

                    self._set_health(
                        state="COGNITION_PENDING",
                        success=None,
                    )

                elif result.get(
                    "success"
                ):

                    self.health[
                        "cognitive_success"
                    ] += 1

                    self._set_health(
                        state="COGNITION_OK",
                        success=True,
                    )

                elif result.get(
                    "failure"
                ):

                    self.health[
                        "cognitive_failure"
                    ] += 1

                    self._set_health(
                        state="COGNITION_FAILURE",
                        success=False,
                        error=result.get(
                            "error"
                        ),
                    )

            # --------------------------------------------------
            # Preserve thought -> result relationship.
            # --------------------------------------------------

            linked_result = {

                "type": (
                    "QuantumThoughtResult"
                ),

                "thought": thought,

                "result": result,

                "qbit_id": (
                    self.current_qbit_id
                ),

                "task_id": (
                    self.current_task_id
                ),

                "track_id": (
                    self.current_track_id
                ),

                "channel_id": (
                    self.current_channel_id
                ),

                "source": (
                    self.current_source
                ),

                "sequence": (
                    self.current_sequence
                ),

                "generation": (
                    self.current_generation
                ),

                "quantum": {
                    "resonance": (
                        self.last_resonance
                    ),

                    "magnitude": (
                        self.last_magnitude
                    ),

                    "probability": (
                        self.last_probability
                    ),
                },

                "connections": (
                    self._connection_state()
                ),

                "timestamp": time.time(),
            }

            self.thought_results.append(
                linked_result
            )

            if len(
                self.thought_results
            ) > self.max_history:

                self.thought_results.pop(
                    0
                )

            self.last_result = result

            self._emit(
                "QUANTUM_COGNITIVE_RESULT",
                linked_result,
            )

            return result

        except Exception as exc:

            self._set_health(
                state="COGNITION_FAILURE",
                success=False,
                error=str(exc),
            )

            failure = {
                "type": "CognitiveResult",

                "thought": thought,

                "action": None,

                "success": False,
                "failure": True,
                "pending": False,

                "error": str(exc),

                "lineage": (
                    self._lineage_state()
                ),

                "connections": (
                    self._connection_state()
                ),
            }

            self.last_result = failure

            self._emit(
                "QUANTUM_COGNITIVE_FAILURE",
                failure,
            )

            return failure

    # ======================================================
    # FULL COGNITIVE PIPELINE
    # ======================================================

    def process_cognitive_cycle(
        self,
        heartbeat=None,
        qbit=None,
        compute_brain=None,
        transformer=None,
    ):


        signal = self.process_runtime_signal(
            heartbeat=heartbeat,
            qbit=qbit,
        )

        if signal.get(
            "failure"
        ):

            return signal

        thought = (
            self.process_qbit_to_thought(
                qbit=qbit,
                compute_brain=(
                    compute_brain
                ),
            )
        )

        if (
            isinstance(
                thought,
                dict,
            )
            and
            thought.get("failure")
        ):

            return thought

        result = self.process_thought(
            thought,
            transformer=transformer,
        )

        return {
            "type": (
                "QuantumCognitiveCycle"
            ),

            "success": (
                bool(
                    isinstance(
                        result,
                        dict,
                    )
                    and
                    result.get(
                        "success",
                        False,
                    )
                )
            ),

            "failure": (
                bool(
                    isinstance(
                        result,
                        dict,
                    )
                    and
                    result.get(
                        "failure",
                        False,
                    )
                )
            ),

            "pending": (
                bool(
                    isinstance(
                        result,
                        dict,
                    )
                    and
                    result.get(
                        "pending",
                        False,
                    )
                )
            ),

            "quantum": {
                "resonance": (
                    self.last_resonance
                ),

                "magnitude": (
                    self.last_magnitude
                ),

                "probability": (
                    self.last_probability
                ),
            },

            "thought": thought,

            "result": result,

            "lineage": (
                self._lineage_state()
            ),

            "connections": (
                self._connection_state()
            ),

            "health": (
                self.health.copy()
            ),

            # Explicit authority boundary.
            "executes_commands": False,
            "submits_commands": False,
            "command_authority": "QbitDialer",
            "command_admission": (
                "submit_command"
            ),
        }

    # ======================================================
    # RESULT FEEDBACK
    # ======================================================

    def receive_result(
        self,
        result,
    ):

        self.last_result = result

        status = "PENDING"

        success = False
        failure = False
        pending = False

        if isinstance(
            result,
            dict,
        ):

            explicit_success = result.get(
                "success"
            )

            explicit_failure = result.get(
                "failure"
            )

            explicit_pending = result.get(
                "pending"
            )

            status_value = str(
                result.get(
                    "status",
                    "",
                )
            ).upper()

            if explicit_success is True:

                success = True

            elif (
                explicit_failure is True
            ):

                failure = True

            elif (
                explicit_pending is True
                or
                status_value in (
                    "PENDING",
                    "PROPOSED",
                    "QUEUED",
                    "DEFERRED",
                )
            ):

                pending = True

            elif status_value in (
                "SUCCESS",
                "OK",
                "COMPLETE",
                "COMPLETED",
            ):

                success = True

            elif status_value in (
                "FAILURE",
                "FAILED",
                "ERROR",
            ):

                failure = True

            else:

                # Unknown result state is not automatically
                # classified as failure.
                pending = True

        else:

            pending = True

        if success:

            status = "SUCCESS"

            self.health[
                "result_success"
            ] += 1

            self._set_health(
                state=status,
                success=True,
            )

        elif failure:

            status = "FAILURE"

            self.health[
                "result_failure"
            ] += 1

            error = (
                result.get("error")
                if isinstance(
                    result,
                    dict,
                )
                else None
            )

            self._set_health(
                state=status,
                success=False,
                error=error,
            )

        else:

            status = "PENDING"

            self._set_health(
                state=status,
                success=None,
            )

        feedback = {

            "type": (
                "QuantumResultFeedback"
            ),

            "status": status,

            "success": success,

            "failure": failure,

            "pending": pending,

            "result": result,

            "qbit_id": (
                self.current_qbit_id
            ),

            "task_id": (
                self.current_task_id
            ),

            "track_id": (
                self.current_track_id
            ),

            "channel_id": (
                self.current_channel_id
            ),

            "connections": (
                self._connection_state()
            ),

            "health": (
                self.health.copy()
            ),
        }

        self._emit(
            "QUANTUM_RESULT_FEEDBACK",
            feedback,
        )

        return self.health.copy()

    # ======================================================
    # LINEAGE
    # ======================================================

    def _capture_lineage(
        self,
        state,
    ):

        if not isinstance(
            state,
            dict,
        ):

            return

        self.current_qbit_id = (
            state.get("qbit_id")
            or state.get("qbit")
            or state.get("id")
            or self.current_qbit_id
        )

        self.current_task_id = (
            state.get("task_id")
            or state.get("task")
            or self.current_task_id
        )

        self.current_track_id = (
            state.get("track_id")
            or state.get("track")
            or self.current_track_id
        )

        self.current_channel_id = (
            state.get("channel_id")
            or state.get("channel")
            or self.current_channel_id
        )

        self.current_source = (
            state.get("source")
            or self.current_source
        )

        self.current_sequence = (
            state.get("sequence")
            or state.get("seq")
            or self.current_sequence
        )

        self.current_generation = (
            state.get("generation")
            or state.get("gen")
            or self.current_generation
        )

    # ======================================================
    # STATE EXTRACTION
    # ======================================================

    def _extract_state(
        self,
        heartbeat,
        qbit,
    ):

        if isinstance(
            heartbeat,
            dict,
        ):

            state = (
                heartbeat.get("state")
                or heartbeat.get(
                    "qbit_state"
                )
                or heartbeat.get(
                    "quantum_state"
                )
            )

            if isinstance(
                state,
                dict,
            ):

                merged = dict(
                    heartbeat
                )

                merged.update(
                    state
                )

                return merged

            return dict(
                heartbeat
            )

        if isinstance(
            qbit,
            dict,
        ):

            return dict(
                qbit
            )

        if qbit is not None:

            for method_name in (
                "get_state",
                "state",
                "snapshot",
            ):

                try:

                    method = getattr(
                        qbit,
                        method_name,
                        None,
                    )

                    if callable(method):

                        result = method()

                        if isinstance(
                            result,
                            dict,
                        ):

                            return result

                    elif isinstance(
                        method,
                        dict,
                    ):

                        return method

                except Exception:
                    continue

        return {}

    # ======================================================
    # HEARTBEAT READER
    # ======================================================

    def _read_latest_heartbeat(
        self,
    ):

        emitter = (
            self.heartbeat_emitter
        )

        if emitter is None:
            return None

        for method_name in (
            "get_latest_heartbeat",
            "latest_heartbeat",
            "get_last_heartbeat",
            "last_heartbeat",
            "snapshot",
            "get_state",
        ):

            try:

                method = getattr(
                    emitter,
                    method_name,
                    None,
                )

                if callable(method):

                    value = method()

                else:

                    value = method

                if value is not None:

                    return value

            except Exception:
                continue

        return None

    # ======================================================
    # HEALTH
    # ======================================================

    def _set_health(
        self,
        state,
        success=None,
        error=None,
    ):

        self.health["state"] = state

        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        if success is True:

            self.health[
                "healthy"
            ] = True

            self.health[
                "success"
            ] += 1

            self.health[
                "last_success"
            ] = time.time()

            self.health[
                "error"
            ] = None

        # --------------------------------------------------
        # FAILURE
        # --------------------------------------------------

        elif success is False:

            self.health[
                "healthy"
            ] = False

            self.health[
                "failure"
            ] += 1

            self.health[
                "last_failure"
            ] = time.time()

            self.health[
                "error"
            ] = error

        # --------------------------------------------------
        # PENDING / OBSERVATIONAL
        # --------------------------------------------------

        else:

            self.health[
                "pending"
            ] += 1

            self.health[
                "last_pending"
            ] = time.time()

            # Pending does not automatically mean unhealthy.
            self.health[
                "healthy"
            ] = True

        return self.health

    # ======================================================
    # CONNECTION STATE
    # ======================================================

    def _connection_state(
        self,
    ):

        return {

            "heartbeat_emitter": (
                self.heartbeat_emitter
                is not None
            ),

            "qbit": (
                self.qbit
                is not None
            ),

            "qbit_queue_loop": (
                self.qbit_queue_loop
                is not None
            ),

            "qbit_dialer": (
                self.qbit_dialer
                is not None
            ),

            "track_system": (
                self.track_system
                is not None
            ),

            "compute_brain": (
                self.compute_brain
                is not None
            ),

            "transformer_brain": (
                self.transformer_brain
                is not None
            ),

            "runtime_context": (
                self.runtime_context
                is not None
            ),

            "event_emitter": (
                callable(self.emit)
            ),
        }

    # ======================================================
    # LINEAGE STATE
    # ======================================================

    def _lineage_state(
        self,
    ):

        return {

            "qbit_id": (
                self.current_qbit_id
            ),

            "task_id": (
                self.current_task_id
            ),

            "track_id": (
                self.current_track_id
            ),

            "channel_id": (
                self.current_channel_id
            ),

            "source": (
                self.current_source
            ),

            "sequence": (
                self.current_sequence
            ),

            "generation": (
                self.current_generation
            ),
        }

    # ======================================================
    # SIGNAL HISTORY
    # ======================================================

    def _record_signal(
        self,
        signal,
    ):

        self.signal_history.append(
            {
                "timestamp": time.time(),
                "signal": signal,
                "lineage": (
                    self._lineage_state()
                ),
            }
        )

        if len(
            self.signal_history
        ) > self.max_signal_history:

            self.signal_history.pop(
                0
            )

    # ======================================================
    # DYNAMIC RUNTIME STATUS
    # ======================================================

    def get_state(
        self,
    ):

        return {

            "module": (
                "QuantumMathEngine"
            ),

            "running": self.running,

            # ----------------------------------------------
            # Connections
            # ----------------------------------------------

            "connections": (
                self._connection_state()
            ),

            "qbit_connected": (
                self.qbit is not None
            ),

            "qbit_queue_connected": (
                self.qbit_queue_loop
                is not None
            ),

            "dialer_connected": (
                self.qbit_dialer
                is not None
            ),

            "heartbeat_connected": (
                self.heartbeat_emitter
                is not None
            ),

            "track_system_connected": (
                self.track_system
                is not None
            ),

            "compute_brain_connected": (
                self.compute_brain
                is not None
            ),

            "transformer_brain_connected": (
                self.transformer_brain
                is not None
            ),

            # ----------------------------------------------
            # Lineage
            # ----------------------------------------------

            "lineage": (
                self._lineage_state()
            ),

            "qbit_id": (
                self.current_qbit_id
            ),

            "task_id": (
                self.current_task_id
            ),

            "track_id": (
                self.current_track_id
            ),

            "channel_id": (
                self.current_channel_id
            ),

            # ----------------------------------------------
            # Quantum state
            # ----------------------------------------------

            "resonance": (
                self.last_resonance
            ),

            "magnitude": (
                self.last_magnitude
            ),

            "probability": (
                self.last_probability
            ),

            # ----------------------------------------------
            # Cognitive state
            # ----------------------------------------------

            "last_thought": (
                self.last_thought
            ),

            "last_result": (
                self.last_result
            ),

            "last_runtime_signal": (
                self.last_runtime_signal
            ),

            "thought_result_count": (
                len(
                    self.thought_results
                )
            ),

            "signal_history_count": (
                len(
                    self.signal_history
                )
            ),

            # ----------------------------------------------
            # Health
            # ----------------------------------------------

            "health": (
                self.health.copy()
            ),

            # ----------------------------------------------
            # Explicit authority boundary.
            # ----------------------------------------------

            "executes_commands": False,

            "submits_commands": False,

            "command_authority": (
                "QbitDialer"
            ),

            "command_admission": (
                "submit_command"
            ),
        }

    # ======================================================
    # EVENT OUTPUT
    # ======================================================

    def _emit(
        self,
        event_type,
        payload,
    ):

        if not callable(
            self.emit
        ):

            return False

        try:

            result = self.emit(
                event_type,
                payload,
            )

            return (
                True
                if result is None
                else bool(result)
            )

        except TypeError:

            try:

                result = self.emit(
                    payload
                )

                return (
                    True
                    if result is None
                    else bool(result)
                )

            except Exception:

                return False

        except Exception:

            return False