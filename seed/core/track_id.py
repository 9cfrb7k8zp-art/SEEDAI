
# ==========================================================
# FILE: track_id.py
# PATH: SEED_ROOT/seed/core/track_id.py
# VERSION: 5.0.0
# SYSTEM LAYER: L2 TRACK IDENTITY / QBIT REGISTRY SPINE
#
# PURPOSE:
#   - Canonical TrackID object
#   - Canonical track identity
#   - Track lineage
#   - Input/output data
#   - Runtime state
#   - Qbit relationship
#   - QbitDialer relationship
#   - HeartbeatEmitter relationship
#   - Runtime transport metadata
#   - Central TrackRegistry
#
# ARCHITECTURAL RULE:
#
#   TrackID
#       = identity of the TRACK
#
#   Qbit.id / qbit_id
#       = identity of the QBIT transport object
#
#   TrackContext.current()
#       = currently executing TRACK identity
#
#   QbitDialer
#       = command authority
#
#   HeartbeatEmitter
#       = heartbeat signal / routing source
#
#   TrackRegistry
#       = remembers relationships between them
#
# IMPORTANT:
#
#   This module DOES NOT instantiate:
#       - QbitDialer
#       - QbitQueueLoop
#       - HeartbeatEmitter
#
#   They attach to an existing Track through the registry.
#
#   This prevents circular boot dependencies while allowing
#   the runtime to discover and utilize the relationships.
#
# IDENTITY FLOW:
#
#   DATA
#      ↓
#   QBIT
#      ↓
#   TRACK ID
#      ↓
#   TRACK REGISTRY
#      ↓
#   DIALER / HEARTBEAT / QUEUE / COGNITION
#
# DATA AXIOM:
#
#   Qbit = blood cell / data transporter
#   TrackID = identity / lineage
#   TrackRegistry = memory of identity relationships
#   QbitDialer = command lock / authority
#   HeartbeatEmitter = heartbeat routing signal
#
# ==========================================================

from __future__ import annotations

import hashlib
import threading
import time
import uuid

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
)


from seed.core.track_action_permissions import (
    TrackActionPermissions,
)


# ==========================================================
# INTERNAL HELPERS
# ==========================================================

def _epoch_ms() -> int:
    return int(time.time() * 1000)


def _short_hash(
    seed: Any,
    length: int = 6,
) -> str:

    return hashlib.sha1(
        str(seed).encode("utf-8")
    ).hexdigest()[:length].upper()


def _normalize(
    value: Any,
    fallback: str,
) -> str:

    value = str(
        value or fallback
    ).strip()

    if not value:
        value = fallback

    return (
        value
        .upper()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def _object_id(
    obj: Any,
) -> Optional[str]:

    if obj is None:
        return None

    for attr in (
        "qbit_id",
        "id",
        "uuid",
        "identity",
    ):

        try:

            value = getattr(
                obj,
                attr,
                None,
            )

        except Exception:
            continue

        if value is not None:

            value = str(
                value
            ).strip()

            if value:
                return value

    return None


def _safe_type_name(
    obj: Any,
) -> Optional[str]:

    if obj is None:
        return None

    try:
        return type(obj).__name__

    except Exception:
        return None


# ==========================================================
# TRACK ID TAG
# ==========================================================

class TrackIDTag:

    ROOT_PARENT = "ROOT"

    # ------------------------------------------------------
    # Global identity protection
    # ------------------------------------------------------

    _seen_lock = threading.RLock()

    _seen_ids: Set[str] = set()

    # ======================================================
    # CONSTRUCTOR
    # ======================================================

    def __init__(
        self,
        *,
        domain: str,
        channel: str,
        skill: str,
        agent: str,
        parent_id: Optional[str],
        priority: int,
        reasoning_input: Optional[
            Dict[str, Any]
        ] = None,
    ):

        # --------------------------------------------------
        # CANONICAL IDENTITY
        # --------------------------------------------------

        self.domain = _normalize(
            domain,
            "UNKNOWN",
        )

        self.channel = _normalize(
            channel,
            "GEN",
        )

        self.skill = _normalize(
            skill,
            "TASK",
        )

        self.agent = _normalize(
            agent,
            "GEN",
        )

        try:

            self.priority = int(
                priority
            )

        except (
            TypeError,
            ValueError,
        ):

            self.priority = 0

        # --------------------------------------------------
        # PERMISSIONS
        #
        # Permissions remain attached to the Track.
        # They do not control Qbit transport here.
        # --------------------------------------------------

        self.permissions = (
            TrackActionPermissions()
        )

        # --------------------------------------------------
        # IDENTITY TIMING
        # --------------------------------------------------

        self.timestamp = _epoch_ms()

        self.uuid = uuid.uuid4().hex

        self.parent_id = (
            str(parent_id).strip()
            if parent_id
            else None
        )

        parent_hash = (
            _short_hash(
                self.parent_id
            )
            if self.parent_id
            else self.ROOT_PARENT
        )

        node_seed = (
            f"{self.domain}|"
            f"{self.channel}|"
            f"{self.agent}|"
            f"{self.skill}|"
            f"{self.timestamp}|"
            f"{self.uuid}"
        )

        node_hash = _short_hash(
            node_seed
        )

        base_id = (
            f"{self.domain}."
            f"{self.channel}."
            f"{self.agent}."
            f"{self.skill}."
            f"{parent_hash}."
            f"{node_hash}"
        )

        # --------------------------------------------------
        # UNIQUE TRACK ID
        # --------------------------------------------------

        with self._seen_lock:

            candidate = base_id

            suffix = 0

            while (
                candidate
                in self._seen_ids
            ):

                suffix += 1

                candidate = (
                    f"{base_id}."
                    f"DUP{suffix}"
                )

            self._seen_ids.add(
                candidate
            )

        self.track_id = candidate

        # ==================================================
        # DATA FLOW
        # ==================================================

        self.input_data: Any = None

        self.output_data: Any = None

        self.payload: Any = None

        # ==================================================
        # REASONING
        # ==================================================

        self.reasoning_input: Dict[
            str,
            Any,
        ] = dict(
            reasoning_input or {}
        )

        self.reasoning_output: Dict[
            str,
            Any,
        ] = {}

        # ==================================================
        # LINEAGE
        # ==================================================

        self.children: List[str] = []

        # ==================================================
        # EXECUTION
        # ==================================================

        self.execution_count = 0

        self.last_execution_at: Optional[
            int
        ] = None

        self.last_executor: Optional[
            str
        ] = None

        # ==================================================
        # ACTIONS
        # ==================================================

        self.actions: Dict[
            str,
            Callable[..., Any],
        ] = {}

        # ==================================================
        # QBIT RELATIONSHIP
        #
        # IMPORTANT:
        #
        # Qbit identity is NOT the TrackID.
        #
        # We retain both.
        # ==================================================

        self.qbit_id: Optional[str] = None

        self.qbit: Any = None

        self.qbit_type: Optional[str] = None

        self.qbit_bound_at: Optional[
            int
        ] = None

        self.qbit_metadata: Dict[
            str,
            Any,
        ] = {}

        # ==================================================
        # DIALER RELATIONSHIP
        #
        # QbitDialer remains the command authority.
        #
        # TrackID only records the relationship.
        # ==================================================

        self.dialer: Any = None

        self.dialer_id: Optional[str] = None

        self.dialer_type: Optional[str] = None

        self.dialer_bound_at: Optional[
            int
        ] = None

        self.dialer_metadata: Dict[
            str,
            Any,
        ] = {}

        # ==================================================
        # HEARTBEAT RELATIONSHIP
        #
        # HeartbeatEmitter is a signal/router relationship.
        # It does not become command authority.
        # ==================================================

        self.heartbeat_emitter: Any = None

        self.heartbeat_emitter_id: Optional[
            str
        ] = None

        self.heartbeat_emitter_type: Optional[
            str
        ] = None

        self.heartbeat_bound_at: Optional[
            int
        ] = None

        self.heartbeat_metadata: Dict[
            str,
            Any,
        ] = {}

        # ==================================================
        # QUEUE / RUNTIME RELATIONSHIPS
        # ==================================================

        self.queue_loop: Any = None

        self.queue_loop_type: Optional[
            str
        ] = None

        self.queue_bound_at: Optional[
            int
        ] = None

        self.runtime_metadata: Dict[
            str,
            Any
        ] = {}

        # ==================================================
        # METADATA
        # ==================================================

        self.metadata: Dict[
            str,
            Any,
        ] = {}

        # ==================================================
        # LIFECYCLE
        # ==================================================

        self.created_at = self.timestamp

        self.last_updated = self.timestamp

        self.state = "INIT"

        # ==================================================
        # CANONICAL IDENTITY METADATA
        # ==================================================

        self.metadata.update(
            {
                "track_id":
                    self.track_id,

                "parent_id":
                    self.parent_id,

                "domain":
                    self.domain,

                "channel":
                    self.channel,

                "skill":
                    self.skill,

                "agent":
                    self.agent,

                "identity_source":
                    "TrackIDTag",

                "identity_version":
                    "5.0.0",
            }
        )

        # ==================================================
        # REGISTRATION
        # ==================================================

        TrackRegistry.register(
            self
        )

    # ======================================================
    # INTERNAL UPDATE
    # ======================================================

    def _touch(
        self,
        state: Optional[str] = None,
    ):

        self.last_updated = (
            _epoch_ms()
        )

        if state is not None:

            self.state = str(
                state
            ).upper()

    # ======================================================
    # QBIT BINDING
    # ======================================================

    def bind_qbit(
        self,
        qbit: Any,
        *,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:

        if qbit is None:
            return False

        qbit_id = _object_id(
            qbit
        )

        self.qbit = qbit

        self.qbit_id = qbit_id

        self.qbit_type = (
            _safe_type_name(qbit)
        )

        self.qbit_bound_at = (
            _epoch_ms()
        )

        if metadata:

            self.qbit_metadata.update(
                metadata
            )

        self.qbit_metadata.update(
            {
                "qbit_id":
                    self.qbit_id,

                "qbit_type":
                    self.qbit_type,

                "track_id":
                    self.track_id,

                "bound_at":
                    self.qbit_bound_at,
            }
        )

        self.metadata.update(
            {
                "qbit_id":
                    self.qbit_id,

                "qbit_type":
                    self.qbit_type,

                "qbit_bound":
                    True,

                "qbit_bound_at":
                    self.qbit_bound_at,
            }
        )

        # --------------------------------------------------
        # Give the Qbit its Track identity when the Qbit
        # implementation exposes compatible attributes.
        #
        # This is deliberately additive.
        # --------------------------------------------------

        for attr in (
            "track_id",
            "track",
        ):

            try:

                if hasattr(
                    qbit,
                    attr,
                ):

                    setattr(
                        qbit,
                        attr,
                        self.track_id,
                    )

            except Exception:
                pass

        # --------------------------------------------------
        # Metadata bridge
        # --------------------------------------------------

        try:

            qbit_metadata = getattr(
                qbit,
                "metadata",
                None,
            )

            if isinstance(
                qbit_metadata,
                dict,
            ):

                qbit_metadata.update(
                    {
                        "track_id":
                            self.track_id,

                        "parent_id":
                            self.parent_id,

                        "channel":
                            self.channel,

                        "skill":
                            self.skill,

                        "agent":
                            self.agent,
                    }
                )

        except Exception:
            pass

        self._touch(
            "QBIT_BOUND"
        )

        return True

    # ======================================================
    # QBIT UNBIND
    # ======================================================

    def unbind_qbit(
        self,
    ) -> bool:

        if self.qbit is None:
            return False

        self.qbit = None

        self.qbit_id = None

        self.qbit_type = None

        self.qbit_bound_at = None

        self.metadata[
            "qbit_bound"
        ] = False

        self._touch()

        return True

    # ======================================================
    # DIALER BINDING
    # ======================================================

    def bind_dialer(
        self,
        dialer: Any,
        *,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:
        """
        Record the QbitDialer responsible for this Track.

        This does NOT execute commands.

        QbitDialer remains the sole command authority.
        """

        if dialer is None:
            return False

        self.dialer = dialer

        self.dialer_id = (
            _object_id(dialer)
        )

        self.dialer_type = (
            _safe_type_name(dialer)
        )

        self.dialer_bound_at = (
            _epoch_ms()
        )

        if metadata:

            self.dialer_metadata.update(
                metadata
            )

        self.dialer_metadata.update(
            {
                "dialer_id":
                    self.dialer_id,

                "dialer_type":
                    self.dialer_type,

                "track_id":
                    self.track_id,

                "bound_at":
                    self.dialer_bound_at,
            }
        )

        self.metadata.update(
            {
                "dialer_id":
                    self.dialer_id,

                "dialer_type":
                    self.dialer_type,

                "dialer_bound":
                    True,

                "dialer_bound_at":
                    self.dialer_bound_at,
            }
        )

        # --------------------------------------------------
        # Back-reference when supported.
        # --------------------------------------------------

        for attr in (
            "track_id",
            "current_track_id",
        ):

            try:

                if hasattr(
                    dialer,
                    attr,
                ):

                    setattr(
                        dialer,
                        attr,
                        self.track_id,
                    )

            except Exception:
                pass

        # --------------------------------------------------
        # If Dialer already owns a Qbit, automatically
        # bind that SAME Qbit to the Track.
        # --------------------------------------------------

        try:

            dialer_qbit = getattr(
                dialer,
                "qbit",
                None,
            )

            if dialer_qbit is not None:

                self.bind_qbit(
                    dialer_qbit,
                    metadata={
                        "source":
                            "QbitDialer"
                    },
                )

        except Exception:
            pass

        self._touch(
            "DIALER_BOUND"
        )

        return True

    # ======================================================
    # HEARTBEAT EMITTER BINDING
    # ======================================================

    def bind_heartbeat_emitter(
        self,
        emitter: Any,
        *,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:
        """
        Bind an existing HeartbeatEmitter.

        Heartbeat remains signal/routing authority.

        It does not receive command authority from TrackID.
        """

        if emitter is None:
            return False

        self.heartbeat_emitter = (
            emitter
        )

        self.heartbeat_emitter_id = (
            _object_id(emitter)
        )

        self.heartbeat_emitter_type = (
            _safe_type_name(emitter)
        )

        self.heartbeat_bound_at = (
            _epoch_ms()
        )

        if metadata:

            self.heartbeat_metadata.update(
                metadata
            )

        self.heartbeat_metadata.update(
            {
                "emitter_id":
                    self.heartbeat_emitter_id,

                "emitter_type":
                    self.heartbeat_emitter_type,

                "track_id":
                    self.track_id,

                "bound_at":
                    self.heartbeat_bound_at,
            }
        )

        self.metadata.update(
            {
                "heartbeat_emitter_id":
                    self.heartbeat_emitter_id,

                "heartbeat_emitter_type":
                    self.heartbeat_emitter_type,

                "heartbeat_bound":
                    True,

                "heartbeat_bound_at":
                    self.heartbeat_bound_at,
            }
        )

        # --------------------------------------------------
        # Attach Track identity when supported.
        # --------------------------------------------------

        for attr in (
            "track_id",
            "current_track_id",
        ):

            try:

                if hasattr(
                    emitter,
                    attr,
                ):

                    setattr(
                        emitter,
                        attr,
                        self.track_id,
                    )

            except Exception:
                pass

        # --------------------------------------------------
        # If emitter already carries the authoritative
        # Qbit, connect that same object.
        # --------------------------------------------------

        try:

            emitter_qbit = getattr(
                emitter,
                "qbit",
                None,
            )

            if emitter_qbit is not None:

                self.bind_qbit(
                    emitter_qbit,
                    metadata={
                        "source":
                            "HeartbeatEmitter"
                    },
                )

        except Exception:
            pass

        self._touch(
            "HEARTBEAT_BOUND"
        )

        return True

    # ======================================================
    # QUEUE LOOP BINDING
    # ======================================================

    def bind_queue_loop(
        self,
        queue_loop: Any,
    ) -> bool:

        if queue_loop is None:
            return False

        self.queue_loop = (
            queue_loop
        )

        self.queue_loop_type = (
            _safe_type_name(
                queue_loop
            )
        )

        self.queue_bound_at = (
            _epoch_ms()
        )

        self.runtime_metadata.update(
            {
                "queue_loop_type":
                    self.queue_loop_type,

                "queue_bound_at":
                    self.queue_bound_at,

                "track_id":
                    self.track_id,
            }
        )

        self.metadata.update(
            {
                "queue_loop_type":
                    self.queue_loop_type,

                "queue_bound":
                    True,
            }
        )

        # --------------------------------------------------
        # Synchronize existing Qbit.
        # --------------------------------------------------

        if self.qbit is not None:

            try:

                if hasattr(
                    queue_loop,
                    "qbit",
                ):

                    queue_loop.qbit = (
                        self.qbit
                    )

            except Exception:
                pass

        # --------------------------------------------------
        # Synchronize existing Dialer.
        # --------------------------------------------------

        if self.dialer is not None:

            try:

                if hasattr(
                    queue_loop,
                    "qbit_dialer",
                ):

                    queue_loop.qbit_dialer = (
                        self.dialer
                    )

            except Exception:
                pass

        # --------------------------------------------------
        # Synchronize TrackID.
        # --------------------------------------------------

        try:

            if hasattr(
                queue_loop,
                "track_id",
            ):

                queue_loop.track_id = (
                    self.track_id
                )

        except Exception:
            pass

        self._touch(
            "QUEUE_BOUND"
        )

        return True

    # ======================================================
    # RELATIONSHIP SNAPSHOT
    # ======================================================

    def transport_info(
        self,
    ) -> Dict[str, Any]:
        """
        Return the complete runtime relationship between
        this Track and its Qbit transport components.
        """

        return {
            "track_id":
                self.track_id,

            "qbit": {
                "id":
                    self.qbit_id,

                "type":
                    self.qbit_type,

                "bound":
                    self.qbit is not None,

                "bound_at":
                    self.qbit_bound_at,

                "metadata":
                    dict(
                        self.qbit_metadata
                    ),
            },

            "dialer": {
                "id":
                    self.dialer_id,

                "type":
                    self.dialer_type,

                "bound":
                    self.dialer is not None,

                "bound_at":
                    self.dialer_bound_at,

                "metadata":
                    dict(
                        self.dialer_metadata
                    ),
            },

            "heartbeat": {
                "id":
                    self.heartbeat_emitter_id,

                "type":
                    self.heartbeat_emitter_type,

                "bound":
                    self.heartbeat_emitter
                    is not None,

                "bound_at":
                    self.heartbeat_bound_at,

                "metadata":
                    dict(
                        self.heartbeat_metadata
                    ),
            },

            "queue_loop": {
                "type":
                    self.queue_loop_type,

                "bound":
                    self.queue_loop
                    is not None,

                "bound_at":
                    self.queue_bound_at,
            },
        }

    # ======================================================
    # RELATIONSHIP / LINEAGE
    # ======================================================

    def add_child(
        self,
        child_id: str,
    ) -> bool:

        if not child_id:
            return False

        child_id = str(
            child_id
        ).strip()

        if not child_id:
            return False

        if child_id == self.track_id:
            return False

        if child_id not in self.children:

            self.children.append(
                child_id
            )

            self._touch()

            return True

        return False

    def has_child(
        self,
        child_id: str,
    ) -> bool:

        return (
            bool(child_id)
            and str(child_id).strip()
            in self.children
        )

    # ======================================================
    # METADATA
    # ======================================================

    def update_metadata(
        self,
        key: str,
        value: Any,
    ) -> bool:

        if not key:
            return False

        key = str(
            key
        ).strip()

        if not key:
            return False

        protected = {
            "track_id",
            "parent_id",
            "domain",
            "channel",
            "skill",
            "agent",
        }

        if key in protected:

            canonical = {
                "track_id":
                    self.track_id,

                "parent_id":
                    self.parent_id,

                "domain":
                    self.domain,

                "channel":
                    self.channel,

                "skill":
                    self.skill,

                "agent":
                    self.agent,
            }

            if value != canonical[key]:
                return False

        self.metadata[key] = value

        self._touch()

        return True

    def update_metadata_bulk(
        self,
        metadata: Optional[
            Dict[str, Any]
        ],
    ) -> bool:

        if not metadata:
            return True

        for key, value in metadata.items():

            if not self.update_metadata(
                key,
                value,
            ):
                return False

        return True

    # ======================================================
    # EXECUTION METADATA
    # ======================================================

    def mark_execution(
        self,
        executor: Optional[str] = None,
    ) -> bool:

        self.execution_count += 1

        self.last_execution_at = (
            _epoch_ms()
        )

        if executor:

            self.last_executor = str(
                executor
            )

        self.metadata[
            "execution_count"
        ] = self.execution_count

        self.metadata[
            "last_execution_at"
        ] = self.last_execution_at

        if self.last_executor:

            self.metadata[
                "last_executor"
            ] = self.last_executor

        self._touch(
            "EXECUTING"
        )

        return True

    def mark_complete(
        self,
        output: Any = None,
    ) -> bool:

        if output is not None:
            self.output_data = output

        self._touch(
            "COMPLETE"
        )

        return True

    def mark_error(
        self,
        error: Any,
    ) -> bool:

        self.metadata[
            "last_error"
        ] = str(error)

        self._touch(
            "ERROR"
        )

        return True

    # ======================================================
    # ACTIONS
    # ======================================================

    def register_action(
        self,
        name: str,
        func: Callable[..., Any],
    ) -> bool:

        if not name or not callable(func):
            return False

        name = str(
            name
        ).strip()

        if not name:
            return False

        self.actions[name] = func

        self._touch()

        return True

    def remove_action(
        self,
        name: str,
    ) -> bool:

        if not name:
            return False

        name = str(
            name
        ).strip()

        if name not in self.actions:
            return False

        del self.actions[name]

        self._touch()

        return True

    def execute_action(
        self,
        name: str,
        *args,
        **kwargs,
    ):

        fn = self.actions.get(
            name
        )

        if not callable(fn):
            return None

        try:

            return fn(
                *args,
                **kwargs,
            )

        except Exception as exc:

            self.metadata[
                "last_action_error"
            ] = str(exc)

            self._touch(
                "ERROR"
            )

            return None

    # ======================================================
    # DATA FLOW
    # ======================================================

    def push(
        self,
        data: Any,
    ) -> bool:

        self.input_data = data

        self.payload = data

        self.reasoning_output[
            "last_push"
        ] = data

        self._touch(
            "ACTIVE"
        )

        self.execute_action(
            "push",
            data,
        )

        return True

    def set_output(
        self,
        data: Any,
    ) -> bool:

        self.output_data = data

        self.reasoning_output[
            "last_output"
        ] = data

        self._touch(
            "OUTPUT"
        )

        self.execute_action(
            "output",
            data,
        )

        return True

    def pull(self):

        self._touch()

        self.execute_action(
            "pull"
        )

        self.reasoning_input[
            "last_pull"
        ] = self.output_data

        return self.output_data

    # ======================================================
    # QBIT DATA SNAPSHOT
    # ======================================================

    def packet(
        self,
        *,
        data: Any = None,
        state: Optional[str] = None,
        stage: Optional[str] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        packet_metadata = dict(
            self.metadata
        )

        if metadata:

            packet_metadata.update(
                metadata
            )

        packet_metadata.update(
            {
                "track_id":
                    self.track_id,

                "parent_id":
                    self.parent_id,

                "qbit_id":
                    self.qbit_id,

                "dialer_id":
                    self.dialer_id,

                "heartbeat_emitter_id":
                    self.heartbeat_emitter_id,
            }
        )

        return {

            # --------------------------------------------------
            # PACKET TYPE
            # --------------------------------------------------

            "qbit_type":
                "TRACK",

            # --------------------------------------------------
            # CANONICAL TRACK IDENTITY
            # --------------------------------------------------

            "track_id":
                self.track_id,

            "parent_id":
                self.parent_id,

            # --------------------------------------------------
            # QBIT IDENTITY
            # --------------------------------------------------

            "qbit_id":
                self.qbit_id,

            "qbit_type_name":
                self.qbit_type,

            # --------------------------------------------------
            # TRACK ATTRIBUTES
            # --------------------------------------------------

            "domain":
                self.domain,

            "channel":
                self.channel,

            "skill":
                self.skill,

            "agent":
                self.agent,

            "priority":
                self.priority,

            # --------------------------------------------------
            # STATE
            # --------------------------------------------------

            "state":
                (
                    state
                    or self.state
                ),

            "stage":
                stage,

            # --------------------------------------------------
            # DATA
            # --------------------------------------------------

            "data":
                (
                    self.payload
                    if data is None
                    else data
                ),

            "input":
                self.input_data,

            "output":
                self.output_data,

            # --------------------------------------------------
            # EXECUTION OBSERVABILITY
            # --------------------------------------------------

            "execution_count":
                self.execution_count,

            "last_execution_at":
                self.last_execution_at,

            "last_executor":
                self.last_executor,

            # --------------------------------------------------
            # TRANSPORT RELATIONSHIPS
            # --------------------------------------------------

            "transport":
                self.transport_info(),

            # --------------------------------------------------
            # METADATA
            # --------------------------------------------------

            "metadata":
                packet_metadata,

            # --------------------------------------------------
            # REASONING
            # --------------------------------------------------

            "reasoning_input":
                dict(
                    self.reasoning_input
                ),

            "reasoning_output":
                dict(
                    self.reasoning_output
                ),

            # --------------------------------------------------
            # LINEAGE
            # --------------------------------------------------

            "children":
                list(
                    self.children
                ),

            # --------------------------------------------------
            # TIMESTAMP
            # --------------------------------------------------

            "timestamp":
                _epoch_ms(),
        }

    # ======================================================
    # INFO
    # ======================================================

    def info(
        self,
    ) -> Dict[str, Any]:

        return {

            "track_id":
                self.track_id,

            "domain":
                self.domain,

            "channel":
                self.channel,

            "skill":
                self.skill,

            "agent":
                self.agent,

            "priority":
                self.priority,

            "state":
                self.state,

            "parent_id":
                self.parent_id,

            "children":
                list(
                    self.children
                ),

            "created_at":
                self.created_at,

            "last_updated":
                self.last_updated,

            "input_data":
                self.input_data,

            "output_data":
                self.output_data,

            "payload":
                self.payload,

            "execution_count":
                self.execution_count,

            "last_execution_at":
                self.last_execution_at,

            "last_executor":
                self.last_executor,

            "metadata":
                dict(
                    self.metadata
                ),

            "reasoning_input":
                dict(
                    self.reasoning_input
                ),

            "reasoning_output":
                dict(
                    self.reasoning_output
                ),

            "actions":
                list(
                    self.actions.keys()
                ),

            "transport":
                self.transport_info(),
        }

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __str__(
        self,
    ):

        return (
            f"[TRACK] {self.track_id} "
            f"| STATE={self.state} "
            f"| P={self.priority} "
            f"| QBIT={self.qbit_id}"
        )

    def __repr__(
        self,
    ):

        return (
            f"<TrackIDTag "
            f"{self.track_id}>"
        )


# ==========================================================
# TRACK REGISTRY
# ==========================================================

class TrackRegistry:

    _lock = threading.RLock()

    _tracks: Dict[
        str,
        TrackIDTag,
    ] = {}

    # ------------------------------------------------------
    # QBIT INDEX
    #
    # Qbit identity → TrackID
    # ------------------------------------------------------

    _qbit_index: Dict[
        str,
        str,
    ] = {}

    # ------------------------------------------------------
    # DIALER INDEX
    #
    # Dialer identity → TrackIDs
    # ------------------------------------------------------

    _dialer_index: Dict[
        str,
        Set[str],
    ] = {}

    # ------------------------------------------------------
    # HEARTBEAT INDEX
    #
    # Emitter identity → TrackIDs
    # ------------------------------------------------------

    _heartbeat_index: Dict[
        str,
        Set[str],
    ] = {}

    # ------------------------------------------------------
    # PENDING LINEAGE
    # ------------------------------------------------------

    _pending_children: Dict[
        str,
        Set[str],
    ] = {}

    # ======================================================
    # REGISTRATION
    # ======================================================

    @classmethod
    def register(
        cls,
        track: TrackIDTag,
    ) -> bool:

        if not isinstance(
            track,
            TrackIDTag,
        ):

            return False

        with cls._lock:

            track_id = (
                track.track_id
            )

            cls._tracks[
                track_id
            ] = track

            # ----------------------------------------------
            # Parent already exists
            # ----------------------------------------------

            if track.parent_id:

                parent = cls._tracks.get(
                    track.parent_id
                )

                if parent:

                    parent.add_child(
                        track_id
                    )

                    parent.reasoning_output.update(
                        track.reasoning_input
                    )

                else:

                    pending = (
                        cls._pending_children
                        .setdefault(
                            track.parent_id,
                            set(),
                        )
                    )

                    pending.add(
                        track_id
                    )

            # ----------------------------------------------
            # Resolve pending children
            # ----------------------------------------------

            waiting = (
                cls._pending_children.pop(
                    track_id,
                    set(),
                )
            )

            for child_id in waiting:

                child = cls._tracks.get(
                    child_id
                )

                if not child:
                    continue

                track.add_child(
                    child_id
                )

                track.reasoning_output.update(
                    child.reasoning_input
                )

            # ----------------------------------------------
            # Existing transport references
            # ----------------------------------------------

            cls._index_track_transports(
                track
            )

            return True

    # ======================================================
    # TRANSPORT INDEXING
    # ======================================================

    @classmethod
    def _index_track_transports(
        cls,
        track: TrackIDTag,
    ):

        # --------------------------------------------------
        # Qbit
        # --------------------------------------------------

        if track.qbit_id:

            cls._qbit_index[
                track.qbit_id
            ] = track.track_id

        # --------------------------------------------------
        # Dialer
        # --------------------------------------------------

        if track.dialer_id:

            cls._dialer_index.setdefault(
                track.dialer_id,
                set(),
            ).add(
                track.track_id
            )

        # --------------------------------------------------
        # Heartbeat
        # --------------------------------------------------

        if (
            track.heartbeat_emitter_id
        ):

            cls._heartbeat_index.setdefault(
                track.heartbeat_emitter_id,
                set(),
            ).add(
                track.track_id
            )

    # ======================================================
    # BIND QBIT
    # ======================================================

    @classmethod
    def bind_qbit(
        cls,
        track_id: str,
        qbit: Any,
        *,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:

        track = cls.get(
            track_id
        )

        if not track:
            return False

        if not track.bind_qbit(
            qbit,
            metadata=metadata,
        ):
            return False

        with cls._lock:

            cls._index_track_transports(
                track
            )

        return True

    # ======================================================
    # BIND DIALER
    # ======================================================

    @classmethod
    def bind_dialer(
        cls,
        track_id: str,
        dialer: Any,
        *,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:

        track = cls.get(
            track_id
        )

        if not track:
            return False

        if not track.bind_dialer(
            dialer,
            metadata=metadata,
        ):
            return False

        with cls._lock:

            cls._index_track_transports(
                track
            )

        return True

    # ======================================================
    # BIND HEARTBEAT
    # ======================================================

    @classmethod
    def bind_heartbeat_emitter(
        cls,
        track_id: str,
        emitter: Any,
        *,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:

        track = cls.get(
            track_id
        )

        if not track:
            return False

        if not track.bind_heartbeat_emitter(
            emitter,
            metadata=metadata,
        ):
            return False

        with cls._lock:

            cls._index_track_transports(
                track
            )

        return True

    # ======================================================
    # BIND QUEUE LOOP
    # ======================================================

    @classmethod
    def bind_queue_loop(
        cls,
        track_id: str,
        queue_loop: Any,
    ) -> bool:

        track = cls.get(
            track_id
        )

        if not track:
            return False

        return track.bind_queue_loop(
            queue_loop
        )

    # ======================================================
    # GET
    # ======================================================

    @classmethod
    def get(
        cls,
        track_id: str,
    ) -> Optional[
        TrackIDTag
    ]:

        if not track_id:
            return None

        with cls._lock:

            return cls._tracks.get(
                str(
                    track_id
                ).strip()
            )

    # ======================================================
    # GET BY QBIT
    # ======================================================

    @classmethod
    def get_by_qbit(
        cls,
        qbit_id: str,
    ) -> Optional[
        TrackIDTag
    ]:

        if not qbit_id:
            return None

        with cls._lock:

            track_id = (
                cls._qbit_index.get(
                    str(qbit_id)
                )
            )

            if not track_id:
                return None

            return cls._tracks.get(
                track_id
            )

    # ======================================================
    # GET BY DIALER
    # ======================================================

    @classmethod
    def get_by_dialer(
        cls,
        dialer_id: str,
    ) -> List[
        TrackIDTag
    ]:

        if not dialer_id:
            return []

        with cls._lock:

            ids = cls._dialer_index.get(
                str(dialer_id),
                set(),
            )

            return [
                cls._tracks[track_id]
                for track_id in ids
                if track_id
                in cls._tracks
            ]

    # ======================================================
    # GET BY HEARTBEAT
    # ======================================================

    @classmethod
    def get_by_heartbeat(
        cls,
        emitter_id: str,
    ) -> List[
        TrackIDTag
    ]:

        if not emitter_id:
            return []

        with cls._lock:

            ids = (
                cls._heartbeat_index.get(
                    str(emitter_id),
                    set(),
                )
            )

            return [
                cls._tracks[track_id]
                for track_id in ids
                if track_id
                in cls._tracks
            ]

    # ======================================================
    # TRANSPORT LOOKUP
    # ======================================================

    @classmethod
    def transport(
        cls,
        track_id: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        track = cls.get(
            track_id
        )

        if not track:
            return None

        return track.transport_info()

    # ======================================================
    # EXISTS
    # ======================================================

    @classmethod
    def exists(
        cls,
        track_id: str,
    ) -> bool:

        return (
            cls.get(track_id)
            is not None
        )

    # ======================================================
    # ALL
    # ======================================================

    @classmethod
    def all(
        cls,
    ) -> List[
        TrackIDTag
    ]:

        with cls._lock:

            return list(
                cls._tracks.values()
            )

    # ======================================================
    # ACTIVE
    # ======================================================

    @classmethod
    def active(
        cls,
        since_ms: Optional[int] = None,
    ) -> List[
        TrackIDTag
    ]:

        now = _epoch_ms()

        with cls._lock:

            tracks = list(
                cls._tracks.values()
            )

        if since_ms is None:

            return [
                track
                for track in tracks
                if track.state
                not in {
                    "COMPLETE",
                    "ERROR",
                }
            ]

        try:

            age_limit = max(
                0,
                int(since_ms),
            )

        except (
            TypeError,
            ValueError,
        ):

            age_limit = 0

        return [
            track
            for track in tracks
            if (
                now
                - track.last_updated
            ) <= age_limit
        ]

    # ======================================================
    # CHILDREN
    # ======================================================

    @classmethod
    def children(
        cls,
        track_id: str,
    ) -> List[
        TrackIDTag
    ]:

        track = cls.get(
            track_id
        )

        if not track:
            return []

        with cls._lock:

            return [
                child
                for child_id
                in track.children
                if (
                    child :=
                    cls._tracks.get(
                        child_id
                    )
                ) is not None
            ]

    # ======================================================
    # PARENT
    # ======================================================

    @classmethod
    def parent(
        cls,
        track_id: str,
    ) -> Optional[
        TrackIDTag
    ]:

        track = cls.get(
            track_id
        )

        if not track:
            return None

        if not track.parent_id:
            return None

        return cls.get(
            track.parent_id
        )

    # ======================================================
    # PUSH
    # ======================================================

    @classmethod
    def push(
        cls,
        track_id: str,
        data: Any,
    ) -> bool:

        track = cls.get(
            track_id
        )

        if not track:
            return False

        return track.push(
            data
        )

    # ======================================================
    # OUTPUT
    # ======================================================

    @classmethod
    def set_output(
        cls,
        track_id: str,
        data: Any,
    ) -> bool:

        track = cls.get(
            track_id
        )

        if not track:
            return False

        return track.set_output(
            data
        )

    # ======================================================
    # PULL
    # ======================================================

    @classmethod
    def pull(
        cls,
        track_id: str,
    ):

        track = cls.get(
            track_id
        )

        if not track:
            return None

        return track.pull()

    # ======================================================
    # PACKET
    # ======================================================

    @classmethod
    def packet(
        cls,
        track_id: str,
        **kwargs,
    ):

        track = cls.get(
            track_id
        )

        if not track:
            return None

        return track.packet(
            **kwargs
        )

    # ======================================================
    # INFO
    # ======================================================

    @classmethod
    def info(
        cls,
        track_id: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        track = cls.get(
            track_id
        )

        if not track:
            return None

        return track.info()

    # ======================================================
    # COUNT
    # ======================================================

    @classmethod
    def count(
        cls,
    ) -> int:

        with cls._lock:

            return len(
                cls._tracks
            )

    # ======================================================
    # REGISTRY STATUS
    # ======================================================

    @classmethod
    def status(
        cls,
    ) -> Dict[str, Any]:

        with cls._lock:

            return {
                "tracks":
                    len(
                        cls._tracks
                    ),

                "qbits":
                    len(
                        cls._qbit_index
                    ),

                "dialers":
                    len(
                        cls._dialer_index
                    ),

                "heartbeat_emitters":
                    len(
                        cls._heartbeat_index
                    ),

                "pending_lineage":
                    len(
                        cls._pending_children
                    ),
            }

    # ======================================================
    # RESET
    # ======================================================

    @classmethod
    def reset(
        cls,
    ):

        with cls._lock:

            cls._tracks.clear()

            cls._qbit_index.clear()

            cls._dialer_index.clear()

            cls._heartbeat_index.clear()

            cls._pending_children.clear()

        with TrackIDTag._seen_lock:

            TrackIDTag._seen_ids.clear()


# ==========================================================
# END FILE
# ==========================================================

