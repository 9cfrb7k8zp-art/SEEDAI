
# ==========================================================
# FILE: track_base.py
# PATH: SEED_ROOT/seed/core/track_base.py
#
# VERSION: 2.0.0
# SYSTEM LAYER: L1 TRACK FOUNDATION / QBIT IDENTITY BRIDGE
#
# STATUS:
#   STABILITY BUILD
#
# PURPOSE:
# ----------------------------------------------------------
# Canonical low-level Track foundation.
#
# This module is the identity/data foundation between:
#
#       Qbit
#          |
#          v
#      TrackBase
#          |
#          v
#      TrackSystem
#          |
#          v
#      QbitDialer
#
# TrackBase DOES:
#
#   - preserve Track identity
#   - preserve parent/child lineage
#   - associate Qbit identity with Track identity
#   - register TrackIDs
#   - register QbitIDs
#   - maintain thread-safe track storage
#   - maintain Qbit lineage records
#   - provide TrackContext compatibility
#   - provide legacy action registration
#   - provide Qbit feed compatibility
#
# TrackBase DOES NOT:
#
#   - execute Qbit commands
#   - execute Dialer commands
#   - control Heartbeat
#   - control QbitQueueLoop
#   - create QbitDialer
#   - become the Qbit brain
#   - replace TrackSystem
#
# AUTHORITY:
# ----------------------------------------------------------
#
# Qbit
#   = data / blood-cell carrier
#
# TrackBase
#   = identity foundation / lineage bridge
#
# TrackIDManager
#   = TrackID creation authority
#
# TrackSystem
#   = Track context / channel / data-flow authority
#
# QbitDialer
#   = Qbit processing + command authority
#
# EventBus
#   = event distribution
#
# Heartbeat
#   = system clock / pulse
#
# DATA AXIOM:
#
#       HEARTBEAT
#           |
#           v
#          QBIT
#           |
#           v
#      TRACK IDENTITY
#           |
#           v
#       TRACK SYSTEM
#           |
#           v
#       QBIT DIALER
#
# IMPORTANT:
# ----------------------------------------------------------
# TrackBase must never create a competing Qbit.
#
# If a Qbit already exists, TrackBase records its identity.
# It does not replace it.
#
# ==========================================================

from __future__ import annotations

import hashlib
import logging
import threading
import time

from typing import (
    Any,
    Dict,
    Optional,
    List,
    Callable,
)


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("TrackBase")

if not logger.handlers:
    logger.addHandler(logging.NullHandler())

logger.setLevel(logging.INFO)


# ==========================================================
# MODULE IDENTITY
# ==========================================================

MODULE_ID = "TRACKBASE"
VERSION = "2.0.0"

TRACK_ID_PREFIX = "TRACK"
QBIT_ID_PREFIX = "QBIT"

DEFAULT_CHANNEL = "DEFAULT"
DEFAULT_PRIORITY = 50
DEFAULT_SOURCE = "SYSTEM"


# ==========================================================
# GLOBAL STORE
#
# Thread-safe because Heartbeat, QueueLoop, Dialer and
# TrackSystem may touch the foundation from different
# execution contexts.
# ==========================================================

_store: Dict[str, Dict[str, Any]] = {}
_store_lock = threading.RLock()


# ==========================================================
# QBIT → TRACK LINEAGE STORE
#
# This is deliberately separate from the normal Track store.
#
# Qbit is the carrier.
# TrackBase records where that carrier belongs.
# ==========================================================

_qbit_lineage: Dict[str, Dict[str, Any]] = {}
_qbit_lineage_lock = threading.RLock()


# ==========================================================
# SEEN TRACK IDS
# ==========================================================

_seen_lock = threading.RLock()
_seen_ids = set()


# ==========================================================
# SEEN QBIT IDS
# ==========================================================

_seen_qbit_lock = threading.RLock()
_seen_qbit_ids = set()


# ==========================================================
# ID REGISTRATION
# ==========================================================

def register_id(track_id: str) -> bool:

    if not track_id:
        return False

    track_id = str(track_id)

    with _seen_lock:

        if track_id in _seen_ids:
            return False

        _seen_ids.add(track_id)

        return True


def is_registered(track_id: str) -> bool:

    if not track_id:
        return False

    with _seen_lock:
        return str(track_id) in _seen_ids


def reset_ids():

    with _seen_lock:
        _seen_ids.clear()

    logger.debug(
        "[TrackBase] Track IDs reset"
    )


# ==========================================================
# QBIT ID REGISTRATION
# ==========================================================

def register_qbit_id(qbit_id: str) -> bool:

    if not qbit_id:
        return False

    qbit_id = str(qbit_id)

    with _seen_qbit_lock:

        if qbit_id in _seen_qbit_ids:
            return False

        _seen_qbit_ids.add(qbit_id)

        return True


def is_qbit_registered(qbit_id: str) -> bool:

    if not qbit_id:
        return False

    with _seen_qbit_lock:
        return str(qbit_id) in _seen_qbit_ids


def reset_qbit_ids():

    with _seen_qbit_lock:
        _seen_qbit_ids.clear()

    logger.debug(
        "[TrackBase] Qbit IDs reset"
    )


# ==========================================================
# QBIT ID EXTRACTION
# ==========================================================

def get_qbit_id(qbit: Any) -> Optional[str]:

    if qbit is None:
        return None

    # ------------------------------------------------------
    # Object API
    # ------------------------------------------------------

    for attr in (
        "qbit_id",
        "id",
    ):

        try:

            value = getattr(
                qbit,
                attr,
                None,
            )

            if value:
                return str(value)

        except Exception:
            continue

    # ------------------------------------------------------
    # Mapping API
    # ------------------------------------------------------

    if isinstance(qbit, dict):

        for key in (
            "qbit_id",
            "id",
        ):

            value = qbit.get(key)

            if value:
                return str(value)

    return None


# ==========================================================
# QBIT TRACK BINDING
# ==========================================================

def bind_qbit_to_track(
    qbit: Any,
    track_id: Optional[str],
    *,
    parent_id: Optional[str] = None,
    channel: str = "QBIT",
    generation: Optional[int] = None,
    source: str = DEFAULT_SOURCE,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:

    if qbit is None:
        return None

    qbit_id = get_qbit_id(qbit)

    if not qbit_id:
        logger.warning(
            "[TrackBase] Qbit rejected for Track binding | "
            "missing qbit_id"
        )
        return None

    if not track_id:
        logger.warning(
            "[TrackBase] Qbit rejected for Track binding | "
            "missing track_id | qbit=%s",
            qbit_id,
        )
        return None

    track_id = str(track_id)
    qbit_id = str(qbit_id)

    register_id(track_id)
    register_qbit_id(qbit_id)

    qbit_source = getattr(qbit, "source", None)
    if qbit_source is None and isinstance(qbit, dict):
        qbit_source = qbit.get("source")

    qbit_provenance = getattr(qbit, "provenance", None)
    if not isinstance(qbit_provenance, dict) and isinstance(qbit, dict):
        qbit_provenance = qbit.get("provenance")
    qbit_provenance = dict(qbit_provenance or {})

    resolved_source = (
        qbit_source
        if qbit_source not in (None, "", "UNKNOWN")
        else source
    )

    resolved_metadata = dict(metadata or {})
    for key in (
        "source_of_start",
        "classification",
        "intent",
        "action",
        "producer",
        "producer_id",
        "creation_reason",
        "upstream_source",
        "skill",
        "command",
        "command_type",
    ):
        value = qbit_provenance.get(key)
        if value is None:
            value = getattr(qbit, key, None)
        if value is None and isinstance(qbit, dict):
            value = qbit.get(key)
        if value is not None:
            resolved_metadata.setdefault(key, value)

    resolved_metadata.setdefault("source", resolved_source)

    lineage = {
        "qbit_id": qbit_id,
        "track_id": track_id,
        "parent_id": (
            str(parent_id)
            if parent_id
            else None
        ),
        "channel": str(
            channel or "QBIT"
        ).upper(),
        "generation": generation,
        "source": resolved_source,
        "source_of_start": resolved_metadata.get(
            "source_of_start",
            resolved_source,
        ),
        "classification": resolved_metadata.get("classification"),
        "intent": resolved_metadata.get("intent"),
        "action": resolved_metadata.get("action"),
        "skill": resolved_metadata.get("skill"),
        "command": resolved_metadata.get("command"),
        "command_type": resolved_metadata.get("command_type"),
        "timestamp": _epoch_ms(),
        "metadata": resolved_metadata,
    }

    with _qbit_lineage_lock:

        _qbit_lineage[qbit_id] = lineage

    # ------------------------------------------------------
    # Also expose the relationship through Track storage.
    # ------------------------------------------------------

    store_write(
        f"qbit:{qbit_id}",
        lineage,
        channel="QBIT",
    )

    store_write(
        f"track:{track_id}:qbit",
        lineage,
        channel="TRACK",
    )

    logger.info(
        "[QBIT→TRACK] bound | "
        "qbit=%s | track=%s | parent=%s | channel=%s",
        qbit_id,
        track_id,
        parent_id,
        lineage["channel"],
    )

    return dict(lineage)


# ==========================================================
# QBIT LINEAGE LOOKUP
# ==========================================================

def get_qbit_lineage(
    qbit_id: str,
) -> Optional[Dict[str, Any]]:

    if not qbit_id:
        return None

    with _qbit_lineage_lock:

        record = _qbit_lineage.get(
            str(qbit_id)
        )

        return (
            dict(record)
            if record is not None
            else None
        )


def get_track_for_qbit(
    qbit_id: str,
) -> Optional[str]:

    record = get_qbit_lineage(
        qbit_id
    )

    if not record:
        return None

    return record.get(
        "track_id"
    )


def get_qbits_for_track(
    track_id: str,
) -> List[str]:

    if not track_id:
        return []

    track_id = str(track_id)

    results = []

    with _qbit_lineage_lock:

        for qbit_id, record in (
            _qbit_lineage.items()
        ):

            if record.get(
                "track_id"
            ) == track_id:

                results.append(
                    qbit_id
                )

    return results


def qbit_lineage_snapshot():
    with _qbit_lineage_lock:
        return {
            qbit_id: dict(record)
            for qbit_id, record
            in _qbit_lineage.items()
        }


# ==========================================================
# STORE API
# ==========================================================

def store_write(
    track_id: str,
    value: Any,
    channel: str = DEFAULT_CHANNEL,
):

    if not track_id:
        return False

    channel = str(
        channel or DEFAULT_CHANNEL
    )

    with _store_lock:

        bucket = _store.setdefault(
            channel,
            {},
        )

        bucket[str(track_id)] = value

    logger.debug(
        "[TrackBase] WRITE: %s.%s",
        channel,
        track_id,
    )

    return True


def store_read(
    track_id: str,
    channel: str = DEFAULT_CHANNEL,
    default: Any = None,
) -> Any:

    if not track_id:
        return default

    channel = str(
        channel or DEFAULT_CHANNEL
    )

    with _store_lock:

        return _store.get(
            channel,
            {},
        ).get(
            str(track_id),
            default,
        )


def store_delete(
    track_id: str,
    channel: Optional[str] = None,
):

    if not track_id:
        return False

    track_id = str(track_id)

    with _store_lock:

        if channel is not None:

            bucket = _store.get(
                str(channel)
            )

            if (
                bucket
                and track_id in bucket
            ):

                del bucket[
                    track_id
                ]

                return True

            return False

        removed = False

        for bucket in _store.values():

            if track_id in bucket:

                del bucket[
                    track_id
                ]

                removed = True

        return removed


def store_clear(
    channel: Optional[str] = None,
):

    with _store_lock:

        if channel is not None:

            _store[
                str(channel)
            ] = {}

        else:

            _store.clear()

    logger.debug(
        "[TrackBase] STORE CLEARED | channel=%s",
        channel or "ALL",
    )


def store_snapshot():

    with _store_lock:

        return {
            channel: dict(values)
            for channel, values
            in _store.items()
        }


# ==========================================================
# UTILITIES
# ==========================================================

def _epoch_ms() -> int:

    return int(
        time.time() * 1000
    )


def _short_hash(
    value: str,
    length: int = 6,
) -> str:

    return hashlib.sha256(
        str(value).encode(
            "utf-8"
        )
    ).hexdigest()[:length]


# ==========================================================
# LEGACY TRACK CONTEXT COMPATIBILITY FACADE
# ==========================================================

class TrackContextBase:

    @classmethod
    def _canonical(cls):

        try:

            from seed.core.track_context import (
                TrackContext,
            )

            return TrackContext

        except Exception as exc:

            logger.debug(
                "[TrackContextBase] Canonical context "
                "unavailable: %s",
                exc,
            )

            return None

    @classmethod
    def get(
        cls,
    ) -> Optional[str]:

        context = cls._canonical()

        if context is not None:

            try:
                return context.current()

            except Exception:
                pass

        return None

    @classmethod
    def get_current(cls):

        return cls.get()

    @classmethod
    def get_parent(cls):

        context = cls._canonical()

        if context is not None:

            try:
                return context.get_parent()

            except Exception:
                pass

        return None

    @classmethod
    def set(
        cls,
        track_id: Optional[str],
    ):

        context = cls._canonical()

        if context is None:
            return track_id

        if track_id:

            context.set(
                track_id
            )

        else:

            context.clear()

        return track_id

    @classmethod
    def reset(cls):

        context = cls._canonical()

        if context is not None:
            context.clear()

    @classmethod
    def current_stack(
        cls,
    ) -> List[str]:

        context = cls._canonical()

        if context is not None:

            try:

                return context.get_stack()

            except Exception:
                pass

        return []

    @classmethod
    def get_stack(cls):

        return cls.current_stack()


# ==========================================================
# TRACK BASE
# ==========================================================

class TrackBase:

    _actions: Dict[
        str,
        Callable,
    ] = {}

    _actions_lock = (
        threading.RLock()
    )

    # ======================================================
    # TRACK ID
    # ======================================================

    @staticmethod
    def current_track_id():

        return TrackContextBase.get()

    @staticmethod
    def set_current_track_id(
        track_id: Optional[str],
    ):

        return TrackContextBase.set(
            track_id
        )

    # ======================================================
    # QBIT IDENTITY
    # ======================================================

    @staticmethod
    def qbit_id(
        qbit: Any,
    ) -> Optional[str]:

        return get_qbit_id(
            qbit
        )

    @staticmethod
    def bind_qbit(
        qbit: Any,
        track_id: Optional[str] = None,
        **kwargs,
    ):

        tid = (
            track_id
            or TrackBase.current_track_id()
        )

        return bind_qbit_to_track(
            qbit,
            tid,
            **kwargs,
        )

    @staticmethod
    def qbit_track(
        qbit_id: str,
    ) -> Optional[str]:

        return get_track_for_qbit(
            qbit_id
        )

    @staticmethod
    def qbits_for_track(
        track_id: str,
    ) -> List[str]:

        return get_qbits_for_track(
            track_id
        )

    # ======================================================
    # ACTION REGISTRATION
    #
    # Legacy compatibility only.
    #
    # QbitDialer remains the command authority.
    # ======================================================

    @classmethod
    def register_action(
        cls,
        name: str,
        func: Callable,
    ):

        if not name or not callable(func):
            return False

        with cls._actions_lock:

            cls._actions[
                str(name)
            ] = func

        logger.debug(
            "[TrackBase] Action registered: %s",
            name,
        )

        return True

    @classmethod
    def execute_action(
        cls,
        name: str,
        *args,
        **kwargs,
    ):

        with cls._actions_lock:

            fn = cls._actions.get(
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

            logger.warning(
                "[TrackBase] Action %s failed: %s",
                name,
                exc,
            )

        return None

    # ======================================================
    # MANAGER SUGGESTION
    # ======================================================

    @classmethod
    def suggest_manager(
        cls,
        track_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        tid = (
            track_id
            or cls.current_track_id()
        )

        metadata = {}

        if tid:

            metadata = (
                store_read(
                    f"track:{tid}:metadata",
                    default={},
                )
                or {}
            )

        with _store_lock:

            channels = list(
                _store.keys()
            )

        with cls._actions_lock:

            actions = list(
                cls._actions.keys()
            )

        return {
            "track_id": tid,
            "priority": DEFAULT_PRIORITY,
            "metadata": metadata,
            "actions": actions,
            "channels": channels,
            "qbits": (
                get_qbits_for_track(
                    tid
                )
                if tid
                else []
            ),
        }

    # ======================================================
    # QBIT FEED
    # ======================================================

    @classmethod
    def qbit_feed(
        cls,
        message: Any,
        track_id: Optional[str] = None,
        channel: str = "QBIT",
        qbit: Any = None,
        parent_id: Optional[str] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ):

        tid = (
            track_id
            or cls.current_track_id()
        )

        context_stack = (
            TrackContextBase.current_stack()
        )

        qbit_id = get_qbit_id(
            qbit
        )

        # --------------------------------------------------
        # If a Qbit is present, establish the identity
        # relationship before storing the feed.
        # --------------------------------------------------

        lineage = None

        if qbit is not None and tid:

            lineage = bind_qbit_to_track(
                qbit,
                tid,
                parent_id=(
                    parent_id
                    or TrackContextBase.get_parent()
                ),
                channel=channel,
                metadata=metadata,
            )

        feed_data = {
            "qbit_type": "TRACK_QBIT",
            "qbit_id": qbit_id,
            "track_id": tid,
            "parent_id": (
                parent_id
                or TrackContextBase.get_parent()
            ),
            "message": message,
            "timestamp": _epoch_ms(),
            "channel": str(
                channel or "QBIT"
            ).upper(),
            "context_stack": context_stack,
            "lineage": lineage,
            "metadata": dict(
                metadata or {}
            ),
        }

        store_write(
            f"QBIT-{tid or 'UNTRACKED'}",
            feed_data,
            channel=channel,
        )

        logger.info(
            "[QBIT FEED] "
            "qbit=%s | track=%s | channel=%s",
            qbit_id,
            tid,
            channel,
        )

        return feed_data


# ==========================================================
# TRACK ID BASE
# ==========================================================

class TrackIDBase:

    def __init__(
        self,
        track_id: str,
    ):

        self.track_id = str(
            track_id
        )

        register_id(
            self.track_id
        )

        self.children: List[str] = []

        self.metadata: Dict[
            str,
            Any,
        ] = {}

        self.priority = (
            DEFAULT_PRIORITY
        )

        self.timestamp = _epoch_ms()

        self.channel = (
            DEFAULT_CHANNEL
        )

        # --------------------------------------------------
        # Qbit identity attached to this Track.
        #
        # This is a reference, not a second Qbit.
        # --------------------------------------------------

        self.qbit_id: Optional[
            str
        ] = None

        self.parent_id: Optional[
            str
        ] = None

    # ======================================================
    # QBIT ATTACHMENT
    # ======================================================

    def attach_qbit(
        self,
        qbit: Any,
        *,
        parent_id: Optional[str] = None,
        channel: str = "QBIT",
        generation: Optional[int] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ):

        lineage = bind_qbit_to_track(
            qbit,
            self.track_id,
            parent_id=(
                parent_id
                or self.parent_id
            ),
            channel=channel,
            generation=generation,
            metadata=metadata,
        )

        if lineage:

            self.qbit_id = lineage[
                "qbit_id"
            ]

            self.parent_id = (
                lineage.get(
                    "parent_id"
                )
            )

        return lineage

    # ======================================================
    # CHILDREN
    # ======================================================

    def add_child(
        self,
        child_id: str,
    ):

        if (
            child_id
            and child_id
            not in self.children
        ):

            self.children.append(
                child_id
            )

            register_id(
                child_id
            )

    # ======================================================
    # METADATA
    # ======================================================

    def update_metadata(
        self,
        key: str,
        value: Any,
    ):

        self.metadata[
            key
        ] = value

        store_write(
            self.track_id,
            self.metadata,
            channel=self.channel,
        )

    # ======================================================
    # SERIALIZATION
    # ======================================================

    def to_dict(self):

        return {
            "track_id": self.track_id,
            "parent_id": self.parent_id,
            "qbit_id": self.qbit_id,
            "children": list(
                self.children
            ),
            "metadata": dict(
                self.metadata
            ),
            "priority": self.priority,
            "timestamp": self.timestamp,
            "channel": self.channel,
        }


# ==========================================================
# MODULE-LEVEL COMPATIBILITY HELPERS
# ==========================================================

def qbit_to_track(
    qbit: Any,
    track_id: Optional[str],
    **kwargs,
):


    return bind_qbit_to_track(
        qbit,
        track_id,
        **kwargs,
    )


def record_qbit_lineage(
    qbit: Any,
    track_id: Optional[str],
    **kwargs,
):


    return bind_qbit_to_track(
        qbit,
        track_id,
        **kwargs,
    )


# ==========================================================
# END FILE
# ==========================================================

