
# ==========================================================
# FILE: channel_id.py
# PATH: SEED_ROOT/seed/core/channel_id.py
# VERSION: 5.0.0
# SYSTEM-INTEGRATED | QBIT-AWARE | TRACK-AWARE | HUD-DISCOVERABLE
# FLOW-CONTROL | MONOTONIC | INTENT | LEARNING | RECOVERY
# UPDATED: 2026-08-30
# ==========================================================
#
# SYSTEM ROLE
# ----------------------------------------------------------
# ChannelID is the authoritative channel identity / flow /
# pressure / learning registry.
#
# ChannelID DOES:
#   - identify channels
#   - sequence channel emissions
#   - enforce channel flow state
#   - maintain channel metadata
#   - maintain channel pressure
#   - maintain intent learning
#   - expose HUD telemetry
#   - expose Qbit-safe channel metadata
#   - provide recovery / learning information
#
# ChannelID DOES NOT:
#   - execute commands
#   - bypass QbitDialer.submit_command()
#   - own TrackSystem context
#   - directly control actuators
#   - become a second command plane
#
# SYSTEM CONNECTIONS
# ----------------------------------------------------------
#   __init__.py / registry
#          │
#          ▼
#      ChannelID
#       │   │
#       │   ├────────► TrackSystem / TrackID
#       │   │
#       │   ├────────► Qbit / QbitDialer telemetry
#       │   │
#       │   ├────────► EventBus
#       │   │
#       │   └────────► Oracle observation
#       │
#       └────────────► HUD / DEVHUD
#
# IMPORTANT:
# ChannelID may describe and gate flow.
# It must never become an alternate command authority.
#
# ==========================================================

import logging
import threading
import time
import uuid

from collections import deque, defaultdict
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger("ChannelID")
logger.setLevel(logging.INFO)

MODULE_ID = "CID-5"

# ==========================================================
# Constants
# ==========================================================

PRESSURE_MAX = 1.0

INTENT_CHAIN_DISCOUNT = 0.6
AGENT_CONFIDENCE_DECAY = 0.98

PRESSURE_PENALTY = 0.10

GENOME_DECAY = 0.02
GENOME_PRUNE_THRESHOLD = -0.75
GENOME_WARNING_THRESHOLD = -0.40

MIN_GENOME_SAMPLES = 6

DEADLOCK_SILENCE = 3.0
FLOOD_RATE = 50.0
HIGH_RATE = 10.0

PRESSURE_INCREASE = {
    "PRESSURE": 0.05,
    "FLOOD": 0.20,
    "DEADLOCK": 0.15,
    "INTENT_FAIL": 0.10,
}

PRESSURE_REWARD = {
    "INTENT_SUCCESS": 0.05,
}

PRESSURE_DECAY = 0.01

STATE_COLORS = {
    "ACTIVE": "#00ff88",
    "PAUSED": "#ffaa00",
    "MUTED": "#555555",
    "ERROR": "#ff0033",
}

FLOW_COLORS = {
    True: "#00ccff",
    False: "#222222",
}

RATE_THRESHOLDS = {
    "LOW": 0.1,
    "NORMAL": 1.0,
    "HIGH": 10.0,
    "FLOOD": 50.0,
}

LEARNING_RATE = 0.15

CROSSOVER_MIN_SCORE = 0.35
CROSSOVER_MIN_SAMPLES = 8
CROSSOVER_MAX_LENGTH = 6

# ==========================================================
# Debug Track Helper
# ----------------------------------------------------------
# NON-AUTHORITATIVE.
# This is diagnostic telemetry only.
# ==========================================================


def track(
    channel,
    state,
    *args,
    priority="MED",
    loop_id=None,
    input_from=None,
    output_to=None,
    note=None,
):
    try:
        parts = [
            "[TRACK]",
            f"{MODULE_ID}:{channel}",
            f"| {state}",
            f"| PRIORITY={priority}",
        ]

        if loop_id:
            parts.append(f"| {loop_id}")

        if input_from:
            parts.append(f"| IN={input_from}")

        if output_to:
            parts.append(f"| OUT={output_to}")

        if note:
            parts.append(f"| NOTE={note}")

        print(" ".join(parts), flush=True)

    except Exception:
        pass


track("CH-3", "B-IMPORT", priority="HIGH")


# ==========================================================
# Optional System / Oracle Connection Helpers
# ==========================================================
#
# These are deliberately lazy imports.
#
# Reason:
#   channel_id.py is a low-level core module.
#   Hard importing registry / Oracle / EventBus / QbitDialer
#   during module import can create circular imports.
#
# These helpers therefore connect only when a system object
# is actually available.
# ==========================================================


def _safe_registry():

    candidates = (
        "seed.core.registry",
        "seed.registry",
        "seed.core.system_registry",
    )

    for module_name in candidates:
        try:
            module = __import__(
                module_name,
                fromlist=["REGISTRY", "registry", "Registry"],
            )

            registry = getattr(module, "REGISTRY", None)

            if registry is not None:
                return registry

            registry = getattr(module, "registry", None)

            if registry is not None:
                return registry

        except Exception:
            continue

    return None


def _registry_publish(name, value):

    registry = _safe_registry()

    if registry is None:
        return False

    try:
        if hasattr(registry, "register"):
            registry.register(name, value)
            return True

        if hasattr(registry, "set"):
            registry.set(name, value)
            return True

        if isinstance(registry, dict):
            registry[name] = value
            return True

    except Exception:
        logger.debug(
            "[ChannelID] Registry publication failed",
            exc_info=True,
        )

    return False


def _safe_emit(event_bus, event_name, payload):

    if event_bus is None:
        return False

    try:
        emit = getattr(event_bus, "emit", None)

        if callable(emit):
            try:
                emit(event_name, payload=payload)
            except TypeError:
                emit(event_name, payload)

            return True

    except Exception:
        logger.debug(
            "[ChannelID] EventBus emission failed",
            exc_info=True,
        )

    return False


def _safe_oracle_observe(oracle, event_name, payload):

    if oracle is None:
        return False

    try:
        observer = getattr(oracle, "observe", None)

        if callable(observer):
            observer(event_name, payload)
            return True

        observer = getattr(oracle, "record", None)

        if callable(observer):
            observer(event_name, payload)
            return True

        observer = getattr(oracle, "ingest", None)

        if callable(observer):
            observer(event_name, payload)
            return True

    except Exception:
        logger.debug(
            "[ChannelID] Oracle observation failed",
            exc_info=True,
        )

    return False


# ==========================================================
# Channel Registry
# ==========================================================


class _ChannelRegistry:

    def __init__(self):
        self.lock = threading.RLock()

        self.counters = {}
        self.metadata = {}
        self.controllers = {}
        self.states = {}
        self.tracks = {}
        self.flow_enabled = {}

        self.intent_log = deque(maxlen=5000)

        self.heatmap = defaultdict(
            lambda: {
                "avg": 0.0,
                "peak": 0.0,
                "events": 0,
                "last_ts": None,
            }
        )

        # --------------------------------------------------
        # Intent genome store
        # --------------------------------------------------

        self.intent_genomes = defaultdict(
            lambda: {
                "score": 0.0,
                "samples": 0,
                "agents": defaultdict(int),
                "channels": defaultdict(int),
                "last_ts": None,
                "status": "ACTIVE",
            }
        )

        self.genome_crossovers = []

        self.recovery_scores = defaultdict(
            lambda: {
                "success": 0,
                "fail": 0,
            }
        )

        # --------------------------------------------------
        # Channel learning
        # --------------------------------------------------

        self.channel_weights = defaultdict(
            lambda: {
                "success": 0,
                "fail": 0,
                "bias": 0.0,
            }
        )

        # --------------------------------------------------
        # Agent learning
        # --------------------------------------------------

        self.agent_weights = defaultdict(
            lambda: {
                "success": 0,
                "fail": 0,
                "confidence": 0.5,
            }
        )

        # --------------------------------------------------
        # Cross-agent consensus
        # --------------------------------------------------

        self.global_channel_bias = defaultdict(
            lambda: {
                "bias": 0.0,
                "contributors": set(),
            }
        )

        self.allowed_states = {
            "ACTIVE",
            "PAUSED",
            "MUTED",
            "ROUTED",
            "ERROR",
            "RECOVERING",
            "CLONED",
        }

        # --------------------------------------------------
        # System connection references
        # --------------------------------------------------

        self.event_bus = None
        self.track_system = None
        self.qbit = None
        self.qbit_dialer = None
        self.hud = None
        self.oracle = None
        self.system_registry = None


REGISTRY = _ChannelRegistry()


# ==========================================================
# System Wiring
# ==========================================================


def connect_system(
    *,
    event_bus=None,
    track_system=None,
    qbit=None,
    qbit_dialer=None,
    hud=None,
    oracle=None,
    registry=None,
):


    with REGISTRY.lock:
        if event_bus is not None:
            REGISTRY.event_bus = event_bus

        if track_system is not None:
            REGISTRY.track_system = track_system

        if qbit is not None:
            REGISTRY.qbit = qbit

        if qbit_dialer is not None:
            REGISTRY.qbit_dialer = qbit_dialer

        if hud is not None:
            REGISTRY.hud = hud

        if oracle is not None:
            REGISTRY.oracle = oracle

        if registry is not None:
            REGISTRY.system_registry = registry

    # Publish ChannelID itself to the authoritative registry
    # when a registry is supplied.
    target_registry = registry or _safe_registry()

    if target_registry is not None:
        try:
            if hasattr(target_registry, "register"):
                target_registry.register("ChannelID", ChannelID)
                target_registry.register("ChannelRegistry", REGISTRY)

            elif hasattr(target_registry, "set"):
                target_registry.set("ChannelID", ChannelID)
                target_registry.set("ChannelRegistry", REGISTRY)

            elif isinstance(target_registry, dict):
                target_registry["ChannelID"] = ChannelID
                target_registry["ChannelRegistry"] = REGISTRY

        except Exception:
            logger.debug(
                "[ChannelID] System registry connection failed",
                exc_info=True,
            )

    payload = {
        "module": MODULE_ID,
        "channel_id": "ChannelID",
        "track_system": track_system is not None,
        "qbit": qbit is not None,
        "qbit_dialer": qbit_dialer is not None,
        "event_bus": event_bus is not None,
        "hud": hud is not None,
        "oracle": oracle is not None,
        "timestamp": time.time(),
    }

    _safe_emit(
        event_bus,
        "CHANNEL_ID_CONNECTED",
        payload,
    )

    _safe_oracle_observe(
        oracle,
        "CHANNEL_ID_CONNECTED",
        payload,
    )

    logger.info(
        "[ChannelID] System connections established | "
        "TrackSystem=%s Qbit=%s Dialer=%s EventBus=%s HUD=%s Oracle=%s",
        track_system is not None,
        qbit is not None,
        qbit_dialer is not None,
        event_bus is not None,
        hud is not None,
        oracle is not None,
    )

    return payload


# ==========================================================
# TrackSystem Connection
# ==========================================================


def attach_track_system(track_system):
    """
    Attach the authoritative TrackSystem.

    ChannelID stores track references for channel discovery,
    but TrackSystem remains the owner of track context.
    """
    REGISTRY.track_system = track_system

    _safe_emit(
        REGISTRY.event_bus,
        "CHANNEL_TRACK_SYSTEM_CONNECTED",
        {
            "module": MODULE_ID,
            "track_system": type(track_system).__name__,
            "timestamp": time.time(),
        },
    )

    return track_system


# ==========================================================
# Qbit / QbitDialer Connection
# ==========================================================


def attach_qbit_system(qbit=None, qbit_dialer=None):

    if qbit is not None:
        REGISTRY.qbit = qbit

    if qbit_dialer is not None:
        REGISTRY.qbit_dialer = qbit_dialer

    payload = {
        "module": MODULE_ID,
        "qbit": qbit is not None,
        "qbit_dialer": qbit_dialer is not None,
        "timestamp": time.time(),
    }

    _safe_emit(
        REGISTRY.event_bus,
        "CHANNEL_QBIT_CONNECTED",
        payload,
    )

    _safe_oracle_observe(
        REGISTRY.oracle,
        "CHANNEL_QBIT_CONNECTED",
        payload,
    )

    return payload


# ==========================================================
# Internal Safe Track Manager Import
# ==========================================================


def _safe_track_manager():
    try:
        from seed.core.track_id_manager import TrackIDManager

        return TrackIDManager

    except Exception:
        logger.debug(
            "[ChannelID] TrackIDManager unavailable",
            exc_info=True,
        )

        return None


# ==========================================================
# ChannelID
# ==========================================================


class ChannelID:

    _registry = {}

    DEFAULT_DOMAIN = "SEED"
    DEFAULT_GROUP = "GEN"

    SYSTEM_WARNING = "SYSTEM_WARNING"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    SYSTEM_LIMP = "SYSTEM_LIMP"

    COMMAND_EXECUTED = "COMMAND_EXECUTED"
    ANALYTICS_UPDATED = "ANALYTICS_UPDATED"
    HEARTBEAT = "HEARTBEAT"

    DEVICE_CONNECTED = "DEVICE_CONNECTED"
    DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"

    SKILL_LOADED = "SKILL_LOADED"
    SKILL_FAILED = "SKILL_FAILED"

    CUSTOM_EVENT = "CUSTOM_EVENT"

    QBIT_TICK = "QBIT_TICK"
    QBIT_RESULT = "QBIT_RESULT"
    QBIT = "QBIT"
    QBIT_DIALER = "QBIT_DIALER"
    QBIT_PHASE = "QBIT_PHASE"
    QBIT_CORE = "QBIT_CORE"

    INTENT_UPDATED = "INTENT_UPDATED"
    INTENT_STATE = "INTENT_STATE"
    SKILL_COMMAND = "SKILL_COMMAND"

    EVENT_BUS_READY = "EVENT_BUS_READY"
    EVENT_BUS = "EVENT_BUS"
    EVENT_EMIT = "EVENT_EMIT"
    EVENT_WRAPPER = "EMIT_WRAPPER"
    EMIT = "EMIT"

    # ------------------------------------------------------
    # Registration
    # ------------------------------------------------------

    @classmethod
    def register(cls, name, controller=None, metadata=None):
        with REGISTRY.lock:
            entry = {
                "controller": controller,
                "metadata": metadata or {},
            }

            cls._registry[name] = entry

            REGISTRY.controllers[name] = (
                controller if controller is not None else "SYSTEM"
            )

            REGISTRY.metadata.setdefault(
                name,
                {
                    "pressure": 0.0,
                    "flags": set(),
                    "last_emit_ts": None,
                    "emit_count": 0,
                },
            )

            REGISTRY.states.setdefault(name, "ACTIVE")
            REGISTRY.counters.setdefault(name, 0)
            REGISTRY.tracks.setdefault(name, [])
            REGISTRY.flow_enabled.setdefault(name, True)

        return entry

    # ------------------------------------------------------
    # Construction
    # ------------------------------------------------------

    @staticmethod
    def build(
        name: str,
        *,
        group: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> str:
        domain = (
            domain or ChannelID.DEFAULT_DOMAIN
        ).upper()

        group = (
            group or ChannelID.DEFAULT_GROUP
        ).upper()

        return f"{domain}:{group}:{name.upper()}"

    # ------------------------------------------------------
    # Internal Ensure
    # ------------------------------------------------------

    @staticmethod
    def _ensure_registered(channel: str):
        if not channel:
            channel = "UNKNOWN"

        with REGISTRY.lock:
            REGISTRY.states.setdefault(
                channel,
                "ACTIVE",
            )

            REGISTRY.controllers.setdefault(
                channel,
                "SYSTEM",
            )

            REGISTRY.metadata.setdefault(
                channel,
                {
                    "pressure": 0.0,
                    "flags": set(),
                    "last_emit_ts": None,
                    "emit_count": 0,
                },
            )

            REGISTRY.counters.setdefault(
                channel,
                0,
            )

            REGISTRY.tracks.setdefault(
                channel,
                [],
            )

            REGISTRY.flow_enabled.setdefault(
                channel,
                True,
            )

            REGISTRY.channel_weights[channel]
            REGISTRY.global_channel_bias[channel]

    # ------------------------------------------------------
    # Sequence
    # ------------------------------------------------------

    @staticmethod
    def next(
        channel,
        *,
        track_id=None,
        overlay=False,
    ):
        ChannelID._ensure_registered(channel)

        with REGISTRY.lock:
            if not REGISTRY.flow_enabled[channel]:
                return None

            if REGISTRY.states[channel] in (
                "PAUSED",
                "MUTED",
                "ROUTED",
            ):
                return None

            REGISTRY.counters[channel] += 1

            REGISTRY.metadata[channel]["emit_count"] += 1
            REGISTRY.metadata[channel]["last_emit_ts"] = time.time()

            if (
                track_id
                and track_id not in REGISTRY.tracks[channel]
            ):
                REGISTRY.tracks[channel].append(track_id)

            seq = REGISTRY.counters[channel]

            pressure = REGISTRY.metadata[channel]["pressure"]

            local = REGISTRY.channel_weights[channel]
            global_b = REGISTRY.global_channel_bias[channel]["bias"]

        if overlay:
            return {
                "channel": channel,
                "seq": seq,
                "pressure": pressure,
                "local_bias": local["bias"],
                "global_bias": round(global_b, 4),
                "state": REGISTRY.states[channel],
                "flow": REGISTRY.flow_enabled[channel],
                "track": track_id,
            }

        return seq

    # ------------------------------------------------------
    # State
    # ------------------------------------------------------

    @staticmethod
    def set_state(
        channel: str,
        state: str,
    ):
        state = str(state).upper()

        if state not in REGISTRY.allowed_states:
            return False

        ChannelID._ensure_registered(channel)

        with REGISTRY.lock:
            REGISTRY.states[channel] = state

        _safe_emit(
            REGISTRY.event_bus,
            "CHANNEL_STATE_CHANGED",
            {
                "channel": channel,
                "state": state,
                "timestamp": time.time(),
            },
        )

        return True

    # ------------------------------------------------------
    # Flow
    # ------------------------------------------------------

    @staticmethod
    def set_flow(
        channel: str,
        enabled: bool,
    ):
        ChannelID._ensure_registered(channel)

        enabled = bool(enabled)

        with REGISTRY.lock:
            REGISTRY.flow_enabled[channel] = enabled

        _safe_emit(
            REGISTRY.event_bus,
            "CHANNEL_FLOW_CHANGED",
            {
                "channel": channel,
                "enabled": enabled,
                "timestamp": time.time(),
            },
        )

        return enabled

    # ------------------------------------------------------
    # Reroute
    # ------------------------------------------------------

    @staticmethod
    def reroute(
        channel: str,
        new_channel: str,
    ):
        ChannelID._ensure_registered(channel)
        ChannelID._ensure_registered(new_channel)

        with REGISTRY.lock:
            REGISTRY.controllers[new_channel] = (
                REGISTRY.controllers[channel]
            )

            REGISTRY.metadata[new_channel].update(
                REGISTRY.metadata[channel]
            )

            REGISTRY.tracks[new_channel].extend(
                REGISTRY.tracks[channel]
            )

            REGISTRY.tracks[new_channel] = list(
                dict.fromkeys(
                    REGISTRY.tracks[new_channel]
                )
            )

            REGISTRY.flow_enabled[channel] = False
            REGISTRY.states[channel] = "ROUTED"

        _safe_emit(
            REGISTRY.event_bus,
            "CHANNEL_REROUTED",
            {
                "channel": channel,
                "new_channel": new_channel,
                "timestamp": time.time(),
            },
        )

        return new_channel

    # ------------------------------------------------------
    # Channel Listing
    # ------------------------------------------------------

    @staticmethod
    def list_channels(
        hud_overlay: bool = False,
    ):
        with REGISTRY.lock:
            if not hud_overlay:
                return list(REGISTRY.states.keys())

            return [
                {
                    "name": channel,
                    "seq": REGISTRY.counters[channel],
                    "state": REGISTRY.states[channel],
                    "controller": REGISTRY.controllers[channel],
                    "flow": REGISTRY.flow_enabled[channel],
                    "tracks": list(
                        REGISTRY.tracks[channel]
                    ),
                    "pressure": REGISTRY.metadata[channel][
                        "pressure"
                    ],
                }
                for channel in REGISTRY.states
            ]

    # ------------------------------------------------------
    # Sorted Channel Discovery
    # ------------------------------------------------------

    @staticmethod
    def get_sorted_channels(
        hud_overlay: bool = False,
    ):

        channels = ChannelID.list_channels(
            hud_overlay=True
        )

        channels.sort(
            key=lambda item: (
                -float(item.get("pressure", 0.0)),
                -int(item.get("seq", 0)),
                str(item.get("name", "")),
            )
        )

        if hud_overlay:
            return channels

        return [
            item["name"]
            for item in channels
        ]

    # ------------------------------------------------------
    # Priority
    # ------------------------------------------------------

    @staticmethod
    def bump_priority(channel: str):
        ChannelID._ensure_registered(channel)

        with REGISTRY.lock:
            REGISTRY.metadata[channel]["pressure"] = min(
                PRESSURE_MAX,
                REGISTRY.metadata[channel]["pressure"]
                + 0.1,
            )

            return REGISTRY.metadata[channel]["pressure"]

    @staticmethod
    def lower_priority(channel: str):
        ChannelID._ensure_registered(channel)

        with REGISTRY.lock:
            REGISTRY.metadata[channel]["pressure"] = max(
                0.0,
                REGISTRY.metadata[channel]["pressure"]
                - 0.05,
            )

            return REGISTRY.metadata[channel]["pressure"]

    # ------------------------------------------------------
    # Track Attachment
    # ------------------------------------------------------

    @staticmethod
    def attach_track(
        channel: str,
        track_id: str,
    ):
        ChannelID._ensure_registered(channel)

        if not track_id:
            return False

        with REGISTRY.lock:
            if track_id not in REGISTRY.tracks[channel]:
                REGISTRY.tracks[channel].append(
                    track_id
                )

        return True

    @staticmethod
    def detach_track(
        channel: str,
        track_id: str,
    ):
        ChannelID._ensure_registered(channel)

        with REGISTRY.lock:
            try:
                REGISTRY.tracks[channel].remove(
                    track_id
                )
            except ValueError:
                pass

        return True


# ==========================================================
# Intent Fields
# ==========================================================

INTENT_FIELDS = {
    "intent_id",
    "agent_id",
    "channel",
    "action",
    "parent_intent",
    "track_id",
    "pressure",
    "ts",
}


# ==========================================================
# Intent Registration
# ==========================================================


def register_intent(
    *,
    agent_id,
    channel,
    action,
    parent_intent=None,
    track_id=None,
):
    ChannelID._ensure_registered(channel)

    intent = {
        "intent_id": (
            f"I-{time.time_ns()}-{uuid.uuid4().hex[:8]}"
        ),
        "agent_id": agent_id,
        "channel": channel,
        "action": action,
        "parent_intent": parent_intent,
        "track_id": track_id,
        "ts": time.time(),
    }

    with REGISTRY.lock:
        REGISTRY.intent_log.append(intent)

    if track_id:
        ChannelID.attach_track(
            channel,
            track_id,
        )

    _safe_emit(
        REGISTRY.event_bus,
        "INTENT_REGISTERED",
        dict(intent),
    )

    _safe_oracle_observe(
        REGISTRY.oracle,
        "INTENT_REGISTERED",
        dict(intent),
    )

    return intent["intent_id"]


# ==========================================================
# Intent Lookup
# ==========================================================


def _find_intent(intent_id):
    with REGISTRY.lock:
        for intent in reversed(REGISTRY.intent_log):
            if intent.get("intent_id") == intent_id:
                return intent

    return None


def resolve_intent_chain(intent_id):

    chain = []

    current_id = intent_id
    visited = set()

    while current_id and current_id not in visited:
        visited.add(current_id)

        intent = _find_intent(current_id)

        if intent is None:
            break

        chain.append(dict(intent))

        current_id = intent.get(
            "parent_intent"
        )

    chain.reverse()

    return chain


# ==========================================================
# Genome Key
# ==========================================================


def _genome_key(
    chain: List[Dict[str, Any]],
) -> str:
    return " > ".join(
        f"{item.get('action')}@{item.get('channel')}"
        for item in chain
    )


# ==========================================================
# Rate / Flood / Deadlock
# ==========================================================


def compute_rate(meta):
    last = meta.get("last_emit_ts")

    if not last:
        return 0.0

    elapsed = max(
        time.time() - last,
        0.001,
    )

    return round(
        1.0 / elapsed,
        2,
    )


def detect_flood(rate):
    if rate >= FLOOD_RATE:
        return "FLOOD"

    if rate >= HIGH_RATE:
        return "PRESSURE"

    return None


def detect_deadlock(meta):
    last = meta.get("last_emit_ts")

    if not last:
        return "COLD_START"

    if (
        time.time() - last
        >= DEADLOCK_SILENCE
    ):
        return "DEADLOCK"

    return None


# ==========================================================
# Pressure
# ==========================================================


def update_pressure(
    meta,
    event_type=None,
    dt=0.5,
):
    p = float(
        meta.get("pressure", 0.0)
    )

    p = max(
        0.0,
        p - PRESSURE_DECAY * dt,
    )

    if event_type in PRESSURE_INCREASE:
        p += PRESSURE_INCREASE[event_type]

    elif event_type in PRESSURE_REWARD:
        p -= PRESSURE_REWARD[event_type]

    meta["pressure"] = min(
        PRESSURE_MAX,
        round(p, 3),
    )

    return meta["pressure"]


# ==========================================================
# Heatmap
# ==========================================================


def update_heatmap(
    channel,
    pressure,
):
    ChannelID._ensure_registered(channel)

    with REGISTRY.lock:
        heatmap = REGISTRY.heatmap[channel]

        heatmap["events"] += 1

        heatmap["avg"] = round(
            heatmap["avg"] * 0.9
            + pressure * 0.1,
            3,
        )

        heatmap["peak"] = max(
            heatmap["peak"],
            pressure,
        )

        heatmap["last_ts"] = time.time()

    return heatmap


# ==========================================================
# Intent Outcome / Cross-Agent Learning
# ==========================================================


def apply_intent_outcome(
    intent_id,
    outcome: str,
):

    outcome = str(outcome).upper()

    chain = resolve_intent_chain(intent_id)

    if not chain:
        logger.debug(
            "[ChannelID] No intent chain for %s",
            intent_id,
        )
        return False

    # ------------------------------------------------------
    # Genome bookkeeping
    # ------------------------------------------------------

    genome = _genome_key(chain)

    with REGISTRY.lock:
        g = REGISTRY.intent_genomes[genome]

        g["samples"] += 1
        g["last_ts"] = time.time()

    # ------------------------------------------------------
    # Learning direction
    # ------------------------------------------------------

    success = outcome in (
        "SUCCESS",
        "OK",
        "INTENT_SUCCESS",
    )

    pressure_delta = (
        -PRESSURE_REWARD.get(
            "INTENT_SUCCESS",
            0.05,
        )
        if success
        else PRESSURE_PENALTY
    )

    genome_delta = (
        0.05
        if success
        else -PRESSURE_PENALTY
    )

    weight = 1.0

    # ------------------------------------------------------
    # Reverse chain learning
    # ------------------------------------------------------

    for intent in reversed(chain):
        channel = intent["channel"]
        agent = intent["agent_id"]

        ChannelID._ensure_registered(channel)

        with REGISTRY.lock:
            genome_state = REGISTRY.intent_genomes[genome]

            channel_weights = (
                REGISTRY.channel_weights[channel]
            )

            agent_weights = (
                REGISTRY.agent_weights[agent]
            )

            global_bias = (
                REGISTRY.global_channel_bias[channel]
            )

            if success:
                channel_weights["success"] += 1
                agent_weights["success"] += 1

                bias_delta = (
                    -LEARNING_RATE * weight
                )

            else:
                channel_weights["fail"] += 1
                agent_weights["fail"] += 1

                bias_delta = (
                    LEARNING_RATE * weight
                )

            channel_weights["bias"] = round(
                channel_weights["bias"]
                + bias_delta,
                4,
            )

            total = (
                agent_weights["success"]
                + agent_weights["fail"]
            )

            if total > 0:
                agent_weights["confidence"] = round(
                    (
                        agent_weights["success"]
                        + 1
                    )
                    / (
                        total
                        + 2
                    ),
                    4,
                )

            meta = REGISTRY.metadata[channel]

            meta["pressure"] = min(
                PRESSURE_MAX,
                max(
                    0.0,
                    meta["pressure"]
                    + pressure_delta * weight,
                ),
            )

            genome_state["agents"][agent] += 1
            genome_state["channels"][channel] += 1

            global_bias["contributors"].add(
                agent
            )

            global_bias["bias"] = round(
                global_bias["bias"]
                * AGENT_CONFIDENCE_DECAY
                + channel_weights["bias"]
                * agent_weights["confidence"]
                * (
                    1
                    - AGENT_CONFIDENCE_DECAY
                ),
                4,
            )

            update_heatmap(
                channel,
                meta["pressure"],
            )

        weight *= INTENT_CHAIN_DISCOUNT

    # ------------------------------------------------------
    # Genome score
    # ------------------------------------------------------

    with REGISTRY.lock:
        g["score"] += genome_delta
        g["score"] -= GENOME_DECAY
        g["score"] = round(
            g["score"],
            4,
        )

    _evaluate_genome(
        genome,
        g,
    )

    payload = {
        "intent_id": intent_id,
        "outcome": outcome,
        "genome": genome,
        "score": g["score"],
        "samples": g["samples"],
        "status": g["status"],
        "timestamp": time.time(),
    }

    _safe_emit(
        REGISTRY.event_bus,
        "INTENT_OUTCOME_APPLIED",
        payload,
    )

    _safe_oracle_observe(
        REGISTRY.oracle,
        "INTENT_OUTCOME_APPLIED",
        payload,
    )

    return True


# ==========================================================
# Learning Introspection
# ==========================================================


def get_channel_learning(
    channel,
):
    ChannelID._ensure_registered(channel)

    with REGISTRY.lock:
        weights = REGISTRY.channel_weights[channel]
        global_bias = (
            REGISTRY.global_channel_bias[channel]
        )
        metadata = REGISTRY.metadata[channel]

        return {
            "channel": channel,
            "local_bias": weights["bias"],
            "success": weights["success"],
            "fail": weights["fail"],
            "global_bias": global_bias["bias"],
            "contributors": len(
                global_bias["contributors"]
            ),
            "pressure": metadata["pressure"],
        }


def get_agent_learning(
    agent_id,
):
    with REGISTRY.lock:
        agent = REGISTRY.agent_weights[agent_id]

        return {
            "agent": agent_id,
            "success": agent["success"],
            "fail": agent["fail"],
            "confidence": agent["confidence"],
        }


def get_learning_snapshot(
    channel,
):
    ChannelID._ensure_registered(channel)

    with REGISTRY.lock:
        weights = REGISTRY.channel_weights[channel]
        metadata = REGISTRY.metadata[channel]

        total = (
            weights["success"]
            + weights["fail"]
        )

        confidence = (
            (
                weights["success"]
                + 1
            )
            / (
                total
                + 2
            )
        )

        return {
            "channel": channel,
            "pressure": metadata["pressure"],
            "bias": weights["bias"],
            "success": weights["success"],
            "fail": weights["fail"],
            "confidence": round(
                confidence,
                3,
            ),
        }


# ==========================================================
# Recovery
# ==========================================================


def build_recovery_plan(
    channel,
):
    ChannelID._ensure_registered(channel)

    with REGISTRY.lock:
        metadata = REGISTRY.metadata[channel]

        return {
            "channel": channel,
            "pressure": metadata["pressure"],
            "state": REGISTRY.states[channel],
            "tracks": list(
                REGISTRY.tracks[channel]
            ),
            "ts": time.time(),
        }


def execute_recovery(
    strategy,
    plan,
):
    channel = plan.get(
        "channel",
        "UNKNOWN",
    )

    logger.warning(
        "[RECOVERY] %s → %s",
        strategy,
        channel,
    )

    ChannelID.set_state(
        channel,
        "RECOVERING",
    )

    _safe_emit(
        REGISTRY.event_bus,
        "CHANNEL_RECOVERY_PROPOSED",
        {
            "strategy": strategy,
            "plan": dict(plan),
            "timestamp": time.time(),
        },
    )

    _safe_oracle_observe(
        REGISTRY.oracle,
        "CHANNEL_RECOVERY_PROPOSED",
        {
            "strategy": strategy,
            "plan": dict(plan),
        },
    )

    return {
        "strategy": strategy,
        "channel": channel,
        "status": "PROPOSED",
        "command_authority": "QBIT_DIALER",
    }


def score_recovery(
    channel,
    outcome,
):
    ChannelID._ensure_registered(channel)

    success = str(outcome).upper() == "OK"

    with REGISTRY.lock:
        REGISTRY.recovery_scores[channel][
            "success"
        ] += int(success)

        REGISTRY.recovery_scores[channel][
            "fail"
        ] += int(not success)

    return REGISTRY.recovery_scores[channel]


# ==========================================================
# Genome Evaluation
# ==========================================================


def _evaluate_genome(
    genome_key,
    g,
):
    if g["samples"] < MIN_GENOME_SAMPLES:
        return

    if (
        g["score"]
        <= GENOME_PRUNE_THRESHOLD
    ):
        g["status"] = "PRUNED"

        logger.warning(
            "[GENOME PRUNED] %s",
            genome_key,
        )

    elif (
        g["score"]
        <= GENOME_WARNING_THRESHOLD
    ):
        g["status"] = "WARNING"

    else:
        g["status"] = "ACTIVE"


# ==========================================================
# Genome Crossover
# ==========================================================


def eligible_genomes():
    with REGISTRY.lock:
        return {
            key: value
            for key, value in REGISTRY.intent_genomes.items()
            if value["status"] == "ACTIVE"
            and value["score"]
            >= CROSSOVER_MIN_SCORE
            and value["samples"]
            >= CROSSOVER_MIN_SAMPLES
        }


def _compatible(
    chain_a,
    chain_b,
):
    seen = {}

    for step in chain_a + chain_b:
        channel = step["channel"]
        action = step["action"]

        if (
            channel in seen
            and seen[channel] != action
        ):
            return False

        seen[channel] = action

    return True


def crossover_genomes(
    genome_a: str,
    genome_b: str,
) -> Optional[Dict[str, Any]]:
    with REGISTRY.lock:
        g1 = REGISTRY.intent_genomes.get(
            genome_a
        )

        g2 = REGISTRY.intent_genomes.get(
            genome_b
        )

    if not g1 or not g2:
        return None

    if (
        g1["status"] != "ACTIVE"
        or g2["status"] != "ACTIVE"
    ):
        return None

    chain_a = [
        item
        for item in genome_a.split(" > ")
        if item
    ]

    chain_b = [
        item
        for item in genome_b.split(" > ")
        if item
    ]

    if (
        len(chain_a)
        + len(chain_b)
        > CROSSOVER_MAX_LENGTH
    ):
        return None

    try:
        a_steps = [
            {
                "action": value.split("@", 1)[0],
                "channel": value.split("@", 1)[1],
            }
            for value in chain_a
        ]

        b_steps = [
            {
                "action": value.split("@", 1)[0],
                "channel": value.split("@", 1)[1],
            }
            for value in chain_b
        ]

    except (IndexError, ValueError):
        return None

    if not _compatible(
        a_steps,
        b_steps,
    ):
        return None

    merged = a_steps + b_steps

    key = " > ".join(
        f"{step['action']}@{step['channel']}"
        for step in merged
    )

    candidate = {
        "genome": key,
        "parents": (
            genome_a,
            genome_b,
        ),
        "created_ts": time.time(),
        "status": "CANDIDATE",
        "score": 0.0,
        "samples": 0,
    }

    with REGISTRY.lock:
        REGISTRY.intent_genomes[key][
            "status"
        ] = "CANDIDATE"

        REGISTRY.genome_crossovers.append(
            candidate
        )

    logger.info(
        "[GENOME CROSSOVER] %s × %s",
        genome_a,
        genome_b,
    )

    return candidate


# ==========================================================
# Genome Enforcement
# ==========================================================


def genome_allowed(
    intent_chain,
) -> bool:
    genome = _genome_key(
        intent_chain
    )

    with REGISTRY.lock:
        genome_state = (
            REGISTRY.intent_genomes.get(
                genome
            )
        )

    if not genome_state:
        return True

    return (
        genome_state["status"]
        != "PRUNED"
    )


# ==========================================================
# HUD / Debug Introspection
# ==========================================================


def list_crossovers(
    limit=20,
):
    limit = max(
        1,
        int(limit),
    )

    with REGISTRY.lock:
        return list(
            REGISTRY.genome_crossovers[
                -limit:
            ]
        )


def list_genomes(
    limit=20,
    status=None,
):
    limit = max(
        1,
        int(limit),
    )

    items = []

    with REGISTRY.lock:
        for key, genome in (
            REGISTRY.intent_genomes.items()
        ):
            if (
                status
                and genome["status"]
                != status
            ):
                continue

            items.append(
                {
                    "genome": key,
                    "score": genome["score"],
                    "samples": genome["samples"],
                    "status": genome["status"],
                    "agents": dict(
                        genome["agents"]
                    ),
                    "channels": dict(
                        genome["channels"]
                    ),
                }
            )

    # Highest-scoring genomes first.
    return sorted(
        items,
        key=lambda item: item["score"],
        reverse=True,
    )[:limit]


# ==========================================================
# Channel Snapshot
# ==========================================================


def get_channel_snapshot(
    channel=None,
):

    if channel:
        ChannelID._ensure_registered(
            channel
        )

    with REGISTRY.lock:
        if channel:
            channels = [channel]
        else:
            channels = list(
                REGISTRY.states.keys()
            )

        snapshot = {}

        for name in channels:
            snapshot[name] = {
                "channel": name,
                "sequence": REGISTRY.counters.get(
                    name,
                    0,
                ),
                "state": REGISTRY.states.get(
                    name,
                    "ACTIVE",
                ),
                "flow_enabled": REGISTRY.flow_enabled.get(
                    name,
                    True,
                ),
                "pressure": REGISTRY.metadata.get(
                    name,
                    {},
                ).get(
                    "pressure",
                    0.0,
                ),
                "tracks": list(
                    REGISTRY.tracks.get(
                        name,
                        [],
                    )
                ),
                "learning": get_channel_learning(
                    name
                ),
            }

    return snapshot


# ==========================================================
# System Telemetry
# ==========================================================


def system_snapshot():

    with REGISTRY.lock:
        return {
            "module": MODULE_ID,
            "channels": len(
                REGISTRY.states
            ),
            "intents": len(
                REGISTRY.intent_log
            ),
            "genomes": len(
                REGISTRY.intent_genomes
            ),
            "crossovers": len(
                REGISTRY.genome_crossovers
            ),
            "connections": {
                "event_bus": (
                    REGISTRY.event_bus
                    is not None
                ),
                "track_system": (
                    REGISTRY.track_system
                    is not None
                ),
                "qbit": (
                    REGISTRY.qbit
                    is not None
                ),
                "qbit_dialer": (
                    REGISTRY.qbit_dialer
                    is not None
                ),
                "hud": (
                    REGISTRY.hud
                    is not None
                ),
                "oracle": (
                    REGISTRY.oracle
                    is not None
                ),
            },
            "command_authority": (
                "QBIT_DIALER"
            ),
            "track_authority": (
                "TRACK_SYSTEM"
            ),
            "transport": "QBIT",
            "timestamp": time.time(),
        }


# ==========================================================
# Track ID Generator Helper
# ----------------------------------------------------------
# Fallback identity only.
#
# TrackSystem remains the authoritative owner of track
# context. This helper creates an identifier when a caller
# specifically needs one and no TrackSystem-generated ID has
# already been supplied.
# ==========================================================


def generate_track_id(
    channel="3",
):
    if not channel:
        channel = "UNKNOWN"

    return (
        f"{str(channel).upper()}-"
        f"{uuid.uuid4().hex}"
    )


# ==========================================================
# Safe Channel Registration Convenience
# ==========================================================


def ensure_channel(
    channel,
    *,
    controller=None,
    metadata=None,
):

    ChannelID._ensure_registered(
        channel
    )

    if (
        controller is not None
        or metadata is not None
    ):
        ChannelID.register(
            channel,
            controller=controller,
            metadata=metadata,
        )

    return channel


# ==========================================================
# Module Registration / Oracle Link
# ==========================================================


def register_with_system(
    *,
    registry=None,
    event_bus=None,
    track_system=None,
    qbit=None,
    qbit_dialer=None,
    hud=None,
    oracle=None,
):

    return connect_system(
        event_bus=event_bus,
        track_system=track_system,
        qbit=qbit,
        qbit_dialer=qbit_dialer,
        hud=hud,
        oracle=oracle,
        registry=registry,
    )


# ==========================================================
# END OF FILE
# ==========================================================

