# ==========================================================
# FILE: track_context.py
# PATH: SEED_ROOT/seed/core/track_context.py
# VERSION: 2.0.0
# SYSTEM LAYER: L4 CONTEXT / IDENTITY / LINEAGE
#
# AUTHORITY:
#   TrackContext = current identity + lineage state
#
# DOES NOT:
#   - own QbitQueueLoop
#   - own QbitDialer
#   - execute Qbit processing
#   - make resource decisions
#   - control boot/shutdown
#
# TrackSystem owns DATA FLOW.
# QbitDialer owns PROCESSING / COMMAND AUTHORITY.
# ==========================================================

from __future__ import annotations

import contextvars
import logging
import time
import uuid

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Callable

from seed.core.track_base import (
    store_write,
    store_read,
    store_clear,
)

from seed.core.permission_record import PermissionRecord


logger = logging.getLogger("TrackContext")


# ==========================================================
# CONTEXT VARIABLES
# ==========================================================

_track_id_ctx = contextvars.ContextVar(
    "track_id",
    default=None,
)

_parent_id_ctx = contextvars.ContextVar(
    "track_parent_id",
    default=None,
)

_hud_id_ctx = contextvars.ContextVar(
    "hud_id",
    default=None,
)

_stack_ctx = contextvars.ContextVar(
    "track_stack",
    default=None,
)

_system_state_ctx = contextvars.ContextVar(
    "system_state",
    default=None,
)


# ==========================================================
# CANONICAL CONSTANTS
# ==========================================================

CHANNELS: List[str] = [
    "GEN",
    "SYS",
    "BOOT",
    "INIT",
    "SHUTDOWN",
    "AI",
    "INTENT",
    "REASON",
    "CODEX",
    "REPAIR",
    "IO",
    "AUDIO",
    "MODEM",
    "NETWORK",
    "SERIAL",
    "HUD",
    "UI",
    "DISPLAY",
    "INPUT",
    "FS",
    "DB",
    "CACHE",
    "STATE",
    "AUTH",
    "PERM",
    "SEC",
    "POLICY",
    "MOD",
    "DEBUG",
    "TRACE",
    "HEALTH",
    "WATCHDOG",
    "QBIT",
]


PRIORITIES: Dict[str, int] = {
    "LOW": 0,
    "MED": 5,
    "HIGH": 10,
    "CRITICAL": 20,
    "FATAL": 30,
}


STATES: List[str] = [
    "ENTER",
    "PROCESS",
    "TRANSLATE",
    "EMIT",
    "WAIT",
    "COMPLETE",
    "FAIL",
    "ERROR",
    "ABORT",
    "TIMEOUT",
]


PIPELINE_STAGES: List[str] = [
    "NUMBER",
    "WORD",
    "CODE",
    "NUMBER_OUT",
    "STRING_OUT",
]


METADATA_KEYS: List[str] = [
    "stage",
    "input_type",
    "output_type",
    "confidence",
    "latency",
    "frequency",
    "channel",
    "error",
    "priority",
    "state",
    "source",
    "module",
    "skill",
    "command",
    "command_type",
]


# ==========================================================
# SYSTEM STATE
# ==========================================================

@dataclass
class SystemState:

    status: str = "OFFLINE"
    phase: str = "INIT"
    authority: str = "QBIT"
    boot_complete: bool = False
    shutdown_requested: bool = False
    degraded: bool = False
    resource_state: str = "UNKNOWN"
    last_track_id: Optional[str] = None
    timestamp: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "phase": self.phase,
            "authority": self.authority,
            "boot_complete": self.boot_complete,
            "shutdown_requested": self.shutdown_requested,
            "degraded": self.degraded,
            "resource_state": self.resource_state,
            "last_track_id": self.last_track_id,
            "timestamp": self.timestamp,
        }


# ==========================================================
# PERMISSION REGISTRY
# ==========================================================

class PermissionRegistry:

    _permissions: Dict[str, PermissionRecord] = {}
    _track_permissions: Dict[str, List[str]] = {}

    @classmethod
    def register_permission(
        cls,
        permission: PermissionRecord,
    ):
        cls._permissions[
            permission.permission_code
        ] = permission

    @classmethod
    def assign_to_track(
        cls,
        track_id: str,
        permission_code: str,
    ):
        if permission_code not in cls._permissions:
            logger.warning(
                "[PermissionRegistry] Unknown permission %s",
                permission_code,
            )
            return False

        values = cls._track_permissions.setdefault(
            track_id,
            [],
        )

        if permission_code not in values:
            values.append(permission_code)

        return True

    @classmethod
    def check_permission(
        cls,
        track_id: str,
        permission_code: str,
    ) -> bool:

        perm = cls._permissions.get(
            permission_code
        )

        return bool(
            perm
            and not perm.is_expired()
            and permission_code
            in cls._track_permissions.get(
                track_id,
                [],
            )
        )

    @classmethod
    def clear_track(
        cls,
        track_id: str,
    ):
        cls._track_permissions.pop(
            track_id,
            None,
        )

    @classmethod
    def clear_all(cls):
        cls._permissions.clear()
        cls._track_permissions.clear()


# ==========================================================
# CANONICAL TRACK CONTEXT
# ==========================================================

class TrackContext:

    LEVEL_THRESHOLDS = PRIORITIES

    _current = None

    # External processor compatibility bridge.
    #
    # IMPORTANT:
    # TrackContext does NOT own processing.
    # TrackSystem/Qbit owns the processor.
    _processor: Optional[
        Callable[..., Any]
    ] = None

    # ------------------------------------------------------
    # STACK
    # ------------------------------------------------------

    @classmethod
    def _get_stack(cls) -> List[str]:
        try:
            value = _stack_ctx.get()
        except Exception:
            return []

        if not value:
            return []

        return list(value)

    @classmethod
    def _set_stack(
        cls,
        stack: List[str],
    ):
        _stack_ctx.set(
            list(stack or [])
        )

    # ------------------------------------------------------
    # CURRENT
    # ------------------------------------------------------

    @classmethod
    def current(cls) -> Optional[str]:

        try:
            value = _track_id_ctx.get()
        except Exception:
            value = None

        if value is None:
            return None

        return str(value)

    # ======================================================
    # DICT / COMPATIBILITY ACCESSOR
    # ======================================================

    @classmethod
    def get(
        cls,
        key,
        default=None,
    ):

        key = str(
            key or ""
        ).strip().lower()

        if not key:
            return default

        # --------------------------------------------------
        # Canonical identity
        # --------------------------------------------------

        if key in (
            "track",
            "track_id",
            "trackid",
            "current",
            "current_track",
        ):
            try:
                value = cls.current()
            except Exception:
                value = None

            return (
                value
                if value is not None
                else default
            )

        # --------------------------------------------------
        # Parent identity
        # --------------------------------------------------

        if key in (
            "parent",
            "parent_id",
            "parent_track",
            "parent_track_id",
        ):
            try:
                value = cls.get_parent()
            except Exception:
                value = None

            return (
                value
                if value is not None
                else default
            )

        # --------------------------------------------------
        # HUD identity
        # --------------------------------------------------

        if key in (
            "hud",
            "hud_id",
            "hudid",
        ):
            try:
                value = cls.get_hud_id()
            except Exception:
                value = None

            return (
                value
                if value is not None
                else default
            )

        # --------------------------------------------------
        # Task identity
        # --------------------------------------------------
        #
        # Task identity is optional. Do not assume that
        # TrackContext owns a task context variable.
        # --------------------------------------------------

        if key in (
            "task",
            "task_id",
            "taskid",
        ):

            task_ctx = globals().get(
                "_task_id_ctx"
            )

            if task_ctx is not None:

                try:
                    value = task_ctx.get()
                except Exception:
                    value = None

                if value is not None:
                    return value

            # Optional metadata fallback.
            try:
                value = cls.read(
                    "task_id",
                    None,
                )

                if value is not None:
                    return value

            except Exception:
                pass

            return default

        # --------------------------------------------------
        # Metadata
        # --------------------------------------------------

        if key in (
            "metadata",
            "meta",
        ):
            try:
                value = cls.get_metadata()
            except Exception:
                value = None

            return (
                value
                if value is not None
                else default
            )

        # --------------------------------------------------
        # Dynamic data
        # --------------------------------------------------

        if key in (
            "data",
            "payload",
            "extra_data",
        ):
            try:
                value = cls.get_data()
            except Exception:
                value = None

            return (
                value
                if value is not None
                else default
            )

        # --------------------------------------------------
        # Stack
        # --------------------------------------------------

        if key in (
            "stack",
            "track_stack",
            "lineage",
        ):
            try:
                value = cls.get_stack()
            except Exception:
                value = None

            return (
                value
                if value is not None
                else default
            )

        # --------------------------------------------------
        # Full context snapshot
        # --------------------------------------------------

        if key in (
            "context",
            "snapshot",
        ):
            try:
                value = cls.snapshot()
            except Exception:
                value = None

            return (
                value
                if value is not None
                else default
            )

        # --------------------------------------------------
        # System state
        # --------------------------------------------------

        if key in (
            "system",
            "system_state",
        ):
            try:
                value = cls.system_state()
            except Exception:
                value = None

            return (
                value
                if value is not None
                else default
            )

        # --------------------------------------------------
        # Dynamic metadata lookup
        # --------------------------------------------------

        try:
            metadata = cls.get_metadata()

            if isinstance(metadata, dict):

                if key in metadata:
                    return metadata[key]

        except Exception:
            pass

        # --------------------------------------------------
        # Dynamic data lookup
        # --------------------------------------------------

        try:
            data = cls.get_data()

            if isinstance(data, dict):

                if key in data:
                    return data[key]

        except Exception:
            pass

        # --------------------------------------------------
        # Last-resort class attribute
        # --------------------------------------------------

        try:
            value = getattr(
                cls,
                key,
                default,
            )

            if value is not None and not callable(value):
                return value

        except Exception:
            pass

        return default

    # ======================================================
    # CURRENT TRACK INFORMATION
    # ======================================================

    @classmethod
    def get_current(
        cls,
    ) -> Optional[str]:


        try:
            current = cls.current()

        except Exception:
            current = None

        if current:

            if isinstance(
                current,
                str,
            ):
                return current

            if isinstance(
                current,
                dict,
            ):

                track_id = (
                    current.get("track_id")
                    or current.get("TrackID")
                    or current.get("id")
                )

                if track_id:
                    return str(
                        track_id
                    )

            track_id = getattr(
                current,
                "track_id",
                None,
            )

            if track_id:
                return str(
                    track_id
                )

        # --------------------------------------------------
        # Last locally synchronized identity.
        #
        # This is written by TrackSystem/TrackContext.set(),
        # never discovered by constructing another subsystem.
        # --------------------------------------------------

        try:
            if cls._current:
                return str(
                    cls._current
                )
        except Exception:
            pass

        return None

    # ======================================================
    # PARENT TRACK
    # ======================================================

    @classmethod
    def get_parent(
        cls,
    ) -> Optional[str]:

        # --------------------------------------------------
        # Primary authority: ContextVar
        # --------------------------------------------------

        try:
            parent_id = _parent_id_ctx.get()

            if parent_id:
                return str(
                    parent_id
                )

        except Exception as exc:

            logger.debug(
                "[TrackContext] "
                "Unable to read parent context: %s",
                exc,
            )

        # --------------------------------------------------
        # Compatibility fallback
        # --------------------------------------------------

        try:
            current = cls.current()

            if isinstance(
                current,
                dict,
            ):

                parent_id = (
                    current.get("parent_id")
                    or current.get("parent")
                    or current.get("parent_track_id")
                )

                if parent_id:
                    return str(
                        parent_id
                    )

            elif current is not None:

                parent_id = getattr(
                    current,
                    "parent_id",
                    None,
                )

                if parent_id:
                    return str(
                        parent_id
                    )

        except Exception:
            pass

        return None

    # ======================================================
    # HUD ID
    # ======================================================

    @classmethod
    def get_hud_id(
        cls,
    ) -> Optional[str]:

        # --------------------------------------------------
        # Canonical ContextVar
        # --------------------------------------------------

        try:
            hud_id = _hud_id_ctx.get()

            if hud_id:
                return str(
                    hud_id
                )

        except Exception as exc:

            logger.debug(
                "[TrackContext] "
                "HUD ContextVar read failed: %s",
                exc,
            )

        # --------------------------------------------------
        # Active context
        # --------------------------------------------------

        try:
            current = cls.current()
        except Exception:
            current = None

        if current is None:
            return None

        # --------------------------------------------------
        # Dictionary context
        # --------------------------------------------------

        if isinstance(
            current,
            dict,
        ):

            hud_id = (
                current.get("hud_id")
                or current.get("HUD_ID")
                or current.get("hud")
                or current.get("hudId")
            )

            if hud_id:
                return str(
                    hud_id
                )

            metadata = current.get(
                "metadata"
            )

            if isinstance(
                metadata,
                dict,
            ):

                hud_id = (
                    metadata.get("hud_id")
                    or metadata.get("HUD_ID")
                    or metadata.get("hud")
                    or metadata.get("hudId")
                    or metadata.get("HUD")
                )

                if hud_id:
                    return str(
                        hud_id
                    )

        # --------------------------------------------------
        # Object context
        # --------------------------------------------------

        else:

            try:
                hud_id = getattr(
                    current,
                    "hud_id",
                    None,
                )

                if hud_id:
                    return str(
                        hud_id
                    )

            except Exception:
                pass

            try:
                metadata = getattr(
                    current,
                    "metadata",
                    None,
                )

                if isinstance(
                    metadata,
                    dict,
                ):

                    hud_id = (
                        metadata.get("hud_id")
                        or metadata.get("HUD_ID")
                        or metadata.get("hud")
                        or metadata.get("hudId")
                        or metadata.get("HUD")
                    )

                    if hud_id:
                        return str(
                            hud_id
                        )

            except Exception:
                pass

        return None

    # ======================================================
    # STACK / LINEAGE
    # ======================================================

    @classmethod
    def get_stack(
        cls,
    ) -> List[dict]:

        try:
            stack = cls._get_stack()

        except Exception as exc:

            logger.debug(
                "[TrackContext] "
                "Stack read failed: %s",
                exc,
            )

            return []

        if not stack:
            return []

        normalized = []

        for item in list(stack):

            if item is None:
                continue

            # --------------------------------------------------
            # Structured entry
            # --------------------------------------------------

            if isinstance(
                item,
                dict,
            ):

                entry = dict(
                    item
                )

            # --------------------------------------------------
            # Tuple/list compatibility
            # --------------------------------------------------

            elif isinstance(
                item,
                (tuple, list),
            ):

                entry = {
                    "data": item,
                }

            # --------------------------------------------------
            # Raw identity
            # --------------------------------------------------

            else:

                entry = {
                    "track_id": str(
                        item
                    )
                }

            # --------------------------------------------------
            # Track identity
            # --------------------------------------------------

            if not entry.get(
                "track_id"
            ):

                try:
                    entry[
                        "track_id"
                    ] = cls.current()

                except Exception:
                    entry[
                        "track_id"
                    ] = None

            # --------------------------------------------------
            # Parent identity
            # --------------------------------------------------

            if not entry.get(
                "parent_id"
            ):

                try:
                    entry[
                        "parent_id"
                    ] = cls.get_parent()

                except Exception:
                    entry[
                        "parent_id"
                    ] = None

            # --------------------------------------------------
            # Task identity
            # --------------------------------------------------

            if not entry.get(
                "task_id"
            ):

                try:
                    task_id = cls.get(
                        "task_id"
                    )

                    if task_id:
                        entry[
                            "task_id"
                        ] = str(
                            task_id
                        )

                except Exception:
                    pass

            # --------------------------------------------------
            # Metadata container
            # --------------------------------------------------

            metadata = entry.get(
                "metadata"
            )

            if not isinstance(
                metadata,
                dict,
            ):
                metadata = {}

            entry[
                "metadata"
            ] = dict(
                metadata
            )

            # --------------------------------------------------
            # HUD correlation
            # --------------------------------------------------

            if not entry.get(
                "hud_id"
            ):

                try:
                    hud_id = cls.get_hud_id()

                    if hud_id:
                        entry[
                            "hud_id"
                        ] = hud_id

                except Exception:
                    pass

            # --------------------------------------------------
            # Source
            # --------------------------------------------------

            entry.setdefault(
                "source",
                "TrackContext",
            )

            # --------------------------------------------------
            # Timestamp
            # --------------------------------------------------

            entry.setdefault(
                "timestamp",
                time.time(),
            )

            # --------------------------------------------------
            # Canonical data field
            # --------------------------------------------------

            if "data" not in entry:

                for key in (
                    "payload",
                    "input",
                    "input_data",
                    "value",
                    "content",
                    "raw",
                ):

                    if key in entry:

                        entry[
                            "data"
                        ] = entry[key]

                        break

            entry.setdefault(
                "data",
                None,
            )

            normalized.append(
                entry
            )

        return normalized

    # ======================================================
    # SET
    # ======================================================

    @classmethod
    def set(
        cls,
        track_id: Optional[str],
        *,
        hud_id: Optional[str] = None,
    ):

        if not track_id:
            cls.clear()
            return None

        track_id = str(
            track_id
        )

        stack = cls._get_stack()

        if (
            not stack
            or stack[-1] != track_id
        ):
            stack.append(
                track_id
            )

        cls._set_stack(
            stack
        )

        _track_id_ctx.set(
            track_id
        )

        cls._current = track_id

        if hud_id is not None:
            _hud_id_ctx.set(
                hud_id
            )

        # --------------------------------------------------
        # System state follows identity.
        # --------------------------------------------------

        state = cls.get_system_state()

        state.last_track_id = (
            track_id
        )

        state.timestamp = (
            time.time()
        )

        _system_state_ctx.set(
            state
        )

        return track_id

    # ======================================================
    # PUSH
    # ======================================================

    @classmethod
    def push(
        cls,
        *,
        channel: str,
        priority: str = "MED",
        permissions: Optional[
            List[str]
        ] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
        hud_id: Optional[str] = None,
        skill: Optional[str] = None,
        command: Optional[str] = None,
        command_type: Optional[str] = None,
    ) -> str:

        channel = str(
            channel or "GEN"
        ).upper()

        if channel not in CHANNELS:

            logger.warning(
                "[TrackContext] "
                "Non-canonical channel: %s",
                channel,
            )

        priority = str(
            priority or "MED"
        ).upper()

        if priority not in PRIORITIES:
            priority = "MED"

        # --------------------------------------------------
        # Parent comes from the current L4 context.
        # --------------------------------------------------

        parent = cls.current()

        # --------------------------------------------------
        # Track identity creation belongs here.
        # --------------------------------------------------

        tid = (
            f"{channel}-"
            f"{uuid.uuid4().hex[:8]}"
        )

        cls.set(
            tid,
            hud_id=hud_id,
        )

        _parent_id_ctx.set(
            parent
        )

        # --------------------------------------------------
        # Canonical metadata.
        # --------------------------------------------------

        cls.write_meta(
            "channel",
            channel,
        )

        cls.write_meta(
            "priority",
            priority,
        )

        cls.write_meta(
            "parent_id",
            parent,
        )

        if skill:
            cls.write_meta("skill", str(skill))

        if command:
            cls.write_meta("command", str(command))

        if command_type:
            cls.write_meta("command_type", str(command_type).upper())

        if metadata:

            for key, value in metadata.items():

                cls.write_meta(
                    key,
                    value,
                )

        # --------------------------------------------------
        # Track permissions.
        # --------------------------------------------------

        if permissions:

            for permission in permissions:

                PermissionRegistry.assign_to_track(
                    tid,
                    permission,
                )

        return tid

    # ======================================================
    # POP
    # ======================================================

    @classmethod
    def pop(
        cls,
    ) -> Optional[str]:

        stack = cls._get_stack()

        if not stack:

            _track_id_ctx.set(
                None
            )

            _parent_id_ctx.set(
                None
            )

            cls._current = None

            return None

        finished = stack.pop()

        PermissionRegistry.clear_track(
            finished
        )

        parent = (
            stack[-1]
            if stack
            else None
        )

        cls._set_stack(
            stack
        )

        _track_id_ctx.set(
            parent
        )

        _parent_id_ctx.set(
            stack[-2]
            if len(stack) >= 2
            else None
        )

        cls._current = parent

        if not stack:
            _hud_id_ctx.set(
                None
            )

        state = cls.get_system_state()

        state.last_track_id = (
            parent
        )

        state.timestamp = (
            time.time()
        )

        _system_state_ctx.set(
            state
        )

        # IMPORTANT:
        # Track history is not cleared here.
        #
        # TrackRegistry / TimeTravel / replay infrastructure
        # owns historical lineage.

        return finished

    # ======================================================
    # CLEAR
    # ======================================================

    @classmethod
    def clear(cls):

        stack = cls._get_stack()

        if stack:

            for tid in stack:

                PermissionRegistry.clear_track(
                    tid
                )

        cls._set_stack([])

        _track_id_ctx.set(
            None
        )

        _parent_id_ctx.set(
            None
        )

        _hud_id_ctx.set(
            None
        )

        cls._current = None

        state = cls.get_system_state()

        state.last_track_id = None
        state.timestamp = time.time()

        _system_state_ctx.set(
            state
        )

    # ======================================================
    # METADATA / TRACK DATA
    # ======================================================

    @classmethod
    def write(
        cls,
        key: str,
        value: Any,
    ) -> bool:

        key = str(key or "").strip()

        if not key:
            return False

        # --------------------------------------------------
        # TrackSystem is the authority for identity.
        #
        # Do NOT manufacture a TrackID here.
        # --------------------------------------------------

        try:
            tid = cls.current()
        except Exception:
            tid = None

        if not tid:
            logger.debug(
                "[TrackContext] Metadata write skipped | "
                "no active TrackID | key=%s",
                key,
            )
            return False

        # --------------------------------------------------
        # Normalize identity.
        # --------------------------------------------------

        tid = str(tid)

        # --------------------------------------------------
        # Write through the canonical Track store.
        # --------------------------------------------------

        try:

            result = store_write(
                f"track:{tid}:{key}",
                value,
            )

            return bool(result)

        except Exception as exc:

            logger.warning(
                "[TrackContext] Metadata write failed | "
                "track=%s key=%s error=%s",
                tid,
                key,
                exc,
            )

            return False

    # ======================================================
    # METADATA READ
    # ======================================================

    @classmethod
    def read(
        cls,
        key: str,
        default: Any = None,
    ) -> Any:

        key = str(key or "").strip()

        if not key:
            return default

        try:
            tid = cls.current()
        except Exception:
            tid = None

        if not tid:
            return default

        try:

            return store_read(
                f"track:{tid}:{key}",
                default=default,
            )

        except Exception as exc:

            logger.debug(
                "[TrackContext] Metadata read failed | "
                "track=%s key=%s error=%s",
                tid,
                key,
                exc,
            )

            return default

    # ======================================================
    # METADATA WRITE
    # ======================================================

    @classmethod
    def write_meta(
        cls,
        key: str,
        value: Any,
    ) -> bool:

        key = str(key or "").strip()

        if not key:
            return False

        if key not in METADATA_KEYS:

            logger.debug(
                "[TrackContext] Extended metadata | "
                "key=%s",
                key,
            )

        return cls.write(
            key,
            value,
        )

    # ======================================================
    # BULK METADATA WRITE
    # ======================================================

    @classmethod
    def write_metadata(
        cls,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:

        if not isinstance(metadata, dict):
            return False

        try:
            tid = cls.current()
        except Exception:
            tid = None

        if not tid:
            logger.debug(
                "[TrackContext] Bulk metadata skipped | "
                "no active TrackID"
            )
            return False

        success = True

        for key, value in metadata.items():

            try:

                if not cls.write_meta(
                    key,
                    value,
                ):
                    success = False

            except Exception as exc:

                success = False

                logger.debug(
                    "[TrackContext] Metadata item failed | "
                    "track=%s key=%s error=%s",
                    tid,
                    key,
                    exc,
                )

        return success

    # ======================================================
    # METADATA SNAPSHOT
    # ======================================================

    @classmethod
    def get_metadata(
        cls,
    ) -> Dict[str, Any]:

        try:
            tid = cls.current()
        except Exception:
            tid = None

        if not tid:
            return {}

        metadata: Dict[str, Any] = {}

        # --------------------------------------------------
        # Canonical metadata.
        # --------------------------------------------------

        for key in METADATA_KEYS:

            try:

                value = cls.read(
                    key,
                    None,
                )

                if value is not None:
                    metadata[key] = value

            except Exception:
                continue

        # --------------------------------------------------
        # Preserve useful extended metadata.
        #
        # The canonical store may contain additional fields
        # written by Heartbeat, HealthMonitor, Qbit, etc.
        # Those fields are intentionally not rejected.
        # --------------------------------------------------

        for key in (
            "cpu",
            "mem",
            "health_state",
            "resource_state",
            "limp_mode",
            "qbit_id",
            "qbit_generation",
            "qbit_state",
            "qbit_score",
            "qbit_vector",
            "watchdog_state",
            "watchdog_reason",
            "heartbeat_tick",
            "timestamp",
        ):

            if key in metadata:
                continue

            try:

                value = cls.read(
                    key,
                    None,
                )

                if value is not None:
                    metadata[key] = value

            except Exception:
                continue

        return metadata

    # ======================================================
    # DYNAMIC TRACK DATA
    # ======================================================

    @classmethod
    def get_data(
        cls,
    ) -> Dict[str, Any]:

        try:
            tid = cls.current()
        except Exception:
            tid = None

        if not tid:
            return {}

        data: Dict[str, Any] = {}

        # --------------------------------------------------
        # Canonical payload/data fields.
        # --------------------------------------------------

        for key in (
            "data",
            "payload",
            "input",
            "input_data",
            "output",
            "output_data",
            "result",
            "value",
        ):

            try:

                value = cls.read(
                    key,
                    None,
                )

                if value is not None:
                    data[key] = value

            except Exception:
                continue

        return data

    # ======================================================
    # TRACK METADATA + DATA PACKET
    # ======================================================

    @classmethod
    def metadata_packet(
        cls,
        data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        tid = cls.current()

        if not tid:
            return {
                "track_id": None,
                "metadata": {},
                "data": data,
            }

        packet_metadata = cls.get_metadata()

        if isinstance(metadata, dict):
            packet_metadata.update(
                metadata
            )

        return {
            "track_id": str(tid),
            "parent_id": cls.get_parent(),
            "metadata": packet_metadata,
            "data": data,
            "timestamp": time.time(),
        }

    # ======================================================
    # DEVICE TRACK
    # ======================================================

    @dataclass
    class DeviceTrack:

        id: str
        name: str
        kind: str = "local"

    # ======================================================
    # SYSTEM STATE
    # ======================================================

    @classmethod
    def get_system_state(
        cls,
    ) -> SystemState:

        state = _system_state_ctx.get()

        if state is None:

            state = SystemState(
                status="ONLINE",
                phase="INIT",
                authority="QBIT",
                timestamp=time.time(),
            )

            _system_state_ctx.set(
                state
            )

        return state

    @classmethod
    def set_system_state(
        cls,
        *,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        boot_complete: Optional[bool] = None,
        shutdown_requested: Optional[bool] = None,
        degraded: Optional[bool] = None,
        resource_state: Optional[str] = None,
    ) -> Dict[str, Any]:

        state = cls.get_system_state()

        if status is not None:
            state.status = str(
                status
            )

        if phase is not None:
            state.phase = str(
                phase
            )

        if boot_complete is not None:
            state.boot_complete = bool(
                boot_complete
            )

        if shutdown_requested is not None:
            state.shutdown_requested = bool(
                shutdown_requested
            )

        if degraded is not None:
            state.degraded = bool(
                degraded
            )

        if resource_state is not None:
            state.resource_state = str(
                resource_state
            )

        state.timestamp = time.time()

        state.last_track_id = (
            cls.current()
        )

        _system_state_ctx.set(
            state
        )

        return state.as_dict()

    @classmethod
    def system_state(
        cls,
    ):
        return (
            cls.get_system_state()
            .as_dict()
        )

    @classmethod
    def mark_boot_complete(cls):
        return cls.set_system_state(
            status="ONLINE",
            phase="RUNTIME",
            boot_complete=True,
            shutdown_requested=False,
        )

    @classmethod
    def mark_shutdown(cls):
        return cls.set_system_state(
            status="SHUTDOWN",
            phase="SHUTDOWN",
            shutdown_requested=True,
        )

    @classmethod
    def mark_degraded(
        cls,
        resource_state: str = "DEGRADED",
    ):
        return cls.set_system_state(
            status="DEGRADED",
            degraded=True,
            resource_state=resource_state,
        )

    # ======================================================
    # QBIT PROCESSOR COMPATIBILITY BRIDGE
    # ======================================================

    @classmethod
    def register_processor(
        cls,
        processor: Callable[..., Any],
    ):

        if not callable(processor):

            raise TypeError(
                "processor must be callable"
            )

        cls._processor = processor

        logger.info(
            "[TrackContext] Processor registered | "
            "authority=QBIT"
        )

        return True

    @classmethod
    def unregister_processor(cls):

        cls._processor = None

        return True

    @classmethod
    def has_processor(cls):

        return callable(
            cls._processor
        )

    # ======================================================
    # QBIT PROCESS
    # ======================================================

    @classmethod
    def process(
        cls,
        *,
        stage: str,
        payload: Any,
        input_type: str,
        output_type: str,
        **metadata,
    ):

        if stage not in PIPELINE_STAGES:

            raise ValueError(
                f"Illegal pipeline stage: {stage}"
            )

        processor = cls._processor

        if processor is None:

            logger.debug(
                "[TrackContext] "
                "No processor registered | TrackID=%s",
                cls.current(),
            )

            return None

        packet = cls.context_packet(
            data=payload,
            metadata={
                **metadata,
                "input_type": input_type,
                "output_type": output_type,
            },
            state="PROCESS",
            stage=stage,
        )

        try:

            return processor(
                packet
            )

        except TypeError:

            return processor(
                stage=stage,
                payload=payload,
                input_type=input_type,
                output_type=output_type,
                track_id=cls.current(),
                parent_id=cls.get_parent(),
                metadata=dict(
                    metadata
                ),
            )

    # ======================================================
    # QBIT PACKET CONTEXT
    # ======================================================

    @classmethod
    def context_packet(
        cls,
        *,
        data: Any = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
        state: str = "ENTER",
        stage: Optional[str] = None,
    ) -> Dict[str, Any]:

        packet_metadata = {}

        # Existing Track metadata first.
        try:

            packet_metadata.update(
                cls.get_metadata()
            )

        except Exception:
            pass

        # Caller metadata overrides defaults.
        if metadata:

            packet_metadata.update(
                metadata
            )

        return {
            "track_id": cls.current(),
            "parent_id": cls.get_parent(),
            "lineage": cls.get_stack(),
            "data": data,
            "metadata": packet_metadata,
            "state": state,
            "stage": stage,
            "timestamp": int(
                time.time() * 1000
            ),
        }

    # ======================================================
    # SNAPSHOT
    # ======================================================

    @classmethod
    def snapshot(cls):

        return {
            "track_id": cls.current(),
            "parent_id": cls.get_parent(),
            "hud_id": cls.get_hud_id(),
            "stack": cls.get_stack(),
            "metadata": cls.get_metadata(),
            "data": cls.get_data(),
            "system": cls.system_state(),
            "processor_registered": cls.has_processor(),

            # ------------------------------------------------
            # Authority declaration
            # ------------------------------------------------
            #
            # TrackContext:
            #   identity + lineage
            #
            # TrackSystem:
            #   data-flow authority
            #
            # Qbit:
            #   processing authority
            #
            # QbitDialer:
            #   command/processing gateway
            # ------------------------------------------------

            "authority": "TRACK_CONTEXT",
            "flow_authority": "TRACK_SYSTEM",
            "processing_authority": "QBIT",
            "command_authority": "QBIT_DIALER",
        }


    @classmethod
    def get_hud_id(cls) -> Optional[str]:


        # ======================================================
        # 1. Canonical HUD ContextVar
        # ======================================================

        try:
            hud_id = _hud_id_ctx.get()

            if hud_id:
                return str(hud_id)

        except Exception as exc:

            logger.debug(
                "[TrackContext] "
                "HUD ContextVar read failed: %s",
                exc,
            )

        # ======================================================
        # 2. Inspect active context
        # ======================================================

        try:
            current = cls.current()

        except Exception:
            current = None

        if current is None:
            return None

        # ======================================================
        # 3. Dictionary-style context
        # ======================================================

        if isinstance(current, dict):

            hud_id = (
                current.get("hud_id")
                or current.get("HUD_ID")
                or current.get("hud")
                or current.get("hudId")
            )

            if hud_id:
                return str(hud_id)

            # ----------------------------------------------
            # Dynamic metadata bridge
            # ----------------------------------------------

            metadata = current.get("metadata")

            if isinstance(metadata, dict):

                hud_id = (
                    metadata.get("hud_id")
                    or metadata.get("HUD_ID")
                    or metadata.get("hud")
                    or metadata.get("hudId")
                    or metadata.get("HUD")
                )

                if hud_id:
                    return str(hud_id)

        # ======================================================
        # 4. Object-style context
        # ======================================================

        else:

            try:
                hud_id = getattr(
                    current,
                    "hud_id",
                    None,
                )

                if hud_id:
                    return str(hud_id)

            except Exception:
                pass

            # ----------------------------------------------
            # Dynamic metadata bridge
            # ----------------------------------------------

            try:
                metadata = getattr(
                    current,
                    "metadata",
                    None,
                )

                if isinstance(metadata, dict):

                    hud_id = (
                        metadata.get("hud_id")
                        or metadata.get("HUD_ID")
                        or metadata.get("hud")
                        or metadata.get("hudId")
                        or metadata.get("HUD")
                    )

                    if hud_id:
                        return str(hud_id)

            except Exception:
                pass

        # ======================================================
        # 5. Optional metadata/context registry fallback
        # ======================================================
        #
        # Some versions of TrackContext maintain metadata
        # separately from current(). If present, use it without
        # requiring a specific implementation.
        # ======================================================

        for attr_name in (
            "get_metadata",
            "metadata",
            "context",
            "state",
        ):

            try:

                source = getattr(
                    cls,
                    attr_name,
                    None,
                )

                if callable(source):
                    source = source()

                if isinstance(source, dict):

                    hud_id = (
                        source.get("hud_id")
                        or source.get("HUD_ID")
                        or source.get("hud")
                        or source.get("hudId")
                    )

                    if hud_id:
                        return str(hud_id)

            except Exception:
                continue

        # ======================================================
        # 6. No HUD identity yet
        # ======================================================

        return None

    @classmethod
    def get_stack(cls) -> List[dict]:

        # ------------------------------------------------------
        # Obtain the underlying stack safely.
        # ------------------------------------------------------

        try:
            stack = cls._get_stack()
        except Exception as exc:
            logger.debug(
                "[TrackContext] Stack read failed: %s",
                exc,
            )
            return []

        if stack is None:
            return []

        # ------------------------------------------------------
        # Normalize stack into structured entries.
        # ------------------------------------------------------

        normalized = []

        for item in list(stack):

            if item is None:
                continue

            # --------------------------------------------------
            # Already structured
            # --------------------------------------------------

            if isinstance(item, dict):

                entry = dict(item)

            # --------------------------------------------------
            # Tuple/list compatibility
            # --------------------------------------------------

            elif isinstance(item, (tuple, list)):

                entry = {
                    "data": item,
                }

            # --------------------------------------------------
            # Raw/unstructured input
            # --------------------------------------------------

            else:

                entry = {
                    "data": item,
                }

            # --------------------------------------------------
            # Resolve identity from current context.
            # --------------------------------------------------

            if not entry.get("track_id"):
                try:
                    entry["track_id"] = cls.get_current()
                except Exception:
                    entry["track_id"] = None

            if not entry.get("parent_id"):
                try:
                    entry["parent_id"] = cls.get_parent()
                except Exception:
                    entry["parent_id"] = None

            # --------------------------------------------------
            # Task identity.
            # --------------------------------------------------

            if not entry.get("task_id"):

                for key in (
                    "task",
                    "taskId",
                    "TaskID",
                ):

                    if entry.get(key):
                        entry["task_id"] = str(
                            entry[key]
                        )
                        break

            # --------------------------------------------------
            # Metadata container.
            # --------------------------------------------------

            metadata = entry.get(
                "metadata"
            )

            if not isinstance(metadata, dict):
                metadata = {}

            entry["metadata"] = metadata

            # --------------------------------------------------
            # Preserve HUD correlation.
            # --------------------------------------------------

            if not entry.get("hud_id"):

                try:
                    hud_id = cls.get_hud_id()

                    if hud_id:
                        entry["hud_id"] = hud_id

                except Exception:
                    pass

            # --------------------------------------------------
            # Source.
            # --------------------------------------------------

            entry.setdefault(
                "source",
                "TrackContext",
            )

            # --------------------------------------------------
            # Timestamp.
            # --------------------------------------------------

            entry.setdefault(
                "timestamp",
                time.time(),
            )

            # --------------------------------------------------
            # Canonical data field.
            #
            # If caller supplied payload/input/output/etc.,
            # preserve it rather than throwing it away.
            # --------------------------------------------------

            if "data" not in entry:

                for key in (
                    "payload",
                    "input",
                    "input_data",
                    "value",
                    "content",
                    "raw",
                ):

                    if key in entry:

                        entry["data"] = entry[key]
                        break

            entry.setdefault(
                "data",
                None,
            )

            normalized.append(entry)

        return normalized
    # ------------------------------------------------------
    # SET
    # ------------------------------------------------------

    @classmethod
    def set(
        cls,
        track_id: Optional[str],
        *,
        hud_id: Optional[str] = None,
    ):

        if not track_id:
            cls.clear()
            return None

        stack = cls._get_stack()

        if not stack or stack[-1] != track_id:
            stack.append(track_id)

        cls._set_stack(stack)
        _track_id_ctx.set(track_id)
        cls._current = track_id

        if hud_id is not None:
            _hud_id_ctx.set(hud_id)

        state = cls.get_system_state()
        state.last_track_id = track_id
        state.timestamp = time.time()
        _system_state_ctx.set(state)

        return track_id

    # ------------------------------------------------------
    # PUSH
    # ------------------------------------------------------

    @classmethod
    def push(
        cls,
        *,
        channel: str,
        priority: str = "MED",
        permissions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        hud_id: Optional[str] = None,
        skill: Optional[str] = None,
        command: Optional[str] = None,
        command_type: Optional[str] = None,
    ) -> str:

        channel = str(channel or "GEN").upper()

        if channel not in CHANNELS:
            logger.warning(
                "[TrackContext] Non-canonical channel: %s",
                channel,
            )

        priority = str(priority or "MED").upper()

        if priority not in PRIORITIES:
            priority = "MED"

        parent = cls.current()

        tid = (
            f"{channel}-"
            f"{uuid.uuid4().hex[:8]}"
        )

        cls.set(
            tid,
            hud_id=hud_id,
        )

        _parent_id_ctx.set(parent)

        cls.write_meta(
            "channel",
            channel,
        )

        cls.write_meta(
            "priority",
            priority,
        )

        cls.write_meta(
            "parent_id",
            parent,
        )

        if skill:
            cls.write_meta("skill", str(skill))

        if command:
            cls.write_meta("command", str(command))

        if command_type:
            cls.write_meta("command_type", str(command_type).upper())

        if metadata:
            for key, value in metadata.items():
                cls.write_meta(
                    key,
                    value,
                )

        if permissions:
            for permission in permissions:
                PermissionRegistry.assign_to_track(
                    tid,
                    permission,
                )

        return tid

    # ------------------------------------------------------
    # POP
    # ------------------------------------------------------

    @classmethod
    def pop(cls) -> Optional[str]:
        stack = cls._get_stack()

        if not stack:
            _track_id_ctx.set(None)
            _parent_id_ctx.set(None)
            cls._current = None
            return None

        finished = stack.pop()

        PermissionRegistry.clear_track(
            finished
        )

        parent = stack[-1] if stack else None

        cls._set_stack(stack)
        _track_id_ctx.set(parent)
        _parent_id_ctx.set(
            stack[-2] if len(stack) >= 2 else None
        )

        cls._current = parent

        if not stack:
            _hud_id_ctx.set(None)

        state = cls.get_system_state()
        state.last_track_id = parent
        state.timestamp = time.time()
        _system_state_ctx.set(state)

        # IMPORTANT:
        # Do NOT clear the global Track store here.
        #
        # Track history belongs to TrackRegistry /
        # TimeTravel / replay infrastructure.

        return finished

    # ------------------------------------------------------
    # CLEAR
    # ------------------------------------------------------

    @classmethod
    def clear(cls):

        stack = cls._get_stack()

        if stack:
            for tid in stack:
                PermissionRegistry.clear_track(tid)

        cls._set_stack([])

        _track_id_ctx.set(None)
        _parent_id_ctx.set(None)
        _hud_id_ctx.set(None)

        cls._current = None

        state = cls.get_system_state()
        state.last_track_id = None
        state.timestamp = time.time()
        _system_state_ctx.set(state)

    # ------------------------------------------------------
    # METADATA
    # ------------------------------------------------------
    # ------------------------------------------------------
    # METADATA
    # ------------------------------------------------------

    @classmethod
    def write(
        cls,
        key: str,
        value: Any,
    ) -> bool:

        tid = cls.current()

        # Allow an explicit TrackID bootstrap write.
        if not tid and key == "track_id" and value:
            tid = str(value)

        if not tid:
            logger.warning(
                "[TrackContext] write without TrackID: %s",
                key,
            )
            return False

        return store_write(
            f"track:{tid}:{key}",
            value,
        )

    @classmethod
    def read(
        cls,
        key: str,
        default: Any = None,
    ) -> Any:

        tid = cls.current()

        if not tid:
            return default

        return store_read(
            f"track:{tid}:{key}",
            default=default,
        )

    @classmethod
    def write_meta(
        cls,
        key: str,
        value: Any,
    ):

        if key not in METADATA_KEYS:
            logger.debug(
                "[TrackContext] Extended metadata: %s",
                key,
            )

        return cls.write(
            key,
            value,
        )

    # ------------------------------------------------------
    # DEVICE TRACK
    # ------------------------------------------------------

    @dataclass
    class DeviceTrack:
        id: str
        name: str
        kind: str = "local"

    # ======================================================
    # SYSTEM STATE
    # ======================================================

    @classmethod
    def get_system_state(cls) -> SystemState:

        state = _system_state_ctx.get()

        if state is None:
            state = SystemState(
                status="ONLINE",
                phase="INIT",
                authority="QBIT",
                timestamp=time.time(),
            )

            _system_state_ctx.set(state)

        return state

    @classmethod
    def set_system_state(
        cls,
        *,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        boot_complete: Optional[bool] = None,
        shutdown_requested: Optional[bool] = None,
        degraded: Optional[bool] = None,
        resource_state: Optional[str] = None,
    ) -> Dict[str, Any]:

        state = cls.get_system_state()

        if status is not None:
            state.status = str(status)

        if phase is not None:
            state.phase = str(phase)

        if boot_complete is not None:
            state.boot_complete = bool(
                boot_complete
            )

        if shutdown_requested is not None:
            state.shutdown_requested = bool(
                shutdown_requested
            )

        if degraded is not None:
            state.degraded = bool(
                degraded
            )

        if resource_state is not None:
            state.resource_state = str(
                resource_state
            )

        state.timestamp = time.time()
        state.last_track_id = cls.current()

        _system_state_ctx.set(state)

        return state.as_dict()

    @classmethod
    def system_state(cls):
        return cls.get_system_state().as_dict()

    @classmethod
    def mark_boot_complete(cls):
        return cls.set_system_state(
            status="ONLINE",
            phase="RUNTIME",
            boot_complete=True,
            shutdown_requested=False,
        )

    @classmethod
    def mark_shutdown(cls):
        return cls.set_system_state(
            status="SHUTDOWN",
            phase="SHUTDOWN",
            shutdown_requested=True,
        )

    @classmethod
    def mark_degraded(
        cls,
        resource_state: str = "DEGRADED",
    ):
        return cls.set_system_state(
            status="DEGRADED",
            degraded=True,
            resource_state=resource_state,
        )

    # ======================================================
    # QBIT PROCESSOR COMPATIBILITY BRIDGE
    # ======================================================

    @classmethod
    def register_processor(
        cls,
        processor: Callable[..., Any],
    ):

        if not callable(processor):
            raise TypeError(
                "processor must be callable"
            )

        cls._processor = processor

        logger.info(
            "[TrackContext] Processor registered | "
            "authority=QBIT"
        )

        return True

    @classmethod
    def unregister_processor(cls):
        cls._processor = None
        return True

    @classmethod
    def has_processor(cls):
        return callable(
            cls._processor
        )

    @classmethod
    def process(
        cls,
        *,
        stage: str,
        payload: Any,
        input_type: str,
        output_type: str,
        **metadata,
    ):

        if stage not in PIPELINE_STAGES:
            raise ValueError(
                f"Illegal pipeline stage: {stage}"
            )

        processor = cls._processor

        if processor is None:
            logger.debug(
                "[TrackContext] No processor registered | "
                "TrackID=%s",
                cls.current(),
            )
            return None

        packet = {
            "track_id": cls.current(),
            "parent_id": cls.get_parent(),
            "stage": stage,
            "input_type": input_type,
            "output_type": output_type,
            "payload": payload,
            "metadata": dict(metadata),
            "lineage": cls.get_stack(),
        }

        try:
            return processor(packet)

        except TypeError:
            return processor(
                stage=stage,
                payload=payload,
                input_type=input_type,
                output_type=output_type,
                track_id=cls.current(),
                parent_id=cls.get_parent(),
                metadata=dict(metadata),
            )

    # ======================================================
    # QBIT PACKET CONTEXT
    # ======================================================

    @classmethod
    def context_packet(
        cls,
        *,
        data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        state: str = "ENTER",
        stage: Optional[str] = None,
    ) -> Dict[str, Any]:

        tid = cls.current()

        packet_metadata = {}

        if metadata:
            packet_metadata.update(
                metadata
            )

        return {
            "track_id": tid,
            "parent_id": cls.get_parent(),
            "lineage": cls.get_stack(),
            "data": data,
            "metadata": packet_metadata,
            "state": state,
            "stage": stage,
            "timestamp": int(
                time.time() * 1000
            ),
        }

    # ======================================================
    # SNAPSHOT
    # ======================================================

    @classmethod
    def snapshot(cls):
        return {
            "track_id": cls.current(),
            "parent_id": cls.get_parent(),
            "hud_id": cls.get_hud_id(),
            "stack": cls.get_stack(),
            "system": cls.system_state(),
            "processor_registered": cls.has_processor(),
            "authority": "TRACK_CONTEXT",
            "processing_authority": "QBIT",
            "flow_authority": "TRACK_SYSTEM",
        }


# ==========================================================
# CANONICAL TRACK API
# ==========================================================

def track(
    *,
    channel: str,
    state: str,
    stage: str,
    payload: Any,
    input_type: str,
    output_type: str,
    priority: str = "MED",
    metadata: Optional[Dict[str, Any]] = None,
):

    tid = TrackContext.push(
        channel=channel,
        priority=priority,
        metadata=metadata,
    )

    try:

        TrackContext.write_meta(
            "stage",
            stage,
        )

        TrackContext.write_meta(
            "input_type",
            input_type,
        )

        TrackContext.write_meta(
            "output_type",
            output_type,
        )

        TrackContext.write_meta(
            "state",
            state,
        )

        return TrackContext.process(
            stage=stage,
            payload=payload,
            input_type=input_type,
            output_type=output_type,
        )

    finally:
        TrackContext.pop()


# ==========================================================
# COMPATIBILITY HELPERS
# ==========================================================

def current_track_id():
    return TrackContext.current()


def get_system_state():
    return TrackContext.system_state()


# ==========================================================
# END FILE
# ==========================================================