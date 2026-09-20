# ==========================================================
# FILE: recovery_timeline.py
# PATH: SEED_ROOT/seed/core/recovery_timeline.py
# VERSION: 2.1
# DESCRIPTION: Failure / Restart / Degradation / Recovery Timeline
# - TrackID-aware
# - Multi-channel logging (CORE, SYSTEM, USER, Qbit)
# - EventBus-safe (no circular imports)
# ==========================================================

import time
import logging

from seed.core.track_id_manager import TrackIDManager

# --- SAFE IMPORTS (no heartbeat dependency) ---
try:
    from seed.core.tracked_data import TrackedData
except Exception:
    class TrackedData:
        def __init__(self, payload=None, source_id=None, channel=None):
            self.payload = payload
            self.source_id = source_id
            self.channel = channel

try:
    from seed.core.track_context import TrackContext
except Exception:
    class TrackContext:
        @staticmethod
        def write(track_id):
            return

logger = logging.getLogger("RecoveryTimeline")

CHANNEL_CORE = "CORE"
CHANNEL_SYSTEM = "SYSTEM"
CHANNEL_USER = "USER"
CHANNEL_QBIT = "QBIT"


class RecoveryTimeline:

    def __init__(
        self,
        event_bus=None,
        max_events=500,
        enable_qbit=True,
        qbit_dialer=None,
    ):
        self.events = []
        self.max_events = max_events
        self.event_bus = event_bus
        self.enable_qbit = enable_qbit
        self.qbit_dialer = qbit_dialer

        logger.info("[RecoveryTimeline v2.1] Initialized")

    # -----------------------------
    # Record an event
    # -----------------------------
    def record(self, module, action, reason=None, channel=CHANNEL_SYSTEM):
        timestamp = time.time()
        track_id = TrackIDManager.generate(
            channel_marker=f"RECOVERY_{module}"
        )

        event = {
            "timestamp": timestamp,
            "module": module,
            "action": action,
            "reason": reason,
            "channel": channel,
            "track_id": track_id,
        }

        self.events.append(event)
        TrackContext.write(track_id)

        if len(self.events) > self.max_events:
            self.events.pop(0)

        # ---- EventBus publish (guarded) ----
        if self.event_bus:
            try:
                payload = TrackedData(
                    payload=event,
                    source_id="RecoveryTimeline",
                    channel=channel,
                )

                publish = getattr(self.event_bus, "publish", None)
                if callable(publish):
                    publish("RECOVERY_EVENT", payload=payload)
            except Exception as e:
                logger.warning(
                    f"[RecoveryTimeline] EventBus publish failed: {e}"
                )

        # ---- Optional Qbit emit ----
        if self.enable_qbit and self.qbit_dialer:
            try:
                qbit_value = int(timestamp * 1000) & 0xFFFFFFFF
                qbit_payload = f"${qbit_value}"

                push = getattr(self.qbit_dialer, "push_data", None)
                if callable(push):
                    push(qbit_payload, track_id=track_id)
            except Exception as e:
                logger.warning(
                    f"[RecoveryTimeline] Qbit push failed: {e}"
                )

        logger.info(
            f"[RecoveryTimeline] Recorded | module={module} "
            f"action={action} track_id={track_id}"
        )

    # -----------------------------
    # Queries
    # -----------------------------
    def recent(self, seconds=60, channel=None):
        now = time.time()
        return [
            e for e in self.events
            if now - e["timestamp"] <= seconds
            and (channel is None or e["channel"] == channel)
        ]

    def for_module(self, module):
        return [e for e in self.events if e["module"] == module]

    # -----------------------------
    # Clear timeline
    # -----------------------------
    def clear(self):
        self.events.clear()
        logger.info("[RecoveryTimeline] Cleared all events")
