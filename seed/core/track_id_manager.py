# ==========================================================
# FILE: track_id_manager.py
# PATH: SEED_ROOT/seed/core/track_id_manager.py
# VERSION: 7.0.0
# SYSTEM LAYER: L3 TRACK ID AUTHORITY
#
# PURPOSE:
#   - TrackID creation authority
#   - parent resolution
#   - domain routing
#   - HUD routing
#   - priority bookkeeping
#   - TrackID build queues
#   - manager-side lineage indexes
#   - TrackRegistry bridge
#
# CONNECTED MODULES:
#
#   L2:
#       seed.core.track_id
#
#   L2/L3:
#       seed.core.track_context
#       seed.core.channel_id
#       seed.core.track_error
#
#   DOWNSTREAM:
#       TrackSystem
#       QbitQueueLoop
#       QbitDialer
#       Qbit
#
# IMPORTANT:
#
#   TrackIDManager CREATES track identity.
#
#   TrackIDTag STORES canonical track identity.
#
#   TrackRegistry STORES canonical track objects.
#
#   TrackContext STORES ACTIVE EXECUTION identity.
#
#   QbitQueueLoop TRANSPORTS execution identity.
#
#   QbitDialer EXECUTES against the active track.
#
# TrackIDManager does NOT:
#   - bind TrackContext
#   - execute Qbits
#   - own QbitQueueLoop
#   - control QbitDialer
#   - make processing decisions
#
# ==========================================================

from __future__ import annotations

import logging
import threading

from collections import (
    defaultdict,
    deque,
)

from typing import (
    Optional,
    List,
    Dict,
    Any,
)


from seed.core.channel_id import (
    ChannelID,
)

from seed.core.track_id import (
    TrackIDTag,
    TrackRegistry,
)


# ==========================================================
# MODULE IDENTITY
# ==========================================================

MODULE_ID = "TIDM-7"
MODULE_VERSION = "7.0.0"

logger = logging.getLogger(
    "TrackIDManager"
)


# ==========================================================
# OPTIONAL LAZY MODULES
# ==========================================================

def _get_context():

    try:

        from seed.core.track_context import (
            TrackContext,
        )

        return TrackContext

    except Exception:

        return None


def _get_error():

    try:

        from seed.core.track_error import (
            TrackError,
        )

        return TrackError

    except Exception:

        return None


# ==========================================================
# DOMAIN ROUTING
# ==========================================================

DOMAIN_MAP = {

    "S": "SEEDCORE",
    "SC": "SEEDCORE",
    "SEED": "SEEDCORE",
    "SEEDCORE": "SEEDCORE",

    "SS": "SYSTEM",
    "SYS": "SYSTEM",
    "SYSTEM": "SYSTEM",

    "U": "USER",
    "USER": "USER",

    "AG": "AGENT",
    "AGENT": "AGENT",
}


# ==========================================================
# HUD ROUTING
# ==========================================================

HUD_CHANNEL_MAP = {

    "SEEDCORE": "HUD-SC",
    "SYSTEM": "HUD-SS",
    "USER": "HUD-U",
    "AGENT": "HUD-A",

    "UNKNOWN": "HUD-X",
}


# ==========================================================
# TRACK ID MANAGER
# ==========================================================

class TrackIDManager:

    _global_instance = None
    _global_lock = threading.RLock()

    # ======================================================
    # SINGLETON
    # ======================================================

    def __new__(
        cls,
        *args,
        **kwargs,
    ):

        with cls._global_lock:

            if cls._global_instance is None:

                cls._global_instance = (
                    super().__new__(cls)
                )

        return cls._global_instance

    # ======================================================
    # INITIALIZATION
    # ======================================================

    def __init__(
        self,
        main_id: str = "CORE",
        enable_timestamp: bool = True,
        max_history: int = 5000,
        channels: Optional[
            List[str]
        ] = None,
    ):

        if getattr(
            self,
            "_initialized",
            False,
        ):
            return

        self._initialized = True

        self.main_id = str(
            main_id or "CORE"
        )

        self.enable_timestamp = bool(
            enable_timestamp
        )

        self.channels = list(
            channels or []
        )

        self._lock = threading.RLock()

        # --------------------------------------------------
        # HISTORY
        # --------------------------------------------------

        self._seen_ids = deque(
            maxlen=max(
                1,
                int(max_history),
            )
        )

        # --------------------------------------------------
        # MANAGER-SIDE LINEAGE INDEX
        #
        # Canonical lineage remains on TrackIDTag /
        # TrackRegistry.
        #
        # These indexes exist for fast L3 lookup and
        # compatibility with existing consumers.
        # --------------------------------------------------

        self._children: Dict[
            str,
            List[str],
        ] = defaultdict(list)

        self._parents: Dict[
            str,
            str,
        ] = {}

        # --------------------------------------------------
        # ROUTING / PRIORITY
        # --------------------------------------------------

        self._priorities: Dict[
            str,
            int,
        ] = {}

        self._domains: Dict[
            str,
            str,
        ] = {}

        self._hud_routes: Dict[
            str,
            str,
        ] = {}

        # --------------------------------------------------
        # MANAGER METADATA INDEX
        #
        # This is a mirror/index.
        #
        # TrackIDTag.metadata remains authoritative.
        # --------------------------------------------------

        self._metadata: Dict[
            str,
            Dict[str, Any],
        ] = {}

        # --------------------------------------------------
        # BUILD QUEUE
        #
        # This is NOT QbitQueueLoop.
        #
        # It contains TrackIDs waiting for downstream
        # TrackSystem construction/processing.
        # --------------------------------------------------

        self._build_queue = deque()

        # --------------------------------------------------
        # PRIORITY BOOKKEEPING
        #
        # This is NOT QbitQueueLoop's execution queue.
        # --------------------------------------------------

        self._priority_queue: Dict[
            int,
            deque,
        ] = defaultdict(
            deque
        )
# --------------------------------------------------
# QBIT ↔ TRACK INDEX
#
# TrackID remains the canonical work identity.
# Qbit remains the transport identity.
#
# This index does NOT replace either identity.
        # It simply lets SEED move between them.
        # --------------------------------------------------

        self._qbit_tracks: Dict[
            str,
            str,
        ] = {}

        self._track_qbits: Dict[
            str,
            List[str],
        ] = defaultdict(list)

        self._qbit_metadata: Dict[
            str,
            Dict[str, Any],
        ] = {}
        # --------------------------------------------------
        # DIAGNOSTIC STATE
        # --------------------------------------------------

        self._last_error: Optional[
            str
        ] = None

        self._created_count = 0

    # ======================================================
    # QBIT ↔ TRACK REGISTRY BRIDGE
    #
    # Qbit is transport identity.
    # TrackID is work/lineage identity.
    #
    # These methods create a relationship between them.
    # They do NOT make the identities interchangeable.
    # ======================================================

    @staticmethod
    def _extract_qbit_id(qbit) -> Optional[str]:

        if qbit is None:
            return None

        for attr in (
            "qbit_id",
            "id",
            "uuid",
        ):

            try:

                value = getattr(
                    qbit,
                    attr,
                    None,
                )

                if value:

                    return str(
                        value
                    ).strip()

            except Exception:

                continue

        return None

    # ======================================================

    @staticmethod
    def _extract_qbit_track_id(qbit) -> Optional[str]:

        if qbit is None:
            return None

        for attr in (
            "track_id",
            "track",
            "track_identity",
        ):

            try:

                value = getattr(
                    qbit,
                    attr,
                    None,
                )

                if value:

                    if isinstance(
                        value,
                        str,
                    ):

                        return value.strip()

                    nested = getattr(
                        value,
                        "track_id",
                        None,
                    )

                    if nested:
                        return str(
                            nested
                        ).strip()

            except Exception:

                continue

        return None

    # ======================================================

    def bind_qbit(
        self,
        qbit,
        track_id: Optional[str] = None,
        *,
        source: str = "SYSTEM",
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:


        qbit_id = self._extract_qbit_id(
            qbit
        )

        if not qbit_id:
            logger.warning(
                "[%s] Qbit binding rejected | "
                "Qbit has no identifiable id",
                MODULE_ID,
            )

            return False

        resolved_track_id = (
            self._extract_track_id(
                track_id
            )
            or self._extract_qbit_track_id(
                qbit
            )
        )

        if not resolved_track_id:

            resolved_track_id = (
                self._resolve_parent()
            )

        if not resolved_track_id:

            logger.warning(
                "[%s] Qbit binding deferred | "
                "no TrackID available | qbit=%s",
                MODULE_ID,
                qbit_id,
            )

            return False

        track = TrackRegistry.get(
            resolved_track_id
        )

        if track is None:

            logger.warning(
                "[%s] Qbit binding rejected | "
                "unknown track=%s | qbit=%s",
                MODULE_ID,
                resolved_track_id,
                qbit_id,
            )

            return False

        qbit_metadata = dict(
            metadata or {}
        )

        qbit_metadata.update(
            {
                "qbit_id": qbit_id,
                "track_id": resolved_track_id,
                "qbit_source": source,
                "bound_at": _epoch_ms(),
            }
        )

        # --------------------------------------------------
        # Store relationship.
        # --------------------------------------------------

        with self._lock:

            self._qbit_tracks[
                qbit_id
            ] = resolved_track_id

            if qbit_id not in (
                self._track_qbits[
                    resolved_track_id
                ]
            ):

                self._track_qbits[
                    resolved_track_id
                ].append(
                    qbit_id
                )

            self._qbit_metadata[
                qbit_id
            ] = qbit_metadata

        # --------------------------------------------------
        # Attach identity to Qbit when the Qbit exposes
        # normal writable identity fields.
        #
        # We do not require a particular Qbit implementation.
        # --------------------------------------------------

        try:

            if hasattr(
                qbit,
                "track_id",
            ):

                qbit.track_id = (
                    resolved_track_id
                )

        except Exception:

            pass

        # --------------------------------------------------
        # Record on canonical Track.
        # --------------------------------------------------

        try:

            track.update_metadata(
                "last_qbit_id",
                qbit_id,
            )

            track.update_metadata(
                "qbit_bound",
                True,
            )

            track.update_metadata(
                "qbit_source",
                source,
            )

        except Exception as exc:

            logger.debug(
                "[%s] Track Qbit metadata update "
                "skipped: %s",
                MODULE_ID,
                exc,
            )

        logger.debug(
            "[%s] Qbit bound | qbit=%s | track=%s",
            MODULE_ID,
            qbit_id,
            resolved_track_id,
        )

        return True

    # ======================================================

    def track_of_qbit(
        self,
        qbit,
    ) -> Optional[str]:

        qbit_id = (
            self._extract_qbit_id(
                qbit
            )
        )

        if not qbit_id:
            return None

        with self._lock:

            return self._qbit_tracks.get(
                qbit_id
            )

    # ======================================================

    def qbits_of_track(
        self,
        track_id: str,
    ) -> List[str]:

        if not track_id:
            return []

        with self._lock:

            return list(
                self._track_qbits.get(
                    str(track_id).strip(),
                    [],
                )
            )

    # ======================================================

    def qbit_metadata(
        self,
        qbit,
    ) -> Dict[str, Any]:

        qbit_id = (
            self._extract_qbit_id(
                qbit
            )
        )

        if not qbit_id:
            return {}

        with self._lock:

            return dict(
                self._qbit_metadata.get(
                    qbit_id,
                    {},
                )
            )

    # ======================================================

    def qbit_packet(
        self,
        qbit,
    ) -> Optional[Dict[str, Any]]:

        qbit_id = (
            self._extract_qbit_id(
                qbit
            )
        )

        if not qbit_id:
            return None

        track_id = (
            self.track_of_qbit(
                qbit
            )
        )

        if not track_id:
            track_id = (
                self._extract_qbit_track_id(
                    qbit
                )
            )

        track = (
            TrackRegistry.get(
                track_id
            )
            if track_id
            else None
        )

        packet = {
            "qbit_type": "QBIT",
            "qbit_id": qbit_id,
            "track_id": track_id,
            "timestamp": _epoch_ms(),
        }

        if track:

            packet.update(
                {
                    "parent_id":
                        track.parent_id,

                    "domain":
                        track.domain,

                    "channel":
                        track.channel,

                    "skill":
                        track.skill,

                    "agent":
                        track.agent,

                    "priority":
                        track.priority,

                    "track_state":
                        track.state,
                }
            )

        packet[
            "metadata"
        ] = self.qbit_metadata(
            qbit
        )

        return packet

    # ======================================================
    # NORMALIZATION
    # ======================================================

    def _normalize_channel(
        self,
        channel,
    ) -> str:

        if hasattr(
            channel,
            "name",
        ):

            channel = channel.name

        if not isinstance(
            channel,
            str,
        ):

            return "UNKNOWN"

        channel = channel.strip()

        if not channel:

            return "UNKNOWN"

        return (
            channel
            .upper()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )

    def _normalize_domain(
        self,
        domain,
    ) -> str:

        if hasattr(
            domain,
            "name",
        ):

            domain = domain.name

        if not isinstance(
            domain,
            str,
        ):

            return "UNKNOWN"

        domain = domain.strip()

        if not domain:

            return "UNKNOWN"

        return (
            domain
            .upper()
            .replace(" ", "_")
        )

    # ======================================================
    # DOMAIN RESOLUTION
    # ======================================================

    def _resolve_domain(
        self,
        channel,
    ) -> str:

        channel = self._normalize_channel(
            channel
        )

        return DOMAIN_MAP.get(
            channel,
            "UNKNOWN",
        )

    # ======================================================
    # HUD RESOLUTION
    # ======================================================

    def _resolve_hud(
        self,
        domain: str,
    ) -> str:

        domain = self._normalize_domain(
            domain
        )

        return HUD_CHANNEL_MAP.get(
            domain,
            "HUD-X",
        )

    # ======================================================
    # TRACK ID EXTRACTION
    # ======================================================

    @staticmethod
    def _extract_track_id(
        value,
    ) -> Optional[str]:

        if value is None:
            return None

        if isinstance(
            value,
            str,
        ):

            value = value.strip()

            return (
                value
                if value
                else None
            )

        track_id = getattr(
            value,
            "track_id",
            None,
        )

        if track_id:

            return str(
                track_id
            ).strip()

        return None

    # ======================================================
    # ACTIVE PARENT RESOLUTION
    # ======================================================

    def _resolve_parent(
        self,
    ) -> Optional[str]:

        context = _get_context()

        if context is None:

            return None

        try:

            current = context.current()

        except Exception as exc:

            logger.debug(
                "[%s] TrackContext.current() "
                "could not be read: %s",
                MODULE_ID,
                exc,
            )

            return None

        return self._extract_track_id(
            current
        )

    # ======================================================
    # PARENT VALIDATION
    # ======================================================

    def _resolve_explicit_parent(
        self,
        parent_id: Optional[str],
    ) -> Optional[str]:

        if not parent_id:
            return None

        parent_id = str(
            parent_id
        ).strip()

        if not parent_id:
            return None

        # --------------------------------------------------
        # Do NOT reject an unknown parent.
        #
        # TrackRegistry 4.0 supports pending lineage so
        # asynchronous creation order does not destroy
        # lineage.
        # --------------------------------------------------

        return parent_id

    # ======================================================
    # CHANNEL BOOKKEEPING
    # ======================================================

    def _register_channel(
        self,
        channel: str,
    ):

        try:

            ChannelID.next(
                channel
            )

        except Exception as exc:

            logger.debug(
                "[%s] ChannelID.next(%s) "
                "unavailable: %s",
                MODULE_ID,
                channel,
                exc,
            )

    # ======================================================
    # CREATE
    # ======================================================

    def new(
        self,
        channel: str = "AG",
        skill: Optional[str] = None,
        *,
        parent_id: Optional[str] = None,
        priority: int = 50,
        qbit_callback=None,
        agent_subclass: Optional[str] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
        domain_override: Optional[str] = None,
        reasoning_input: Optional[
            Dict[str, Any]
        ] = None,
        **_ignored,
    ) -> Optional[str]:

        channel = self._normalize_channel(
            channel
        )

        metadata = dict(
            metadata or {}
        )

        # --------------------------------------------------
        # PARENT RESOLUTION
        #
        # Explicit parent wins.
        # Otherwise inherit the active execution context.
        # --------------------------------------------------

        parent_id = (
            self._resolve_explicit_parent(
                parent_id
            )
            or self._resolve_parent()
        )

        # --------------------------------------------------
        # DOMAIN
        # --------------------------------------------------

        if domain_override:

            domain = self._normalize_domain(
                domain_override
            )

        else:

            domain = self._resolve_domain(
                channel
            )

        # --------------------------------------------------
        # HUD
        # --------------------------------------------------

        hud = self._resolve_hud(
            domain
        )

        # --------------------------------------------------
        # PRIORITY
        # --------------------------------------------------

        try:

            priority = int(
                priority
            )

        except (
            TypeError,
            ValueError,
        ):

            priority = 50

        # --------------------------------------------------
        # CREATE
        # --------------------------------------------------

        try:

            # ----------------------------------------------
            # ChannelID remains independent channel
            # bookkeeping.
            # ----------------------------------------------

            self._register_channel(
                channel
            )

            # ----------------------------------------------
            # L2 canonical Track object.
            # ----------------------------------------------

            track_obj = TrackIDTag(

                domain=domain,

                channel=channel,

                skill=(
                    skill
                    or "TASK"
                ),

                agent=(
                    agent_subclass
                    or "GEN"
                ),

                parent_id=parent_id,

                priority=priority,

                reasoning_input=(
                    reasoning_input
                    or {}
                ),
            )

            # ----------------------------------------------
            # Routing metadata.
            #
            # These values are useful downstream but do
            # not replace canonical TrackID fields.
            # ----------------------------------------------

            canonical_metadata = {

                "module_id":
                    MODULE_ID,

                "manager_version":
                    MODULE_VERSION,

                "hud_route":
                    hud,

                "domain_route":
                    domain,

                "track_authority":
                    MODULE_ID,

                "track_id":
                    track_obj.track_id,

                "parent_id":
                    parent_id,

            }

            canonical_metadata.update(
                metadata
            )

            canonical_metadata.setdefault(
                "qbit_enabled",
                True,
            )

            canonical_metadata.setdefault(
                "qbit_track_authority",
                MODULE_ID,
            )

            canonical_metadata.setdefault(
                "transport_identity",
                "QBIT",
            )

            canonical_metadata.setdefault(
                "track_identity",
                "TRACKID",
            )

            # ----------------------------------------------
            # Apply metadata to canonical Track object.
            # ----------------------------------------------

            for (
                key,
                value,
            ) in canonical_metadata.items():

                # Canonical fields are already established
                # by TrackIDTag. update_metadata() protects
                # them from conflicting values.
                track_obj.update_metadata(
                    key,
                    value,
                )

            track_id = (
                track_obj.track_id
            )

        except Exception as exc:

            self._last_error = str(
                exc
            )

            logger.error(
                "[%s] TrackID creation failed: %s",
                MODULE_ID,
                exc,
                exc_info=True,
            )

            TrackError = _get_error()

            if TrackError:

                try:

                    TrackError(
                        message=(
                            "L3 TrackID creation failed: "
                            f"{exc}"
                        ),
                        priority="HIGH",
                        track_id=parent_id,
                    ).execute_plan()

                except Exception:

                    logger.debug(
                        "[%s] TrackError escalation "
                        "failed",
                        MODULE_ID,
                        exc_info=True,
                    )

            # ------------------------------------------------
            # DO NOT fabricate a TrackID.
            #
            # A fake ID would violate the canonical identity
            # contract and could enter QbitQueueLoop as if it
            # were a real track.
            # ------------------------------------------------

            return None

        # ==================================================
        # MANAGER INDEX UPDATE
        # ==================================================

        with self._lock:

            self._seen_ids.append(
                track_id
            )

            self._priorities[
                track_id
            ] = priority

            self._domains[
                track_id
            ] = domain

            self._hud_routes[
                track_id
            ] = hud

            self._metadata[
                track_id
            ] = dict(
                track_obj.metadata
            )

            # ----------------------------------------------
            # Lineage mirror.
            # ----------------------------------------------

            if parent_id:

                self._parents[
                    track_id
                ] = parent_id

                if track_id not in (
                    self._children[
                        parent_id
                    ]
                ):

                    self._children[
                        parent_id
                    ].append(
                        track_id
                    )

            # ----------------------------------------------
            # Build queue.
            #
            # TrackID only.
            # No Qbit execution payload here.
            # ----------------------------------------------

            self._build_queue.append(
                track_id
            )

            # ----------------------------------------------
            # Priority bookkeeping.
            # ----------------------------------------------

            self._priority_queue[
                priority
            ].append(
                track_id
            )

            self._created_count += 1

        # ==================================================
        # OPTIONAL CALLBACK
        # ==================================================

        if callable(
            qbit_callback
        ):

            callback_payload = {

                "track_id":
                    track_id,

                "channel":
                    channel,

                "domain":
                    domain,

                "hud":
                    hud,

                "priority":
                    priority,

                "parent_id":
                    parent_id,

                "metadata":
                    dict(
                        track_obj.metadata
                    ),
            }

            try:

                qbit_callback(
                    **callback_payload
                )

            except Exception as exc:

                logger.warning(
                    "[%s] Track creation callback "
                    "failed for %s: %s",
                    MODULE_ID,
                    track_id,
                    exc,
                    exc_info=True,
                )

        logger.debug(
            "[%s] created track=%s "
            "parent=%s "
            "domain=%s "
            "channel=%s "
            "priority=%s",
            MODULE_ID,
            track_id,
            parent_id,
            domain,
            channel,
            priority,
        )

        return track_id

    # ======================================================
    # STATIC GENERATION
    # ======================================================

    @staticmethod
    def generate(
        channel: str = "AG",
        **kwargs,
    ):

        if hasattr(
            channel,
            "name",
        ):

            channel = channel.name

        if not isinstance(
            channel,
            str,
        ):

            channel = "UNKNOWN"

        return TrackIDManager().new(
            channel=channel,
            **kwargs,
        )

    # ======================================================
    # SUB-ID GENERATION
    # ======================================================

    @staticmethod
    def generate_sub_id(
        channel: str,
        parent_id: str,
        **kwargs,
    ):

        return TrackIDManager().new(
            channel=channel,
            parent_id=parent_id,
            **kwargs,
        )

    # ======================================================
    # TRACK LOOKUP
    # ======================================================

    def get_track(
        self,
        track_id: str,
    ):

        return TrackRegistry.get(
            track_id
        )

    def exists(
        self,
        track_id: str,
    ) -> bool:

        return (
            self.get_track(
                track_id
            )
            is not None
        )

    # ======================================================
    # LINEAGE
    # ======================================================

    def children_of(
        self,
        parent_id: str,
    ) -> List[str]:

        if not parent_id:
            return []

        # --------------------------------------------------
        # Prefer canonical TrackRegistry lineage.
        # --------------------------------------------------

        try:

            track = TrackRegistry.get(
                parent_id
            )

            if track:

                return list(
                    track.children
                )

        except Exception:

            pass

        # --------------------------------------------------
        # Compatibility fallback.
        # --------------------------------------------------

        with self._lock:

            return list(
                self._children.get(
                    parent_id,
                    [],
                )
            )

    # ======================================================

    def parent_of(
        self,
        track_id: str,
    ) -> Optional[str]:

        if not track_id:
            return None

        # --------------------------------------------------
        # Prefer canonical Track object.
        # --------------------------------------------------

        try:

            track = TrackRegistry.get(
                track_id
            )

            if track:

                return track.parent_id

        except Exception:

            pass

        # --------------------------------------------------
        # Compatibility fallback.
        # --------------------------------------------------

        with self._lock:

            return self._parents.get(
                track_id
            )

    # ======================================================

    def lineage_of(
        self,
        track_id: str,
    ) -> List[str]:

        if not track_id:
            return []

        result = []

        current = str(
            track_id
        ).strip()

        visited = set()

        # --------------------------------------------------
        # Guard against accidental cyclic lineage.
        # --------------------------------------------------

        while current:

            if current in visited:

                logger.error(
                    "[%s] lineage cycle detected at %s",
                    MODULE_ID,
                    current,
                )

                break

            visited.add(
                current
            )

            result.append(
                current
            )

            current = self.parent_of(
                current
            )

        result.reverse()

        return result

    # ======================================================
    # ATTRIBUTES
    # ======================================================

    def priority_of(
        self,
        track_id: str,
    ) -> int:

        track = TrackRegistry.get(
            track_id
        )

        if track:

            return track.priority

        with self._lock:

            return self._priorities.get(
                track_id,
                50,
            )

    # ======================================================

    def domain_of(
        self,
        track_id: str,
    ) -> str:

        track = TrackRegistry.get(
            track_id
        )

        if track:

            return track.domain

        with self._lock:

            return self._domains.get(
                track_id,
                "UNKNOWN",
            )

    # ======================================================

    def hud_of(
        self,
        track_id: str,
    ) -> str:

        with self._lock:

            return self._hud_routes.get(
                track_id,
                "HUD-X",
            )

    # ======================================================

    def metadata_of(
        self,
        track_id: str,
    ) -> Dict[str, Any]:

        # --------------------------------------------------
        # Canonical metadata first.
        # --------------------------------------------------

        track = TrackRegistry.get(
            track_id
        )

        if track:

            metadata = dict(
                track.metadata
            )

            metadata.setdefault(
                "track_id",
                track.track_id,
            )

            metadata.setdefault(
                "parent_id",
                track.parent_id,
            )

            return metadata

        # --------------------------------------------------
        # Compatibility mirror.
        # --------------------------------------------------

        with self._lock:

            return dict(
                self._metadata.get(
                    track_id,
                    {},
                )
            )

    # ======================================================
    # ROUTING INFO
    # ======================================================

    def routing_of(
        self,
        track_id: str,
    ) -> Dict[str, Any]:

        return {
            "track_id":
                track_id,

            "domain":
                self.domain_of(
                    track_id
                ),

            "hud":
                self.hud_of(
                    track_id
                ),

            "priority":
                self.priority_of(
                    track_id
                ),
        }

    # ======================================================
    # BUILD QUEUE
    # ======================================================

    def next_build(
        self,
    ) -> Optional[str]:

        with self._lock:

            if not self._build_queue:

                return None

            return (
                self._build_queue.popleft()
            )

    # ======================================================

    def build_queue_size(
        self,
    ) -> int:

        with self._lock:

            return len(
                self._build_queue
            )

    # ======================================================
    # PRIORITY QUEUE
    # ======================================================

    def next_priority(
        self,
        level: int,
    ) -> Optional[str]:

        try:

            level = int(
                level
            )

        except (
            TypeError,
            ValueError,
        ):

            level = 50

        with self._lock:

            queue = (
                self._priority_queue.get(
                    level
                )
            )

            if not queue:

                return None

            return queue.popleft()

    # ======================================================

    def priority_queue_size(
        self,
        level: int,
    ) -> int:

        try:

            level = int(
                level
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0

        with self._lock:

            queue = (
                self._priority_queue.get(
                    level
                )
            )

            return (
                len(queue)
                if queue
                else 0
            )

    # ======================================================
    # DATA BRIDGE
    # ======================================================

    def push_data(
        self,
        track_id: str,
        data: Any,
    ):

        return TrackRegistry.push(
            track_id,
            data,
        )

    # ======================================================

    def set_output(
        self,
        track_id: str,
        data: Any,
    ):

        return TrackRegistry.set_output(
            track_id,
            data,
        )

    # ======================================================

    def packet(
        self,
        track_id: str,
        **kwargs,
    ):

        return TrackRegistry.packet(
            track_id,
            **kwargs,
        )

    # ======================================================
    # EXECUTION MARKERS
    #
    # These are bookkeeping helpers only.
    #
    # They do NOT bind TrackContext.
    #
    # The execution boundary / QbitQueueLoop should call
    # these when appropriate.
    # ======================================================

    def mark_execution(
        self,
        track_id: str,
        executor: Optional[str] = None,
    ) -> bool:

        track = TrackRegistry.get(
            track_id
        )

        if not track:

            return False

        return track.mark_execution(
            executor=executor
        )

    # ======================================================

    def mark_complete(
        self,
        track_id: str,
        output: Any = None,
    ) -> bool:

        track = TrackRegistry.get(
            track_id
        )

        if not track:

            return False

        return track.mark_complete(
            output
        )

    # ======================================================

    def mark_error(
        self,
        track_id: str,
        error: Any,
    ) -> bool:

        track = TrackRegistry.get(
            track_id
        )

        if not track:

            return False

        return track.mark_error(
            error
        )

    # ======================================================
    # STATISTICS
    # ======================================================

    def count(
        self,
    ) -> int:

        with self._lock:

            return self._created_count

    # ======================================================

    def registry_count(
        self,
    ) -> int:

        return TrackRegistry.count()

    # ======================================================

    def last_error(
        self,
    ) -> Optional[str]:

        with self._lock:

            return self._last_error

    # ======================================================
    # RESET
    # ======================================================

    def reset(
        self,
    ):

        logger.info(
            "[%s] resetting TrackIDManager",
            MODULE_ID,
        )

        with self._lock:

            self._seen_ids.clear()

            self._children.clear()

            self._parents.clear()

            self._priorities.clear()

            self._domains.clear()

            self._hud_routes.clear()

            self._metadata.clear()

            self._build_queue.clear()

            self._priority_queue.clear()

            self.channels.clear()

            self._qbit_tracks.clear()

            self._track_qbits.clear()

            self._qbit_metadata.clear()

            self._last_error = None

            self._created_count = 0

        # --------------------------------------------------
        # TrackRegistry remains the canonical L2 registry.
        # --------------------------------------------------

        TrackRegistry.reset()


# ==========================================================
# GLOBAL ACCESSOR
# ==========================================================

def get_track_id_manager() -> TrackIDManager:

    return TrackIDManager()


# ==========================================================
# END FILE
# ==========================================================