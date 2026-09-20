
# ==========================================================
# FILE: intent_to_action_mapper.py
# PATH: SEED_ROOT/seed/core/intent_to_action_mapper.py
#
# INTENT → ACTUATION MAPPER – Level 6
# VERSION: 2.1-FIX
#
# ROLE:
#   Intent observation
#       ↓
#   Intent normalization
#       ↓
#   Arbitration / safety
#       ↓
#   Action proposal
#       ↓
#   Actuator command
#
# QBIT / QBITDIALER:
#   Qbit carries identity and lineage.
#   QbitDialer remains the authoritative command plane.
#   This mapper does NOT become a second command authority.
# ==========================================================

import asyncio
import json
import logging
import math
import threading
import time
import uuid
from collections import deque
from typing import Callable, Dict, Optional

from seed.core.intent_memory import IntentMemory
from seed.core.safety_governor import SafetyGovernor
from seed.core.multi_agent_arbitrator import MultiAgentArbitrator
from seed.core.time_travel_engine import TimeTravelEngine

from seed.core.actuator_engine import ActuatorEngine, ActuatorFeed
from seed.core.intent_engine import (
    IntentEngine,
    INTENT_STATE,
    SYSTEM_ACTION,
)

from seed.systemutils.ethics import EthicsDecision


logger = logging.getLogger("IntentToActionMapper")


# ==========================================================
# SPEC CONSTANTS
# ==========================================================

CONFIDENCE_FLOOR = 0.20
DEFAULT_PRIORITY = 0.5
DEFAULT_QBIT = 0.0

MAX_REPLAY_EVENTS = 500
MAX_LEARNING_BUFFER = 1000

ACTUATION_RATE_LIMIT_SEC = 0.05

TREND_INDEX_FILE = "intent_mapper_trend_index.json"
REPLAY_EVENTS_FILE = "intent_mapper_replay.json"

REQUIRED_FIELDS = {
    "intent",
    "confidence",
}


# ==========================================================
# OPTIONAL TRACK ID
# ==========================================================

try:
    from seed.core.track_id_manager import TrackIDManager
except ImportError:
    TrackIDManager = None


# ==========================================================
# INTENT → ACTION REGISTRY
# ==========================================================

INTENT_ACTION_MAP = {}


def register_intent(prefix: str):
    def wrapper(fn):
        INTENT_ACTION_MAP[prefix] = fn
        return fn

    return wrapper


@register_intent("CAM_MOTION")
def _map_camera_motion(data):
    return {
        "actuator": "motor",
        "value": data.get(
            "confidence",
            0.0,
        ),
        "rotation_deg": math.degrees(
            data.get(
                "direction",
                {},
            ).get(
                "heading",
                0.0,
            )
        ),
    }


@register_intent("CAM_LIGHT")
def _map_camera_light(data):
    return {
        "actuator": "led",
        "value": data.get(
            "confidence",
            0.0,
        ),
    }


@register_intent("DEFAULT")
def _map_default(data):
    return {
        "actuator": "generic",
        "value": data.get(
            "confidence",
            0.0,
        ),
    }


# ==========================================================
# INTENT TO ACTION MAPPER
# ==========================================================

class IntentToActionMapper:

    # ======================================================
    # INITIALIZATION
    # ======================================================

    def __init__(
        self,
        emit=None,
        qbit=None,
        payload=None,
        intent_engine=None,
        module_registry=None,
        memory_crystallizer=None,
        health_monitor=None,
        track_system=None,
        ethics_manager=None,
        event_bus=None,
        dialer=None,
        actuators=None,
        intent="DEFAULT",
        intent_memory=IntentMemory,
        agent_manager=MultiAgentArbitrator,
        actuator_feed=ActuatorFeed,
    ):

        from seed.core.event_bus import SEEDEventBus
        from seed.systemutils.ethics import EthicsManager

        # --------------------------------------------------
        # Core dependencies
        # --------------------------------------------------

        self.event_bus = event_bus
        self.emit = emit
        self.qbit = qbit
        self.dialer = dialer

        self.intent_engine = intent_engine
        self.health_monitor = health_monitor
        self.track_system = track_system
        self.module_registry = module_registry
        self.memory_crystallizer = memory_crystallizer

        # --------------------------------------------------
        # EventBus is authoritative.
        # --------------------------------------------------

        if event_bus is None:
            raise ValueError(
                "IntentToActionMapper requires an event_bus instance"
            )

        if not hasattr(
            event_bus,
            "subscribe",
        ):
            raise TypeError(
                "event_bus must be a SEEDEventBus instance, not a class"
            )

        self.event_bus = event_bus

        # --------------------------------------------------
        # Actuator container
        # --------------------------------------------------

        self.actuators = (
            actuators
            if actuators is not None
            else {}
        )

        # --------------------------------------------------
        # Arbitration
        # --------------------------------------------------

        self.agent_manager = (
            agent_manager()
            if isinstance(
                agent_manager,
                type,
            )
            else agent_manager
        )

        self.arbitrator = MultiAgentArbitrator()

        self.actuator_feed = (
            actuator_feed()
            if isinstance(
                actuator_feed,
                type,
            )
            else actuator_feed
        )

        self.intent = intent

        # --------------------------------------------------
        # Safety
        # --------------------------------------------------

        self.safety_governor = SafetyGovernor()

        # --------------------------------------------------
        # Runtime state
        # --------------------------------------------------

        self.latest_event = None

        self._trend_index = 0

        self._replay_queue = deque(
            maxlen=MAX_REPLAY_EVENTS
        )

        self._last_emit_ts = 0.0

        self._stop_flag = threading.Event()

        # --------------------------------------------------
        # Ethics
        # --------------------------------------------------

        if ethics_manager is not None:
            self.ethics_manager = ethics_manager
        else:
            self.ethics_manager = EthicsManager()

        # --------------------------------------------------
        # Ethics decision layer
        #
        # This is governance/observation.
        # It does not become command authority.
        # --------------------------------------------------

        self.ethics_decision = EthicsDecision(
            memory_crystallizer=self.memory_crystallizer,
            health_monitor=self.health_monitor,
            module_registry=self.module_registry,
            track_system=self.track_system,
            emit=self.emit,
            qbit=self.qbit,
            event_bus=self.event_bus,
            intent_engine=self.intent_engine,
        )

        # --------------------------------------------------
        # Time Travel
        # --------------------------------------------------

        self.time_travel = TimeTravelEngine(
            dialer=self.dialer,
            emit=self.emit,
            enable_hardware=True,
            event_bus=self.event_bus,
        )

        try:
            self.time_travel.record(
                "ARBITRATED_INTENT",
                {
                    "intent": None,
                    "track_id": None,
                },
            )
        except Exception:
            logger.exception(
                "[IntentMapper] Initial TimeTravel record failed"
            )

        # --------------------------------------------------
        # Intent Memory
        # --------------------------------------------------

        self.intent_memory = IntentMemory(
            emit=self.emit,
            event_bus=self.event_bus,
            qbit_dialer=self.dialer,
            time_travel_engine=self.time_travel,
        )

        # --------------------------------------------------
        # Event subscriptions
        # --------------------------------------------------

        if hasattr(
            self.event_bus,
            "subscribe",
        ):

            self.event_bus.subscribe(
                "INTENT_STATE",
                self._handle_intent_event,
            )

            self.event_bus.subscribe(
                "INTENT_UPDATED",
                self._handle_intent_event,
            )

            self.event_bus.subscribe(
                "COMMAND_EXECUTED",
                self._handle_intent_event,
            )

            self.event_bus.subscribe(
                "INFO",
                self._handle_intent_event,
            )

        # --------------------------------------------------
        # Initial ethics evaluation
        # --------------------------------------------------

        try:

            evaluate = getattr(
                self.ethics_manager,
                "evaluate",
                None,
            )

            if callable(evaluate):

                result = evaluate(
                    intent="INTENT_STATE"
                )

                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        pass

        except Exception:
            logger.exception(
                "[IntentMapper] Initial ethics evaluation failed"
            )

        # --------------------------------------------------
        # Persistence
        # --------------------------------------------------

        self._trend_index = (
            self._load_trend_index()
        )

        self._replay_queue.extend(
            self._load_replay_queue()
        )

        self._setup_listeners()

    # ======================================================
    # LISTENERS
    # ======================================================

    def _setup_listeners(self):

        if not hasattr(
            self.event_bus,
            "subscribe",
        ):
            return

        # Avoid assuming duplicate subscriptions are harmless.
        self.event_bus.subscribe(
            "INTENT_STATE",
            self._handle_intent_event,
        )

        self.event_bus.subscribe(
            "INFO",
            self._handle_intent_event,
        )

    # ======================================================
    # TRACK ID
    # ======================================================

    def _gen_track_id(
        self,
        prefix="ITAM",
    ):

        if TrackIDManager:

            try:

                return TrackIDManager.generate(
                    channel_marker=prefix
                )

            except Exception:
                logger.debug(
                    "[IntentMapper] TrackIDManager generation failed",
                    exc_info=True,
                )

        return (
            f"{prefix}-"
            f"{uuid.uuid4().hex[:8]}"
        )

    # ======================================================
    # PERSISTENCE
    # ======================================================

    def _load_trend_index(self):

        try:

            with open(
                TREND_INDEX_FILE,
                "r",
                encoding="utf-8",
            ) as f:

                data = json.load(f)

                return int(
                    data.get(
                        "trend_index",
                        0,
                    )
                )

        except Exception:
            return 0

    def _save_trend_index(self):

        try:

            with open(
                TREND_INDEX_FILE,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    {
                        "trend_index": self._trend_index
                    },
                    f,
                )

        except Exception as exc:

            logger.warning(
                "[IntentMapper] trend_index save failed: %s",
                exc,
            )

    def _load_replay_queue(self):

        try:

            with open(
                REPLAY_EVENTS_FILE,
                "r",
                encoding="utf-8",
            ) as f:

                data = json.load(f)

                return (
                    data
                    if isinstance(
                        data,
                        list,
                    )
                    else []
                )

        except Exception:
            return []

    def _save_replay_queue(self):

        try:

            with open(
                REPLAY_EVENTS_FILE,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    list(
                        self._replay_queue
                    ),
                    f,
                )

        except Exception as exc:

            logger.warning(
                "[IntentMapper] replay save failed: %s",
                exc,
            )

    # ======================================================
    # EVENT NORMALIZATION
    # ======================================================

    def _normalize_event(
        self,
        data: dict,
    ) -> dict:

        data = dict(data)

        if (
            "dominant_intent" in data
            and "intent" not in data
        ):

            data["intent"] = str(
                data["dominant_intent"]
            )

        data.setdefault(
            "intent",
            "idle",
        )

        data.setdefault(
            "confidence",
            0.0,
        )

        data.setdefault(
            "priority",
            DEFAULT_PRIORITY,
        )

        data.setdefault(
            "qbit",
            DEFAULT_QBIT,
        )

        data.setdefault(
            "timestamp",
            time.time(),
        )

        data.setdefault(
            "agent_id",
            None,
        )

        data.setdefault(
            "track_id",
            self._gen_track_id(),
        )

        return data

    # ======================================================
    # EVENT HANDLER
    # ======================================================

    def _handle_intent_event(
        self,
        event,
    ):

        data = (
            event.get(
                "data",
                event,
            )
            if isinstance(
                event,
                dict,
            )
            else event
        )

        if not isinstance(
            data,
            dict,
        ):
            return

        try:

            data = self._normalize_event(
                data
            )

            self.latest_event = data

            # --------------------------------------------------
            # Arbitration receives the normalized observation.
            # --------------------------------------------------

            ingest = getattr(
                self.arbitrator,
                "ingest",
                None,
            )

            if callable(ingest):

                ingest(data)

            # --------------------------------------------------
            # Learning data
            # --------------------------------------------------

            if (
                self.agent_manager
                and hasattr(
                    self.agent_manager,
                    "learning_data",
                )
            ):

                try:

                    self._trend_index += 1

                    snapshot = {

                        "trend_index":
                            self._trend_index,

                        "intent":
                            data["intent"],

                        "confidence":
                            data["confidence"],

                        "qbit":
                            data["qbit"],

                        "priority":
                            data["priority"],

                        "timestamp":
                            data["timestamp"],

                        "agent_id":
                            data["agent_id"],

                        "track_id":
                            data["track_id"],
                    }

                    self.agent_manager.learning_data.append(
                        snapshot
                    )

                    if len(
                        self.agent_manager.learning_data
                    ) > MAX_LEARNING_BUFFER:

                        self.agent_manager.learning_data.pop(
                            0
                        )

                    self._save_trend_index()

                except Exception as exc:

                    logger.warning(
                        "[IntentMapper] learning push failed: %s",
                        exc,
                    )

                    self._replay_queue.append(
                        data
                    )

                    self._save_replay_queue()

        except Exception:

            logger.exception(
                "[IntentMapper] Intent event processing failed"
            )

    # ======================================================
    # START
    # ======================================================

    def start(
        self,
        interval: float = ACTUATION_RATE_LIMIT_SEC,
    ):

        self._stop_flag.clear()

        threading.Thread(
            target=self._loop,
            args=(interval,),
            daemon=True,
            name="IntentToActionMapper",
        ).start()

        threading.Thread(
            target=self._process_replay_queue,
            daemon=True,
            name="IntentReplayProcessor",
        ).start()

        logger.info(
            "[IntentMapper] started"
        )

    # ======================================================
    # STOP
    # ======================================================

    def stop(self):

        self._stop_flag.set()

        logger.info(
            "[IntentMapper] stopped"
        )

    # ======================================================
    # MAPPER LOOP
    # ======================================================

    def _loop(
        self,
        interval,
    ):

        while not self._stop_flag.is_set():

            try:

                event = self.latest_event

                if (
                    not event
                    or event.get(
                        "confidence",
                        0.0,
                    ) < CONFIDENCE_FLOOR
                ):

                    time.sleep(interval)
                    continue

                now = time.time()

                if (
                    now - self._last_emit_ts
                    < interval
                ):

                    time.sleep(interval)
                    continue

                cmd = self._map_intent(
                    event
                )

                if not cmd:

                    time.sleep(interval)
                    continue

                qbit_value = max(
                    0.0,
                    min(
                        1.0,
                        float(
                            event.get(
                                "qbit",
                                DEFAULT_QBIT,
                            )
                        ),
                    ),
                )

                priority_value = max(
                    0.0,
                    min(
                        1.0,
                        float(
                            event.get(
                                "priority",
                                DEFAULT_PRIORITY,
                            )
                        ),
                    ),
                )

                weight = (
                    (
                        0.5
                        + 0.5 * qbit_value
                    )
                    *
                    (
                        0.5
                        + 0.5 * priority_value
                    )
                )

                cmd["value"] *= weight

                cmd["track_id"] = (
                    event.get(
                        "track_id"
                    )
                    or self._gen_track_id(
                        "CMD"
                    )
                )

                cmd["qbit"] = self.qbit

                cmd["qbit_id"] = (
                    event.get(
                        "qbit_id"
                    )
                )

                cmd["task_id"] = (
                    event.get(
                        "task_id"
                    )
                )

                cmd["pipeline_id"] = (
                    event.get(
                        "pipeline_id"
                    )
                )

                cmd["source"] = (
                    event.get(
                        "source",
                        "IntentToActionMapper",
                    )
                )

                cmd["_source"] = (
                    "IntentToActionMapper"
                )

                # --------------------------------------------------
                # Action proposal enters the mapper emission path.
                # QbitDialer remains the authoritative command plane.
                # --------------------------------------------------

                self._emit_command(
                    cmd
                )

                self._last_emit_ts = now

            except Exception as exc:

                logger.warning(
                    "[IntentMapperLoop] %s",
                    exc,
                )

            time.sleep(
                interval
            )

    # ======================================================
    # REPLAY
    # ======================================================

    def _process_replay_queue(self):

        while (
            not self._stop_flag.is_set()
            and self._replay_queue
        ):

            data = (
                self._replay_queue.popleft()
            )

            self._handle_intent_event(
                {
                    "data": data
                }
            )

        self._save_replay_queue()

    # ======================================================
    # MAPPING
    # ======================================================

    def _map_intent(
        self,
        data: dict,
    ) -> dict:

        intent = str(
            data.get(
                "intent",
                "DEFAULT",
            )
        ).upper()

        for prefix, fn in INTENT_ACTION_MAP.items():

            if intent.startswith(
                prefix
            ):

                return fn(data)

        return INTENT_ACTION_MAP[
            "DEFAULT"
        ](data)

    # ======================================================
    # EMIT COMMAND
    # ======================================================

    def _emit_command(
        self,
        command: dict,
    ):

        # --------------------------------------------------
        # EventBus observation / actuator proposal.
        # --------------------------------------------------

        if hasattr(
            self.event_bus,
            "emit",
        ):

            try:

                loop = asyncio.get_running_loop()

                result = self.event_bus.emit(
                    "ACTUATOR_COMMAND",
                    data=command,
                )

                if asyncio.iscoroutine(
                    result
                ):

                    loop.create_task(
                        result
                    )

            except RuntimeError:
                pass

            except Exception:

                logger.exception(
                    "[IntentMapper] EventBus command emission failed"
                )

        # --------------------------------------------------
        # Safety validation before direct actuator use.
        # --------------------------------------------------

        actuator_name = command.get(
            "actuator"
        )

        actuator = None

        if isinstance(
            self.actuators,
            dict,
        ):

            actuator = self.actuators.get(
                actuator_name
            )

        elif self.actuators is not None:

            actuator = getattr(
                self.actuators,
                actuator_name,
                None,
            )

        if (
            actuator
            and hasattr(
                actuator,
                "apply",
            )
        ):

            try:

                safe = (
                    self.safety_governor.validate(
                        command
                    )
                )

                if safe:

                    actuator.apply(
                        safe
                    )

            except Exception as exc:

                logger.warning(
                    "[IntentMapper] actuator apply failed "
                    "(%s): %s",
                    actuator_name,
                    exc,
                )

