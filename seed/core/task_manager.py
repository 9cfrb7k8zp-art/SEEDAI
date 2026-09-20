# ==========================================================
# FILE: task_manager.py
# PATH: seed/core/task_manager.py
# VERSION: 2.0.0
# BUILD: DEVELOPMENT TASK ORCHESTRATOR / QBIT AUTHORITY SAFE
# PURPOSE: Track SEED development work and route it through the
#          existing Qbit -> Compute -> Dialer -> Queue pipeline.
# AUTHORITY: QbitDialer for executable command admission.
# ==========================================================

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path


class TaskManager:
    _global_instance = None
    _global_lock = threading.Lock()
    DEFAULT_GOALS = ("LIVE", "LEARN", "GROW")

    @classmethod
    def get_global(cls, **kwargs):
        with cls._global_lock:
            if cls._global_instance is None:
                cls._global_instance = cls(**kwargs)
            else:
                cls._global_instance.bind_runtime(**kwargs)
            return cls._global_instance

    def __init__(self, loop=None, event_bus=None, qbit_dialer=None,
                 qbit=None, qbit_queue_loop=None, action_engine=None,
                 seed_action_controller=None, storage_root=r"C:\SEED_ROOT",
                 registry=None, blackbox=None, **kwargs):
        self.loop = loop
        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer
        self.qbit = qbit
        self.qbit_queue_loop = qbit_queue_loop
        self.action_engine = action_engine
        self.seed_action_controller = seed_action_controller
        self.registry = registry
        self.blackbox = blackbox
        self.storage_root = os.path.abspath(storage_root or r"C:\SEED_ROOT")
        self.task_dir = os.path.join(self.storage_root, "storage", "development")
        self.task_file = os.path.join(self.task_dir, "seed_development_tasks.json")
        self.message_file = os.path.join(self.task_dir, "seed_ai_team_messages.json")
        self._tasks = []
        self._messages = []
        self._lock = threading.RLock()
        self.goals = list(self.DEFAULT_GOALS)
        self.active = True
        self._ensure_storage()
        self._load()
        TaskManager._global_instance = self

    def _ensure_storage(self):
        Path(self.task_dir).mkdir(parents=True, exist_ok=True)

    def _load(self):
        for path, target in ((self.task_file, "tasks"), (self.message_file, "messages")):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if target == "tasks" and isinstance(data, list):
                    self._tasks = data[-1000:]
                if target == "messages" and isinstance(data, list):
                    self._messages = data[-1000:]
            except (OSError, ValueError, TypeError):
                pass

    def _save(self):
        with self._lock:
            for path, data in ((self.task_file, self._tasks), (self.message_file, self._messages)):
                temp = path + ".tmp"
                try:
                    with open(temp, "w", encoding="utf-8") as handle:
                        json.dump(data[-1000:], handle, indent=2, default=str)
                    os.replace(temp, path)
                except OSError:
                    try:
                        if os.path.exists(temp):
                            os.remove(temp)
                    except OSError:
                        pass

    def bind_runtime(self, **kwargs):
        for name in ("loop", "event_bus", "qbit_dialer", "qbit", "qbit_queue_loop",
                     "action_engine", "seed_action_controller", "registry", "blackbox"):
            value = kwargs.get(name)
            if value is not None:
                setattr(self, name, value)
        return self

    def create_task(self, title, description="", level="L1", subsystem="CORE",
                    priority=5, goal="GROW", source="DEVHUD", metadata=None):
        task = {
            "task_id": "DEV-" + uuid.uuid4().hex[:12],
            "title": str(title), "description": str(description),
            "level": str(level).upper(), "subsystem": str(subsystem),
            "priority": int(priority), "goal": str(goal).upper(),
            "source": str(source), "state": "CATALOGED",
            "created_at": time.time(), "updated_at": time.time(),
            "qbit_id": None, "track_id": None, "parent_id": None,
            "metadata": dict(metadata or {}),
        }
        with self._lock:
            self._tasks.append(task)
        self._save()
        self._emit("DEVELOPMENT_TASK_CREATED", task)
        return task

    def submit_task(self, task, command_list=None):
        dialer = self.qbit_dialer
        if dialer is None or not callable(getattr(dialer, "create_task", None)):
            task["state"] = "PENDING"
            self._save()
            return {"status": "pending", "task": task}
        payload = {"development_task": task, "source": "TaskManager",
                   "goal": task.get("goal", "GROW"), "level": task.get("level", "L1"),
                   "subsystem": task.get("subsystem", "CORE")}
        try:
            result = dialer.create_task(payload, command_list=command_list,
                                        task_name=task.get("title", "SEED_DEVELOPMENT_TASK"),
                                        source_qbit=self.qbit)
            task["state"] = "DISPATCHED"
            if isinstance(result, dict):
                task["qbit_id"] = result.get("task_qbit_id") or result.get("qbit_id")
                task["track_id"] = result.get("track_id")
                task["parent_id"] = result.get("parent_id")
            task["updated_at"] = time.time()
            self._save()
            self._emit("DEVELOPMENT_TASK_DISPATCHED", task)
            return result
        except Exception as exc:
            task["state"] = "ERROR"
            task["error"] = str(exc)
            task["updated_at"] = time.time()
            self._save()
            self._emit("DEVELOPMENT_TASK_ERROR", task)
            return {"status": "error", "error": str(exc), "task": task}

    def add_task(self, func, metadata=None):
        return self.create_task(getattr(func, "__name__", "CALLABLE_TASK"),
                                level="L2", subsystem="LEGACY", metadata=metadata)

    def help(self, request, source="TaskManager", context=None):
        message = {"message_id": "HELP-" + uuid.uuid4().hex[:12],
                   "request": str(request), "source": str(source),
                   "context": dict(context or {}), "timestamp": time.time(),
                   "state": "OPEN"}
        with self._lock:
            self._messages.append(message)
        self._save()
        self._emit("SEED_AI_TEAM_HELP", message)
        return message

    def complete_task(self, task_id, result=None):
        with self._lock:
            for task in self._tasks:
                if task.get("task_id") == task_id:
                    task["state"] = "COMPLETE"
                    task["result"] = result
                    task["updated_at"] = time.time()
                    self._save()
                    self._emit("DEVELOPMENT_TASK_COMPLETE", task)
                    return task
        return None

    def status(self):
        with self._lock:
            counts = {}
            for task in self._tasks:
                state = task.get("state", "UNKNOWN")
                counts[state] = counts.get(state, 0) + 1
        return {"active": self.active, "goals": list(self.goals),
                "task_count": len(self._tasks), "message_count": len(self._messages),
                "states": counts, "qbit": self.qbit is not None,
                "qbit_queue_loop": self.qbit_queue_loop is not None,
                "qbit_dialer": self.qbit_dialer is not None,
                "action_engine": self.action_engine is not None,
                "seed_action_controller": self.seed_action_controller is not None,
                "blackbox": self.blackbox is not None}

    def task_count(self):
        with self._lock:
            return len(self._tasks)

    def execute_all(self):
        return self.status()

    def _emit(self, event, payload):
        bus = self.event_bus
        publish = getattr(bus, "publish", None) if bus is not None else None
        emit = getattr(bus, "emit", None) if bus is not None else None
        try:
            if callable(publish):
                return publish(event, payload=payload)
            if callable(emit):
                return emit(event, payload)
        except Exception:
            return None
        return None
