# seed/core/channel_emit.py

from seed.core.channel_id import ChannelID
from seed.core.event_bus import SEEDEventBus

def emit(
    event_bus: SEEDEventBus,
    channel: str,
    payload: dict,
    *,
    track_id: str = None,
    metadata: dict = None,
):
    seq = ChannelID.next(
        channel,
        track_id=track_id,
        overlay=True,
        metadata=metadata,
    )

    if not seq:
        return False  # blocked by ChannelID

    event_bus.publish(
        channel,
        {
            "seq": seq["seq"],
            "payload": payload,
            "channel": channel,
            "tracks": seq["tracks"],
            "controller": seq["controller"],
            "state": seq["state"],
            "ts": seq["ts"],
        }
    )
    return True

ChannelOverlay = {
    "name": str,                 # channel name
    "seq": int,                  # last issued sequence
    "state": str,                # ACTIVE | PAUSED | MUTED | ERROR
    "flow": bool,                # True = emitting allowed
    "controller": str,           # SYSTEM | QBIT | AGENT | USER
    "tracks": list[str],         # active track IDs
    "last_ts": float,            # last emission timestamp
    "rate": float,               # events/sec (rolling)
    "errors": int,               # error count
    "flags": list[str],          # warnings / alerts
}

STATE_COLORS = {
    "ACTIVE":  "#00ff88",  # green
    "PAUSED":  "#ffaa00",  # amber
    "MUTED":   "#555555",  # gray
    "ERROR":   "#ff0033",  # red
}

FLOW_COLORS = {
    True:  "#00ccff",      # cyan (flowing)
    False: "#222222",      # dark (blocked)
}

RATE_THRESHOLDS = {
    "LOW":    0.1,
    "NORMAL": 1.0,
    "HIGH":   10.0,
    "FLOOD":  50.0,
}
if rate >= FLOOD:
    flags.append("FLOOD_RISK")
elif rate >= HIGH:
    flags.append("HIGH_PRESSURE")


