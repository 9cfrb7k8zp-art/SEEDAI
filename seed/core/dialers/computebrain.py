# ==========================================================
# FILE: computebrain.py
# PATH: SEED_ROOT/seed/core/dialers/computebrain.py
# VERSION: 3.2.0
# BUILD: LIFECYCLE-SAFE / SINGLE-QBIT / QUEUE-AUTHORITY
# UPDATED: 2026-09-02
# ==========================================================

import asyncio
import cmath
import inspect
import logging
import math
import os
import queue
import random
import shutil
import threading
import time
import traceback
import tracemalloc
import uuid

from queue import Empty
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

import psutil
import seed.core.qbit.qbit as qbit_module
from .quantum_math_engine import QuantumMathEngine
from seed.core.qbit.qbit_encoder import QbitEncoder
from SRegistry import register_module
from SRegistry import SEED_KERNEL_REGISTRY

# ==========================================================
# AUTHORITATIVE CHANNEL CONTROL
#
# IMPORTANT:
#
# EventBus owns qbit_channel_control.
#
# ComputeBrain must NEVER import it from QbitDialer.
#
# Dependency direction:
#
# EventBus
#    |
#    +--> qbit_channel_control
#             |
#             +--> ComputeBrain
#             |
#             +--> QbitDialer
#
# This prevents:
#
# QbitDialer -> ComputeBrain -> QbitDialer
#
# circular initialization.
# ==========================================================

try:
    from seed.core.event_bus import qbit_channel_control
except ImportError:
    qbit_channel_control = None


# ==========================================================
# QUANTUM MATH ENGINE IMPORT
#
# Mathematical engine remains separate from ComputeBrain.
# ==========================================================

try:
    from seed.core.dialers.quantum_math_engine import (
        QuantumMathEngine,
    )
except ImportError:

    QuantumMathEngine = None


# ==========================================================
# COMPUTE BRAIN
# ==========================================================

class ComputeBrain:

    VERSION = "3.2.0"

    def __init__(
        self,
        name="compute_brain",
        qbit=None,
        quantum_engine=None,
        encoder=None,
        decoder=None,
        decryptor=None,
        track_system=None,
        channel_manager=None,
        action_engine=None,
        intent_engine=None,
        analytics_engine=None,
        adaptive_engine=None,
        adaptive_priority_engine=None,
        transformer_brain=None,
        channel_control=None,
        event_bus=None,
        registry=None,
    ):

        # ==================================================
        # IDENTITY
        # ==================================================

        self.name = name

        # ==================================================
        # AUTHORITATIVE SYSTEM REFERENCES
        #
        # References only.
        #
        # ComputeBrain does not create:
        #
        # - Qbits
        # - queues
        # - runtimes
        # - command planes
        # ==================================================

        self.event_bus = event_bus

        self.registry = (
            registry
            if registry is not None
            else SEED_KERNEL_REGISTRY
        )

        # --------------------------------------------------
        # Preserve explicit injection.
        #
        # Otherwise use the EventBus-owned controller.
        # --------------------------------------------------

        if channel_control is not None:

            self.channel_control = channel_control

        else:

            self.channel_control = (
                qbit_channel_control
            )

        # ==================================================
        # QBIT REFERENCE
        #
        # Reference only.
        #
        # ComputeBrain does NOT create or replace Qbits.
        # ==================================================

        self.qbit = qbit

        # ==================================================
        # PROCESSING DEPENDENCIES
        # ==================================================

        self.encoder = encoder

        self.decoder = decoder

        self.decryptor = decryptor

        self.track_system = track_system

        self.channel_manager = channel_manager

        self.action_engine = action_engine
        self.intent_engine = intent_engine
        self.analytics_engine = analytics_engine
        self.adaptive_engine = adaptive_engine
        self.adaptive_priority_engine = adaptive_priority_engine
        self.transformer_brain = transformer_brain
        self.ai_input_weights = {}
        self.ai_model_oracle = None

        # ==================================================
        # QUANTUM COMPUTATION ENGINE
        # ==================================================

        if quantum_engine is not None:

            self.engine = quantum_engine

        else:

            if QuantumMathEngine is None:

                raise RuntimeError(
                    "[ComputeBrain] "
                    "QuantumMathEngine unavailable"
                )

            self.engine = QuantumMathEngine()

        # ==================================================
        # COMPUTE STATE
        # ==================================================

        self.confidence = 0.0

        self.score = 0.0

        self.samples = 0

        self.compute_count = 0

        self.last_qbit = None

        self.last_decoded = None

        self.last_state = None

        self.last_thought = None

        self.last_error = None

        # ==================================================
        # IDENTITY / LINEAGE STATE
        # ==================================================

        self.last_qbit_id = None

        self.last_track_id = None

        self.last_channel_id = None

        self.last_source = None

        self.last_task_id = None

        # ==================================================
        # HISTORY
        #
        # History is observational/adaptive state only.
        # It does not execute commands.
        # ==================================================

        self.history = deque(
            maxlen=256
        )

    # ======================================================
    # QBIT BINDING
    # ======================================================

    def bind_qbit(
        self,
        qbit,
    ):

        if qbit is None:

            raise ValueError(
                "[ComputeBrain] "
                "Cannot bind None Qbit"
            )

        self.qbit = qbit

        return qbit

    # ======================================================
    # SYSTEM BINDING
    #
    # Existing SEED infrastructure only.
    #
    # No Qbit creation.
    # No queue creation.
    # No runtime creation.
    # ======================================================

    def bind_systems(
        self,
        *,
        event_bus=None,
        track_system=None,
        channel_manager=None,
        channel_control=None,
        action_engine=None,
        intent_engine=None,
        analytics_engine=None,
        adaptive_engine=None,
        adaptive_priority_engine=None,
        transformer_brain=None,
        registry=None,
        encoder=None,
        decoder=None,
        decryptor=None,
    ):

        if event_bus is not None:

            self.event_bus = event_bus

            # ----------------------------------------------
            # EventBus remains authoritative.
            #
            # Only acquire its controller if one was not
            # explicitly injected.
            # ----------------------------------------------

            if (
                channel_control is None
                and self.channel_control is None
            ):

                event_control = getattr(
                    event_bus,
                    "qbit_channel_control",
                    None,
                )

                if event_control is not None:

                    self.channel_control = (
                        event_control
                    )

        if track_system is not None:

            self.track_system = track_system

        if channel_manager is not None:

            self.channel_manager = channel_manager

        if channel_control is not None:

            self.channel_control = (
                channel_control
            )

        if registry is not None:

            self.registry = registry

        if encoder is not None:

            self.encoder = encoder

        if action_engine is not None:
            self.action_engine = action_engine
        if intent_engine is not None:
            self.intent_engine = intent_engine
        if analytics_engine is not None:
            self.analytics_engine = analytics_engine
        if adaptive_engine is not None:
            self.adaptive_engine = adaptive_engine
        if adaptive_priority_engine is not None:
            self.adaptive_priority_engine = adaptive_priority_engine
        if transformer_brain is not None:
            self.transformer_brain = transformer_brain

        if decoder is not None:

            self.decoder = decoder

        if decryptor is not None:

            self.decryptor = decryptor

        return self

    # ======================================================
    # AUTHORITATIVE ENTRY POINT
    # ======================================================

    def receive_qbit(
        self,
        qbit=None,
        **kwargs,
    ):

        active_qbit = (
            qbit
            if qbit is not None
            else self.qbit
        )

        if active_qbit is None:

            raise RuntimeError(
                "[ComputeBrain] "
                "No Qbit available for processing"
            )

        return self.process(
            active_qbit,
            **kwargs,
        )

    # ======================================================
    # PROCESS QBIT
    #
    # AUTHORITATIVE COMPUTE ENTRY.
    #
    # Consumes an existing Qbit.
    #
    # Returns a ThoughtPacket.
    #
    # Does NOT:
    #
    # - submit commands
    # - execute commands
    # - create Qbits
    # - create queues
    # - create runtimes
    # ======================================================

    def bind_ai_input_weights(self, weights, model_oracle=None):
        self.ai_input_weights = dict(weights or {})
        self.ai_model_oracle = model_oracle
        return True

    # ======================================================
    # AI INPUT WEIGHT BINDING
    # ======================================================

    def process(
        self,
        qbit=None,
        **kwargs,
    ):

        active_qbit = (
            qbit
            if qbit is not None
            else self.qbit
        )

        if active_qbit is None:

            raise RuntimeError(
                "[ComputeBrain] "
                "process() requires Qbit"
            )

        # --------------------------------------------------
        # COMPUTE ACCOUNTING
        # --------------------------------------------------

        self.compute_count += 1

        self.last_error = None

        self.last_qbit = active_qbit

        try:

            # ==============================================
            # 1. READ AUTHORITATIVE IDENTITY FIRST
            # ==============================================

            qbit_id = (
                self._field(
                    active_qbit,
                    "qbit_id",
                    None,
                )
                or
                self._field(
                    active_qbit,
                    "id",
                    None,
                )
            )

            track_id = self._field(
                active_qbit,
                "track_id",
                None,
            )

            if track_id is None:

                track = self._field(
                    active_qbit,
                    "track",
                    None,
                )

                if isinstance(
                    track,
                    dict,
                ):

                    track_id = (
                        track.get("track_id")
                        or
                        track.get("id")
                    )

                elif track is not None:

                    track_id = (
                        getattr(
                            track,
                            "track_id",
                            None,
                        )
                        or
                        getattr(
                            track,
                            "id",
                            None,
                        )
                    )

            channel_id = (
                self._field(
                    active_qbit,
                    "channel_id",
                    None,
                )
                or
                self._field(
                    active_qbit,
                    "channel",
                    None,
                )
            )

            source = (
                self._field(
                    active_qbit,
                    "source",
                    None,
                )
                or
                self._field(
                    active_qbit,
                    "origin",
                    "QBIT",
                )
            )

            task = self._field(
                active_qbit,
                "task",
                None,
            )

            task_id = (
                task.get("task_id")
                if isinstance(
                    task,
                    dict,
                )
                else
                self._field(
                    active_qbit,
                    "task_id",
                    None,
                )
            )
        # ==============================================
        # 1A. SEMANTIC QBIT CONTEXT
        #
        # Preserve the SAME Qbit's WHO / WHAT /
        # WHERE / WHY / HOW information.
        #
        # Qbit is authoritative.
        # Task fills missing semantic fields.
        # Nothing is fabricated.
        # ==============================================

            task_context = (
                task
                if isinstance(task, dict)
                else {}
            )

            def _semantic_field(name, *fallbacks):
                value = self._field(
                    active_qbit,
                    name,
                    None,
                )

                if value is not None:
                    return value

                value = task_context.get(
                    name
                )

                if value is not None:
                    return value

                for fallback in fallbacks:
                    value = self._field(
                        active_qbit,
                        fallback,
                        None,
                    )

                    if value is not None:
                        return value

                    value = task_context.get(
                        fallback
                    )

                    if value is not None:
                        return value

                return None

            who = _semantic_field(
                "who",
                "source",
                "origin",
            )

            what = _semantic_field(
                "what",
                "payload",
                "data",
            )

            where = _semantic_field(
                "where",
                "destination",
                "target",
            )

            why = _semantic_field(
                "why",
                "intent",
                "reason",
                "purpose",
            )

            how = _semantic_field(
                "how",
                "action",
                "method",
            )

            self.last_qbit_id = qbit_id

            self.last_track_id = track_id

            self.last_channel_id = channel_id

            self.last_source = source

            self.last_task_id = task_id

            # ==============================================
            # 2. DECODE
            # ==============================================

            decoded = self._decode_qbit(
                active_qbit
            )

            self.last_decoded = decoded

            # ==============================================
            # 3. DECRYPT
            # ==============================================

            decrypted = self._decrypt(
                decoded
            )

            # ==============================================
            # 4. VALIDATE
            # ==============================================

            validated = self._validate(
                decrypted
            )

            # ==============================================
            # 5. NORMALIZE
            # ==============================================

            normalized = self._normalize(
                validated
            )

        # ==============================================
        # 6A. PRESERVE SEMANTIC CONTEXT
        # ==============================================

            if isinstance(
                normalized,
                dict,
            ):

                normalized.setdefault(
                    "who",
                    who,
                )

                normalized.setdefault(
                    "what",
                    what,
                )

                normalized.setdefault(
                    "where",
                    where,
                )

                normalized.setdefault(
                    "why",
                    why,
                )

                normalized.setdefault(
                    "how",
                    how,
                )

                normalized.setdefault(
                    "qbit_context",
                    {
                        "who": who,
                        "what": what,
                        "where": where,
                        "why": why,
                        "how": how,
                    },
                )
            # ==============================================
            # 6. PRESERVE IDENTITY
            # ==============================================

            if isinstance(
                normalized,
                dict,
            ):

                normalized.setdefault(
                    "qbit_id",
                    qbit_id,
                )

                normalized.setdefault(
                    "track_id",
                    track_id,
                )

                normalized.setdefault(
                    "channel_id",
                    channel_id,
                )

                normalized.setdefault(
                    "source",
                    source,
                )

                if task_id is not None:

                    normalized.setdefault(
                        "task_id",
                        task_id,
                    )

            # ==============================================
            # 7. EXTRACT + AUTHORITATIVELY NORMALIZE STATE
            # ==============================================

            state = self._extract_qbit_state(
                normalized
            )

            self.last_state = state

            # ==============================================
            # 8. QUANTUM COMPUTATION
            #
            # IMPORTANT:
            #
            # `state` is ALWAYS a normalized
            # `(alpha, beta)` tuple here.
            # ==============================================

            probabilities = (
                self.engine.state_probability(
                    state
                )
            )

            magnitude = (
                self.engine.state_magnitude(
                    state
                )
            )

            resonance = (
                self.engine.resonance(
                    state
                )
            )

            # ==============================================
            # 9. IDENTITY / CHANNEL / TRACK
            # ==============================================

            identity = self._identify(
                active_qbit,
                normalized,
            )

            # ==============================================
            # 10. CLASSIFY
            # ==============================================

            classification = (
                self._classify(
                    state,
                    probabilities,
                )
            )

            # ==============================================
            # 11. LABEL
            # ==============================================

            labeled = self._label(
                normalized,
                identity,
                classification,
            )

            # ==============================================
            # 12. AGGREGATE
            # ==============================================

            aggregate = self._aggregate(
                labeled,
                probabilities,
                magnitude,
                resonance,
            )

            # ==============================================
            # 13. SCORE
            # ==============================================

            self.score = (
                self._compute_score(
                    aggregate
                )
            )

            # ==============================================
            # 14. CONFIDENCE
            # ==============================================

            self.confidence = (
                self._compute_confidence(
                    aggregate,
                    resonance,
                )
            )

            # ==============================================
            # 14A. STRUCTURED COGNITIVE INPUT
            #
            # Every downstream engine contributes named context.
            # The encoder receives the same canonical context so
            # transport representation cannot silently diverge
            # from the ThoughtPacket.
            # ==============================================

            def _component_state(component):
                if component is None:
                    return None
                for method_name in ("status", "snapshot", "get_state"):
                    method = getattr(component, method_name, None)
                    if callable(method):
                        try:
                            value = method()
                            if isinstance(value, dict):
                                return value
                        except Exception:
                            pass
                return {"type": type(component).__name__}

            cognitive_context = {
                "qbit_id": qbit_id,
                "task_id": task_id,
                "track_id": track_id,
                "channel_id": channel_id,
                "semantic": {
                    "who": who,
                    "what": what,
                    "where": where,
                    "why": why,
                    "how": how,
                },
                "normalized": normalized,
                "classification": classification,
                "identity": identity,
                "action_engine": _component_state(self.action_engine),
                "intent_engine": _component_state(self.intent_engine),
                "analytics_engine": _component_state(self.analytics_engine),
                "adaptive_engine": _component_state(self.adaptive_engine),
                "adaptive_priority_engine": _component_state(self.adaptive_priority_engine),
                "transformer_brain": _component_state(self.transformer_brain),
            }

            # ==============================================
            # 14B. THREE-BRANCH SEED AI INPUT WEIGHTING
            # ==============================================
            weight_factors = (
                self.ai_input_weights.get("weight_factors", {})
                if isinstance(self.ai_input_weights, dict)
                else {}
            )
            ai_weight_factor = float(
                weight_factors.get("combined_compute_weight", 1.0) or 1.0
            )
            ai_weight_factor = max(0.0, min(1.0, ai_weight_factor))
            cognitive_context["seed_ai_input_weights"] = dict(
                self.ai_input_weights
            )
            cognitive_context["seed_ai_compute_weight"] = ai_weight_factor
            aggregate["seed_ai_compute_weight"] = ai_weight_factor

            encoded_payload = None
            if self.encoder is not None:
                try:
                    encoded_payload = self.encoder.encode(
                        active_qbit,
                        metadata=cognitive_context,
                    )
                except Exception as exc:
                    self.last_error = f"Encoder: {type(exc).__name__}: {exc}"

            # ==============================================
            # 15. THOUGHT PACKET
            # ==============================================

            thought = {
                "type": "ThoughtPacket",
                "version": self.VERSION,
                "qbit": active_qbit,
                "qbit_id": qbit_id,
                "task_id": task_id,
                "track_id": track_id,
                "channel_id": channel_id,
                "source": identity["source"],
                "channel": identity["channel"],
                "track": identity["track"],
                "decoded": decoded,
                "normalized": normalized,
                "state": {
                    "alpha": state[0],
                    "beta": state[1],
                },
                "probability": probabilities,
                "magnitude": magnitude,
                "resonance": resonance,
                "classification": classification,
                "label": labeled["label"],
                "identity": identity,
                "aggregate": aggregate,
                "cognitive_context": cognitive_context,
                "encoding": {
                    "enabled": self.encoder is not None,
                    "encoded": encoded_payload is not None,
                    "bytes": len(encoded_payload) if encoded_payload is not None else 0,
                },
                "score": self.score,
                "confidence": self.confidence,
                "organized": True,
                "stage": "COMPUTE_COMPLETE",

                "encoder_context": {
                    "qbit": active_qbit,
                    "qbit_id": qbit_id,
                    "task_id": task_id,
                    "track_id": track_id,
                    "channel_id": channel_id,
                    "source": source,
                    "who": who,
                    "what": what,
                    "where": where,
                    "why": why,
                    "how": how,
                    "state": {
                        "alpha": state[0],
                        "beta": state[1],
                    },
                    "classification": classification,
                    "intent": self._field(
                        active_qbit,
                        "intent",
                        task_context.get("intent"),
                    ),
                    "action": self._field(
                        active_qbit,
                        "action",
                        task_context.get("action"),
                    ),
                    "payload": normalized,
                },
            }

            # ==============================================
            # 16. RELATIONSHIP METADATA
            # ==============================================

            thought["relationships"] = {
                "qbit_id": qbit_id,
                "task_id": task_id,
                "track_id": track_id,
                "channel_id": channel_id,
                "source": source,
                "processor": self.name,
                "command_authority": "QbitDialer",
            }

            # ==============================================
            # 17. DATA LINEAGE
            # ==============================================

            thought["data_lineage"] = {

                "created_by": "QBIT",

                "source": source,

                "qbit_id": qbit_id,

                "task_id": task_id,

                "track_id": track_id,

                "channel_id": channel_id,

                "processor": "ComputeBrain",

                "next_stage": "TransformerBrain",

            }

            # ==============================================
            # 18. STORE STATE
            # ==============================================

            self.samples += 1

            self.last_thought = thought

            self.history.append(
                thought
            )

            return thought

        except Exception as exc:

            self.last_error = (
                f"{type(exc).__name__}: {exc}"
            )

            raise

    # ======================================================
    # DECODE
    # ======================================================

    def _decode_qbit(
        self,
        qbit,
    ):

        if self.decoder is not None:

            method = getattr(
                self.decoder,
                "decode",
                None,
            )

            if callable(method):

                return method(
                    qbit
                )

        if isinstance(
            qbit,
            dict,
        ):

            return dict(qbit)

        for method_name in (
            "to_dict",
            "get_state",
            "serialize",
        ):

            method = getattr(
                qbit,
                method_name,
                None,
            )

            if callable(method):

                try:

                    result = method()

                    if result is not None:

                        return result

                except Exception:

                    continue

        return qbit

    # ======================================================
    # DECRYPT
    # ======================================================

    def _decrypt(
        self,
        data,
    ):

        if self.decryptor is None:

            return data

        method = getattr(
            self.decryptor,
            "decrypt",
            None,
        )

        if not callable(method):

            return data

        return method(
            data
        )

    # ======================================================
    # VALIDATE
    # ======================================================

    def _validate(
        self,
        data,
    ):

        if data is None:

            raise ValueError(
                "[ComputeBrain] "
                "Decoded Qbit produced None"
            )

        return data

    # ======================================================
    # NORMALIZE DATA
    # ======================================================

    def _normalize(
        self,
        data,
    ):

        if isinstance(
            data,
            dict,
        ):

            return dict(data)

        if isinstance(
            data,
            (list, tuple),
        ):

            return {

                f"value_{index}": value

                for index, value
                in enumerate(data)

            }

        return {
            "value": data
        }

    # ======================================================
    # EXTRACT QBIT STATE
    #
    # ONE NORMALIZATION BOUNDARY
    #
    # Everything entering the quantum math engine must
    # leave this method as exactly:
    #
    #     (complex alpha, complex beta)
    #
    # This prevents the historical:
    #
    #     TypeError: cannot unpack alpha, beta
    #
    # failure.
    # ======================================================

    def _extract_qbit_state(
        self,
        qbit,
    ):

        if qbit is None:

            return self.normalize_qbit_input(
                None
            )

        state_input = qbit

        if isinstance(
            qbit,
            dict,
        ):

            if "state" in qbit:

                state_input = qbit[
                    "state"
                ]

            elif "qbit" in qbit:

                state_input = qbit[
                    "qbit"
                ]

            elif (
                "alpha" in qbit
                or
                "beta" in qbit
            ):

                state_input = {

                    "alpha": qbit.get(
                        "alpha",
                        0.0 + 0.0j,
                    ),

                    "beta": qbit.get(
                        "beta",
                        0.0 + 0.0j,
                    ),

                }

        else:

            state = getattr(
                qbit,
                "state",
                None,
            )

            if state is not None:

                state_input = state

            elif (
                hasattr(
                    qbit,
                    "alpha",
                )
                or
                hasattr(
                    qbit,
                    "beta",
                )
            ):

                state_input = {

                    "alpha": getattr(
                        qbit,
                        "alpha",
                        0.0 + 0.0j,
                    ),

                    "beta": getattr(
                        qbit,
                        "beta",
                        0.0 + 0.0j,
                    ),

                }

        return self.normalize_qbit_input(
            state_input
        )

    # ======================================================
    # QBIT STATE NORMALIZATION
    #
    # ComputeBrain owns the boundary normalization.
    #
    # QuantumMathEngine may expose the same mathematical
    # operation, but ComputeBrain guarantees the value
    # passed into the engine is already canonical.
    # ======================================================

    @staticmethod
    def normalize_qbit_input(
        state_input: Any,
    ) -> Tuple[complex, complex]:

        if state_input is None:

            state_input = (
                1.0 / math.sqrt(2.0),
                1.0 / math.sqrt(2.0),
            )

        elif isinstance(
            state_input,
            (int, float, complex),
        ):

            state_input = (
                complex(state_input),
                0.0 + 0.0j,
            )

        elif isinstance(
            state_input,
            dict,
        ):

            if (
                "alpha" in state_input
                or
                "beta" in state_input
            ):

                state_input = (

                    complex(
                        state_input.get(
                            "alpha",
                            0.0 + 0.0j,
                        )
                    ),

                    complex(
                        state_input.get(
                            "beta",
                            0.0 + 0.0j,
                        )
                    ),

                )

            elif "state" in state_input:

                return ComputeBrain.normalize_qbit_input(
                    state_input[
                        "state"
                    ]
                )

            elif "qbit" in state_input:

                return ComputeBrain.normalize_qbit_input(
                    state_input[
                        "qbit"
                    ]
                )

            else:

                raise ValueError(
                    "[ComputeBrain] "
                    "Dictionary does not contain "
                    "a recognizable Qbit state"
                )

        elif isinstance(
            state_input,
            (list, tuple),
        ):

            if len(state_input) == 0:

                state_input = (
                    1.0 / math.sqrt(2.0),
                    1.0 / math.sqrt(2.0),
                )

            elif len(state_input) == 1:

                state_input = (
                    state_input[0],
                    0.0 + 0.0j,
                )

            else:

                state_input = (
                    state_input[0],
                    state_input[1],
                )

        else:

            # --------------------------------------------------
            # Object-level state fallback.
            # --------------------------------------------------

            state = getattr(
                state_input,
                "state",
                None,
            )

            if state is not None:

                return ComputeBrain.normalize_qbit_input(
                    state
                )

            if (
                hasattr(
                    state_input,
                    "alpha",
                )
                or
                hasattr(
                    state_input,
                    "beta",
                )
            ):

                return ComputeBrain.normalize_qbit_input(

                    {

                        "alpha": getattr(
                            state_input,
                            "alpha",
                            0.0 + 0.0j,
                        ),

                        "beta": getattr(
                            state_input,
                            "beta",
                            0.0 + 0.0j,
                        ),

                    }

                )

            raise ValueError(
                "[ComputeBrain] Cannot convert "
                f"{type(state_input)!r} "
                "to Qbit state"
            )

        # ------------------------------------------------------
        # FINAL CANONICAL CONVERSION
        # ------------------------------------------------------

        try:

            alpha = complex(
                state_input[0]
            )

            beta = complex(
                state_input[1]
            )

        except (
            TypeError,
            ValueError,
            IndexError,
            KeyError,
        ) as exc:

            raise ValueError(
                "[ComputeBrain] Invalid Qbit state; "
                "expected alpha/beta pair"
            ) from exc

        # ------------------------------------------------------
        # NORMALIZATION
        # ------------------------------------------------------

        norm = math.sqrt(
            abs(alpha) ** 2
            +
            abs(beta) ** 2
        )

        if not math.isfinite(norm):

            raise ValueError(
                "[ComputeBrain] "
                "Qbit state norm is not finite"
            )

        if norm <= 0.0:

            alpha = (
                1.0 / math.sqrt(2.0)
            )

            beta = (
                1.0 / math.sqrt(2.0)
            )

            norm = 1.0

        return (
            alpha / norm,
            beta / norm,
        )

    # ======================================================
    # IDENTITY
    # ======================================================

    def _identify(
        self,
        qbit,
        data,
    ):

        source = self._field(
            qbit,
            "source",
            None,
        )

        if source is None:

            source = self._field(
                qbit,
                "origin",
                None,
            )

        if source is None:

            source = self._field(
                data,
                "source",
                None,
            )

        if source is None:

            source = self._field(
                data,
                "origin",
                None,
            )

        if source is None:

            source = "QBIT"

        # --------------------------------------------------
        # CHANNEL
        # --------------------------------------------------

        channel = self._field(
            qbit,
            "channel_id",
            None,
        )

        if channel is None:

            channel = self._field(
                qbit,
                "channel",
                None,
            )

        if channel is None:

            channel = self._field(
                data,
                "channel_id",
                None,
            )

        if channel is None:

            channel = self._field(
                data,
                "channel",
                None,
            )

        if channel is None:

            channel = "QBIT"

        # --------------------------------------------------
        # TRACK
        # --------------------------------------------------

        track = self._field(
            qbit,
            "track_id",
            None,
        )

        if track is None:

            track = self._field(
                qbit,
                "track",
                None,
            )

        if track is None:

            track = self._field(
                data,
                "track_id",
                None,
            )

        if track is None:

            track = self._field(
                data,
                "track",
                None,
            )

        return {

            "source": source,

            "channel": channel,

            "track": track,

            "qbit_id": self._field(
                qbit,
                "qbit_id",
                self._field(
                    qbit,
                    "id",
                    None,
                ),
            ),

            "track_id": track,

            "channel_id": channel,

        }

    # ======================================================
    # FIELD
    # ======================================================

    @staticmethod
    def _field(
        obj,
        name,
        default=None,
    ):

        if isinstance(
            obj,
            dict,
        ):

            return obj.get(
                name,
                default,
            )

        return getattr(
            obj,
            name,
            default,
        )

    # ======================================================
    # CLASSIFICATION
    # ======================================================

    def _classify(
        self,
        state,
        probabilities,
    ):

        alpha_probability = float(
            probabilities.get(
                "alpha_probability",
                0.0,
            )
        )

        beta_probability = float(
            probabilities.get(
                "beta_probability",
                0.0,
            )
        )

        if alpha_probability >= 0.90:

            return "ALPHA_DOMINANT"

        if beta_probability >= 0.90:

            return "BETA_DOMINANT"

        return "SUPERPOSITION"

    # ======================================================
    # LABEL
    # ======================================================

    def _label(
        self,
        data,
        identity,
        classification,
    ):

        label = None

        if isinstance(
            data,
            dict,
        ):

            label = (
                data.get("label")
                or
                data.get("intent")
            )

        if not label:

            label = (
                f"{classification}:"
                f"{identity['source']}"
            )

        return {

            "data": data,

            "label": label,

            "source": identity[
                "source"
            ],

            "channel": identity[
                "channel"
            ],

            "track": identity[
                "track"
            ],

        }

    # ======================================================
    # AGGREGATE
    # ======================================================

    def _aggregate(
        self,
        labeled,
        probabilities,
        magnitude,
        resonance,
    ):

        values = []

        payload = labeled.get(
            "data",
            {},
        )

        if isinstance(
            payload,
            dict,
        ):

            for value in payload.values():

                if isinstance(
                    value,
                    bool,
                ):

                    values.append(
                        1.0
                        if value
                        else 0.0
                    )

                elif isinstance(
                    value,
                    (int, float),
                ):

                    values.append(
                        float(value)
                    )

        return {

            "numeric_values": values,

            "count": len(values),

            "label": labeled.get(
                "label"
            ),

            "source": labeled.get(
                "source"
            ),

            "channel": labeled.get(
                "channel"
            ),

            "track": labeled.get(
                "track"
            ),

            "probability": probabilities,

            "magnitude": magnitude,

            "resonance": resonance,

        }

    # ======================================================
    # SCORE
    # ======================================================

    def _compute_score(
        self,
        aggregate,
    ):

        values = aggregate.get(
            "numeric_values",
            [],
        )

        if not values:

            return 0.0

        normalized = []

        for value in values:

            magnitude = abs(
                float(value)
            )

            if magnitude > 1.0:

                magnitude = (
                    magnitude
                    /
                    (
                        1.0
                        +
                        magnitude
                    )
                )

            normalized.append(
                max(
                    0.0,
                    min(
                        1.0,
                        magnitude,
                    ),
                )
            )

        return (
            sum(normalized)
            /
            len(normalized)
        )

    # ======================================================
    # CONFIDENCE
    # ======================================================

    def _compute_confidence(
        self,
        aggregate,
        resonance,
    ):

        count = aggregate.get(
            "count",
            0,
        )

        signal_confidence = min(
            1.0,
            count / 8.0,
        )

        try:

            resonance_value = abs(
                float(resonance)
            )

        except (
            TypeError,
            ValueError,
        ):

            resonance_value = 0.0

        resonance_confidence = min(
            1.0,
            resonance_value,
        )

        confidence = (

            self.score * 0.50

            +

            signal_confidence * 0.20

            +

            resonance_confidence * 0.30

        )

        return max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

    # ======================================================
    # ADAPT
    #
    # Feedback modifies cognitive state only.
    #
    # It does NOT submit or execute commands.
    # ======================================================

    def adapt(
        self,
        feedback=None,
    ):

        if feedback is None:

            return self.last_thought

        try:

            adjustment = float(
                feedback
            )

        except (
            TypeError,
            ValueError,
        ):

            return self.last_thought

        self.confidence = max(
            0.0,
            min(
                1.0,
                self.confidence
                +
                adjustment,
            ),
        )

        if self.last_thought is not None:

            self.last_thought[
                "confidence"
            ] = self.confidence

        return self.last_thought

    # ======================================================
    # STATE
    # ======================================================

    def get_state(
        self,
    ):

        return {

            "brain": self.name,

            "role": "ComputeBrain",

            "version": self.VERSION,

            "qbit_bound": (
                self.qbit is not None
            ),

            "channel_control_bound": (
                self.channel_control is not None
            ),

            "event_bus_bound": (
                self.event_bus is not None
            ),

            "compute_count": (
                self.compute_count
            ),

            "samples": self.samples,

            "score": self.score,

            "confidence": self.confidence,

            "last_qbit": self.last_qbit,

            "last_qbit_id": self.last_qbit_id,

            "last_task_id": self.last_task_id,

            "last_track_id": self.last_track_id,

            "last_channel_id": (
                self.last_channel_id
            ),

            "last_source": self.last_source,

            "last_thought": self.last_thought,

            "last_error": self.last_error,

        }


# ==========================================================
# MODULE REGISTRATION
# ==========================================================

try:

    register_module(
        "ComputeBrain",
        ComputeBrain,
    )

except Exception:

    pass