
# ==========================================================
# FILE: memory_manager.py
# PATH: SEED_ROOT/core/memory_manager.py
# PURPOSE:
# SEED Memory Manager with storage-aware allocation,
# predictive memory migration, automatic short-to-long term
# promotion, backup drives, personnel memory split, audits,
# importance-based retention, HUD prompts for critical
# migration, and authoritative SEED runtime integration.
#
# VERSION: 13.0
# UPDATED: 2026-09-05
# ==========================================================

import asyncio
import datetime
import json
import logging
import os
import re
import shutil
import uuid

from seed.skills.autofix.base_fix_skill import AutoFixPipeline
from seed.skills.action_registry import (
    get_registered_actions,
    queue_action,
)

logger = logging.getLogger("SEEDMemoryManager")
logging.basicConfig(level=logging.INFO)


# ==========================================================
# TrackID helper
# ==========================================================

def generate_track_id(prefix="MEM", category=None, parent_id=None):
    ts = int(datetime.datetime.now().timestamp() * 1000)
    short_uuid = uuid.uuid4().hex[:8]

    cat_part = (
        category.replace(" ", "")
        if category
        else "GEN"
    )

    track_id = (
        f"{prefix}-{cat_part}-{ts}-{short_uuid}"
    )

    if parent_id:
        track_id += f"-P-{parent_id[:8]}"

    return track_id


# ==========================================================
# File / Function link checker & stub generator
# ==========================================================

def check_file_function_references(payload, base_dir):
    issues = []
    suggestions = []
    stubs = []

    if "content" not in payload:
        return issues, suggestions, stubs

    content = payload["content"]

    # ------------------------------------------------------
    # Detect file imports
    # ------------------------------------------------------

    file_refs = re.findall(
        r"(?:(?:import\s+([\w\.]+))|"
        r"(?:from\s+([\w\.]+)\s+import))",
        content,
    )

    file_refs = [
        ref
        for tup in file_refs
        for ref in tup
        if ref
    ]

    for ref in file_refs:
        ref_path = (
            os.path.join(
                base_dir,
                *ref.split("."),
            )
            + ".py"
        )

        if not os.path.exists(ref_path):
            issues.append(
                f"Broken file reference: {ref_path}"
            )

            suggestions.append(
                f"# AUTOFIX: create missing file {ref_path}"
            )

            stubs.append(ref_path)

    # ------------------------------------------------------
    # Detect function calls
    # ------------------------------------------------------

    func_defs = re.findall(
        r"def\s+(\w+)\s*\(",
        content,
    )

    func_calls = re.findall(
        r"(\w+)\s*\(",
        content,
    )

    for call in func_calls:
        if call not in func_defs:
            issues.append(
                f"Potential missing function: {call}"
            )

            suggestions.append(
                "def "
                f"{call}():\n"
                "    # AUTOFIX: generated stub\n"
                "    pass\n"
            )

    return issues, suggestions, stubs


# ==========================================================
# SEED Memory Manager
# ==========================================================

class SEEDMemoryManager:

    # ======================================================
    # INITIALIZATION
    # ======================================================

    def __init__(
        self,
        storage_root="./SEED_ROOT",
        backup_drives=None,
        qbit=None,
        base_dir=None,
        event_bus=None,
        intent_engine=None,
        qbit_dialer=None,
        agent_manager=None,
        build_manager=None,
        notify_operator=None,
        autofix_pipeline=AutoFixPipeline,
        max_short_term=500,
        min_importance=0.5,
        recall_window=100,

        # --------------------------------------------------
        # Authoritative SEED runtime dependencies
        # --------------------------------------------------

        queue_loop=None,
        track_system=None,
        track_context=None,
        registry=None,
        nodes=None,
    ):
        self.storage_root = storage_root
        self.base_dir = base_dir or os.getcwd()

        # --------------------------------------------------
        # Core runtime references
        # --------------------------------------------------

        self.event_bus = event_bus
        self.qbit = qbit
        self.qbit_dialer = qbit_dialer
        self.queue_loop = queue_loop

        self.intent_engine = intent_engine
        self.agent_manager = agent_manager
        self.build_manager = build_manager
        self.notify_operator = notify_operator
        self.autofix_pipeline = autofix_pipeline

        # --------------------------------------------------
        # SEED data / identity authorities
        # --------------------------------------------------

        self.track_system = track_system
        self.track_context = track_context
        self.registry = registry
        self.nodes = nodes

        # --------------------------------------------------
        # Maintenance state
        # --------------------------------------------------

        self._prune_task = None

        # --------------------------------------------------
        # Memory configuration
        # --------------------------------------------------

        self.max_short_term = max_short_term
        self.min_importance = min_importance
        self.recall_window = recall_window

        # ==================================================
        # MEMORY STORAGE
        # ==================================================

        self.memory_dir = os.path.join(
            storage_root,
            "memory",
        )

        os.makedirs(
            self.memory_dir,
            exist_ok=True,
        )

        self.short_term_file = os.path.join(
            self.memory_dir,
            "short_term.json",
        )

        self.long_term_file = os.path.join(
            self.memory_dir,
            "long_term.json",
        )

        # --------------------------------------------------
        # Load memory
        # --------------------------------------------------

        self.short_term = self._load(
            self.short_term_file,
            default=[],
        )

        self.long_term = self._load(
            self.long_term_file,
            default=[],
        )

        # ==================================================
        # STORAGE / MEMORY ALLOCATION
        # ==================================================

        self.total_space, self.free_space = (
            self._get_storage_stats(storage_root)
        )

        self.memory_quota = (
            self.total_space * 0.5
        )

        self.system_quota = (
            self.total_space * 0.5
        )

        self.backup_drives = (
            backup_drives or []
        )

        self.backup_status = {
            drive: self._get_storage_stats(drive)
            for drive in self.backup_drives
        }

        # --------------------------------------------------
        # Split memory into short-term and long-term
        # quotas
        # --------------------------------------------------

        self.short_term_quota = (
            self.memory_quota * 0.25
        )

        self.long_term_quota = (
            self.memory_quota * 0.25
        )

        logger.info(
            "[MEMORY INIT] Total space: %s, Free space: %s",
            self.total_space,
            self.free_space,
        )

        logger.info(
            "[MEMORY INIT] Memory quota: %s, "
            "Short-term: %s, Long-term: %s",
            self.memory_quota,
            self.short_term_quota,
            self.long_term_quota,
        )

        if self.backup_drives:
            logger.info(
                "[MEMORY INIT] Backup drives detected: %s",
                self.backup_drives,
            )

        logger.info(
            "[MEMORY INIT] Runtime bindings | "
            "qbit=%s | dialer=%s | queue_loop=%s | "
            "track_system=%s | track_context=%s | "
            "registry=%s | nodes=%s | event_bus=%s",
            type(self.qbit).__name__
            if self.qbit is not None
            else "NONE",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer is not None
            else "NONE",
            type(self.queue_loop).__name__
            if self.queue_loop is not None
            else "NONE",
            type(self.track_system).__name__
            if self.track_system is not None
            else "NONE",
            type(self.track_context).__name__
            if self.track_context is not None
            else "NONE",
            type(self.registry).__name__
            if self.registry is not None
            else "NONE",
            type(self.nodes).__name__
            if self.nodes is not None
            else "NONE",
            type(self.event_bus).__name__
            if self.event_bus is not None
            else "NONE",
        )

    # ======================================================
    # RUNTIME BINDING
    # ======================================================

    def bind_runtime(
        self,
        *,
        qbit=None,
        queue_loop=None,
        qbit_dialer=None,
        event_bus=None,
        intent_engine=None,
        agent_manager=None,
        build_manager=None,
        track_system=None,
        track_context=None,
        registry=None,
        nodes=None,
        notify_operator=None,
    ):

        if qbit is not None:
            self.qbit = qbit

        if queue_loop is not None:
            self.queue_loop = queue_loop

        if qbit_dialer is not None:
            self.qbit_dialer = qbit_dialer

        if event_bus is not None:
            self.event_bus = event_bus

        if intent_engine is not None:
            self.intent_engine = intent_engine

        if agent_manager is not None:
            self.agent_manager = agent_manager

        if build_manager is not None:
            self.build_manager = build_manager

        if track_system is not None:
            self.track_system = track_system

        if track_context is not None:
            self.track_context = track_context

        if registry is not None:
            self.registry = registry

        if nodes is not None:
            self.nodes = nodes

        if notify_operator is not None:
            self.notify_operator = notify_operator

        logger.info(
            "[MEMORY BIND] Runtime synchronized | "
            "qbit=%s | dialer=%s | queue_loop=%s | "
            "track_system=%s | registry=%s | nodes=%s",
            type(self.qbit).__name__
            if self.qbit is not None
            else "NONE",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer is not None
            else "NONE",
            type(self.queue_loop).__name__
            if self.queue_loop is not None
            else "NONE",
            type(self.track_system).__name__
            if self.track_system is not None
            else "NONE",
            type(self.registry).__name__
            if self.registry is not None
            else "NONE",
            type(self.nodes).__name__
            if self.nodes is not None
            else "NONE",
        )

        return self

    # ======================================================
    # STORAGE STATS
    # ======================================================

    def _get_storage_stats(self, path):
        try:
            total, used, free = (
                shutil.disk_usage(path)
            )

            return total, free

        except Exception as e:
            logger.warning(
                "[STORAGE] Failed to get storage stats "
                "for %s: %s",
                path,
                e,
            )

            return 0, 0

    # ======================================================
    # LOAD / SAVE
    # ======================================================

    def _load(self, path, default):
        if os.path.exists(path):
            try:
                with open(
                    path,
                    "r",
                    encoding="utf-8",
                ) as f:
                    return json.load(f)

            except Exception as e:
                logger.warning(
                    "[MEMORY LOAD] Failed to load %s: %s",
                    path,
                    e,
                )

        return default

    def _save(self):
        try:
            with open(
                self.short_term_file,
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    self.short_term,
                    f,
                    indent=2,
                )

            with open(
                self.long_term_file,
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    self.long_term,
                    f,
                    indent=2,
                )

        except Exception as e:
            logger.warning(
                "[MEMORY SAVE] Failed to save memory: %s",
                e,
            )

    # ======================================================
    # RUNTIME IDENTITY
    # ======================================================

    def _resolve_track_id(
        self,
        event_type,
        parent_id=None,
    ):
        return generate_track_id(
            prefix="MEM",
            category=event_type,
            parent_id=parent_id,
        )

    def _runtime_metadata(self):

        metadata = {}

        if self.qbit is not None:
            metadata["qbit_id"] = getattr(
                self.qbit,
                "qbit_id",
                getattr(
                    self.qbit,
                    "id",
                    None,
                ),
            )

        if self.track_context is not None:
            metadata["track_context_id"] = (
                getattr(
                    self.track_context,
                    "track_id",
                    getattr(
                        self.track_context,
                        "id",
                        None,
                    ),
                )
            )

        return metadata

    # ======================================================
    # RECORD / INGEST
    # ======================================================

    def record(
        self,
        event_type,
        payload,
        parent_id=None,
        importance=1.0,
        limp_mode=False,
        auto_actions=True,
    ):
        if payload is None:
            payload = {}

        if limp_mode:
            importance *= 0.5

        # --------------------------------------------------
        # Qbit-based memory scoring
        # --------------------------------------------------

        if self.qbit_dialer:
            try:
                importance = (
                    self.qbit_dialer.score_memory(
                        payload,
                        base_importance=importance,
                    )
                )

            except Exception as e:
                logger.warning(
                    "[QBIT SCORE] Memory scoring failed: %s",
                    e,
                )

        if importance < self.min_importance:
            logger.debug(
                "[MEMORY RECORD] Skipped memory: %s | "
                "importance=%s",
                event_type,
                importance,
            )

            return None

        # --------------------------------------------------
        # Canonical memory Track ID
        # --------------------------------------------------

        track_id = self._resolve_track_id(
            event_type,
            parent_id=parent_id,
        )

        entry = {
            "track_id": track_id,
            "timestamp": (
                datetime.datetime.utcnow().isoformat()
            ),
            "event": event_type,
            "payload": payload,
            "parent_id": parent_id,
            "importance": importance,
            "limp_mode": limp_mode,
            "issues": [],
            "suggestions": [],
            "stubs": [],
        }

        # --------------------------------------------------
        # Preserve runtime identity metadata
        # --------------------------------------------------

        runtime_metadata = (
            self._runtime_metadata()
        )

        if runtime_metadata:
            entry["runtime"] = runtime_metadata

        # ==================================================
        # AutoFix
        # ==================================================

        if (
            self.autofix_pipeline
            and "content" in payload
        ):
            try:
                payload["content"] = (
                    asyncio.run(
                        self.autofix_pipeline.run_async(
                            payload["content"],
                            track_id=track_id,
                        )
                    )
                )

                entry["payload"] = payload

            except Exception as e:
                logger.warning(
                    "[AUTOFIX] Failed for memory %s: %s",
                    track_id,
                    e,
                )

        # ==================================================
        # File / function checks
        # ==================================================

        (
            issues,
            suggestions,
            stubs,
        ) = check_file_function_references(
            payload,
            self.base_dir,
        )

        entry["issues"].extend(issues)
        entry["suggestions"].extend(
            suggestions
        )
        entry["stubs"].extend(stubs)

        # --------------------------------------------------
        # Apply suggestions
        # --------------------------------------------------

        if (
            suggestions
            and "content" in payload
        ):
            payload["content"] += (
                "\n\n"
                + "\n".join(suggestions)
            )

            entry["payload"] = payload

        # ==================================================
        # Store in short-term memory
        # ==================================================

        self.short_term.append(entry)

        self._enforce_memory_quota()

        # ==================================================
        # Save to disk
        # ==================================================

        self._save()

        # ==================================================
        # Feed connected systems
        # ==================================================

        self._feed_event(entry)

        # ==================================================
        # Generate stubs
        # ==================================================

        for stub_path in stubs:
            try:
                os.makedirs(
                    os.path.dirname(stub_path),
                    exist_ok=True,
                )

                if not os.path.exists(
                    stub_path
                ):
                    with open(
                        stub_path,
                        "w",
                        encoding="utf-8",
                    ) as f:
                        f.write(
                            "# AUTOGENERATED STUB\n"
                        )

                    logger.info(
                        "[MEMORY STUB] Generated "
                        "missing file: %s",
                        stub_path,
                    )

            except Exception as e:
                logger.warning(
                    "[MEMORY STUB] Failed to create "
                    "stub %s: %s",
                    stub_path,
                    e,
                )

        # ==================================================
        # Optional HUD alert
        # ==================================================

        if (
            self.notify_operator
            and (
                issues
                or importance > 0.8
            )
        ):
            try:
                asyncio.create_task(
                    self.notify_operator(
                        {
                            "avg_intensity":
                                importance * 100,
                            "motion_level":
                                len(issues),
                            "track_id":
                                track_id,
                        },
                        limp_mode=limp_mode,
                    )
                )

            except Exception as e:
                logger.warning(
                    "[MEMORY HUD] Notification failed "
                    "for %s: %s",
                    track_id,
                    e,
                )

        # ==================================================
        # Auto-trigger actions
        # ==================================================

        if (
            auto_actions
            and importance >= 0.8
        ):
            for action_name in (
                get_registered_actions().keys()
            ):
                if (
                    action_name.startswith("run_")
                    or action_name.startswith(
                        "assemble_"
                    )
                ):
                    try:
                        queue_action(
                            action_name,
                            payload=payload,
                            sparkplug=self.build_manager,
                            priority=importance,
                        )

                    except Exception as e:
                        logger.warning(
                            "[MEMORY ACTION] Failed to "
                            "queue %s: %s",
                            action_name,
                            e,
                        )

        return track_id

    # ======================================================
    # ENFORCE MEMORY QUOTA
    # ======================================================

    def _enforce_memory_quota(self):
        current_size = sum(
            len(json.dumps(m))
            for m in self.short_term
        )

        while (
            current_size > self.short_term_quota
            and self.short_term
        ):
            min_entry = min(
                self.short_term,
                key=lambda m: m.get(
                    "importance",
                    0,
                ),
            )

            if (
                min_entry.get(
                    "importance",
                    0,
                )
                >= 0.8
            ):
                self.long_term.append(
                    min_entry
                )

                logger.info(
                    "[MEMORY PROMOTE] Promoted memory "
                    "to long-term: %s",
                    min_entry.get(
                        "track_id",
                        "N/A",
                    ),
                )

            else:
                logger.info(
                    "[MEMORY QUOTA] Removed "
                    "short-term memory: %s",
                    min_entry.get(
                        "track_id",
                        "N/A",
                    ),
                )

            self.short_term.remove(
                min_entry
            )

            current_size = sum(
                len(json.dumps(m))
                for m in self.short_term
            )

        # --------------------------------------------------
        # Ensure long-term quota is not exceeded
        # --------------------------------------------------

        long_size = sum(
            len(json.dumps(m))
            for m in self.long_term
        )

        while (
            long_size > self.long_term_quota
            and self.long_term
        ):
            removed = self.long_term.pop(0)

            logger.info(
                "[LONG-TERM QUOTA] Removed oldest "
                "long-term memory: %s",
                removed.get(
                    "track_id",
                    "N/A",
                ),
            )

            long_size = sum(
                len(json.dumps(m))
                for m in self.long_term
            )

        # --------------------------------------------------
        # Predict memory growth / backup
        # --------------------------------------------------

        try:
            asyncio.create_task(
                self._predictive_backup_hud()
            )
        except RuntimeError:
            logger.debug(
                "[MEMORY] No active event loop for "
                "predictive backup scheduling"
            )

    # ======================================================
    # FEED TO CONNECTED SYSTEMS
    # ======================================================

    def _feed_event(self, entry):
        # --------------------------------------------------
        # EventBus
        # --------------------------------------------------

        try:
            if self.event_bus:
                emit = getattr(
                    self.event_bus,
                    "emit",
                    None,
                )

                if callable(emit):
                    try:
                        emit(
                            "memory",
                            entry,
                        )

                    except TypeError:
                        try:
                            emit(
                                {
                                    "type": "memory",
                                    "payload": entry,
                                    "track_id":
                                        entry.get(
                                            "track_id"
                                        ),
                                }
                            )

                        except Exception as e:
                            logger.warning(
                                "[EVENT BUS] Memory event "
                                "failed: %s",
                                e,
                            )

        except Exception as e:
            logger.warning(
                "[EVENT BUS] Memory feed failed: %s",
                e,
            )

        # --------------------------------------------------
        # Intent Engine
        # --------------------------------------------------

        try:
            if self.intent_engine:
                process_scores = getattr(
                    self.intent_engine,
                    "process_scores",
                    None,
                )

                if callable(process_scores):
                    result = process_scores(
                        {
                            entry["event"]:
                                entry["importance"]
                        }
                    )

                    if asyncio.iscoroutine(result):
                        try:
                            asyncio.create_task(
                                result
                            )
                        except RuntimeError:
                            logger.debug(
                                "[INTENT FEED] No active "
                                "event loop"
                            )

        except Exception as e:
            logger.warning(
                "[INTENT FEED] Failed for %s: %s",
                entry["track_id"],
                e,
            )

        # --------------------------------------------------
        # Qbit Dialer
        # --------------------------------------------------

        try:
            if (
                self.qbit_dialer
                and hasattr(
                    self.qbit_dialer,
                    "enqueue_event",
                )
            ):
                self.qbit_dialer.enqueue_event(
                    entry
                )

        except Exception as e:
            logger.warning(
                "[QBIT FEED] Failed for %s: %s",
                entry["track_id"],
                e,
            )

        # --------------------------------------------------
        # Agent Manager
        # --------------------------------------------------

        try:
            if (
                self.agent_manager
                and hasattr(
                    self.agent_manager,
                    "receive_event",
                )
            ):
                self.agent_manager.receive_event(
                    entry
                )

        except Exception as e:
            logger.warning(
                "[AGENT FEED] Failed for %s: %s",
                entry["track_id"],
                e,
            )

        # --------------------------------------------------
        # Build Manager
        # --------------------------------------------------

        try:
            if (
                self.build_manager
                and hasattr(
                    self.build_manager,
                    "track_memory_event",
                )
            ):
                self.build_manager.track_memory_event(
                    entry
                )

        except Exception as e:
            logger.warning(
                "[BUILD FEED] Failed for %s: %s",
                entry["track_id"],
                e,
            )

        # --------------------------------------------------
        # TrackSystem observation bridge
        # --------------------------------------------------

        try:
            if self.track_system:
                handler = getattr(
                    self.track_system,
                    "record",
                    None,
                )

                if not callable(handler):
                    handler = getattr(
                        self.track_system,
                        "ingest",
                        None,
                    )

                if callable(handler):
                    try:
                        result = handler(entry)

                        if asyncio.iscoroutine(
                            result
                        ):
                            try:
                                asyncio.create_task(
                                    result
                                )
                            except RuntimeError:
                                logger.debug(
                                    "[TRACK FEED] No active "
                                    "event loop"
                                )

                    except TypeError:
                        # Preserve compatibility with
                        # TrackSystem implementations that
                        # require named payload arguments.
                        pass

        except Exception as e:
            logger.warning(
                "[TRACK FEED] Failed for %s: %s",
                entry["track_id"],
                e,
            )

    # ======================================================
    # PREDICTIVE BACKUP / HUD PROMPT
    # ======================================================

    async def _predictive_backup_hud(self):
        for drive, _ in self.backup_status.items():
            total, free = (
                self._get_storage_stats(drive)
            )

            if (
                free
                < self.short_term_quota * 0.1
            ):
                logger.warning(
                    "[BACKUP ALERT] Drive %s "
                    "critically low on space.",
                    drive,
                )

                low_importance = [
                    m
                    for m in self.long_term
                    if m.get(
                        "importance",
                        0,
                    ) < 0.6
                ]

                if low_importance:
                    suggested = (
                        low_importance[:5]
                    )

                    if self.notify_operator:
                        approve = (
                            await self.notify_operator(
                                {
                                    "message":
                                        f"Drive {drive} "
                                        "low on space. "
                                        f"Migrate "
                                        f"{len(suggested)} "
                                        "low-importance "
                                        "memories?",
                                    "memories": [
                                        m.get(
                                            "track_id"
                                        )
                                        for m in suggested
                                    ],
                                }
                            )
                        )

                        if approve:
                            for mem in suggested:
                                try:
                                    backup_path = (
                                        os.path.join(
                                            drive,
                                            f"{mem['track_id']}.json",
                                        )
                                    )

                                    with open(
                                        backup_path,
                                        "w",
                                        encoding="utf-8",
                                    ) as f:
                                        json.dump(
                                            mem,
                                            f,
                                            indent=2,
                                        )

                                    self.long_term.remove(
                                        mem
                                    )

                                    logger.info(
                                        "[BACKUP MIGRATION] "
                                        "Migrated memory %s → %s",
                                        mem["track_id"],
                                        drive,
                                    )

                                except Exception as e:
                                    logger.warning(
                                        "[BACKUP MIGRATION] "
                                        "Failed for %s: %s",
                                        mem.get(
                                            "track_id",
                                            "N/A",
                                        ),
                                        e,
                                    )

    # ======================================================
    # MEMORY SEARCH & RECALL
    # ======================================================

    def search_memory(
        self,
        keyword,
        limit=None,
    ):
        results = []

        keyword_lower = keyword.lower()

        for entry in reversed(
            self.short_term[
                -self.recall_window:
            ]
        ):
            content = str(
                entry.get(
                    "payload",
                    "",
                )
            )

            if keyword_lower in (
                content.lower()
            ):
                results.append(entry)

                if (
                    limit
                    and len(results) >= limit
                ):
                    return results

        for entry in reversed(
            self.long_term[
                -self.recall_window:
            ]
        ):
            summary_str = json.dumps(
                entry
            )

            if keyword_lower in (
                summary_str.lower()
            ):
                results.append(entry)

                if (
                    limit
                    and len(results) >= limit
                ):
                    return results

        return results

    # ======================================================
    # PRUNING RULES
    # ======================================================

    def prune(self, max_age_hours=24):
        cutoff = (
            datetime.datetime.utcnow()
            - datetime.timedelta(
                hours=max_age_hours
            )
        )

        retained = []

        for entry in self.short_term:
            try:
                ts = (
                    datetime.datetime.fromisoformat(
                        entry["timestamp"]
                    )
                )

                if ts >= cutoff:
                    retained.append(entry)

            except Exception as e:
                logger.warning(
                    "[MEMORY PRUNE] Invalid timestamp "
                    "%s: %s",
                    entry.get(
                        "timestamp"
                    ),
                    e,
                )

        self.short_term = (
            retained[-self.max_short_term:]
        )

        self._save()

        logger.debug(
            "[MEMORY PRUNE] Retained %s "
            "short-term memories",
            len(self.short_term),
        )

    # ======================================================
    # COMPRESSION
    # ======================================================

    def compress(self):
        if not self.short_term:
            return

        summary = {
            "start":
                self.short_term[0]["timestamp"],
            "end":
                self.short_term[-1]["timestamp"],
            "event_counts": {},
            "track_ids": [
                entry["track_id"]
                for entry in self.short_term
            ],
        }

        for entry in self.short_term:
            evt = entry["event"]

            summary["event_counts"][evt] = (
                summary["event_counts"].get(
                    evt,
                    0,
                )
                + 1
            )

        self.long_term.append(
            summary
        )

        self.short_term.clear()

        self._save()

        logger.info(
            "[MEMORY COMPRESS] Compressed %s "
            "events into long-term",
            len(summary["track_ids"]),
        )

    # ======================================================
    # AUTO MAINTENANCE
    # ======================================================

    async def auto_maintenance(
        self,
        prune_interval=60,
        compress_interval=300,
    ):
        while True:
            try:
                self.prune()

                await asyncio.sleep(
                    prune_interval
                )

                self.compress()

                await asyncio.sleep(
                    compress_interval
                )

                await self._predictive_backup_hud()

            except asyncio.CancelledError:
                logger.info(
                    "[MEMORY MAINTENANCE] "
                    "Task cancelled"
                )

                break

            except Exception as e:
                logger.warning(
                    "[MEMORY MAINTENANCE] Error: %s",
                    e,
                )

    # ======================================================
    # START / STOP ASYNC MAINTENANCE
    # ======================================================

    def start_async_maintenance(
        self,
        loop=None,
    ):
        if loop is None:
            loop = asyncio.get_event_loop()

        if (
            self._prune_task
            and not self._prune_task.done()
        ):
            return self._prune_task

        self._prune_task = (
            loop.create_task(
                self.auto_maintenance()
            )
        )

        return self._prune_task

    def stop_async_maintenance(self):
        if self._prune_task:
            self._prune_task.cancel()
            self._prune_task = None
