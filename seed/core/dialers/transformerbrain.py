# ============================================================
# FILE: transformerbrain.py
# PATH: SEED_ROOT/seed/core/brains/transformerbrain.py
# VERSION: 25.0.4
# UPDATED: 2026-09-08
# BUILD: THOUGHTPACKET-PRESERVING / COMMAND-PROPOSAL-CONTRACT /
#        SINGLE-CORRECT-IMPORT / DYNAMIC-BINDING
# ============================================================

import logging
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional

from seed.core.dialers.quantum_math_engine import QuantumMathEngine


logger = logging.getLogger(__name__)


class TransformerBrain:
    VERSION = "25.0.4"

    def __init__(
        self,
        name="qbit_dialer",
        learning_rate=0.02,
        *,
        engine: Optional[QuantumMathEngine] = None,
        quantum_math_engine: Optional[QuantumMathEngine] = None,
        qbit=None,
        compute_brain=None,
        qbit_queue_loop=None,
        qbit_dialer=None,
        heartbeat_emitter=None,
        event_bus=None,
        registry=None,
        logger_instance: Optional[logging.Logger] = None,
        emit=None,
        **kwargs: Any,
    ) -> None:

        self.logger = (
            logger_instance
            if logger_instance is not None
            else logger
        )

        self.name = name
        self.learning_rate = learning_rate

        self.qbit = qbit
        self.qbit_queue_loop = qbit_queue_loop
        self.qbit_dialer = qbit_dialer
        self.heartbeat_emitter = heartbeat_emitter
        self.compute_brain = compute_brain
        self.event_bus = event_bus
        self.registry = registry
        self.emit = emit

        self.engine = (
            quantum_math_engine
            if quantum_math_engine is not None
            else engine
        )

        if self.engine is None:
            self.engine = QuantumMathEngine(
                qbit=qbit,
                qbit_queue_loop=qbit_queue_loop,
                qbit_dialer=qbit_dialer,
                heartbeat_emitter=heartbeat_emitter,
                emit=emit,
                compute_brain=compute_brain,
                transformer_brain=self,
            )

        self.weights = defaultdict(
            lambda: 1.0
        )

        self.history = deque(
            maxlen=256
        )

        self.confidence = 1.0
        self.samples = 0

        self.last_thought = None
        self.last_analysis = None
        self.last_result = None
        self.last_action = None

        self.runtime_bound = False
        self.initialized_at = time.time()

        self.logger.info(
            "TransformerBrain initialized | version=%s | name=%s",
            self.VERSION,
            self.name,
        )

    # ==========================================================
    # RUNTIME BINDING
    # ==========================================================

    def bind_runtime(
        self,
        *,
        qbit=None,
        qbit_queue_loop=None,
        qbit_dialer=None,
        compute_brain=None,
        event_bus=None,
        registry=None,
        heartbeat_emitter=None,
        emit=None,
        **kwargs: Any,
    ) -> "TransformerBrain":

        if qbit is not None:
            self.qbit = qbit

        if qbit_queue_loop is not None:
            self.qbit_queue_loop = qbit_queue_loop

        if qbit_dialer is not None:
            self.qbit_dialer = qbit_dialer

        if compute_brain is not None:
            self.compute_brain = compute_brain

        if event_bus is not None:
            self.event_bus = event_bus

        if registry is not None:
            self.registry = registry

        if heartbeat_emitter is not None:
            self.heartbeat_emitter = heartbeat_emitter

        if emit is not None:
            self.emit = emit

        binder = getattr(
            self.engine,
            "bind_runtime",
            None,
        )

        if callable(binder):

            try:

                binder(
                    qbit=self.qbit,
                    qbit_queue_loop=self.qbit_queue_loop,
                    qbit_dialer=self.qbit_dialer,
                    heartbeat_emitter=self.heartbeat_emitter,
                    event_bus=self.event_bus,
                    compute_brain=self.compute_brain,
                    transformer_brain=self,
                    emit=self.emit,
                )

            except TypeError:

                binder(
                    qbit=self.qbit,
                    qbit_queue_loop=self.qbit_queue_loop,
                    qbit_dialer=self.qbit_dialer,
                    heartbeat_emitter=self.heartbeat_emitter,
                    compute_brain=self.compute_brain,
                    transformer_brain=self,
                    emit=self.emit,
                )

        self.runtime_bound = True

        self.logger.info(
            "TransformerBrain runtime bound | "
            "qbit=%s | queue_loop=%s | dialer=%s | compute=%s",
            bool(self.qbit),
            bool(self.qbit_queue_loop),
            bool(self.qbit_dialer),
            bool(self.compute_brain),
        )

        return self

    # ==========================================================
    # RESULT CONTRACT
    # ==========================================================

    def _build_result(
        self,
        *,
        intent=None,
        action=None,
        command_proposal=None,
        confidence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        thought: Any = None,
        classification=None,
        correlation=None,
        resonance=None,
        score=None,
        success=True,
        failure=False,
        health="COGNITION_OK",
    ) -> Dict[str, Any]:

        proposal = None
        command = None

        # --------------------------------------------------
        # Normalize the ActionProposal contract.
        #
        # IMPORTANT:
        #
        # command_proposal is ALWAYS a proposal envelope
        # when a command exists.
        #
        # It is never a bare command string.
        # --------------------------------------------------

        if isinstance(
            command_proposal,
            dict,
        ):
            proposal = dict(
                command_proposal
            )

        elif isinstance(
            action,
            dict,
        ):
            proposal = dict(
                action
            )

        elif isinstance(
            command_proposal,
            str,
        ):
            normalized = (
                command_proposal
                .strip()
            )

            if normalized:
                proposal = {
                    "type": "ActionProposal",
                    "command": normalized,
                    "authorized": False,
                    "proposal_only": True,
                    "command_authority": "QbitDialer",
                    "command_admission": "submit_command",
                    "execution_required": True,
                    "execution_requested": True,
                    "executes_commands": False,
                    "submits_commands": False,
                }

        if isinstance(
            proposal,
            dict,
        ):

            for key in (
                "command",
                "proposed_command",
                "cmd",
            ):

                candidate = proposal.get(
                    key
                )

                if isinstance(
                    candidate,
                    str,
                ):

                    candidate = (
                        candidate
                        .strip()
                    )

                    if candidate:
                        command = candidate
                        break

        if command is None and isinstance(
            action,
            dict,
        ):

            for key in (
                "command",
                "proposed_command",
                "cmd",
            ):

                candidate = action.get(
                    key
                )

                if isinstance(
                    candidate,
                    str,
                ):

                    candidate = (
                        candidate
                        .strip()
                    )

                    if candidate:
                        command = candidate
                        break

        return {
            "type": "CognitiveResult",
            "brain": self.name,
            "thought": thought,
            "classification": classification,
            "correlation": (
                correlation
                if isinstance(
                    correlation,
                    dict,
                )
                else {}
            ),
            "score": score,
            "resonance": resonance,
            "confidence": confidence,
            "intent": intent,
            "action": action,
            "command": command,
            "proposed_command": command,
            "command_proposal": proposal,
            "has_actionable_command": (
                command is not None
            ),
            "learn": True,
            "success": success,
            "failure": failure,
            "health": health,
            "command_authority": "QbitDialer",
            "command_admission": "submit_command",
            "command_executed": False,
            "authorized": False,
            "proposal_only": True,
            "executes_commands": False,
            "submits_commands": False,
            "metadata": (
                metadata
                if isinstance(
                    metadata,
                    dict,
                )
                else {}
            ),
        }

    # ==========================================================
    # AUTHORITATIVE TRANSFORM ENTRY
    # ==========================================================

    def analyze(
        self,
        thought: Any,
        *,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        context = (
            context
            if isinstance(
                context,
                dict,
            )
            else {}
        )

        # --------------------------------------------------
        # Invalid / empty input
        # --------------------------------------------------

        if thought is None:

            result = self._build_result(
                confidence=0.05,
                thought=None,
                success=False,
                failure=True,
                health="FAILURE",
                metadata={
                    "status": "invalid_input",
                    "reason": "thought_is_none",
                    "transformer_version": self.VERSION,
                },
            )

            self.last_result = result
            self.last_analysis = result

            return result

        if not isinstance(
            thought,
            dict,
        ):

            result = self._build_result(
                confidence=0.05,
                thought=thought,
                success=False,
                failure=True,
                health="FAILURE",
                metadata={
                    "status": "invalid_input",
                    "reason": "thought_not_dict",
                    "input_type": type(
                        thought
                    ).__name__,
                    "transformer_version": self.VERSION,
                },
            )

            self.last_result = result
            self.last_analysis = result

            return result

        self.last_thought = thought

        try:

            # --------------------------------------------------
            # Quantum analysis happens HERE.
            #
            # ThoughtPacket remains the cognitive input.
            # --------------------------------------------------

            resonance = self.engine.resonance(
                thought.get(
                    "state",
                    {},
                )
            )

            classification = thought.get(
                "classification",
                "UNKNOWN",
            )

            if not isinstance(
                classification,
                str,
            ):
                classification = str(
                    classification
                )

            source = thought.get(
                "source",
                thought.get(
                    "origin"
                ),
            )

            channel = thought.get(
                "channel",
                thought.get(
                    "channel_id"
                ),
            )

            track = (
                thought.get(
                    "track"
                )
                or thought.get(
                    "track_id"
                )
            )

            weight = self.weights[
                classification
            ]

            weighted_score = (
                resonance
                * weight
            )

            confidence = max(
                0.05,
                min(
                    2.50,
                    weighted_score,
                ),
            )

            correlation = {
                "source": source,
                "channel": channel,
                "track": track,
                "classification": classification,
                "qbit_id": getattr(
                    self.engine,
                    "current_qbit_id",
                    None,
                ),
                "task_id": getattr(
                    self.engine,
                    "current_task_id",
                    None,
                ),
                "track_id": getattr(
                    self.engine,
                    "current_track_id",
                    None,
                ),
                "channel_id": getattr(
                    self.engine,
                    "current_channel_id",
                    None,
                ),
            }

            intent = self._generate_intent(
                thought,
                confidence,
                context=context,
            )

            action = self._generate_action(
                thought,
                intent=intent,
                context=context,
            )

            # --------------------------------------------------
            # FIX:
            #
            # Preserve the COMPLETE ActionProposal envelope.
            #
            # The previous contract reduced this to:
            #
            #     action["command"]
            #
            # which converted command_proposal into a bare
            # string and broke downstream action extraction.
            #
            # QbitDialer must receive the proposal envelope.
            # --------------------------------------------------

            proposal = (
                dict(
                    action
                )
                if isinstance(
                    action,
                    dict,
                )
                else None
            )

            result = self._build_result(
                intent=intent,
                action=action,
                command_proposal=proposal,
                confidence=confidence,
                thought=thought,
                classification=classification,
                correlation=correlation,
                resonance=resonance,
                score=weighted_score,
                metadata={
                    "transformer_version": self.VERSION,
                    "runtime_bound": self.runtime_bound,
                    "source": source,
                    "context": dict(
                        context
                    ),
                },
            )

            self.samples += 1
            self.confidence = confidence

            self.history.append(
                result
            )

            self.last_analysis = result
            self.last_result = result
            self.last_action = action

            # --------------------------------------------------
            # IMPORTANT:
            #
            # Do NOT call:
            #
            #     self.engine.process_thought(...)
            #
            # here.
            #
            # TransformerBrain has already processed the
            # ThoughtPacket. Calling process_thought() here
            # re-enters the TransformerBrain through the engine.
            #
            # Preserve the completed result directly.
            # --------------------------------------------------

            try:

                self.engine.last_result = result

            except Exception:

                pass

            self._emit(
                "TRANSFORMER_COGNITIVE_RESULT",
                result,
            )

            return result

        except Exception as exc:

            self.logger.exception(
                "TransformerBrain analysis failed: %s",
                exc,
            )

            result = self._build_result(
                confidence=0.05,
                thought=thought,
                success=False,
                failure=True,
                health="FAILURE",
                metadata={
                    "status": "analysis_failed",
                    "error": str(exc),
                    "error_type": type(
                        exc
                    ).__name__,
                    "transformer_version": self.VERSION,
                },
            )

            self.last_result = result
            self.last_analysis = result

            return result

    # ==========================================================
    # COMPUTE COMPATIBILITY
    # ==========================================================

    def compute(
        self,
        signals: Any,
        *,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:

        # --------------------------------------------------
        # Existing ThoughtPacket:
        #
        # TransformerBrain is the second cognitive stage.
        # Do not send it through ComputeBrain again.
        # --------------------------------------------------

        if (
            isinstance(
                signals,
                dict,
            )
            and signals.get(
                "type"
            ) == "ThoughtPacket"
        ):

            return self.analyze(
                signals,
                context=context,
                **kwargs,
            )

        # --------------------------------------------------
        # Compatibility path:
        #
        # Non-ThoughtPacket input may still enter through
        # ComputeBrain for older callers.
        # --------------------------------------------------

        if self.compute_brain is None:

            failure = self._build_result(
                confidence=0.05,
                thought=signals,
                success=False,
                failure=True,
                health="FAILURE",
                metadata={
                    "status": (
                        "compute_brain_unavailable"
                    ),
                    "error": (
                        "COMPUTE_BRAIN_UNAVAILABLE"
                    ),
                    "transformer_version": self.VERSION,
                },
            )

            self.last_result = failure
            self.last_analysis = failure

            try:

                self.engine.receive_result(
                    failure
                )

            except Exception:

                pass

            return 0.05

        try:

            processor = getattr(
                self.compute_brain,
                "process",
                None,
            )

            if not callable(
                processor
            ):

                processor = getattr(
                    self.compute_brain,
                    "receive_qbit",
                    None,
                )

            if not callable(
                processor
            ):

                raise AttributeError(
                    "ComputeBrain exposes neither "
                    "process() nor receive_qbit()"
                )

            thought = processor(
                signals
            )

            analysis = self.analyze(
                thought,
                context=context,
                **kwargs,
            )

            return analysis.get(
                "confidence",
                0.05,
            )

        except Exception as exc:

            failure = self._build_result(
                confidence=0.05,
                thought=signals,
                success=False,
                failure=True,
                health="FAILURE",
                metadata={
                    "status": "compute_failed",
                    "error": str(exc),
                    "error_type": type(
                        exc
                    ).__name__,
                    "transformer_version": self.VERSION,
                },
            )

            self.last_result = failure
            self.last_analysis = failure

            try:

                self.engine.receive_result(
                    failure
                )

            except Exception:

                pass

            return 0.05

    # ==========================================================
    # INTENT
    # ==========================================================

    def _generate_intent(
        self,
        thought: Dict[str, Any],
        confidence: float,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        context = (
            context
            if isinstance(
                context,
                dict,
            )
            else {}
        )

        intent_value = (
            thought.get(
                "intent"
            )
            or thought.get(
                "classification"
            )
            or context.get(
                "intent"
            )
        )

        return {
            "type": "Intent",
            "source": thought.get(
                "source",
                thought.get(
                    "origin"
                ),
            ),
            "channel": thought.get(
                "channel",
                thought.get(
                    "channel_id"
                ),
            ),
            "track": (
                thought.get(
                    "track"
                )
                or thought.get(
                    "track_id"
                )
            ),
            "classification": thought.get(
                "classification"
            ),
            "intent": intent_value,
            "confidence": confidence,
        }

    # ==========================================================
    # ACTION PROPOSAL
    # ==========================================================

    def _generate_action(
        self,
        thought: Dict[str, Any],
        *,
        intent: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        context = (
            context
            if isinstance(
                context,
                dict,
            )
            else {}
        )

        command = None
        command_source = None

        # --------------------------------------------------
        # Cognitive / routing / quantum-state values are
        # NOT executable commands.
        # --------------------------------------------------

        ignored = {
            "",
            "UNKNOWN",
            "NONE",
            "THOUGHT",
            "SIGNAL",
            "IDLE",
            "COMPUTE_BRAIN",
            "_PLAN",
            "PLAN",
            "ALPHA_DOMINANT",
            "BETA_DOMINANT",
            "BALANCED",
            "SUPERPOSITION",
            "COHERENT",
            "DECOHERENT",
        }

        # --------------------------------------------------
        # Helper:
        #
        # Only explicitly supplied command values are allowed
        # to become command proposals.
        # --------------------------------------------------

        def normalize_command(
            candidate: Any,
        ) -> Optional[str]:

            if not isinstance(
                candidate,
                str,
            ):
                return None

            candidate = (
                candidate
                .strip()
            )

            if not candidate:
                return None

            normalized = (
                candidate
                .upper()
            )

            if normalized in ignored:
                return None

            if normalized.endswith(
                "_PLAN"
            ):
                return None

            return candidate

        # --------------------------------------------------
        # 1. Explicit command fields on ThoughtPacket.
        # --------------------------------------------------

        for key in (
            "command",
            "proposed_command",
            "cmd",
        ):

            candidate = normalize_command(
                thought.get(
                    key
                )
            )

            if candidate is not None:

                command = candidate
                command_source = (
                    f"thought.{key}"
                )

                break

        # --------------------------------------------------
        # 2. Explicit action dictionary.
        # --------------------------------------------------

        if command is None:

            action_value = thought.get(
                "action"
            )

            if isinstance(
                action_value,
                dict,
            ):

                for key in (
                    "command",
                    "proposed_command",
                    "cmd",
                    "name",
                    "action",
                ):

                    candidate = normalize_command(
                        action_value.get(
                            key
                        )
                    )

                    if candidate is not None:

                        command = candidate
                        command_source = (
                            f"thought.action.{key}"
                        )

                        break

            elif isinstance(
                action_value,
                str,
            ):

                candidate = normalize_command(
                    action_value
                )

                if candidate is not None:

                    command = candidate
                    command_source = (
                        "thought.action"
                    )

        # --------------------------------------------------
        # 3. Explicit command supplied in cognitive context.
        #
        # This supports upstream command propagation without
        # converting intent/classification/state into commands.
        # --------------------------------------------------

        if command is None:

            for key in (
                "command",
                "proposed_command",
                "cmd",
            ):

                candidate = normalize_command(
                    context.get(
                        key
                    )
                )

                if candidate is not None:

                    command = candidate
                    command_source = (
                        f"context.{key}"
                    )

                    break

        # --------------------------------------------------
        # IMPORTANT FIX:
        #
        # DO NOT use ThoughtPacket classification as an
        # executable command fallback.
        #
        # This was the source of:
        #
        #     command=ALPHA_DOMINANT
        #
        # ALPHA_DOMINANT is a cognitive/quantum
        # classification, not a QbitDialer command.
        #
        # Classification remains available in the
        # CognitiveResult and Intent structures.
        # --------------------------------------------------

        proposal = {
            "type": "ActionProposal",
            "intent": intent,
            "command": command,
            "proposed_command": command,
            "command_source": command_source,
            "authorized": False,
            "proposal_only": True,
            "command_authority": "QbitDialer",
            "command_admission": "submit_command",
            "execution_required": (
                command is not None
            ),
            "execution_requested": (
                command is not None
            ),
            "actionable": (
                command is not None
            ),
            "executes_commands": False,
            "submits_commands": False,
        }

        return proposal

    # ==========================================================
    # CONFIDENCE
    # ==========================================================

    def _extract_confidence(
        self,
        thought: Dict[str, Any],
    ) -> float:

        for candidate in (
            thought.get(
                "confidence"
            ),
            thought.get(
                "score"
            ),
            thought.get(
                "probability"
            ),
        ):

            try:

                value = float(
                    candidate
                )

                if value != value:
                    continue

                return max(
                    0.0,
                    min(
                        1.0,
                        value,
                    ),
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

        return 0.0

    # ==========================================================
    # LEARNING / ADAPTATION
    # ==========================================================

    def adapt(
        self,
    ):

        if len(
            self.history
        ) < 2:

            return None

        previous = (
            self.history[-2].get(
                "confidence",
                1.0,
            )
        )

        current = (
            self.history[-1].get(
                "confidence",
                1.0,
            )
        )

        delta = (
            current
            - previous
        )

        for key in list(
            self.weights.keys()
        ):

            self.weights[key] += (
                delta
                * self.learning_rate
            )

            self.weights[key] = max(
                0.05,
                min(
                    2.50,
                    self.weights[key],
                ),
            )

        return dict(
            self.weights
        )

    # ==========================================================
    # STATE
    # ==========================================================

    def get_state(
        self,
    ) -> Dict[str, Any]:

        return {
            "module": "TransformerBrain",
            "version": self.VERSION,
            "name": self.name,
            "runtime_bound": (
                self.runtime_bound
            ),
            "qbit_bound": (
                self.qbit is not None
            ),
            "queue_loop_bound": (
                self.qbit_queue_loop
                is not None
            ),
            "dialer_bound": (
                self.qbit_dialer
                is not None
            ),
            "compute_brain_bound": (
                self.compute_brain
                is not None
            ),
            "samples": self.samples,
            "confidence": self.confidence,
            "last_thought": self.last_thought,
            "last_analysis": self.last_analysis,
            "last_result": self.last_result,
            "last_action": self.last_action,
            "weights": dict(
                self.weights
            ),
            "history_size": len(
                self.history
            ),
            "command_authority": (
                "QbitDialer"
            ),
            "command_admission": (
                "submit_command"
            ),
            "executes_commands": False,
            "submits_commands": False,
        }

    # ==========================================================
    # EVENT OUTPUT
    # ==========================================================

    def _emit(
        self,
        event_type: str,
        payload: Any,
    ) -> bool:

        if callable(
            self.emit
        ):

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

        bus = self.event_bus

        if bus is not None:

            try:

                emitter = getattr(
                    bus,
                    "emit",
                    None,
                )

                if callable(
                    emitter
                ):

                    result = emitter(
                        event_type,
                        payload,
                    )

                    return (
                        True
                        if result is None
                        else bool(result)
                    )

                publisher = getattr(
                    bus,
                    "publish",
                    None,
                )

                if callable(
                    publisher
                ):

                    result = publisher(
                        event_type,
                        payload,
                    )

                    return (
                        True
                        if result is None
                        else bool(result)
                    )

            except Exception:

                self.logger.debug(
                    "TransformerBrain event emission failed",
                    exc_info=True,
                )

        return False


__all__ = [
    "TransformerBrain",
]