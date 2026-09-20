# File: qbit_memory_graph.py
# Path: seed/core/memory/qbit_memory_graph.py
# ROLE: authoritative Qbit lineage memory graph
from __future__ import annotations

import time
import uuid
import logging
from collections import defaultdict
from threading import RLock
from typing import Any, Dict, List, Optional

log = logging.getLogger("QbitMemoryGraph")


class QbitMemoryGraph:
    """Thread-safe graph for Qbit lineage, outcomes, and adaptive feedback."""

    VERSION = "2.0.0"

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = RLock()
        self.last_feedback: Optional[Dict[str, Any]] = None

    @staticmethod
    def _read(qbit, key, default=None):
        if isinstance(qbit, dict):
            return qbit.get(key, default)
        return getattr(qbit, key, default)

    def add_qbit(self, qbit, *, parent_id=None, relation="caused"):
        """Record one Qbit and optionally connect it to its parent."""
        qid = (
            self._read(qbit, "qbit_id")
            or self._read(qbit, "task_id")
            or self._read(qbit, "id")
            or str(uuid.uuid4())
        )
        metadata = self._read(qbit, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}

        record = {
            "qbit_id": str(qid),
            "intent": self._read(qbit, "intent"),
            "track_id": self._read(qbit, "track_id"),
            "state": self._read(qbit, "state"),
            "skill": self._read(qbit, "skill") or metadata.get("skill"),
            "command": self._read(qbit, "command") or metadata.get("command"),
            "command_type": self._read(qbit, "command_type") or metadata.get("command_type"),
            "timestamp": self._read(qbit, "timestamp", time.time()),
            "metadata": dict(metadata),
        }

        with self._lock:
            self.nodes[str(qid)] = record
            if parent_id is not None:
                self.link(parent_id, str(qid), relation=relation)
        return str(qid)

    def link(self, parent_id, child_id, relation="caused"):
        with self._lock:
            edge = {"target": str(child_id), "relation": str(relation)}
            if edge not in self.edges[str(parent_id)]:
                self.edges[str(parent_id)].append(edge)

    def record_feedback(self, qbit_id, feedback, *, outcome=None):
        """Attach execution/cognitive feedback to an existing Qbit node."""
        qid = str(qbit_id)
        data = feedback if isinstance(feedback, dict) else {"value": feedback}
        with self._lock:
            node = self.nodes.setdefault(qid, {"qbit_id": qid, "metadata": {}})
            node["feedback"] = dict(data)
            node["outcome"] = outcome
            node["feedback_timestamp"] = time.time()
            self.last_feedback = {
                "qbit_id": qid,
                "outcome": outcome,
                "feedback": dict(data),
                "timestamp": node["feedback_timestamp"],
            }
            return dict(self.last_feedback)

    def neighbors(self, qid):
        with self._lock:
            return list(self.edges.get(str(qid), []))

    def get(self, qid):
        with self._lock:
            node = self.nodes.get(str(qid))
            return dict(node) if isinstance(node, dict) else None
    def children(self, qid):
        return self.neighbors(qid)

    def parents(self, qid):
        target = str(qid)
        with self._lock:
            return [
                {"source": source, **edge}
                for source, edges in self.edges.items()
                for edge in edges
                if edge.get("target") == target
            ]

    def update_qbit(self, qbit_id, **fields):
        with self._lock:
            node = self.nodes.setdefault(
                str(qbit_id),
                {"qbit_id": str(qbit_id), "metadata": {}},
            )
            node.update(fields)
            return dict(node)

    def stats(self):
        with self._lock:
            return {
                "version": self.VERSION,
                "nodes": len(self.nodes),
                "edges": sum(len(v) for v in self.edges.values()),
                "feedback_recorded": sum(
                    1 for node in self.nodes.values()
                    if "feedback" in node
                ),
            }

    def snapshot(self):
        with self._lock:
            return {
                "version": self.VERSION,
                "nodes": {key: dict(value) for key, value in self.nodes.items()},
                "edges": {
                    key: [dict(edge) for edge in value]
                    for key, value in self.edges.items()
                },
                "last_feedback": (
                    dict(self.last_feedback)
                    if self.last_feedback else None
                ),
            }

    def bind_runtime(self, *, track_system=None, module_registry=None,
                     adaptive_priority_engine=None, evolution_engine=None):
        """Bind observers only; this graph never becomes command authority."""
        self.track_system = track_system
        self.module_registry = module_registry
        self.adaptive_priority_engine = adaptive_priority_engine
        self.evolution_engine = evolution_engine
        return self

    def observe_result(self, qbit, result=None, *, parent_id=None):
        """Record a result Qbit and feed its outcome into the graph."""
        qid = self.add_qbit(qbit, parent_id=parent_id, relation="result")
        if result is not None:
            self.record_feedback(
                qid,
                result,
                outcome=(
                    result.get("status")
                    if isinstance(result, dict) else None
                ),
            )
        return qid
