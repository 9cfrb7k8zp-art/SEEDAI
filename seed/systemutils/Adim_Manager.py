# ================================================================
# FILE: Adim_Manager.py
# PATH: SEED_ROOT/seed/systemutils/Adim_Manager.py
# VERSION: 2.0.0
# ROLE: STAGNATION-AWARE / CURIOSITY-DRIVEN ADMIN CORE
#
# ARCHITECTURE:
#
#   SRegistry
#       |
#       v
#   AdimManager <---- Oracle
#       |
#       +---- TrackSystem
#       +---- Qbit
#       +---- QbitDialer
#       +---- QbitQueueLoop
#       +---- ComputeBrain
#       +---- TransformerBrain
#       +---- Nodes
#       +---- EventBus
#
#   AdimManager
#       |
#       | proposal only
#       v
#   QbitDialer.submit_command()
#       |
#       v
#   QbitQueueLoop
#       |
#       v
#   Authoritative execution
#
# IMPORTANT:
#   AdimManager is NOT command authority.
#   QbitDialer remains command authority.
#   AdimManager does not create a second queue or runtime.
# ================================================================

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, asdict
from threading import RLock
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger("AdimManager")


# ================================================================
# OPTIONAL IMPORTS
# ================================================================

try:
    from seed.core.tracked_data import TrackedData
except Exception:
    TrackedData = None


try:
    from seed.core.action_engine import ActionEngine
except Exception:
    ActionEngine = None


try:
    from seed.core.registry import SEED_KERNEL_REGISTRY
except Exception:
    try:
        from seed.core.seed_kernel_registry import SEED_KERNEL_REGISTRY
    except Exception:
        SEED_KERNEL_REGISTRY = {}


# ================================================================
# STATES
# ================================================================

CONSTRUCTED = "CONSTRUCTED"
BOUND = "BOUND"
READY = "READY"
OBSERVING = "OBSERVING"
STOPPING = "STOPPING"
STOPPED = "STOPPED"


# ================================================================
# HEALTH STATES
# ================================================================

HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
STAGNANT = "STAGNANT"
BLOCKED = "BLOCKED"
RECOVERING = "RECOVERING"
CRITICAL = "CRITICAL"
UNKNOWN = "UNKNOWN"


# ================================================================
# RESEARCH CODEX
# ================================================================

class ResearchCodex:


    def __init__(self, max_entries: int = 500):
        self.max_entries = max(10, int(max_entries))

        self.knowledge_base: deque = deque(
            maxlen=self.max_entries
        )

        self.skills_inbox: deque = deque(
            maxlen=self.max_entries
        )

        self._lock = RLock()

    def add_research(
        self,
        topic: str,
        content: Any,
        *,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        record = {
            "id": f"RESEARCH-{uuid.uuid4().hex[:12]}",
            "type": "research",
            "topic": topic,
            "content": content,
            "source": source,
            "metadata": dict(metadata or {}),
            "timestamp": time.time(),
        }

        with self._lock:
            self.knowledge_base.append(record)

        return record

    def add_skill_insight(
        self,
        skill: str,
        insight: Any,
        *,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        record = {
            "id": f"SKILL-{uuid.uuid4().hex[:12]}",
            "type": "skill_insight",
            "skill": skill,
            "insight": insight,
            "source": source,
            "metadata": dict(metadata or {}),
            "timestamp": time.time(),
        }

        with self._lock:
            self.skills_inbox.append(record)

        return record

    def get_knowledge(
        self,
        topic: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:

        limit = max(1, int(limit))

        with self._lock:
            items = list(self.knowledge_base)

        if topic:
            topic_lower = str(topic).lower()

            items = [
                item
                for item in items
                if topic_lower in str(
                    item.get("topic", "")
                ).lower()
            ]

        return items[-limit:]

    def snapshot(self) -> Dict[str, Any]:

        with self._lock:
            return {
                "knowledge_count": len(
                    self.knowledge_base
                ),
                "skills_count": len(
                    self.skills_inbox
                ),
                "knowledge": list(
                    self.knowledge_base
                )[-20:],
                "skills": list(
                    self.skills_inbox
                )[-20:],
            }


# ================================================================
# DOCTOR
# ================================================================

class DoctorModule:

    def __init__(
        self,
        health_threshold: float = 0.70,
    ):
        self.health_threshold = float(
            health_threshold
        )

        self.last_assessment = None
        self.assessment_count = 0

    def assess_health(
        self,
        system_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        stats = dict(system_stats or {})

        score = stats.get(
            "health_score",
            stats.get(
                "score",
                None,
            ),
        )

        if score is None:
            state = UNKNOWN
            score_value = None

        else:
            try:
                score_value = float(score)

                if score_value >= self.health_threshold:
                    state = HEALTHY

                elif score_value >= 0.40:
                    state = DEGRADED

                elif score_value > 0.0:
                    state = CRITICAL

                else:
                    state = UNKNOWN

            except (
                TypeError,
                ValueError,
            ):
                score_value = None
                state = UNKNOWN

        result = {
            "state": state,
            "score": score_value,
            "threshold": self.health_threshold,
            "timestamp": time.time(),
            "stats": stats,
        }

        self.last_assessment = result
        self.assessment_count += 1

        return result

    def perform_repair(
        self,
        system_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        return {
            "status": "PROPOSAL_ONLY",
            "action": "repair",
            "state": RECOVERING,
            "system_stats": dict(
                system_stats or {}
            ),
            "timestamp": time.time(),
        }


# ================================================================
# SPECIALIST
# ================================================================

class SpecialistModule:


    def escalate(
        self,
        admin_manager,
        system_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        stats = dict(system_stats or {})

        affected = []

        qbit_groups = getattr(
            admin_manager,
            "_qbit_groups",
            {},
        )

        if isinstance(qbit_groups, dict):
            affected.extend(
                str(key)
                for key in qbit_groups.keys()
            )

        if not affected:
            affected = [
                "system"
            ]

        return {
            "status": "ESCALATION_PROPOSED",
            "affected": affected,
            "system_stats": stats,
            "authority": "QbitDialer",
            "timestamp": time.time(),
        }


# ================================================================
# UPGRADE PROPOSAL
# ================================================================

@dataclass
class UpgradeProposal:
    proposal_id: str
    reason: str
    target: str
    action: str
    priority: int = 0
    confidence: float = 0.0
    state: str = "PROPOSED"
    qbit_id: Optional[str] = None
    task_id: Optional[str] = None
    track_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ================================================================
# ADIM MANAGER
# ================================================================

class AdimManager:

    VERSION = "2.0.0"

    ROLE = (
        "stagnation_aware_"
        "curiosity_driven_admin_core"
    )

    COMMAND_AUTHORITY = "QbitDialer"

    def __init__(
        self,
        storage_root="./SEED_ROOT",
        event_bus=None,
        agent_manager=None,
        smart_transformer=None,
        qbit_dialer=None,
        qbit=None,
        seed_core=None,
        oracle=None,
        track_system=None,
        registry=None,
        compute_brain=None,
        transformer_brain=None,
        qbit_queue_loop=None,
        node_manager=None,
        node_registry=None,
        action_engine=None,
        health_monitor=None,
        analytics_engine=None,
        memory_system=None,
        memory_manager=None,
        intent_engine=None,
        ethics_manager=None,
        channel_manager=None,
        channel_controller=None,
        watchdog=None,
        cognition_map=None,
        governor=None,
        time_travel_engine=None,
        **kwargs,
    ):

        self.logger = LOGGER

        self.storage_root = storage_root

        # --------------------------------------------------------
        # DIRECT DEPENDENCY REFERENCES
        # --------------------------------------------------------

        self.event_bus = event_bus
        self.agent_manager = agent_manager
        self.smart_transformer = smart_transformer

        self.qbit_dialer = qbit_dialer
        self.qbit = qbit
        self.seed_core = seed_core

        self.oracle = oracle
        self.track_system = track_system
        self.registry = (
            registry
            if registry is not None
            else SEED_KERNEL_REGISTRY
        )

        self.compute_brain = compute_brain
        self.transformer_brain = transformer_brain
        self.qbit_queue_loop = qbit_queue_loop

        self.node_manager = node_manager
        self.node_registry = node_registry

        self.health_monitor = health_monitor
        self.analytics_engine = analytics_engine

        self.memory_system = memory_system
        self.memory_manager = memory_manager

        self.intent_engine = intent_engine
        self.ethics_manager = ethics_manager

        self.channel_manager = channel_manager
        self.channel_controller = channel_controller

        self.watchdog = watchdog
        self.cognition_map = cognition_map
        self.governor = governor
        self.time_travel_engine = time_travel_engine

        self.extra_dependencies = dict(
            kwargs
        )

        # --------------------------------------------------------
        # ACTION ENGINE
        #
        # Existing instance is preferred.
        # No command authority is granted.
        # --------------------------------------------------------

        self.action_engine = action_engine

        # --------------------------------------------------------
        # STATE
        # --------------------------------------------------------

        self.state = CONSTRUCTED

        self._lock = RLock()

        self._running = False
        self._stop_requested = False
        self._auto_upgrade_task = None

        # --------------------------------------------------------
        # CORE DATA
        # --------------------------------------------------------

        self.system_stats = {}

        self.last_snapshot = None
        self.last_health = None

        self.stagnation_detected = False
        self.stagnation_score = 0.0
        self.last_progress_timestamp = time.time()

        self.progress_counter = 0
        self.observation_counter = 0

        self._qbit_groups = {}

        self.upgrade_queue = deque(
            maxlen=200
        )

        self.proposals = deque(
            maxlen=200
        )

        self.research_codex = ResearchCodex()

        self.doctor = DoctorModule()

        self.specialist = SpecialistModule()

        # --------------------------------------------------------
        # CONFIGURATION
        # --------------------------------------------------------

        self.stagnation_threshold = float(
            kwargs.get(
                "stagnation_threshold",
                0.70,
            )
        )

        self.stagnation_window = float(
            kwargs.get(
                "stagnation_window",
                60.0,
            )
        )

        self.upgrade_threshold = float(
            kwargs.get(
                "upgrade_threshold",
                0.75,
            )
        )

        self.curiosity_enabled = bool(
            kwargs.get(
                "curiosity_enabled",
                True,
            )
        )

        self.max_upgrade_queue = max(
            1,
            int(
                kwargs.get(
                    "max_upgrade_queue",
                    50,
                )
            ),
        )

        # --------------------------------------------------------
        # EVENT HISTORY
        # --------------------------------------------------------

        self.event_history = deque(
            maxlen=500
        )

        self.last_event = None

        self.logger.info(
            "[AdimManager] constructed | "
            "version=%s | authority=%s",
            self.VERSION,
            self.COMMAND_AUTHORITY,
        )

    # ============================================================
    # EVENT BUS
    # ============================================================

    def _emit(
        self,
        event_name: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:

        event = {
            "event": event_name,
            "source": "AdimManager",
            "authority": self.COMMAND_AUTHORITY,
            "timestamp": time.time(),
            "payload": dict(payload or {}),
        }

        self.last_event = event

        try:
            self.event_history.append(event)
        except Exception:
            pass

        bus = self.event_bus

        if bus is None:
            return False

        emit = getattr(
            bus,
            "emit",
            None,
        )

        if not callable(emit):
            return False

        try:
            emit(
                event_name,
                event["payload"],
            )
            return True

        except Exception:
            self.logger.debug(
                "[AdimManager] EventBus emission failed",
                exc_info=True,
            )
            return False

    # ============================================================
    # LIFECYCLE
    # ============================================================

    def bind_systems(self):
        """
        Bind dependency references.

        This method does not start workers or queues.
        """

        with self._lock:

            if self.state == STOPPED:
                self.state = CONSTRUCTED

            self.state = BOUND

        self._emit(
            "ADIM_SYSTEMS_BOUND",
            self._dependency_status(),
        )

        return True

    def start(self):
        """
        Start observation state only.

        No background worker is created here.
        """

        with self._lock:

            if self.state == STOPPED:
                return False

            if self.state == CONSTRUCTED:
                self.state = BOUND

            self._running = True
            self._stop_requested = False
            self.state = READY

        self._emit(
            "ADIM_INITIALIZED",
            self._dependency_status(),
        )

        return True

    def begin_observing(self):
        with self._lock:

            if not self._running:
                return False

            self.state = OBSERVING

        self._emit(
            "ADIM_OBSERVING",
            {
                "state": self.state,
            },
        )

        return True

    def stop(self):
        with self._lock:

            self.state = STOPPING
            self._stop_requested = True
            self._running = False

        task = self._auto_upgrade_task

        if task is not None:

            try:
                task.cancel()
            except Exception:
                pass

            self._auto_upgrade_task = None

        with self._lock:
            self.state = STOPPED

        self._emit(
            "ADIM_STOPPED",
            {},
        )

        return True

    # ============================================================
    # DEPENDENCY STATUS
    # ============================================================

    def _dependency_status(self):

        names = (
            "event_bus",
            "qbit",
            "qbit_dialer",
            "track_system",
            "registry",
            "compute_brain",
            "transformer_brain",
            "qbit_queue_loop",
            "oracle",
            "node_manager",
            "node_registry",
            "health_monitor",
            "analytics_engine",
            "memory_system",
            "intent_engine",
            "ethics_manager",
            "channel_manager",
            "watchdog",
            "cognition_map",
            "governor",
        )

        return {
            name: getattr(
                self,
                name,
                None,
            ) is not None
            for name in names
        }

    # ============================================================
    # QBIT OBSERVATION
    # ============================================================

    def observe_qbit(
        self,
        qbit=None,
    ) -> Dict[str, Any]:

        qbit = (
            qbit
            if qbit is not None
            else self.qbit
        )

        if qbit is None:
            return {
                "present": False,
                "state": UNKNOWN,
            }

        qbit_id = getattr(
            qbit,
            "id",
            getattr(
                qbit,
                "qbit_id",
                None,
            ),
        )

        track_id = getattr(
            qbit,
            "track_id",
            getattr(
                qbit,
                "track",
                None,
            ),
        )

        task_id = getattr(
            qbit,
            "task_id",
            None,
        )

        pipeline_id = getattr(
            qbit,
            "pipeline_id",
            None,
        )

        state = getattr(
            qbit,
            "state",
            None,
        )

        generation = getattr(
            qbit,
            "generation",
            None,
        )

        observation = {
            "present": True,
            "qbit_id": qbit_id,
            "track_id": track_id,
            "task_id": task_id,
            "pipeline_id": pipeline_id,
            "state": state,
            "generation": generation,
            "action": getattr(
                qbit,
                "action",
                None,
            ),
            "source": getattr(
                qbit,
                "source",
                None,
            ),
            "timestamp": time.time(),
        }

        self.observation_counter += 1

        if qbit_id:

            self._qbit_groups.setdefault(
                qbit_id,
                {
                    "qbit_id": qbit_id,
                    "observations": 0,
                    "last_seen": None,
                },
            )

            group = self._qbit_groups[
                qbit_id
            ]

            group[
                "observations"
            ] += 1

            group[
                "last_seen"
            ] = observation[
                "timestamp"
            ]

        self._emit(
            "ADIM_QBIT_OBSERVED",
            observation,
        )

        return observation

    # ============================================================
    # DIALER OBSERVATION
    # ============================================================

    def observe_dialer(self):

        dialer = self.qbit_dialer

        if dialer is None:
            return {
                "present": False,
                "state": UNKNOWN,
            }

        command_plane = getattr(
            dialer,
            "command_plane",
            None,
        )

        qbit_health = getattr(
            dialer,
            "qbit_health",
            None,
        )

        result = {
            "present": True,
            "state": getattr(
                dialer,
                "state",
                None,
            ),
            "running": getattr(
                dialer,
                "running",
                None,
            ),
            "online": (
                command_plane.get(
                    "online"
                )
                if isinstance(
                    command_plane,
                    dict,
                )
                else None
            ),
            "command_plane": (
                dict(command_plane)
                if isinstance(
                    command_plane,
                    dict,
                )
                else None
            ),
            "qbit_health": (
                dict(qbit_health)
                if isinstance(
                    qbit_health,
                    dict,
                )
                else None
            ),
        }

        return result

    # ============================================================
    # QUEUE LOOP OBSERVATION
    # ============================================================

    def observe_qbit_queue(self):

        loop = self.qbit_queue_loop

        if loop is None:
            return {
                "present": False,
                "state": UNKNOWN,
            }

        result = {
            "present": True,
            "state": getattr(
                loop,
                "state",
                None,
            ),
            "running": getattr(
                loop,
                "running",
                None,
            ),
            "queue_depth": None,
            "active_qbit": None,
            "duplicate_blocks": getattr(
                loop,
                "duplicate_blocks",
                None,
            ),
        }

        for attr in (
            "queue",
            "qbit_queue",
            "_queue",
        ):

            queue = getattr(
                loop,
                attr,
                None,
            )

            if queue is None:
                continue

            try:
                result[
                    "queue_depth"
                ] = queue.qsize()
                break
            except Exception:
                try:
                    result[
                        "queue_depth"
                    ] = len(queue)
                    break
                except Exception:
                    pass

        result[
            "active_qbit"
        ] = getattr(
            loop,
            "active_qbit",
            getattr(
                loop,
                "current_qbit",
                None,
            ),
        )

        return result

    # ============================================================
    # TRACK SYSTEM OBSERVATION
    # ============================================================

    def observe_track_system(self):

        track = self.track_system

        if track is None:
            return {
                "present": False,
                "state": UNKNOWN,
            }

        result = {
            "present": True,
            "state": getattr(
                track,
                "state",
                None,
            ),
        }

        for attr in (
            "active_track",
            "current_track",
            "track_id",
            "active_context",
        ):

            value = getattr(
                track,
                attr,
                None,
            )

            if value is not None:
                result[attr] = value

        return result

    # ============================================================
    # BRAIN OBSERVATION
    # ============================================================

    def observe_brains(self):

        def inspect_brain(brain):

            if brain is None:
                return {
                    "present": False,
                    "state": UNKNOWN,
                }

            return {
                "present": True,
                "state": getattr(
                    brain,
                    "state",
                    None,
                ),
                "running": getattr(
                    brain,
                    "running",
                    None,
                ),
                "online": getattr(
                    brain,
                    "online",
                    None,
                ),
            }

        return {
            "compute_brain": inspect_brain(
                self.compute_brain
            ),
            "transformer_brain": inspect_brain(
                self.transformer_brain
            ),
        }

    # ============================================================
    # NODE SYNCHRONIZATION
    # ============================================================

    def sync_system_nodes(self):

        sources = (
            self.node_manager,
            self.node_registry,
            self.registry,
        )

        nodes = {}

        for source in sources:

            if source is None:
                continue

            if isinstance(
                source,
                dict,
            ):
                candidates = source

            else:
                candidates = None

                for attr in (
                    "nodes",
                    "_nodes",
                    "registry",
                    "registered_nodes",
                ):

                    value = getattr(
                        source,
                        attr,
                        None,
                    )

                    if isinstance(
                        value,
                        dict,
                    ):
                        candidates = value
                        break

            if not isinstance(
                candidates,
                dict,
            ):
                continue

            for node_id, node in candidates.items():

                if node_id in nodes:
                    continue

                if isinstance(
                    node,
                    dict,
                ):
                    nodes[
                        str(node_id)
                    ] = dict(node)

                else:
                    nodes[
                        str(node_id)
                    ] = {
                        "id": str(node_id),
                        "name": getattr(
                            node,
                            "name",
                            None,
                        ),
                        "type": getattr(
                            node,
                            "type",
                            None,
                        ),
                        "role": getattr(
                            node,
                            "role",
                            None,
                        ),
                        "state": getattr(
                            node,
                            "state",
                            None,
                        ),
                        "health": getattr(
                            node,
                            "health",
                            None,
                        ),
                        "capabilities": getattr(
                            node,
                            "capabilities",
                            None,
                        ),
                    }

        result = {
            "count": len(nodes),
            "nodes": nodes,
            "timestamp": time.time(),
        }

        self._emit(
            "ADIM_NODE_OBSERVED",
            result,
        )

        return result

    # ============================================================
    # ORACLE OBSERVATION
    # ============================================================

    def observe_oracle(self):

        oracle = self.oracle

        if oracle is None:
            return {
                "present": False,
                "state": UNKNOWN,
            }

        result = {
            "present": True,
            "state": getattr(
                oracle,
                "state",
                None,
            ),
            "mode": getattr(
                oracle,
                "mode",
                None,
            ),
        }

        snapshot = getattr(
            oracle,
            "snapshot",
            None,
        )

        if callable(snapshot):

            try:
                result[
                    "snapshot"
                ] = snapshot()

            except Exception:
                self.logger.debug(
                    "[AdimManager] Oracle snapshot failed",
                    exc_info=True,
                )

        return result

    # ============================================================
    # SYSTEM STATS
    # ============================================================

    def update_system_stats(
        self,
        stats: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:

        incoming = dict(
            stats or {}
        )

        incoming.update(
            kwargs
        )

        incoming[
            "timestamp"
        ] = time.time()

        with self._lock:

            self.system_stats.update(
                incoming
            )

        self.progress_counter += 1
        self.last_progress_timestamp = (
            incoming["timestamp"]
        )

        self._emit(
            "ADIM_STATE_UPDATED",
            dict(
                self.system_stats
            ),
        )

        return dict(
            self.system_stats
        )

    def get_system_stats(self):

        with self._lock:
            return dict(
                self.system_stats
            )

    # ============================================================
    # STAGNATION
    # ============================================================

    def detect_stagnation(
        self,
        system_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        stats = dict(
            system_stats
            if system_stats is not None
            else self.system_stats
        )

        now = time.time()

        explicit = stats.get(
            "stagnation",
            stats.get(
                "stagnant",
                None,
            ),
        )

        progress = stats.get(
            "progress",
            None,
        )

        age = (
            now
            - self.last_progress_timestamp
        )

        if explicit is not None:
            detected = bool(
                explicit
            )

        elif progress is not None:

            try:
                detected = (
                    float(progress)
                    <= 0.0
                    and age
                    >= self.stagnation_window
                )
            except (
                TypeError,
                ValueError,
            ):
                detected = (
                    age
                    >= self.stagnation_window
                )

        else:
            detected = (
                age
                >= self.stagnation_window
            )

        score = min(
            1.0,
            max(
                0.0,
                age
                / max(
                    self.stagnation_window,
                    1.0,
                ),
            ),
        )

        self.stagnation_detected = detected
        self.stagnation_score = score

        result = {
            "detected": detected,
            "score": score,
            "age": age,
            "threshold": self.stagnation_threshold,
            "window": self.stagnation_window,
            "timestamp": now,
        }

        if detected:

            self._emit(
                "ADIM_STAGNATION_DETECTED",
                result,
            )

        return result

    # ============================================================
    # QBIT ACTION HOOK
    # ============================================================

    def _qbit_action_hook(
        self,
        qbit=None,
    ) -> Dict[str, Any]:

        observation = self.observe_qbit(
            qbit
        )

        action = observation.get(
            "action"
        )

        return {
            "status": "OBSERVED",
            "action": action,
            "qbit": observation,
            "authority": self.COMMAND_AUTHORITY,
            "execution": False,
        }

    # ============================================================
    # UPGRADE PLANNING
    # ============================================================

    def plan_upgrade(
        self,
        reason: str,
        target: str = "system",
        action: str = "system_upgrade",
        *,
        priority: int = 0,
        confidence: float = 0.0,
        qbit_id: Optional[str] = None,
        task_id: Optional[str] = None,
        track_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        proposal = UpgradeProposal(
            proposal_id=(
                f"ADIM-{uuid.uuid4().hex[:12]}"
            ),
            reason=str(reason),
            target=str(target),
            action=str(action),
            priority=int(priority),
            confidence=float(
                confidence
            ),
            state="PROPOSED",
            qbit_id=qbit_id,
            task_id=task_id,
            track_id=track_id,
            pipeline_id=pipeline_id,
            timestamp=time.time(),
        )

        data = proposal.to_dict()

        self.proposals.append(
            data
        )

        if len(
            self.upgrade_queue
        ) < self.max_upgrade_queue:

            self.upgrade_queue.append(
                data
            )

        self._emit(
            "ADIM_UPGRADE_PLANNED",
            data,
        )

        return data

    # ============================================================
    # EVALUATE UPGRADES
    # ============================================================

    def evaluate_upgrades(
        self,
        system_stats: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:

        stats = dict(
            system_stats
            if system_stats is not None
            else self.system_stats
        )

        proposals = []

        stagnation = self.detect_stagnation(
            stats
        )

        if stagnation["detected"]:

            proposals.append(
                self.plan_upgrade(
                    reason=(
                        "system stagnation "
                        "detected"
                    ),
                    target="affected_system",
                    action="diagnose_and_recover",
                    priority=8,
                    confidence=(
                        stagnation["score"]
                    ),
                )
            )

        health = self.doctor.assess_health(
            stats
        )

        if health["state"] in (
            DEGRADED,
            CRITICAL,
        ):

            proposals.append(
                self.plan_upgrade(
                    reason=(
                        "system health "
                        "requires intervention"
                    ),
                    target="affected_system",
                    action="diagnose_and_repair",
                    priority=9,
                    confidence=(
                        1.0
                        - (
                            health.get(
                                "score"
                            )
                            or 0.0
                        )
                    ),
                )
            )

        if proposals:

            self._emit(
                "ADIM_UPGRADE_PROPOSED",
                {
                    "count": len(
                        proposals
                    ),
                    "proposals": proposals,
                },
            )

        return proposals

    # ============================================================
    # CHECK FOR UPGRADES
    # ============================================================

    def check_for_upgrades(self):

        proposals = list(
            self.proposals
        )

        return [
            proposal
            for proposal in proposals
            if proposal.get(
                "state"
            ) == "PROPOSED"
            and proposal.get(
                "confidence",
                0.0,
            ) >= self.upgrade_threshold
        ]

    # ============================================================
    # AUTHORITATIVE SUBMISSION
    # ============================================================

    def _submit_authorized_proposal(
        self,
        proposal: Dict[str, Any],
    ) -> Dict[str, Any]:

        dialer = self.qbit_dialer

        if dialer is None:

            proposal[
                "state"
            ] = "DEFERRED"

            self._emit(
                "ADIM_UPGRADE_DEFERRED",
                proposal,
            )

            return {
                "status": "DEFERRED",
                "reason": (
                    "QbitDialer unavailable"
                ),
                "proposal": proposal,
            }

        submit = getattr(
            dialer,
            "submit_command",
            None,
        )

        if not callable(submit):

            proposal[
                "state"
            ] = "DEFERRED"

            self._emit(
                "ADIM_UPGRADE_DEFERRED",
                proposal,
            )

            return {
                "status": "DEFERRED",
                "reason": (
                    "QbitDialer.submit_command "
                    "unavailable"
                ),
                "proposal": proposal,
            }

        command = {
            "name": proposal.get(
                "action",
                "system_upgrade",
            ),
            "command": proposal.get(
                "action",
                "system_upgrade",
            ),
            "action": proposal.get(
                "action",
                "system_upgrade",
            ),
            "target": proposal.get(
                "target",
                "system",
            ),
            "reason": proposal.get(
                "reason"
            ),
            "priority": proposal.get(
                "priority",
                0,
            ),
            "confidence": proposal.get(
                "confidence",
                0.0,
            ),
            "source": "AdimManager",
            "authority": self.COMMAND_AUTHORITY,
            "proposal_id": proposal.get(
                "proposal_id"
            ),
            "qbit_id": proposal.get(
                "qbit_id"
            ),
            "task_id": proposal.get(
                "task_id"
            ),
            "track_id": proposal.get(
                "track_id"
            ),
            "pipeline_id": proposal.get(
                "pipeline_id"
            ),
        }

        try:

            result = submit(
                command
            )

            if asyncio.iscoroutine(
                result
            ):
                return {
                    "status": "SUBMITTED_ASYNC",
                    "command": command,
                }

            proposal[
                "state"
            ] = "SUBMITTED"

            self._emit(
                "ADIM_UPGRADE_AUTHORIZATION_REQUESTED",
                {
                    "proposal": proposal,
                    "command": command,
                    "result": result,
                },
            )

            return {
                "status": "SUBMITTED",
                "command": command,
                "result": result,
            }

        except Exception as exc:

            proposal[
                "state"
            ] = "FAILED_TO_SUBMIT"

            self.logger.exception(
                "[AdimManager] "
                "QbitDialer submission failed"
            )

            self._emit(
                "ADIM_ERROR",
                {
                    "operation": (
                        "submit_authorized_proposal"
                    ),
                    "error": str(exc),
                    "proposal": proposal,
                },
            )

            return {
                "status": "FAILED_TO_SUBMIT",
                "error": str(exc),
                "proposal": proposal,
            }

    # ============================================================
    # EXECUTE SYSTEM UPGRADE
    #
    # IMPORTANT:
    #
    # This method NEVER directly executes the upgrade.
    # It submits the proposal to QbitDialer.
    # ============================================================

    def execute_system_upgrade(
        self,
        proposal: Optional[
            Dict[str, Any]
        ] = None,
    ):

        if proposal is None:

            candidates = (
                self.check_for_upgrades()
            )

            if not candidates:
                return {
                    "status": "NO_PROPOSAL"
                }

            proposal = candidates[0]

        proposal[
            "state"
        ] = "AUTHORIZATION_PENDING"

        return self._submit_authorized_proposal(
            proposal
        )

    # ============================================================
    # RESEARCH
    # ============================================================

    def add_research(
        self,
        topic: str,
        content: Any,
        *,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):

        result = self.research_codex.add_research(
            topic,
            content,
            source=source,
            metadata=metadata,
        )

        self._emit(
            "ADIM_RESEARCH_ADDED",
            result,
        )

        return result

    def add_skill_insight(
        self,
        skill: str,
        insight: Any,
        *,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):

        result = (
            self.research_codex.add_skill_insight(
                skill,
                insight,
                source=source,
                metadata=metadata,
            )
        )

        self._emit(
            "ADIM_SKILL_INSIGHT_ADDED",
            result,
        )

        return result

    # ============================================================
    # CURIOSITY
    # ============================================================

    def curiosity_proposal(
        self,
        topic: str,
        reason: str = "exploration",
    ) -> Dict[str, Any]:

        if not self.curiosity_enabled:

            return {
                "status": "DISABLED"
            }

        proposal = self.plan_upgrade(
            reason=(
                f"curiosity:{reason}"
            ),
            target=topic,
            action="research_and_evaluate",
            priority=2,
            confidence=0.50,
        )

        proposal[
            "state"
        ] = "RESEARCH_PROPOSAL"

        self._emit(
            "ADIM_CURIOSITY_PROPOSED",
            proposal,
        )

        return proposal

    # ============================================================
    # DOCTOR / SPECIALIST
    # ============================================================

    def doctor_assessment(self):

        result = self.doctor.assess_health(
            self.system_stats
        )

        self.last_health = result

        self._emit(
            "ADIM_HEALTH_ASSESSMENT",
            result,
        )

        return result

    def specialist_escalation(self):

        result = self.specialist.escalate(
            self,
            self.system_stats,
        )

        self._emit(
            "ADIM_SPECIALIST_INTERVENTION",
            result,
        )

        return result

    # ============================================================
    # FULL SYSTEM SNAPSHOT
    # ============================================================

    def get_system_snapshot(self):

        qbit = self.observe_qbit()

        dialer = self.observe_dialer()

        queue = self.observe_qbit_queue()

        track = self.observe_track_system()

        brains = self.observe_brains()

        oracle = self.observe_oracle()

        nodes = self.sync_system_nodes()

        stagnation = self.detect_stagnation()

        health = self.doctor.assess_health(
            self.system_stats
        )

        snapshot = {
            "identity": {
                "component": "AdimManager",
                "version": self.VERSION,
                "role": self.ROLE,
                "authority": self.COMMAND_AUTHORITY,
            },

            "lifecycle": {
                "state": self.state,
                "running": self._running,
            },

            "qbit": qbit,

            "qbit_dialer": dialer,

            "qbit_queue_loop": queue,

            "track_system": track,

            "registry": {
                "present": (
                    self.registry is not None
                ),
            },

            "brains": brains,

            "oracle": oracle,

            "nodes": nodes,

            "health": health,

            "stagnation": stagnation,

            "progress": {
                "counter": (
                    self.progress_counter
                ),
                "last_progress": (
                    self.last_progress_timestamp
                ),
            },

            "upgrades": {
                "queued": len(
                    self.upgrade_queue
                ),
                "proposals": len(
                    self.proposals
                ),
            },

            "research": (
                self.research_codex.snapshot()
            ),

            "dependencies": (
                self._dependency_status()
            ),

            "timestamp": time.time(),
        }

        self.last_snapshot = snapshot

        self._emit(
            "ADIM_SYSTEM_SNAPSHOT",
            snapshot,
        )

        return snapshot

    # ============================================================
    # AUTO UPGRADE LOOP
    #
    # This loop only generates proposals and requests authority.
    # It never bypasses QbitDialer.
    # ============================================================

    async def auto_upgrade_loop(
        self,
        interval: float = 5.0,
    ):

        try:
            interval = max(
                0.25,
                float(interval),
            )
        except (
            TypeError,
            ValueError,
        ):
            interval = 5.0

        self._running = True
        self.begin_observing()

        while (
            self._running
            and not self._stop_requested
        ):

            try:

                stats = self.get_system_stats()

                health = (
                    self.doctor.assess_health(
                        stats
                    )
                )

                self.last_health = health

                self.detect_stagnation(
                    stats
                )

                proposals = (
                    self.evaluate_upgrades(
                        stats
                    )
                )

                for proposal in proposals:

                    if (
                        proposal.get(
                            "confidence",
                            0.0,
                        )
                        >= self.upgrade_threshold
                    ):
                        self.execute_system_upgrade(
                            proposal
                        )

            except asyncio.CancelledError:
                raise

            except Exception as exc:

                self.logger.exception(
                    "[AdimManager] "
                    "auto-upgrade observation failed"
                )

                self._emit(
                    "ADIM_ERROR",
                    {
                        "operation": (
                            "auto_upgrade_loop"
                        ),
                        "error": str(exc),
                    },
                )

            await asyncio.sleep(
                interval
            )

    def start_auto_upgrade_loop(
        self,
        interval: float = 5.0,
    ):

        if self._auto_upgrade_task is not None:

            if not self._auto_upgrade_task.done():
                return self._auto_upgrade_task

        try:

            loop = asyncio.get_running_loop()

        except RuntimeError:

            self.logger.warning(
                "[AdimManager] "
                "No running asyncio loop; "
                "auto-upgrade loop deferred"
            )

            return None

        self._auto_upgrade_task = (
            loop.create_task(
                self.auto_upgrade_loop(
                    interval
                )
            )
        )

        return self._auto_upgrade_task

    # ============================================================
    # REPORT
    # ============================================================

    def status(self):

        return {
            "component": "AdimManager",
            "version": self.VERSION,
            "state": self.state,
            "running": self._running,
            "authority": self.COMMAND_AUTHORITY,
            "stagnation": self.stagnation_detected,
            "stagnation_score": (
                self.stagnation_score
            ),
            "upgrade_queue": len(
                self.upgrade_queue
            ),
            "proposals": len(
                self.proposals
            ),
            "research": (
                self.research_codex.snapshot()
            ),
            "dependencies": (
                self._dependency_status()
            ),
            "timestamp": time.time(),
        }


# ================================================================
# COMPATIBILITY ALIAS
# ================================================================

ADIMManager = AdimManager


# ================================================================
# MODULE METADATA
# ================================================================

__all__ = [
    "AdimManager",
    "ADIMManager",
    "ResearchCodex",
    "DoctorModule",
    "SpecialistModule",
    "UpgradeProposal",
    "CONSTRUCTED",
    "BOUND",
    "READY",
    "OBSERVING",
    "STOPPING",
    "STOPPED",
    "HEALTHY",
    "DEGRADED",
    "STAGNANT",
    "BLOCKED",
    "RECOVERING",
    "CRITICAL",
    "UNKNOWN",
]