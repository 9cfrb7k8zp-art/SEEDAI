# ==========================================================
# FILE: blackbox.py
# PATH: SEED_ROOT/seed/systemutils/blackbox.py
# VERSION: 1.0.0
# BUILD: CORE INTEGRITY / LIVE-LEARN-GROW / OBSERVER SAFE
# PURPOSE: Protect SEED runtime integrity through observation,
#          bounded recovery requests, and durable audit state.
# AUTHORITY: Existing SEEDCore, QbitDialer, QueueLoop, EventBus.
# ==========================================================

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Callable

logger = logging.getLogger("BlackBox")


class BlackBox:
    GOALS = ("LIVE", "LEARN", "GROW")

    def __init__(self, name="SEED", seed_ai=None, storage_root=r"C:\SEED_ROOT",
                 seed_core=None, event_bus=None, qbit_dialer=None,
                 qbit_queue_loop=None, task_manager=None):
        self.name = name
        self.seed_ai = seed_ai
        self.seed_core = seed_core
        self.event_bus = event_bus
        self.qbit_dialer = qbit_dialer
        self.qbit_queue_loop = qbit_queue_loop
        self.task_manager = task_manager
        self.active = False
        self.goals = list(self.GOALS)
        self.registered_devices: List[str] = []
        self.privacy_rules: Dict[str, Dict] = {}
        self._devhud_output = None
        self._audio_callback: Callable[[str], None] = None
        self._lock = threading.RLock()
        self.storage_root = os.path.abspath(storage_root or r"C:\SEED_ROOT")
        self.state_dir = os.path.join(self.storage_root, "storage", "development")
        self.state_file = os.path.join(self.state_dir, "seed_blackbox_state.json")
        Path(self.state_dir).mkdir(parents=True, exist_ok=True)
        self._state = {"goals": list(self.GOALS), "events": [], "protections": []}
        self._load_state()
        logger.info("[BB-001] BlackBox '%s' initialized", self.name)

    def bind_core(self, seed_core=None, event_bus=None, qbit_dialer=None,
                  qbit_queue_loop=None, task_manager=None, **kwargs):
        with self._lock:
            if seed_core is not None:
                self.seed_core = seed_core
            if event_bus is not None:
                self.event_bus = event_bus
            if qbit_dialer is not None:
                self.qbit_dialer = qbit_dialer
            if qbit_queue_loop is not None:
                self.qbit_queue_loop = qbit_queue_loop
            if task_manager is not None:
                self.task_manager = task_manager
        self.record("CORE_BOUND", self.status())
        return True

    def register_device(self, device_id):
        if device_id not in self.registered_devices:
            self.registered_devices.append(str(device_id))
            self.record("DEVICE_REGISTERED", {"device_id": str(device_id)})

    def connect_seed_ai(self, seed_ai):
        self.seed_ai = seed_ai
        self.record("SEED_AI_BOUND", {"type": type(seed_ai).__name__})

    def connect_devhud(self, devhud_output_callable):
        self._devhud_output = devhud_output_callable
        return True

    def connect_audio_output(self, audio_callback):
        self._audio_callback = audio_callback
        return True

    def protect(self, reason, component=None, state=None):
        protection = {"reason": str(reason), "component": component,
                      "state": state or {}, "timestamp": time.time(),
                      "goals": list(self.goals)}
        self._state["protections"].append(protection)
        self._state["protections"] = self._state["protections"][-200:]
        self.record("PROTECTION", protection)
        self._output_to_devhud("Protection: " + str(reason))
        return protection

    def protect_goal(self, goal, reason, component=None):
        goal = str(goal).upper()
        if goal not in self.goals:
            return False
        return self.protect(reason, component=component, state={"goal": goal})

    def check_runtime(self):
        state = self.status()
        failures = []
        if not state["event_bus"]:
            failures.append("EventBus")
        if not state["qbit_dialer"]:
            failures.append("QbitDialer")
        if not state["qbit_queue_loop"]:
            failures.append("QbitQueueLoop")
        if failures:
            self.protect("runtime authority missing", component=",".join(failures), state=state)
        return {"healthy": not failures, "failures": failures, "state": state}

    def request_help(self, request, context=None):
        if self.task_manager is not None and callable(getattr(self.task_manager, "help", None)):
            return self.task_manager.help(request, source="BlackBox", context=context)
        self.record("HELP_REQUEST", {"request": str(request), "context": context or {}})
        return {"state": "OPEN", "request": str(request)}

    def record(self, event, payload=None):
        entry = {"event": str(event), "payload": payload or {}, "timestamp": time.time()}
        with self._lock:
            self._state["events"].append(entry)
            self._state["events"] = self._state["events"][-500:]
            self._save_state()
        bus = self.event_bus
        try:
            publish = getattr(bus, "publish", None) if bus is not None else None
            if callable(publish):
                publish("BLACKBOX_EVENT", payload=entry)
        except Exception:
            pass
        return entry

    def status(self):
        return {
            "name": self.name,
            "active": self.active,
            "goals": list(self.goals),
            "seed_core": self.seed_core is not None,
            "event_bus": self.event_bus is not None,
            "qbit_dialer": self.qbit_dialer is not None,
            "qbit_queue_loop": self.qbit_queue_loop is not None,
            "task_manager": self.task_manager is not None,
            "event_count": len(self._state.get("events", [])),
            "protection_count": len(self._state.get("protections", [])),
        }

    def _output_to_devhud(self, message):
        callback = self._devhud_output
        if callable(callback):
            try:
                callback("[BlackBox] " + str(message))
            except Exception:
                pass

    def _save_state(self):
        temp = self.state_file + ".tmp"
        try:
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(self._state, handle, indent=2, default=str)
            os.replace(temp, self.state_file)
        except OSError:
            try:
                if os.path.exists(temp):
                    os.remove(temp)
            except OSError:
                pass

    def _load_state(self):
        try:
            with open(self.state_file, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self._state.update(loaded)
        except (OSError, ValueError, TypeError):
            pass

    def start(self):
        self.active = True
        self.record("BLACKBOX_ONLINE", self.status())
        return True

    def stop(self):
        self.active = False
        self.record("BLACKBOX_OFFLINE", self.status())
        return True
