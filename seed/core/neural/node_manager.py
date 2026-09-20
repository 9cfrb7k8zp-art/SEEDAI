# ==========================================================
# FILE: node_manager.py
# PATH: C:\\SEED_ROOT\\seed\\core\\neural\\node_manager.py
# MODULE: SEED Neural Node Manager
# VERSION: 2.0.0
# BUILD: PASSIVE / REGISTRY-AWARE / SINGLE-RUNTIME
#
# PURPOSE:
# - Provide a valid node-management boundary for the neural package.
# - Use the authoritative Node_Registry when supplied.
# - Never create a second registry, Qbit, queue, EventBus, or runtime.
# ==========================================================

from __future__ import annotations

import logging
import uuid

log = logging.getLogger("NodeManager")


def gen_track_id(prefix="NODE_MANAGER"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class Node_Manager:
    VERSION = "2.0.0"
    NAME = "NodeManager"

    def __init__(self, node_registry=None, registry=None, **kwargs):
        self.node_registry = node_registry
        self.registry = registry
        self.track_id = gen_track_id()
        self.state = "READY"
        self.last_error = None

    def bind_registry(self, node_registry=None, registry=None):
        if node_registry is not None:
            self.node_registry = node_registry
        if registry is not None:
            self.registry = registry
        self.state = "READY"
        return True

    def get_nodes(self):
        source = self.node_registry or self.registry
        if source is None:
            return {}
        for name in ("get_nodes", "list_nodes", "all_nodes"):
            method = getattr(source, name, None)
            if callable(method):
                try:
                    result = method()
                    return result if result is not None else {}
                except Exception as exc:
                    self.last_error = str(exc)
                    log.warning("[NodeManager] node read failed: %s", exc)
                    return {}
        if isinstance(source, dict):
            return source.get("tree", source.get("nodes", {}))
        return {}

    def get_status(self):
        nodes = self.get_nodes()
        return {
            "name": self.NAME,
            "version": self.VERSION,
            "state": self.state,
            "track_id": self.track_id,
            "node_count": len(nodes) if hasattr(nodes, "__len__") else 0,
            "registry_bound": self.registry is not None,
            "node_registry_bound": self.node_registry is not None,
            "last_error": self.last_error,
        }

    def refresh(self):
        source = self.node_registry
        if source is not None:
            method = getattr(source, "refresh", None)
            if callable(method):
                try:
                    result = method()
                    self.state = "READY"
                    return result
                except Exception as exc:
                    self.last_error = str(exc)
                    self.state = "DEGRADED"
                    log.warning("[NodeManager] refresh failed: %s", exc)
        return self.get_status()

    def start(self):
        self.state = "RUNNING"
        return True

    def stop(self):
        self.state = "READY"
        return True


NodeManager = Node_Manager

__all__ = ["Node_Manager", "NodeManager", "gen_track_id"]
