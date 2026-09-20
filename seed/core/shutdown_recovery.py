# ==========================================================
# FILE: shutdown_recovery.py
# PATH: SEED_ROOT/seed/core/shutdown_recovery.py
# Handles orchestrated shutdown and emergency recovery with TrackID
# VERSION: 1.3 (TrackID + EventBus + HUD + BackupEngine integration)
# UPDATED: 2025-12-31
# ==========================================================

import time

from seed.core.track_id_manager import TrackIDManager
from copy import deepcopy


class RecoveryTimeline:
    def __init__(self, max_events=500):

        self.events = []  # list of dicts {track_id, timestamp, module, event, reason}
        self.max_events = max_events

    def record(self, module, event, reason=None, track_id=None):
        track_id = track_id or TrackIDManager.generate(channel_marker="RECOVERY")
        entry = {
            "track_id": track_id,
            "timestamp": time.time(),
            "module": module,
            "event": event,
            "reason": reason
        }
        self.events.append(entry)
        if len(self.events) > self.max_events:
            self.events.pop(0)
        print(f"[RECOVERY_TIMELINE] {module} → {event} | Reason: {reason} | TrackID={track_id}")
        return track_id

    def recent(self, count=5):
        return self.events[-count:]

class SEEDShutdownRecovery:

    def __init__(self, orchestrator, event_bus=None, backup_engine=None):
        from seed.core.backup_engine import SEEDBackupEngine
        from seed.core.event_bus import SEEDEventBus, SYSTEM_SHUTDOWN, SYSTEM_WARNING, TrackedData
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        self.backup_engine = SEEDBackupEngine()
        self.recovery_timeline = RecoveryTimeline()  # initialize timeline

    # ----------------------------
    # GRACEFUL SHUTDOWN
    # ----------------------------
    def shutdown(self):
        try:
            # Stop Adaptive Engine
            if hasattr(self.orchestrator, "adaptive_engine"):
                self.orchestrator.adaptive_engine.stop()
                track_id = self.recovery_timeline.record("adaptive_engine", "shutdown")
                self._publish_event("adaptive_engine", "shutdown", track_id)

            # Stop Agents
            if hasattr(self.orchestrator, "agent_manager"):
                for agent_id in self.orchestrator.agent_manager.list_agents().keys():
                    self.orchestrator.agent_manager.stop_agent(agent_id)
                    track_id = self.recovery_timeline.record(f"agent_{agent_id}", "shutdown")
                    self._publish_event(f"agent_{agent_id}", "shutdown", track_id)

            # Stop Watchdog
            if hasattr(self.orchestrator, "watchdog"):
                self.orchestrator.watchdog.stop()
                track_id = self.recovery_timeline.record("watchdog", "shutdown")
                self._publish_event("watchdog", "shutdown", track_id)

            # Stop Scheduler
            if hasattr(self.orchestrator, "scheduler"):
                self.orchestrator.scheduler.stop()
                track_id = self.recovery_timeline.record("scheduler", "shutdown")
                self._publish_event("scheduler", "shutdown", track_id)

            # Save backups
            if self.backup_engine:
                self.backup_engine.backup()
                track_id = self.recovery_timeline.record("backup_engine", "backup")
                self._publish_event("backup_engine", "backup", track_id)

            # Publish shutdown event
            shutdown_id = TrackIDManager.generate(channel_marker="SYSTEM")
            self.event_bus.publish(SYSTEM_SHUTDOWN, payload={
                "message": "System shutdown completed gracefully.",
                "track_id": shutdown_id
            })
            print("[SHUTDOWN] System shutdown completed.")

        except Exception as e:
            fail_id = TrackIDManager.generate(channel_marker="SYSTEM")
            self.event_bus.publish(SYSTEM_WARNING, payload={
                "source": "ShutdownRecovery",
                "error": str(e),
                "track_id": fail_id
            })
            self.recovery_timeline.record("shutdown", "failed", reason=str(e), track_id=fail_id)

    # ----------------------------
    # EMERGENCY RECOVERY
    # ----------------------------
    def emergency_recover(self):
        try:
            print("[WATCHDOG] Performing emergency recovery on initialization...")
            print("[RECOVERY] Emergency recovery initiated.")

            # Try to restore last backup
            last_backup = {}
            if self.backup_engine:
                try:
                    last_backup = self.backup_engine.restore(layer="local")
                    track_id = self.recovery_timeline.record("backup_engine", "restore")
                    self._publish_event("backup_engine", "restore", track_id)
                except FileNotFoundError:
                    print("[RECOVERY] No backups found, initializing empty state.")
                    track_id = self.recovery_timeline.record("backup_engine", "no_backup")
                    self._publish_event("backup_engine", "no_backup", track_id)
                    last_backup = {"short_term": [], "long_term": []}
                except Exception as e:
                    print(f"[RECOVERY] Restore failed: {e}")
                    track_id = self.recovery_timeline.record("backup_engine", "restore_failed", reason=str(e))
                    self._publish_event("backup_engine", "restore_failed", track_id)
                    last_backup = {"short_term": [], "long_term": []}

            # Restore memory
            if hasattr(self.orchestrator, "memory_manager"):
                self.orchestrator.memory_manager.short_term = last_backup.get("short_term", [])
                self.orchestrator.memory_manager.long_term = last_backup.get("long_term", [])
                track_id = self.recovery_timeline.record("memory_manager", "restore")
                self._publish_event("memory_manager", "restore", track_id)

            # Restart critical modules
            if hasattr(self.orchestrator, "adaptive_engine"):
                self.orchestrator.adaptive_engine.start()
                track_id = self.recovery_timeline.record("adaptive_engine", "restart")
                self._publish_event("adaptive_engine", "restart", track_id)

            if hasattr(self.orchestrator, "watchdog"):
                self.orchestrator.watchdog.start()
                track_id = self.recovery_timeline.record("watchdog", "restart")
                self._publish_event("watchdog", "restart", track_id)

            # HUD integration (if available)
            if hasattr(self.orchestrator, "hud_overlay"):
                for entry in self.recovery_timeline.recent():
                    self.orchestrator.hud_overlay.handle_watchdog_event({
                        "module": entry["module"],
                        "action": "recover" if entry["event"] in ["restart", "restore"] else "fail",
                        "reason": entry.get("reason"),
                        "track_id": entry.get("track_id")
                    })

            # Publish recovery event
            recovery_id = TrackIDManager.generate(channel_marker="SYSTEM")
            self.event_bus.publish("SYSTEM_RECOVERY", payload={
                "message": "Emergency recovery completed.",
                "track_id": recovery_id
            })
            print("[RECOVERY] Emergency recovery completed.")

        except Exception as e:
            fail_id = TrackIDManager.generate(channel_marker="SYSTEM")
            self.event_bus.publish(SYSTEM_WARNING, payload={
                "source": "EmergencyRecovery",
                "error": str(e),
                "track_id": fail_id
            })
            self.recovery_timeline.record("emergency_recover", "failed", reason=str(e), track_id=fail_id)
            print(f"[RECOVERY] Failed: {e}")

    # ----------------------------
    # EventBus helper
    # ----------------------------
    def _publish_event(self, module, event, track_id):
        if not self.event_bus:
            return
        try:
            payload = {
                "track_id": track_id,
                "module": module,
                "event": event,
                "timestamp": time.time()
            }
            td = TrackedData(payload=payload, source_id="ShutdownRecovery")
            self.event_bus.publish("RECOVERY_EVENT", payload=td)
        except Exception as e:
            print(f"[RECOVERY] Event publish failed: {e}")

# ==========================================================
# END OF FILE: shutdown_recovery.py
# v1.3 – TrackID + EventBus + HUD + BackupEngine
# Timestamp: 2025-12-31
# ==========================================================
