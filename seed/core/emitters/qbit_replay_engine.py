# ========================================================================
# FILE: qbit_replay_engine.py
#
# PURPOSE:
#   Replay persisted Qbit states through the AUTHORITATIVE QbitQueueLoop.
#
# ROLE:
#   Persistence / replay / rewind INPUT ADAPTER.
#
# ARCHITECTURE:
#
#   Persisted State
#        ↓
#   QbitReplayEngine
#        ↓
#   Replay Admission Metadata
#        ↓
#   AUTHORITATIVE QbitQueueLoop
#        ↓
#   AUTHORITATIVE Qbit Runtime
#        ↓
#   QbitDialer
#        ↓
#   ComputeBrain / TransformerBrain / Ethics
#        ↓
#   Authorized Execution
#        ↓
#   Result / Feedback / History
#        ↓
#   New Generation
#
# HARD RULES:
#
#   - NEVER construct a Qbit.
#   - NEVER replace the authoritative Qbit.
#   - NEVER create another queue.
#   - NEVER create another QbitQueueLoop.
#   - NEVER create another runtime loop.
#   - NEVER call dialer.receive_qbit() for replay.
#   - NEVER execute commands directly.
#   - NEVER bypass QbitDialer command authority.
#   - NEVER bypass QbitQueueLoop admission.
#   - NEVER treat a new replay/feedback generation as a duplicate merely
#     because it originated from the same parent Qbit.
#
# REPLAY IS AN INPUT INTO THE EXISTING RUNTIME.
#
# ========================================================================

from __future__ import annotations

import asyncio
import glob
import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


logger = logging.getLogger("QbitReplayEngine")


class QbitReplayEngine:

    VERSION = "6.0.0"

    REPLAY_TYPE = "QBIT_REPLAY"
    REWIND_TYPE = "QBIT_REWIND"

    ROLE = "persistence_replay_input_adapter"

    # ------------------------------------------------------------------
    # CONSTRUCTOR
    # ------------------------------------------------------------------

    def __init__(
        self,
        dialer=None,
        qbit_queue=None,
        qbit_loop=None,
        state_path="C:/SEED_ROOT/seed/qbit_states",
        event_bus=None,
        track_system=None,
        registry=None,
        oracle=None,
        ethics=None,
        adim_manager=None,
        compute_brain=None,
        transformer_brain=None,
        seed_core=None,
    ):

        self.dialer = dialer
        self.event_bus = event_bus
        self.track_system = track_system
        self.registry = registry
        self.oracle = oracle
        self.ethics = ethics
        self.adim_manager = adim_manager
        self.compute_brain = compute_brain
        self.transformer_brain = transformer_brain
        self.seed_core = seed_core

        self.state_path = Path(state_path)

        # --------------------------------------------------------------
        # Authoritative transport.
        #
        # Never construct a queue here.
        # --------------------------------------------------------------

        if (
            qbit_queue is not None
            and qbit_loop is not None
            and qbit_queue is not qbit_loop
        ):
            raise RuntimeError(
                "[QbitReplayEngine] "
                "qbit_queue and qbit_loop must reference "
                "the SAME authoritative QbitQueueLoop instance"
            )

        self.qbit_loop = (
            qbit_loop
            if qbit_loop is not None
            else qbit_queue
        )

        self.qbit_queue = self.qbit_loop

        # --------------------------------------------------------------
        # Replay state.
        # --------------------------------------------------------------

        self.replay_count = 0
        self.rewind_count = 0

        self.last_replayed_state = None
        self.last_replay_admission = None
        self.last_error = None

        # --------------------------------------------------------------
        # Admission identity.
        #
        # This is deliberately NOT only qbit_id.
        #
        # The same parent Qbit may legitimately produce:
        #
        #   replay generation 1
        #   feedback generation 2
        #   learning generation 3
        #
        # without those being duplicates.
        # --------------------------------------------------------------

        self._submitted_admissions: Set[str] = set()

        # Prevent unbounded local memory growth.
        self._max_admission_history = 10000

        # --------------------------------------------------------------
        # Lifecycle.
        # --------------------------------------------------------------

        self._attached = self.qbit_loop is not None
        self._started = False
        self._stopped = False

        logger.info(
            "[QbitReplayEngine] Initialized | version=%s | "
            "queue=%s | dialer=%s | event_bus=%s | track_system=%s | "
            "registry=%s | oracle=%s | ethics=%s",
            self.VERSION,
            type(self.qbit_loop).__name__
            if self.qbit_loop is not None
            else "NONE",
            type(self.dialer).__name__
            if self.dialer is not None
            else "NONE",
            type(self.event_bus).__name__
            if self.event_bus is not None
            else "NONE",
            type(self.track_system).__name__
            if self.track_system is not None
            else "NONE",
            type(self.registry).__name__
            if self.registry is not None
            else "NONE",
            type(self.oracle).__name__
            if self.oracle is not None
            else "NONE",
            type(self.ethics).__name__
            if self.ethics is not None
            else "NONE",
        )

    # ==================================================================
    # AUTHORITATIVE QUEUE ATTACHMENT
    # ==================================================================

    def attach_queue(self, qbit_queue):

        if qbit_queue is None:
            raise ValueError(
                "[QbitReplayEngine] "
                "authoritative QbitQueueLoop is required"
            )

        # --------------------------------------------------------------
        # Never silently replace a different authoritative instance.
        # --------------------------------------------------------------

        if (
            self.qbit_loop is not None
            and self.qbit_loop is not qbit_queue
        ):
            raise RuntimeError(
                "[QbitReplayEngine] "
                "Refusing to replace existing authoritative "
                "QbitQueueLoop instance"
            )

        self.qbit_loop = qbit_queue
        self.qbit_queue = qbit_queue
        self._attached = True

        logger.info(
            "[QbitReplayEngine] "
            "AUTHORITATIVE QbitQueueLoop attached | "
            "instance=%s | type=%s",
            id(qbit_queue),
            type(qbit_queue).__name__,
        )

        self._emit_event(
            "QBIT_REPLAY_QUEUE_ATTACHED",
            {
                "component": "QbitReplayEngine",
                "queue_type": type(qbit_queue).__name__,
                "queue_instance": id(qbit_queue),
            },
        )

        return self

    # ==================================================================
    # SYSTEM ATTACHMENT
    # ==================================================================

    def attach_systems(
        self,
        *,
        dialer=None,
        event_bus=None,
        track_system=None,
        registry=None,
        oracle=None,
        ethics=None,
        adim_manager=None,
        compute_brain=None,
        transformer_brain=None,
        seed_core=None,
    ):
        if dialer is not None:
            self.dialer = dialer

        if event_bus is not None:
            self.event_bus = event_bus

        if track_system is not None:
            self.track_system = track_system

        if registry is not None:
            self.registry = registry

        if oracle is not None:
            self.oracle = oracle

        if ethics is not None:
            self.ethics = ethics

        if adim_manager is not None:
            self.adim_manager = adim_manager

        if compute_brain is not None:
            self.compute_brain = compute_brain

        if transformer_brain is not None:
            self.transformer_brain = transformer_brain

        if seed_core is not None:
            self.seed_core = seed_core

        logger.info(
            "[QbitReplayEngine] System references synchronized | "
            "dialer=%s | event_bus=%s | track=%s | registry=%s | "
            "oracle=%s | ethics=%s | adim=%s | compute=%s | "
            "transformer=%s",
            bool(self.dialer),
            bool(self.event_bus),
            bool(self.track_system),
            bool(self.registry),
            bool(self.oracle),
            bool(self.ethics),
            bool(self.adim_manager),
            bool(self.compute_brain),
            bool(self.transformer_brain),
        )

        self._emit_event(
            "QBIT_REPLAY_SYSTEMS_ATTACHED",
            self.system_snapshot(),
        )

        return self

    # ==================================================================
    # SYSTEM SNAPSHOT
    # ==================================================================

    def system_snapshot(self) -> Dict[str, Any]:
        return {
            "component": "QbitReplayEngine",
            "version": self.VERSION,
            "role": self.ROLE,
            "attached": self._attached,
            "started": self._started,
            "stopped": self._stopped,
            "authoritative_queue": (
                type(self.qbit_loop).__name__
                if self.qbit_loop is not None
                else None
            ),
            "authoritative_queue_instance": (
                id(self.qbit_loop)
                if self.qbit_loop is not None
                else None
            ),
            "dialer": bool(self.dialer),
            "event_bus": bool(self.event_bus),
            "track_system": bool(self.track_system),
            "registry": bool(self.registry),
            "oracle": bool(self.oracle),
            "ethics": bool(self.ethics),
            "adim_manager": bool(self.adim_manager),
            "compute_brain": bool(self.compute_brain),
            "transformer_brain": bool(self.transformer_brain),
            "seed_core": bool(self.seed_core),
            "replay_count": self.replay_count,
            "rewind_count": self.rewind_count,
            "submitted_admissions": len(
                self._submitted_admissions
            ),
        }

    # ==================================================================
    # VALIDATION
    # ==================================================================

    def validate_authority(self) -> bool:

        if self.qbit_loop is None:
            logger.error(
                "[QbitReplayEngine] "
                "No authoritative QbitQueueLoop attached"
            )
            return False

        queue_loop = self.qbit_loop

        # --------------------------------------------------------------
        # If the QueueLoop exposes an authoritative marker, honor it.
        # --------------------------------------------------------------

        authoritative = getattr(
            queue_loop,
            "authoritative",
            None,
        )

        if authoritative is False:
            logger.error(
                "[QbitReplayEngine] "
                "Attached QbitQueueLoop explicitly reports "
                "authoritative=False"
            )
            return False

        # --------------------------------------------------------------
        # If the loop exposes a singleton/current-instance accessor,
        # verify identity when possible.
        # --------------------------------------------------------------

        for attr_name in (
            "authoritative_instance",
            "_authoritative_instance",
        ):
            candidate = getattr(
                queue_loop,
                attr_name,
                None,
            )

            if candidate is not None and candidate is not queue_loop:
                logger.error(
                    "[QbitReplayEngine] "
                    "QueueLoop authority mismatch | "
                    "candidate=%s | attached=%s",
                    id(candidate),
                    id(queue_loop),
                )
                return False

        # --------------------------------------------------------------
        # Do NOT accept raw queue.Queue as the runtime authority.
        #
        # This specifically protects against the SEEDCore problem where
        # a plain queue.Queue was being late-bound into QbitDialer.
        # --------------------------------------------------------------

        type_name = type(queue_loop).__name__

        if type_name == "Queue":
            logger.error(
                "[QbitReplayEngine] "
                "Plain queue.Queue cannot be authoritative transport"
            )
            return False

        # --------------------------------------------------------------
        # The authoritative loop needs an actual submission surface.
        #
        # receive_qbit is preferred because it represents the Qbit
        # admission boundary rather than direct raw queue insertion.
        # --------------------------------------------------------------

        supported = any(
            callable(
                getattr(
                    queue_loop,
                    name,
                    None,
                )
            )
            for name in (
                "receive_qbit",
                "admit_qbit",
                "submit_qbit",
            )
        )

        if not supported:
            logger.error(
                "[QbitReplayEngine] "
                "Authoritative QbitQueueLoop exposes no "
                "supported Qbit admission API"
            )
            return False

        return True

    # ==================================================================
    # LIFECYCLE
    # ==================================================================

    def start(self) -> bool:

        if self._stopped:
            return False

        if not self.validate_authority():
            return False

        self._started = True

        logger.info(
            "[QbitReplayEngine] READY | "
            "authoritative QueueLoop validated"
        )

        self._emit_event(
            "QBIT_REPLAY_ENGINE_READY",
            self.system_snapshot(),
        )

        return True

    def stop(self) -> None:

        self._stopped = True
        self._started = False

        logger.info(
            "[QbitReplayEngine] stopped | "
            "authoritative runtime remains untouched"
        )

        self._emit_event(
            "QBIT_REPLAY_ENGINE_STOPPED",
            self.system_snapshot(),
        )

    # ==================================================================
    # STATE DISCOVERY
    # ==================================================================

    def load_states(self) -> List[Dict[str, Any]]:

        if not self.state_path.exists():
            logger.info(
                "[QbitReplayEngine] "
                "State directory does not exist | path=%s",
                self.state_path,
            )
            return []

        files = sorted(
            glob.glob(
                str(
                    self.state_path / "qbit_*.json"
                )
            ),
            key=lambda file_path: Path(
                file_path
            ).stat().st_mtime,
        )

        states: List[Dict[str, Any]] = []

        for file_path in files:
            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8",
                ) as fh:
                    state = json.load(fh)

                if isinstance(state, dict):
                    state.setdefault(
                        "_replay_source_file",
                        file_path,
                    )
                    states.append(state)

            except Exception as exc:
                logger.error(
                    "[QbitReplayEngine] "
                    "Unable to load state '%s' | %s",
                    file_path,
                    exc,
                    exc_info=True,
                )

        logger.info(
            "[QbitReplayEngine] "
            "Loaded persisted states | count=%s",
            len(states),
        )

        return states

    # ==================================================================
    # REPLAY
    # ==================================================================

    def replay(
        self,
        limit=None,
    ) -> int:

        self._ensure_ready()

        states = self.load_states()

        if limit is not None:
            try:
                limit = int(limit)
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Replay limit must be an integer"
                ) from exc

            if limit > 0:
                states = states[-limit:]

        replayed = 0

        for state in states:
            result = self._enqueue_state(
                state,
                replay_reason="persisted_replay",
            )

            if result is True:
                replayed += 1

        self.replay_count += replayed

        if states:
            self.last_replayed_state = states[-1]

        logger.info(
            "[QbitReplayEngine] "
            "Replay complete | queued=%s | total=%s",
            replayed,
            self.replay_count,
        )

        return replayed

    # ==================================================================
    # ASYNC REPLAY
    # ==================================================================

    async def replay_async(
        self,
        limit=None,
    ) -> int:

        self._ensure_ready()

        states = self.load_states()

        if limit is not None:
            try:
                limit = int(limit)
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Replay limit must be an integer"
                ) from exc

            if limit > 0:
                states = states[-limit:]

        replayed = 0

        for state in states:
            result = await self._enqueue_state_async(
                state,
                replay_reason="persisted_replay",
            )

            if result:
                replayed += 1

        self.replay_count += replayed

        if states:
            self.last_replayed_state = states[-1]

        logger.info(
            "[QbitReplayEngine] "
            "Async replay complete | queued=%s | total=%s",
            replayed,
            self.replay_count,
        )

        return replayed

    # ==================================================================
    # REWIND
    # ==================================================================

    def rewind(
        self,
        steps=10,
    ):

        self._ensure_ready()

        states = self.load_states()

        if not states:
            logger.info(
                "[QbitReplayEngine] "
                "No persisted states available for rewind"
            )
            return None

        try:
            steps = int(steps)
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Rewind steps must be an integer"
            ) from exc

        if steps < 1:
            steps = 1

        if len(states) <= steps:
            rewind_state = states[0]
        else:
            rewind_state = states[-steps]

        queued = self._enqueue_state(
            rewind_state,
            replay_reason="rewind",
        )

        if queued is True:
            self.rewind_count += 1
            self.last_replayed_state = rewind_state

            logger.info(
                "[QbitReplayEngine] "
                "Rewind queued | steps=%s | rewind_count=%s",
                steps,
                self.rewind_count,
            )

            return rewind_state

        return None

    # ==================================================================
    # BUILD REPLAY PAYLOAD
    # ==================================================================

    def _build_replay_payload(
        self,
        state: Dict[str, Any],
        replay_reason: str = "persisted_replay",
    ) -> Dict[str, Any]:

        parent_qbit_id = state.get(
            "qbit_id"
        )

        parent_track_id = state.get(
            "track_id"
        )

        parent_task_id = state.get(
            "task_id"
        )

        parent_lineage = state.get(
            "lineage",
            state.get(
                "metadata",
                {},
            ).get(
                "lineage"
            ),
        )

        parent_generation = self._extract_generation(
            state
        )

        cycle_id = self._new_cycle_id(
            parent_qbit_id=parent_qbit_id,
            reason=replay_reason,
        )

        replay_id = self._new_replay_id(
            parent_qbit_id=parent_qbit_id,
            cycle_id=cycle_id,
        )

        generation = parent_generation + 1

        admission_id = self._build_admission_id(
            parent_qbit_id=parent_qbit_id,
            replay_id=replay_id,
            generation=generation,
            cycle_id=cycle_id,
            reason=replay_reason,
        )

        payload = {
            # ----------------------------------------------------------
            # Admission identity.
            # ----------------------------------------------------------

            "type": (
                self.REWIND_TYPE
                if replay_reason == "rewind"
                else self.REPLAY_TYPE
            ),
            "source": "QbitReplayEngine",

            "replay": True,
            "rewind": (
                replay_reason == "rewind"
            ),

            "replay_id": replay_id,
            "admission_id": admission_id,
            "cycle_id": cycle_id,

            # ----------------------------------------------------------
            # Lineage.
            # ----------------------------------------------------------

            "parent_qbit_id": parent_qbit_id,
            "parent_task_id": parent_task_id,
            "parent_track_id": parent_track_id,

            "qbit_id": parent_qbit_id,

            "generation": generation,
            "parent_generation": parent_generation,

            "lineage": self._build_lineage(
                state=state,
                parent_lineage=parent_lineage,
                parent_qbit_id=parent_qbit_id,
                generation=generation,
                cycle_id=cycle_id,
                replay_id=replay_id,
                replay_reason=replay_reason,
            ),

            # ----------------------------------------------------------
            # Cognitive input.
            # ----------------------------------------------------------

            "intent": state.get(
                "intent"
            ),

            "payload": state.get(
                "payload"
            ),

            "command_list": list(
                state.get(
                    "command_list",
                    [],
                )
                or []
            ),

            # ----------------------------------------------------------
            # Persisted source state.
            # ----------------------------------------------------------

            "metadata": dict(
                state.get(
                    "metadata",
                    {},
                )
                or {}
            ),

            "state": state,

            # ----------------------------------------------------------
            # Replay control metadata.
            #
            # These are INPUT annotations.
            #
            # They do not authorize execution.
            # ----------------------------------------------------------

            "replay_context": {
                "engine": "QbitReplayEngine",
                "engine_version": self.VERSION,
                "reason": replay_reason,
                "replay_id": replay_id,
                "admission_id": admission_id,
                "cycle_id": cycle_id,
                "parent_qbit_id": parent_qbit_id,
                "generation": generation,
                "parent_generation": parent_generation,
                "timestamp": time.time(),
            },

            "authority": {
                "transport": "QbitQueueLoop",
                "command": "QbitDialer",
                "execution": "QbitQueueLoop",
                "replay_engine": "INPUT_ONLY",
            },
        }

        return payload

    # ==================================================================
    # LINEAGE
    # ==================================================================

    def _build_lineage(
        self,
        *,
        state,
        parent_lineage,
        parent_qbit_id,
        generation,
        cycle_id,
        replay_id,
        replay_reason,
    ) -> Dict[str, Any]:

        if isinstance(
            parent_lineage,
            dict,
        ):
            lineage = dict(
                parent_lineage
            )
        elif isinstance(
            parent_lineage,
            list,
        ):
            lineage = {
                "parents": list(
                    parent_lineage
                )
            }
        else:
            lineage = {}

        lineage.update(
            {
                "parent_qbit_id": parent_qbit_id,
                "generation": generation,
                "cycle_id": cycle_id,
                "replay_id": replay_id,
                "replay_reason": replay_reason,
                "origin": "persisted_state",
            }
        )

        return lineage

    # ==================================================================
    # IDENTIFIERS
    # ==================================================================

    @staticmethod
    def _new_cycle_id(
        parent_qbit_id=None,
        reason="persisted_replay",
    ) -> str:

        return (
            "QCYCLE."
            f"{reason.upper()}."
            f"{uuid.uuid4().hex[:12]}"
        )

    @staticmethod
    def _new_replay_id(
        parent_qbit_id=None,
        cycle_id=None,
    ) -> str:
        """
        Create a unique replay admission identity.
        """

        return (
            "QREPLAY."
            f"{uuid.uuid4().hex[:16]}"
        )

    @staticmethod
    def _build_admission_id(
        *,
        parent_qbit_id,
        replay_id,
        generation,
        cycle_id,
        reason,
    ) -> str:

        material = (
            f"{parent_qbit_id}|"
            f"{replay_id}|"
            f"{generation}|"
            f"{cycle_id}|"
            f"{reason}"
        )

        digest = hashlib.sha256(
            material.encode(
                "utf-8"
            )
        ).hexdigest()[:24]

        return (
            "QADMISSION."
            f"{digest}"
        )

    # ==================================================================
    # GENERATION
    # ==================================================================

    @staticmethod
    def _extract_generation(
        state: Dict[str, Any],
    ) -> int:

        candidates = [
            state.get(
                "generation"
            ),
            state.get(
                "metadata",
                {},
            ).get(
                "generation"
            )
            if isinstance(
                state.get(
                    "metadata"
                ),
                dict,
            )
            else None,
            state.get(
                "lineage",
                {},
            ).get(
                "generation"
            )
            if isinstance(
                state.get(
                    "lineage"
                ),
                dict,
            )
            else None,
        ]

        for value in candidates:
            try:
                if value is not None:
                    return max(
                        0,
                        int(value),
                    )
            except (
                TypeError,
                ValueError,
            ):
                continue

        return 0

    # ==================================================================
    # QUEUE SUBMISSION
    # ==================================================================

    def _enqueue_state(
        self,
        state: Dict[str, Any],
        replay_reason: str = "persisted_replay",
    ) -> bool:

        if self._stopped:
            logger.warning(
                "[QbitReplayEngine] "
                "Replay rejected because engine is stopped"
            )
            return False

        if not self.validate_authority():
            return False

        payload = self._build_replay_payload(
            state,
            replay_reason=replay_reason,
        )

        admission_id = payload[
            "admission_id"
        ]

        # --------------------------------------------------------------
        # Exact-admission duplicate suppression.
        #
        # A different generation/cycle/replay_id is NOT a duplicate.
        # --------------------------------------------------------------

        if admission_id in self._submitted_admissions:
            logger.debug(
                "[QbitReplayEngine] "
                "Exact replay admission already submitted | "
                "admission_id=%s",
                admission_id,
            )
            return False

        queue_loop = self.qbit_loop

        method = self._resolve_admission_method(
            queue_loop
        )

        if method is None:
            logger.error(
                "[QbitReplayEngine] "
                "No authoritative Qbit admission method available"
            )
            return False

        try:
            result = method(
                payload
            )

            # ----------------------------------------------------------
            # Sync QueueLoop path.
            # ----------------------------------------------------------

            if not inspect_is_awaitable(result):
                self._record_admission(
                    payload
                )

                logger.info(
                    "[QbitReplayEngine] "
                    "Replay admitted | method=%s | "
                    "parent_qbit=%s | generation=%s | "
                    "replay_id=%s",
                    getattr(
                        method,
                        "__name__",
                        type(method).__name__,
                    ),
                    payload.get(
                        "parent_qbit_id"
                    ),
                    payload.get(
                        "generation"
                    ),
                    payload.get(
                        "replay_id"
                    ),
                )

                return True

            # ----------------------------------------------------------
            # Async-only QueueLoop cannot be silently executed from a
            # synchronous API by creating another event loop.
            # ----------------------------------------------------------

            logger.warning(
                "[QbitReplayEngine] "
                "Authoritative QueueLoop admission is async; "
                "use replay_async()"
            )

            return False

        except Exception as exc:
            self.last_error = str(
                exc
            )

            logger.error(
                "[QbitReplayEngine] "
                "Authoritative replay admission failed | %s",
                exc,
                exc_info=True,
            )

            self._emit_event(
                "QBIT_REPLAY_ADMISSION_ERROR",
                {
                    "error": str(exc),
                    "payload": payload,
                },
            )

            return False

    # ==================================================================
    # ASYNC QUEUE SUBMISSION
    # ==================================================================

    async def _enqueue_state_async(
        self,
        state: Dict[str, Any],
        replay_reason: str = "persisted_replay",
    ) -> bool:

        if self._stopped:
            return False

        if not self.validate_authority():
            return False

        payload = self._build_replay_payload(
            state,
            replay_reason=replay_reason,
        )

        admission_id = payload[
            "admission_id"
        ]

        if admission_id in self._submitted_admissions:
            logger.debug(
                "[QbitReplayEngine] "
                "Exact async replay admission already submitted | "
                "admission_id=%s",
                admission_id,
            )
            return False

        method = self._resolve_admission_method(
            self.qbit_loop
        )

        if method is None:
            return False

        try:
            result = method(
                payload
            )

            if inspect_is_awaitable(result):
                result = await result

            self._record_admission(
                payload
            )

            logger.info(
                "[QbitReplayEngine] "
                "Async replay admitted | "
                "parent_qbit=%s | generation=%s | "
                "replay_id=%s",
                payload.get(
                    "parent_qbit_id"
                ),
                payload.get(
                    "generation"
                ),
                payload.get(
                    "replay_id"
                ),
            )

            return True

        except Exception as exc:
            self.last_error = str(
                exc
            )

            logger.error(
                "[QbitReplayEngine] "
                "Async replay admission failed | %s",
                exc,
                exc_info=True,
            )

            self._emit_event(
                "QBIT_REPLAY_ADMISSION_ERROR",
                {
                    "error": str(exc),
                    "payload": payload,
                },
            )

            return False

    # ==================================================================
    # AUTHORITATIVE ADMISSION METHOD
    # ==================================================================

    @staticmethod
    def _resolve_admission_method(
        queue_loop,
    ):

        for method_name in (
            "receive_qbit",
            "admit_qbit",
            "submit_qbit",
        ):
            method = getattr(
                queue_loop,
                method_name,
                None,
            )

            if callable(method):
                return method

        return None

    # ==================================================================
    # ADMISSION RECORD
    # ==================================================================

    def _record_admission(
        self,
        payload: Dict[str, Any],
    ) -> None:

        admission_id = payload.get(
            "admission_id"
        )

        if not admission_id:
            return

        self._submitted_admissions.add(
            admission_id
        )

        # --------------------------------------------------------------
        # Bounded history.
        # --------------------------------------------------------------

        if (
            len(
                self._submitted_admissions
            )
            > self._max_admission_history
        ):
            # Sets are intentionally converted only for bounded cleanup.
            excess = (
                len(
                    self._submitted_admissions
                )
                - self._max_admission_history
            )

            for item in list(
                self._submitted_admissions
            )[:excess]:
                self._submitted_admissions.discard(
                    item
                )

        self.last_replay_admission = payload

        self._emit_event(
            "QBIT_REPLAY_ADMITTED",
            {
                "replay_id": payload.get(
                    "replay_id"
                ),
                "admission_id": admission_id,
                "parent_qbit_id": payload.get(
                    "parent_qbit_id"
                ),
                "generation": payload.get(
                    "generation"
                ),
                "cycle_id": payload.get(
                    "cycle_id"
                ),
                "reason": payload.get(
                    "replay_context",
                    {},
                ).get(
                    "reason"
                ),
            },
        )

    # ==================================================================
    # FEEDBACK / NEW GENERATION
    # ==================================================================

    def build_feedback_payload(
        self,
        processed_state: Dict[str, Any],
        *,
        feedback_reason: str = "processed_feedback",
    ) -> Dict[str, Any]:

        return self._build_replay_payload(
            processed_state,
            replay_reason=feedback_reason,
        )

    # ==================================================================
    # PERSISTED STATE LOOKUP
    # ==================================================================

    def latest_state(self) -> Optional[Dict[str, Any]]:
        """
        Return the newest persisted state without replaying it.
        """

        states = self.load_states()

        if not states:
            return None

        return states[-1]

    def state_count(self) -> int:

        return len(
            self.load_states()
        )

    # ==================================================================
    # READY CHECK
    # ==================================================================

    def _ensure_ready(self) -> None:

        if self._stopped:
            raise RuntimeError(
                "[QbitReplayEngine] "
                "ReplayEngine is stopped"
            )

        if not self._attached:
            raise RuntimeError(
                "[QbitReplayEngine] "
                "No authoritative QbitQueueLoop attached"
            )

        if not self.validate_authority():
            raise RuntimeError(
                "[QbitReplayEngine] "
                "Authoritative QbitQueueLoop validation failed"
            )

        if not self._started:
            self.start()

    # ==================================================================
    # EVENTBUS
    # ==================================================================

    def _emit_event(
        self,
        event_name: str,
        payload: Dict[str, Any],
    ) -> None:

        if self.event_bus is None:
            return

        event = {
            "type": event_name,
            "source": "QbitReplayEngine",
            "component": "QbitReplayEngine",
            "timestamp": time.time(),
            "payload": payload,
        }

        for method_name in (
            "emit",
            "publish",
            "send",
            "dispatch",
        ):
            method = getattr(
                self.event_bus,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(
                    event
                )
                return

            except TypeError:
                try:
                    method(
                        event_name,
                        event,
                    )
                    return
                except Exception:
                    continue

            except Exception:
                logger.debug(
                    "[QbitReplayEngine] "
                    "EventBus emission failed | event=%s",
                    event_name,
                    exc_info=True,
                )
                return

    # ==================================================================
    # LEGACY REBUILD BLOCKER
    # ==================================================================

    def _rebuild_qbit(
        self,
        state,
    ):

        logger.warning(
            "[QbitReplayEngine] "
            "_rebuild_qbit() requested; "
            "Qbit construction is prohibited during replay"
        )

        return self._build_replay_payload(
            state,
            replay_reason="legacy_rebuild_blocked",
        )

    # ==================================================================
    # DIAGNOSTICS
    # ==================================================================

    def diagnostics(self) -> Dict[str, Any]:

        snapshot = self.system_snapshot()

        snapshot.update(
            {
                "last_replay": (
                    self.last_replay_admission
                    if isinstance(
                        self.last_replay_admission,
                        dict,
                    )
                    else None
                ),
                "last_error": self.last_error,
                "persisted_state_count": self.state_count(),
                "authority_valid": (
                    self.validate_authority()
                    if self.qbit_loop is not None
                    else False
                ),
            }
        )

        return snapshot


# ========================================================================
# ASYNC DETECTION
# ========================================================================

def inspect_is_awaitable(
    value: Any,
) -> bool:

    return hasattr(
        value,
        "__await__",
    )


# ========================================================================
# MODULE EXPORT
# ========================================================================

__all__ = [
    "QbitReplayEngine",
]