# ==========================================================
# FILE: analytics_dashboard.py
# PATH: SEED_ROOT/seed/core/analytics_dashboard.py
# MODULE: SEED Analytics Dashboard – Real-time Monitoring & Observability
# VERSION: 0.2 (Track ID Enhanced + Parent/Child + Event Bus Integration)
# ==========================================================

import threading
import datetime
import json
from collections import defaultdict
from seed.core.event_bus import SEEDEventBus, TrackedData, ChannelID
import uuid
import logging

logger = logging.getLogger("AnalyticsDashboard")
logging.basicConfig(level=logging.INFO)


def gen_track_id(prefix="AD", parent_id=None):
    """Generate a unique Track ID with optional parent linkage"""
    tid = f"{prefix}-{str(uuid.uuid4())[:8]}"
    return {"track_id": tid, "parent_id": parent_id}


class AnalyticsDashboard:
    """
    Observability dashboard for SEED:
      - Monitors device outcomes
      - Monitors FAT events
      - Tracks system state with Track IDs and parent relationships
      - Publishes dashboard events to EventBus
      - Supports hierarchical ID tracking for downstream systems
    """

    def __init__(self, event_bus=None):
        self.event_bus = event_bus or SEEDEventBus()
        self.lock = threading.Lock()

        self.device_stats = defaultdict(list)  # device_id -> list of (timestamp, success_rate)
        self.fat_stats = defaultdict(lambda: {"count": 0, "last_seen": None})
        self.track_log = {}  # track_id -> event metadata

    # -----------------------------
    # Device result ingestion
    # -----------------------------
    def ingest_device_result(self, device_id, success_rate, parent_id=None):
        ts = datetime.datetime.now()
        ids = gen_track_id("DEVICE", parent_id)
        track_id, parent_id = ids["track_id"], ids["parent_id"]

        with self.lock:
            self.device_stats[device_id].append((ts, success_rate))
            self.track_log[track_id] = {
                "type": "device_result",
                "device": device_id,
                "success_rate": success_rate,
                "timestamp": ts,
                "parent_id": parent_id
            }

        payload = {
            "track_id": track_id,
            "parent_id": parent_id,
            "device_id": device_id,
            "success_rate": success_rate,
            "timestamp": ts.isoformat()
        }
        self._publish_event("DASHBOARD_DEVICE_UPDATE", payload)

    # -----------------------------
    # FAT event ingestion
    # -----------------------------
    def ingest_fat_event(self, source, message=None, parent_id=None):
        ts = datetime.datetime.now()
        ids = gen_track_id("FAT", parent_id)
        track_id, parent_id = ids["track_id"], ids["parent_id"]

        with self.lock:
            self.fat_stats[source]["count"] += 1
            self.fat_stats[source]["last_seen"] = ts
            self.track_log[track_id] = {
                "type": "fat_event",
                "source": source,
                "message": message,
                "timestamp": ts,
                "parent_id": parent_id
            }

        payload = {
            "track_id": track_id,
            "parent_id": parent_id,
            "source": source,
            "message": message,
            "count": self.fat_stats[source]["count"],
            "last_seen": ts.isoformat()
        }
        self._publish_event("DASHBOARD_FAT_UPDATE", payload)

    # -----------------------------
    # Publish event to EventBus
    # -----------------------------
    def _publish_event(self, event_name, payload):
        if self.event_bus:
            try:
                td = TrackedData(
                    payload=payload,
                    source_id=ChannelID.next("AnalyticsDashboard")
                )
                self.event_bus.publish(event_name, td)
            except Exception as e:
                logger.warning(f"[AnalyticsDashboard] Failed to publish {event_name}: {e}")

    # -----------------------------
    # Snapshot for dashboard
    # -----------------------------
    def snapshot(self):
        """
        Returns a snapshot of current device and FAT stats,
        including full track_log for ID tracking
        """
        with self.lock:
            snapshot = {
                "devices": {k: list(v) for k, v in self.device_stats.items()},
                "fat": {k: dict(v) for k, v in self.fat_stats.items()},
                "track_log": dict(self.track_log)
            }
        return snapshot

    # -----------------------------
    # Export snapshot to JSON
    # -----------------------------
    def export_snapshot(self, path="./analytics_dashboard_snapshot.json"):
        snapshot = self.snapshot()
        try:
            with open(path, "w") as f:
                json.dump(snapshot, f, default=str, indent=2)
            logger.info(f"[AnalyticsDashboard] Snapshot exported to {path}")
        except Exception as e:
            logger.warning(f"[AnalyticsDashboard] Failed to export snapshot: {e}")


# -----------------------------
# Entry point for testing
# -----------------------------
if __name__ == "__main__":
    dashboard = AnalyticsDashboard()
    # Device events with parent tracking
    parent_id = gen_track_id("SESSION")["track_id"]
    dashboard.ingest_device_result("DeviceA", 0.92, parent_id=parent_id)
    dashboard.ingest_fat_event("core_module", "Test FAT message", parent_id=parent_id)
    print(json.dumps(dashboard.snapshot(), indent=2))
