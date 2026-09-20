# ==========================================================
# FILE: time_travel_engine.py
# PATH: SEED_ROOT/seed/core/time_travel_engine.py
#
# SYSTEM LAYER: Passive Time-Travel Replay / Checkpoint /
#               Rollback / Temporal Observation
#
# VERSION: 3.0.0
# BUILD: PASSIVE-QBIT-DIALER-AUTHORITY
#
# PURPOSE:
# - Record SEED event history safely
# - Persist timeline without destroying previous history
# - Preserve TrackID / ChannelID / source metadata
# - Observe system events without controlling system lifecycle
# - Remain completely passive during boot
# - Never start background threads
# - Never autonomously activate
# - Never autonomously replay
# - Never directly execute actuator commands
# - Feed temporal/Qbit information to QbitDialer
# - QbitDialer remains the command/execution authority
# - Support checkpoints and navigation
# - Support dry-run temporal simulation
# - Prevent replay recursion
# - Remain hardware-safe by default
#
# AUTHORITY MODEL
# ----------------------------------------------------------
# TimeTravelEngine:
#     OBSERVE
#     RECORD
#     STORE
#     REPLAY-REQUEST
#     QBIT-FEED
#
# QbitDialer:
#     COMMAND AUTHORITY
#     EXECUTION AUTHORITY
#     QBIT DECISION
#
# TimeTravelEngine NEVER:
#     - starts SEED
#     - stops SEED
#     - starts threads
#     - repairs modules
#     - executes actuator commands directly
#     - forces EventBus execution
#     - controls boot lifecycle
#     - creates autonomous work loops
# ==========================================================

from __future__ import annotations

import copy
import json
import logging
import os
import random
import threading
import time
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional


logger = logging.getLogger("TimeTravelEngine")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(levelname)s] %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


DEFAULT_TIMELINE_FILE = "./SEED_ROOT/beats.json"
MAX_TIMELINE_EVENTS = 5000


class TimeTravelEngine:

    VERSION = "3.0.0"

    # ------------------------------------------------------
    # INIT
    # ------------------------------------------------------

    def __init__(
        self,
        dialer=None,
        event_name=None,
        seedcore=None,
        emit=None,
        event_bus=None,
        track=None,
        task_id=None,
        track_id=None,
        boot_cycle=None,
        auto_persist=True,
        storage_root="./SEED_ROOT",
        timeline_file=DEFAULT_TIMELINE_FILE,
        enable_hardware=False,
        max_events=MAX_TIMELINE_EVENTS,
        **kwargs,
    ):

        # --------------------------------------------------
        # References only.
        #
        # TimeTravel does not create or start any subsystem.
        # --------------------------------------------------

        self.dialer = dialer
        self.seedcore = seedcore
        self.event_bus = event_bus
        self.emit = event_bus.emit
        self.track = track

        self.task_id = task_id
        self.track_id = track_id
        self.boot_cycle = boot_cycle

        self.event_name = event_name

        self.auto_persist = bool(auto_persist)

        # Hardware execution remains disabled by default.
        # Even when enabled, execution is delegated to dialer.
        self.enable_hardware = bool(enable_hardware)

        self.storage_root = storage_root
        self.timeline_file = (
            timeline_file or DEFAULT_TIMELINE_FILE
        )

        try:
            self.max_events = int(
                max_events or MAX_TIMELINE_EVENTS
            )
        except Exception:
            self.max_events = MAX_TIMELINE_EVENTS

        # --------------------------------------------------
        # Lifecycle state
        #
        # These are state markers only.
        # No thread is started here.
        # --------------------------------------------------

        self.active = False
        self.recording = False
        self.replaying = False

        self._boot_complete = False
        self._shutdown_requested = False
        self._activation_requested = False

        # --------------------------------------------------
        # Data
        # --------------------------------------------------

        self.history: List[dict] = []
        self.event_log: List[dict] = []
        self.subscribe = []
        self.relay_queue = []

        self._timeline: List[dict] = []
        self._cursor = -1
        self._current_snapshot_value = None

        # --------------------------------------------------
        # Diagnostics / pressure observation
        # --------------------------------------------------

        self.pressure_observations: List[dict] = []
        self.last_pressure = None
        self.last_health_signal = None
        self.last_qbit = None

        # --------------------------------------------------
        # Locks
        # --------------------------------------------------

        self._lock = threading.RLock()

        # EventBus hook state.
        self._event_hook_installed = False
        self._previous_event_hook = None

        self._status_handler = None

        # --------------------------------------------------
        # Storage
        # --------------------------------------------------

        self._ensure_storage()

        # CRITICAL:
        # Never open timeline with "w" during initialization.
        self._load_timeline()

        # --------------------------------------------------
        # EventBus attachment is observational only.
        # --------------------------------------------------

        if self.event_bus is not None:
            self.attach_event_bus(self.event_bus)

        logger.info(
            "[TimeTravel] Initialized | version=%s | "
            "events=%d | passive=True | dialer=%s | file=%s",
            self.VERSION,
            len(self._timeline),
            type(self.dialer).__name__
            if self.dialer is not None
            else "None",
            self.timeline_file,
        )

    # ======================================================
    # STORAGE
    # ======================================================

    def _ensure_storage(self):
        try:
            timeline_dir = os.path.dirname(
                os.path.abspath(self.timeline_file)
            )

            os.makedirs(
                timeline_dir,
                exist_ok=True,
            )

        except Exception as exc:
            logger.warning(
                "[TimeTravel] Storage initialization failed: %s",
                exc,
            )

    @staticmethod
    def _json_safe(value: Any):

        if value is None:
            return None

        if isinstance(
            value,
            (str, int, float, bool),
        ):
            return value

        if isinstance(value, dict):
            return {
                str(k): TimeTravelEngine._json_safe(v)
                for k, v in value.items()
            }

        if isinstance(
            value,
            (list, tuple, set),
        ):
            return [
                TimeTravelEngine._json_safe(v)
                for v in value
            ]

        for attr in (
            "id",
            "track_id",
            "channel",
            "source",
        ):
            if hasattr(value, attr):
                try:
                    return {
                        "__type__": type(value).__name__,
                        attr: TimeTravelEngine._json_safe(
                            getattr(value, attr)
                        ),
                    }
                except Exception:
                    pass

        try:
            return {
                "__type__": type(value).__name__,
                "__repr__": repr(value),
            }
        except Exception:
            return {
                "__type__": type(value).__name__,
                "__repr__": "<unserializable>",
            }

    # ======================================================
    # LOAD / SAVE
    # ======================================================

    def _load_timeline(self):

        with self._lock:

            try:

                if not os.path.exists(
                    self.timeline_file
                ):

                    self._timeline = []
                    self._cursor = -1

                    logger.info(
                        "[TimeTravel] Timeline does not "
                        "exist; starting empty"
                    )

                    return

                with open(
                    self.timeline_file,
                    "r",
                    encoding="utf-8",
                ) as handle:

                    data = json.load(handle)

                if not isinstance(data, list):

                    logger.warning(
                        "[TimeTravel] Invalid timeline format; "
                        "expected list"
                    )

                    data = []

                self._timeline = data[
                    -self.max_events:
                ]

                self._cursor = (
                    len(self._timeline) - 1
                )

                logger.info(
                    "[TimeTravel] Loaded %d events",
                    len(self._timeline),
                )

            except json.JSONDecodeError as exc:

                logger.error(
                    "[TimeTravel] Timeline JSON is corrupt: %s",
                    exc,
                )

                # Do NOT destroy corrupt evidence.
                self._timeline = []
                self._cursor = -1

            except Exception as exc:

                logger.warning(
                    "[TimeTravel] Timeline load failed: %s",
                    exc,
                )

                self._timeline = []
                self._cursor = -1

    def _save_timeline(self):

        with self._lock:

            temp_file = (
                self.timeline_file + ".tmp"
            )

            try:

                self._ensure_storage()

                payload = self._json_safe(
                    self._timeline
                )

                with open(
                    temp_file,
                    "w",
                    encoding="utf-8",
                ) as handle:

                    json.dump(
                        payload,
                        handle,
                        indent=2,
                        ensure_ascii=False,
                    )

                os.replace(
                    temp_file,
                    self.timeline_file,
                )

            except Exception as exc:

                logger.error(
                    "[TimeTravel] Failed saving timeline: %s",
                    exc,
                )

                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception:
                    pass

    # ======================================================
    # EVENTBUS ATTACHMENT
    #
    # OBSERVATIONAL ONLY
    # ======================================================

    def attach_event_bus(self, event_bus):

        if event_bus is None:
            return False

        self.event_bus = event_bus

        try:

            previous_hook = getattr(
                event_bus,
                "_emit_hook",
                None,
            )

            self._previous_event_hook = (
                previous_hook
            )

            def temporal_hook(
                event_name,
                payload=None,
            ):

                # Preserve an existing hook.
                if callable(previous_hook):

                    try:
                        previous_hook(
                            event_name,
                            payload,
                        )

                    except Exception:
                        logger.exception(
                            "[TimeTravel] Previous "
                            "EventBus hook failed"
                        )

                # TimeTravel is strictly passive.
                if self._runtime_ready():

                    self._capture_event(
                        event_name,
                        payload,
                    )

            event_bus._emit_hook = temporal_hook

            self._event_hook_installed = True

            logger.info(
                "[TimeTravel] EventBus recorder attached "
                "| passive=True"
            )

            return True

        except Exception as exc:

            logger.error(
                "[TimeTravel] EventBus attachment failed: %s",
                exc,
            )

            return False

    def detach_event_bus(self):

        if self.event_bus is None:
            return False

        try:

            if self._event_hook_installed:

                current_hook = getattr(
                    self.event_bus,
                    "_emit_hook",
                    None,
                )

                # Only restore our hook.
                if current_hook is not None:

                    self.event_bus._emit_hook = (
                        self._previous_event_hook
                    )

            self._event_hook_installed = False
            self._previous_event_hook = None

            logger.info(
                "[TimeTravel] EventBus recorder detached"
            )

            return True

        except Exception as exc:

            logger.warning(
                "[TimeTravel] EventBus detach failed: %s",
                exc,
            )

            return False

    # ======================================================
    # LIFECYCLE
    #
    # TimeTravel observes lifecycle.
    # It does not control lifecycle.
    # ======================================================

    def _system_boot_complete(self):

        try:

            from seed.core.track_context import (
                TrackContext,
            )

            getter = getattr(
                TrackContext,
                "system_state",
                None,
            )

            if callable(getter):

                state = getter() or {}

                if isinstance(state, dict):

                    if state.get(
                        "shutdown_requested",
                        False,
                    ):
                        return False

                    return bool(
                        state.get(
                            "boot_complete",
                            False,
                        )
                    )

        except Exception:
            pass

        return bool(
            self._boot_complete
        ) and not bool(
            self._shutdown_requested
        )

    def _runtime_ready(self):

        return bool(
            self.active
            and self.recording
            and self._system_boot_complete()
            and not self._shutdown_requested
        )

    def set_boot_complete(
        self,
        value=True,
    ):

        self._boot_complete = bool(value)

        if not self._boot_complete:

            self.active = False
            self.recording = False

            return False

        if self._shutdown_requested:
            return False

        # IMPORTANT:
        # A previous activation request may release the recorder,
        # but this method itself does not initiate activation.
        if self._activation_requested:

            self.active = True
            self.recording = True

        return self.active

    async def activate(self):

        # Activation is explicit only.
        self._activation_requested = True

        if self._shutdown_requested:
            return False

        if not self._system_boot_complete():

            logger.info(
                "[TimeTravel] Activation deferred | "
                "SEED BOOT not complete"
            )

            return False

        self.active = True
        self.recording = True

        logger.info(
            "[TimeTravel] Activated | passive recorder"
        )

        return True

    def activate_sync(self):

        self._activation_requested = True

        if (
            self._shutdown_requested
            or not self._system_boot_complete()
        ):

            logger.info(
                "[TimeTravel] Activation deferred | "
                "SEED BOOT not complete"
            )

            return False

        self.active = True
        self.recording = True

        logger.info(
            "[TimeTravel] Activated | passive recorder"
        )

        return True

    def deactivate(self):

        self.active = False
        self.recording = False
        self._activation_requested = False

        logger.info(
            "[TimeTravel] Deactivated"
        )

        return True

    def shutdown(self):

        self._shutdown_requested = True
        self.active = False
        self.recording = False
        self._activation_requested = False

        try:
            self.detach_event_bus()
        except Exception:
            pass

        logger.info(
            "[TimeTravel] Shutdown complete"
        )

        return True

    # ======================================================
    # EVENT CAPTURE
    # ======================================================

    def _capture_event(
        self,
        event_name,
        payload=None,
    ):

        if not self._runtime_ready():
            return None

        if self.replaying:
            return None

        if not self.recording:
            return None

        try:

            event_name = str(
                event_name
            )

            metadata = {}

            if isinstance(
                payload,
                dict,
            ):

                metadata.update(
                    {
                        "track_id": payload.get(
                            "track_id"
                        ),
                        "parent_id": payload.get(
                            "parent_id"
                        ),
                        "channel": payload.get(
                            "channel"
                        ),
                        "source": payload.get(
                            "source"
                        ),
                        "device_id": payload.get(
                            "device_id"
                        ),
                        "priority": payload.get(
                            "priority"
                        ),
                    }
                )

            snapshot = {
                "ts": time.time(),
                "type": event_name,
                "payload": self._json_safe(
                    payload
                ),
                "track_id": (
                    metadata.get("track_id")
                    or self.track_id
                ),
                "parent_id": metadata.get(
                    "parent_id"
                ),
                "channel": metadata.get(
                    "channel"
                ),
                "source": metadata.get(
                    "source"
                ),
                "device_id": metadata.get(
                    "device_id"
                ),
                "priority": metadata.get(
                    "priority"
                ),
                "task_id": self.task_id,
                "boot_cycle": self.boot_cycle,
                "temporal_version": self.VERSION,
            }

            return self._append_snapshot(
                snapshot,
                persist=self.auto_persist,
            )

        except Exception:

            logger.exception(
                "[TimeTravel] Failed capturing event: %s",
                event_name,
            )

            return None

    # ======================================================
    # PRESSURE / HEALTH OBSERVATION
    #
    # TimeTravel records pressure.
    # It does NOT respond to pressure.
    # ======================================================

    def observe_pressure(
        self,
        pressure=None,
        cpu=None,
        memory=None,
        source=None,
        module=None,
        operation=None,
        track_id=None,
        cause=None,
        payload=None,
    ):

        observation = {
            "ts": time.time(),
            "type": "RESOURCE_PRESSURE_OBSERVATION",
            "pressure": pressure,
            "cpu": cpu,
            "memory": memory,
            "source": source,
            "module": module,
            "operation": operation,
            "track_id": track_id,
            "cause": cause,
            "payload": self._json_safe(
                payload
            ),
        }

        self.last_pressure = (
            observation
        )

        with self._lock:

            self.pressure_observations.append(
                observation
            )

            if len(
                self.pressure_observations
            ) > self.max_events:

                del self.pressure_observations[
                    :-
                    self.max_events
                ]

        # Only record if TimeTravel has been
        # explicitly released for runtime recording.
        if self._runtime_ready():

            self._append_snapshot(
                observation,
                persist=self.auto_persist,
            )

        return observation

    def observe_health(
        self,
        health_payload=None,
    ):

        observation = {
            "ts": time.time(),
            "type": "HEALTH_OBSERVATION",
            "payload": self._json_safe(
                health_payload
            ),
        }

        self.last_health_signal = (
            observation
        )

        if self._runtime_ready():

            self._append_snapshot(
                observation,
                persist=self.auto_persist,
            )

        return observation

    # ======================================================
    # RECORD
    # ======================================================

    def _append_snapshot(
        self,
        snapshot: dict,
        persist=True,
    ):

        if not isinstance(
            snapshot,
            dict,
        ):
            return False

        if persist and not self._runtime_ready():
            return False

        with self._lock:

            self._timeline.append(
                deepcopy(snapshot)
            )

            if (
                len(self._timeline)
                > self.max_events
            ):

                overflow = (
                    len(self._timeline)
                    - self.max_events
                )

                del self._timeline[
                    :overflow
                ]

            self._cursor = (
                len(self._timeline) - 1
            )

            if persist:
                self._save_timeline()

        return deepcopy(snapshot)

    def record(
        self,
        event_type,
        payload,
    ):

        if not self._runtime_ready():
            return None

        payload_dict = (
            payload
            if isinstance(
                payload,
                dict,
            )
            else {}
        )

        snapshot = {
            "ts": time.time(),
            "type": str(event_type),
            "payload": self._json_safe(
                payload
            ),
            "track_id": (
                payload_dict.get(
                    "track_id"
                )
                or self.track_id
            ),
            "parent_id": payload_dict.get(
                "parent_id"
            ),
            "channel": payload_dict.get(
                "channel"
            ),
            "source": payload_dict.get(
                "source"
            ),
            "device_id": payload_dict.get(
                "device_id"
            ),
            "priority": payload_dict.get(
                "priority"
            ),
            "task_id": self.task_id,
            "boot_cycle": self.boot_cycle,
            "temporal_version": self.VERSION,
        }

        return self._append_snapshot(
            snapshot,
            persist=self.auto_persist,
        )

    # ======================================================
    # COMMAND RECORDING
    #
    # RECORD ONLY.
    # NEVER EXECUTE.
    # ======================================================

    def record_command(
        self,
        command_obj,
        event_name,
        payload=None,
    ):

        if command_obj is None:
            logger.debug(
                "[TimeTravel] Ignoring empty command"
            )
            return None

        command_ref = {
            "class": type(
                command_obj
            ).__name__,
            "methods": [],
        }

        try:

            command_ref["methods"] = [
                method
                for method in dir(
                    command_obj
                )
                if callable(
                    getattr(
                        command_obj,
                        method,
                        None,
                    )
                )
                and not method.startswith("_")
            ]

        except Exception:
            pass

        command_payload = {
            "command_ref": command_ref,
            "payload": self._json_safe(
                payload or {}
            ),
        }

        return self.record(
            event_name,
            command_payload,
        )

    # ======================================================
    # QBIT → DIALER
    #
    # This is the important authority boundary.
    #
    # TimeTravel may FEED a Qbit to the Dialer.
    # TimeTravel does not execute the Qbit.
    # ======================================================

    def feed_qbit(
        self,
        qbit,
        source="time_travel",
    ):

        if qbit is None:
            logger.debug(
                "[TimeTravel] feed_qbit ignored | qbit=None"
            )
            return False

        self.last_qbit = qbit

        dialer = self.dialer

        if dialer is None:

            logger.debug(
                "[TimeTravel] Qbit retained but "
                "Dialer is unavailable"
            )

            return False

        # --------------------------------------------------
        # Preferred Dialer API
        # --------------------------------------------------

        for method_name in (
            "receive_qbit",
            "submit_qbit",
            "accept_qbit",
            "enqueue_qbit",
        ):

            method = getattr(
                dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:

                result = method(
                    qbit
                )

                logger.debug(
                    "[TimeTravel] Qbit fed to "
                    "QbitDialer.%s | source=%s",
                    method_name,
                    source,
                )

                return result

            except TypeError:

                # Some Dialer implementations may
                # accept metadata as a second parameter.
                try:

                    result = method(
                        qbit,
                        source=source,
                    )

                    logger.debug(
                        "[TimeTravel] Qbit fed to "
                        "QbitDialer.%s with source",
                        method_name,
                    )

                    return result

                except Exception as exc:

                    logger.warning(
                        "[TimeTravel] Dialer Qbit "
                        "handoff failed: %s",
                        exc,
                    )

            except Exception as exc:

                logger.warning(
                    "[TimeTravel] Dialer Qbit "
                    "handoff failed: %s",
                    exc,
                )

        logger.debug(
            "[TimeTravel] Dialer exposes no compatible "
            "Qbit receive API"
        )

        return False

    # Backward-compatible hardware path.
    def execute_best(
        self,
        qbit,
    ):

        if qbit is None:
            return None

        # NEVER execute directly.
        #
        # Even hardware-enabled operation is delegated
        # entirely to QbitDialer.
        if self.enable_hardware:

            return self.feed_qbit(
                qbit,
                source="time_travel_execute_best",
            )

        logger.info(
            "[TimeTravel] execute_best blocked | "
            "hardware disabled | Qbit retained only"
        )

        return self.simulate(
            qbit
        )

    # ======================================================
    # RELAY
    #
    # IMPORTANT:
    # This no longer assumes record_command() succeeded.
    # It also does NOT call EventBus._emit().
    #
    # Commands go to QbitDialer.
    # ======================================================

    def relay(
        self,
        command_obj,
        emit_to_bus=True,
    ):

        if command_obj is None:

            logger.debug(
                "[TimeTravel] relay ignored | "
                "command_obj=None"
            )

            return None

        try:

            # ------------------------------------------------
            # Record only when runtime is released.
            # ------------------------------------------------

            snapshot = self.record_command(
                command_obj,
                "ACTUATOR_COMMAND",
                {},
            )

            # ------------------------------------------------
            # This fixes the original NoneType bug.
            #
            # record_command() legitimately returns None
            # when TimeTravel is not active.
            # ------------------------------------------------

            if snapshot is None:

                logger.debug(
                    "[TimeTravel] relay not recorded | "
                    "TimeTravel inactive"
                )

                return None

            self.relay_queue.append(
                deepcopy(snapshot)
            )

            # ------------------------------------------------
            # DO NOT execute through EventBus.
            #
            # TimeTravel is not the command authority.
            # ------------------------------------------------

            logger.debug(
                "[TimeTravel] Command recorded | "
                "execution delegated to QbitDialer"
            )

            return snapshot

        except Exception as exc:

            logger.warning(
                "[TimeTravel] Failed to relay command: %s",
                exc,
            )

            return None

    # ======================================================
    # NAVIGATION
    # ======================================================

    def get_events(self):

        with self._lock:
            return deepcopy(
                self._timeline
            )

    def rewind(
        self,
        steps: int = 1,
    ) -> Optional[dict]:

        with self._lock:

            if not self._timeline:
                return None

            self._cursor = max(
                -1,
                self._cursor
                - max(
                    1,
                    int(steps),
                ),
            )

            return self._current_snapshot()

    def fast_forward(
        self,
        steps: int = 1,
    ) -> Optional[dict]:

        with self._lock:

            if not self._timeline:
                return None

            self._cursor = min(
                len(self._timeline) - 1,
                self._cursor
                + max(
                    1,
                    int(steps),
                ),
            )

            return self._current_snapshot()

    def goto(
        self,
        index: int,
    ) -> Optional[dict]:

        with self._lock:

            if 0 <= index < len(
                self._timeline
            ):

                self._cursor = index

                return self._current_snapshot()

            return None

    def latest(self):

        with self._lock:

            if not self._timeline:
                return None

            self._cursor = (
                len(self._timeline) - 1
            )

            return self._current_snapshot()

    def _current_snapshot(self):

        if (
            0 <= self._cursor
            < len(self._timeline)
        ):

            return deepcopy(
                self._timeline[
                    self._cursor
                ]
            )

        return None

    # ======================================================
    # CHECKPOINT
    # ======================================================

    def checkpoint(
        self,
        name="SEED_CHECKPOINT",
        state=None,
    ):

        if not self._runtime_ready():

            logger.debug(
                "[TimeTravel] Checkpoint ignored | "
                "runtime not released"
            )

            return None

        snapshot = {
            "ts": time.time(),
            "type": "TIME_TRAVEL_CHECKPOINT",
            "checkpoint": str(name),
            "payload": self._json_safe(
                state or {}
            ),
            "track_id": self.track_id,
            "task_id": self.task_id,
            "boot_cycle": self.boot_cycle,
            "temporal_version": self.VERSION,
        }

        result = self._append_snapshot(
            snapshot,
            persist=True,
        )

        if result is not False:

            logger.info(
                "[TimeTravel] CHECKPOINT created | "
                "name=%s | index=%d",
                name,
                self._cursor,
            )

        return result

    # ======================================================
    # REPLAY
    #
    # Replay is explicit.
    #
    # It does NOT execute actuator commands.
    # ======================================================

    def replay(
        self,
        from_index=0,
        to_index=None,
        emit_fn=None,
        delay=0.05,
        dry_run=True,
    ):

        if (
            self.event_bus is None
            and emit_fn is None
            and not dry_run
        ):

            raise RuntimeError(
                "[TimeTravelEngine] replay() requires "
                "EventBus or emit_fn when dry_run=False"
            )

        with self._lock:

            timeline_length = len(
                self._timeline
            )

        if timeline_length == 0:

            logger.warning(
                "[TimeTravel] Replay requested "
                "but timeline is empty"
            )

            return []

        start = max(
            0,
            int(from_index),
        )

        end = (
            timeline_length - 1
            if to_index is None
            else min(
                int(to_index),
                timeline_length - 1,
            )
        )

        if end < start:
            return []

        replayed = []

        previous_recording = (
            self.recording
        )

        previous_replaying = (
            self.replaying
        )

        self.replaying = True
        self.recording = False

        try:

            for idx in range(
                start,
                end + 1,
            ):

                with self._lock:

                    snapshot = deepcopy(
                        self._timeline[idx]
                    )

                event_type = snapshot.get(
                    "type"
                )

                payload = snapshot.get(
                    "payload"
                )

                logger.info(
                    "[TimeTravel] REPLAY | "
                    "idx=%d | type=%s | "
                    "track=%s | dry_run=%s",
                    idx,
                    event_type,
                    snapshot.get(
                        "track_id"
                    ),
                    dry_run,
                )

                # ------------------------------------------------
                # Explicit replay only.
                #
                # Never replay actuator commands directly.
                # They must be converted to Qbits and handed
                # to QbitDialer by the caller/authority layer.
                # ------------------------------------------------

                if (
                    not dry_run
                    and event_type
                    != "ACTUATOR_COMMAND"
                ):

                    if callable(emit_fn):

                        emit_fn(
                            event_type,
                            payload,
                        )

                    elif (
                        self.event_bus is not None
                    ):

                        emitter = getattr(
                            self.event_bus,
                            "_emit",
                            None,
                        )

                        if callable(emitter):

                            emitter(
                                event_type,
                                payload,
                            )

                elif (
                    not dry_run
                    and event_type
                    == "ACTUATOR_COMMAND"
                ):

                    logger.info(
                        "[TimeTravel] ACTUATOR_COMMAND "
                        "replay held | QbitDialer authority required"
                    )

                replayed.append(
                    snapshot
                )

                if delay:

                    time.sleep(
                        max(
                            0.0,
                            float(delay),
                        )
                    )

        finally:

            self.recording = (
                previous_recording
            )

            self.replaying = (
                previous_replaying
            )

        return replayed

    # ======================================================
    # SIMULATION
    # ======================================================

    def simulate(
        self,
        qbit,
        branches=3,
    ):

        if qbit is None:
            return None

        simulations = []

        for _ in range(
            max(
                1,
                int(branches),
            )
        ):

            try:
                sim_qbit = copy.deepcopy(
                    qbit
                )
            except Exception:
                sim_qbit = qbit

            outcome = self._run_simulation(
                sim_qbit
            )

            simulations.append(
                outcome
            )

        return self._score(
            simulations
        )

    def _run_simulation(
        self,
        qbit,
    ):

        result = {
            "timestamp": time.time(),
            "qbit_id": getattr(
                qbit,
                "id",
                None,
            ),
            "intent": getattr(
                qbit,
                "intent",
                None,
            ),
            "confidence": random.random(),
            "commands": getattr(
                qbit,
                "command_list",
                [],
            ),
        }

        self.history.append(
            result
        )

        return result

    def _score(
        self,
        simulations,
    ):

        if not simulations:
            return None

        return max(
            simulations,
            key=lambda item: item.get(
                "confidence",
                0.0,
            ),
        )

    # ======================================================
    # FORK
    # ======================================================

    def fork(
        self,
        index: int,
    ) -> List[dict]:

        with self._lock:

            if (
                0 <= index
                < len(self._timeline)
            ):

                branch = deepcopy(
                    self._timeline[
                        : index + 1
                    ]
                )

                logger.info(
                    "[TimeTravel] Forked timeline "
                    "at index %d",
                    index,
                )

                return branch

        return []

    # ======================================================
    # STATUS
    # ======================================================

    def status(self):

        with self._lock:

            return {
                "version": self.VERSION,
                "active": self.active,
                "recording": self.recording,
                "passive": True,
                "boot_complete":
                    self._system_boot_complete(),
                "activation_requested":
                    self._activation_requested,
                "shutdown_requested":
                    self._shutdown_requested,
                "replaying":
                    self.replaying,
                "events":
                    len(self._timeline),
                "cursor":
                    self._cursor,
                "max_events":
                    self.max_events,
                "timeline_file":
                    self.timeline_file,
                "event_bus_attached":
                    self.event_bus is not None,
                "event_hook_installed":
                    self._event_hook_installed,
                "hardware_enabled":
                    self.enable_hardware,
                "dialer_attached":
                    self.dialer is not None,
                "dialer_authority":
                    True,
                "last_pressure":
                    deepcopy(
                        self.last_pressure
                    ),
                "last_health_signal":
                    deepcopy(
                        self.last_health_signal
                    ),
                "qbit_available":
                    self.last_qbit is not None,
            }

    # ======================================================
    # CLEAR
    # ======================================================

    def clear(
        self,
        confirm=False,
    ):

        if not confirm:

            raise RuntimeError(
                "[TimeTravel] clear() requires confirm=True"
            )

        with self._lock:

            self._timeline.clear()
            self._cursor = -1

            self._save_timeline()

        logger.warning(
            "[TimeTravel] Timeline explicitly cleared"
        )

        return True


# ==========================================================
# END OF FILE
# ==========================================================