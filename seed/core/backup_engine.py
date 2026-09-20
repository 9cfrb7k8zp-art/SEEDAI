# ==========================================================
# FILE: backup_engine.py
# PATH: SEED_ROOT/core/backup_engine.py
# MODULE TRACK ID: B-1
# VERSION: 3.0
# DESCRIPTION: Full-featured Backup + Auto-Patch Engine
# - TrackID + EventBus + SparkPlug Integration
# - Async inbox loop
# - Multi-channel snapshot logging
# - Thread-safe state restoration
# ==========================================================

import os
import json
import shutil
import datetime
import re
import asyncio
import threading
import time
import logging
from pathlib import Path

from seed.core.event_bus import SEEDEventBus, SYSTEM_WARNING
from seed.skills.sparkplug import SparkPlug

from seed.core.memory_manager import SEEDMemoryManager

logger = logging.getLogger("SEEDBackupEngine")


# -----------------------------
# TrackContext stub
# -----------------------------
class TrackContext:
    _stack = []

    @classmethod
    def write(cls, track_id):
        cls._stack.append(track_id)


# -----------------------------
# TrackedData snapshot
# -----------------------------
class TrackedData:
    def __init__(self, payload=None, source_id=None, channel=None):
        self.payload = payload or {}
        self.source_id = source_id
        self.channel = channel


# ==========================================================
# SEEDBackupEngine
# ==========================================================
class SEEDBackupEngine:
    def __init__(self, storage_root, memory_manager=None, analytics_engine=None,
                 event_bus=None, sparkplug=None, max_snapshots=10):
        from seed.analytics.analytics_engine import SEEDAnalyticsEngine
        from seed.core.track_id_manager import TrackIDManager
        self.storage_root = storage_root
        self.memory = memory_manager
        self.analytics = analytics_engine
        self.event_bus = event_bus or SEEDEventBus()
        self.sparkplug = sparkplug
        self.max_snapshots = max_snapshots

        # Backup folders
        self.layers = {
            "local": Path(storage_root) / "backup_local",
            "daily": Path(storage_root) / "backup_daily",
        }
        for path in self.layers.values():
            path.mkdir(parents=True, exist_ok=True)

        # Inbox/outbox for auto-patching
        self.inbox = Path(storage_root) / "skills" / "inbox"
        self.outbox = Path(storage_root) / "skills" / "outbox"
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.outbox.mkdir(parents=True, exist_ok=True)

        # Rolling snapshots
        self.snapshots = []

        # Rolling log for processed patches
        self.processed_log = []

        # Async loop control
        self._loop_running = False

        # Thread lock for backup
        self._lock = threading.Lock()

        logger.info("[SEEDBackupEngine] Initialized")

	# ----------------------------
	# Save system snapshot
	# ----------------------------
	def save_state(self, tick=None, state_data=None, channel="CORE"):
		tick_id = tick or int(time.time())
		snapshot_file = self.layers["local"] / f"snapshot_{tick_id}.json"

		# --------------------------------------------------
		# TRACK CONTEXT
		# --------------------------------------------------
		#
		# TrackSystem owns TrackContext state.
		# BackupEngine only reads the current lineage.
		#
		try:
			track_context = TrackContext.snapshot()
		except Exception as exc:
			logger.debug(
				"[BACKUP] TrackContext snapshot unavailable: %s",
				exc,
			)
			track_context = {
				"track_id": TrackContext.current(),
				"parent_id": TrackContext.get_parent(),
				"stack": TrackContext.get_stack(),
			}

		snapshot = TrackedData(
			payload={
				"tick": tick_id,
				"timestamp": time.time(),
				"state_data": state_data or {
					"memory": {
						"short_term": getattr(
							self.memory,
							"short_term",
							[],
						),
						"long_term": getattr(
							self.memory,
							"long_term",
							[],
						),
					},
					"analytics": getattr(
						self.analytics,
						"metrics",
						{},
					),
					"audit": getattr(
						self.memory,
						"audit_log",
						[],
					),
				},

				# --------------------------------------------------
				# Canonical L4 TrackContext snapshot.
				# DO NOT access TrackContext._stack directly.
				# --------------------------------------------------
				"track_context": track_context,

				"channel": channel,
			},
			source_id="SEEDBackupEngine",
			channel=channel,
		)

		with self._lock:
			try:
				with snapshot_file.open(
					"w",
					encoding="utf-8",
				) as f:
					json.dump(
						snapshot.payload,
						f,
						indent=2,
						default=str,
					)

				self.snapshots.append(
					snapshot_file
				)

				# --------------------------------------------------
				# Track backup event only when a TrackID exists.
				#
				# TrackContext.write() requires:
				#     write(key, value)
				#
				# BackupEngine must NOT create a TrackID.
				# TrackSystem owns that authority.
				# --------------------------------------------------
				current_track_id = TrackContext.current()

				if current_track_id:
					TrackContext.write(
						"backup",
						{
							"tick": tick_id,
							"snapshot": str(
								snapshot_file
							),
							"channel": channel,
							"timestamp": time.time(),
						},
					)

					TrackContext.write_meta(
						"source",
						"SEEDBackupEngine",
					)

					TrackContext.write_meta(
						"channel",
						channel,
					)

				else:
					logger.debug(
						"[BACKUP] No active TrackID | "
						"snapshot=%s",
						snapshot_file.name,
					)

				# --------------------------------------------------
				# Limit snapshots
				# --------------------------------------------------
				if len(self.snapshots) > self.max_snapshots:
					old_snapshot = self.snapshots.pop(0)

					if old_snapshot.exists():
						old_snapshot.unlink()

				# --------------------------------------------------
				# EventBus notification
				# --------------------------------------------------
				if self.event_bus:
					self.event_bus.publish(
						"BACKUP_SAVED",
						payload=snapshot.payload,
					)

				logger.info(
					"[BACKUP] Snapshot saved | "
					"tick=%s | track=%s",
					tick_id,
					current_track_id,
				)

				return snapshot_file

			except Exception as e:
				logger.error(
					"[BACKUP] Failed to save snapshot %s: %s",
					tick_id,
					e,
				)

				if self.event_bus:
					self.event_bus.publish(
						SYSTEM_WARNING,
						payload={
							"source": "SEEDBackupEngine",
							"error": str(e),
							"tick": tick_id,
						},
					)

				return None

    # ----------------------------
    # Restore last snapshot
    # ----------------------------
    def restore_state(self):
        with self._lock:
            if not self.snapshots:
                logger.warning("[BACKUP] No snapshots to restore")
                return None
            last_snapshot_file = self.snapshots[-1]
            try:
                with last_snapshot_file.open("r", encoding="utf-8") as f:
                    snapshot = json.load(f)
                TrackContext._stack = snapshot.get("track_context", []).copy()
                if self.event_bus:
                    self.event_bus.publish("BACKUP_RESTORED", payload=snapshot)
                logger.info(f"[BACKUP] Restored snapshot | tick={snapshot['tick']}")
                return snapshot
            except Exception as e:
                logger.error(f"[BACKUP] Failed to restore snapshot {last_snapshot_file}: {e}")
                return None

    # ----------------------------
    # Backup Memory + Analytics
    # ----------------------------
    def backup(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            memory_data = {
                "short_term": getattr(self.memory, "short_term", []),
                "long_term": getattr(self.memory, "long_term", [])
            }
            self._write_backup("memory", memory_data, timestamp)

            analytics_data = getattr(self.analytics, "metrics", {})
            self._write_backup("analytics", analytics_data, timestamp)

            audit_log = getattr(self.memory, "audit_log", [])
            self._write_backup("audit", audit_log, timestamp)

            self.save_state(state_data={
                "memory": memory_data,
                "analytics": analytics_data,
                "audit": audit_log
            })

            logger.info(f"[BACKUP] Backup completed at {timestamp}")

        except Exception as e:
            if self.event_bus:
                self.event_bus.publish(SYSTEM_WARNING, payload={
                    "source": "BackupEngine",
                    "error": str(e)
                })

    def _write_backup(self, name, data, timestamp):
        filename = f"{name}_{timestamp}.json"
        for layer, path in self.layers.items():
            filepath = path / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    # ----------------------------
    # Restore backup by layer
    # ----------------------------
    def restore(self, layer="local", name=None):
        path = self.layers.get(layer)
        if not path:
            raise ValueError(f"Invalid backup layer: {layer}")

        files = sorted([f for f in os.listdir(path) if f.endswith(".json")], reverse=True)
        if not files:
            raise FileNotFoundError(f"No backups found in {layer}")

        target_file = name if name else files[0]
        filepath = os.path.join(path, target_file)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    # ----------------------------
    # Auto-patch workflow
    # ----------------------------
    def process_inbox(self):
        inbox_files = [f for f in os.listdir(self.inbox) if f.endswith(".json")]
        for file_name in inbox_files:
            file_path = self.inbox / file_name
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                error_msg = payload.get("error")
                module_name = payload.get("module")
                plan = payload.get("plan", "Auto-generated patch plan")

                if not error_msg or not module_name:
                    continue

                patch_code = self._generate_patch(module_name, error_msg, plan, payload)
                out_file = f"{module_name}_patch_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
                out_path = self.outbox / out_file
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(patch_code)

                track_id = self.sparkplug.submit_skill(
                    skill_name="auto_patch_skill",
                    payload={"module": module_name, "patch_file": out_file},
                    priority=0.8,
                    source="SEEDBackupEngine"
                )

                self.processed_log.append({
                    "module": module_name,
                    "original_error": error_msg,
                    "patch_file": out_file,
                    "track_id": track_id
                })

                logger.info(f"[AUTO-PATCH] Generated patch for {module_name}, queued track {track_id}")
                os.remove(file_path)

            except Exception as e:
                if self.event_bus:
                    self.event_bus.publish(SYSTEM_WARNING, payload={
                        "source": "BackupEngine",
                        "error": f"Failed processing {file_name}: {str(e)}"
                    })

    # ----------------------------
    # Patch generator
    # ----------------------------
    def _generate_patch(self, module_name, error_msg, plan, payload):
        fix_lines = []
        reasoning_comments = [f"# Plan: {plan}", f"# Original error: {error_msg}"]

        name_error_match = re.search(r"NameError: name '(\w+)' is not defined", error_msg)
        if name_error_match:
            missing_name = name_error_match.group(1)
            reasoning_comments.append(f"# Detected missing variable or import: {missing_name}")
            fix_lines.append(f"{missing_name} = None  # Auto-generated placeholder")

        attr_error_match = re.search(r"AttributeError: '(\w+)' object has no attribute '(\w+)'", error_msg)
        if attr_error_match:
            cls, attr = attr_error_match.groups()
            reasoning_comments.append(f"# Missing attribute '{attr}' in class {cls}")
            fix_lines.append(f"class {cls}:\n    {attr} = None  # Auto-inserted")

        mod_error_match = re.search(r"ModuleNotFoundError: No module named '(\w+)'", error_msg)
        if mod_error_match:
            missing_module = mod_error_match.group(1)
            reasoning_comments.append(f"# Missing module import: {missing_module}")
            fix_lines.insert(0, f"import {missing_module}  # Auto-imported")

        type_error_match = re.search(r"TypeError: (\w+)\(\) got an unexpected keyword argument '(\w+)'", error_msg)
        if type_error_match:
            func_name, arg_name = type_error_match.groups()
            reasoning_comments.append(f"# Unexpected keyword argument '{arg_name}' in {func_name}")
            fix_lines.append(f"def {func_name}(payload=None, **kwargs):\n    pass  # Signature fixed automatically")

        if not fix_lines:
            reasoning_comments.append("# Generic patch applied")
            fix_lines.append("def run(payload, **kwargs):\n    return {'status': 'auto-fixed', 'payload': payload}")

        patch_code = "\n".join(reasoning_comments) + "\n\n" + "\n".join(fix_lines)
        return patch_code

	# ----------------------------
	# Async inbox watcher
	# ----------------------------
	async def start_inbox_loop(self, interval=1.0):
		if self._loop_running:
			return

		self._loop_running = True

		logger.info(
			"[SEEDBackupEngine] Starting async inbox loop"
		)

		try:
			while self._loop_running:

				try:
					await asyncio.to_thread(
						self.process_inbox
					)

				except Exception as exc:

					logger.error(
						"[SEEDBackupEngine] "
						"Inbox loop error: %s",
						exc,
					)

					# EventBus is optional during startup/shutdown.
					try:
						if self.event_bus:
							self.event_bus.publish(
								SYSTEM_WARNING,
								payload={
									"source": "BackupEngine",
									"error": str(exc),
								},
							)
					except Exception as bus_exc:
						logger.debug(
							"[SEEDBackupEngine] "
							"Warning publish skipped: %s",
							bus_exc,
						)

				# Do not sleep again after shutdown.
				if not self._loop_running:
					break

				try:
					await asyncio.sleep(
						max(0.05, float(interval))
					)
				except asyncio.CancelledError:
					logger.info(
						"[SEEDBackupEngine] "
						"Inbox loop cancelled"
					)
					break

		finally:
			self._loop_running = False

			logger.info(
				"[SEEDBackupEngine] "
				"Inbox loop offline"
			)

	# ----------------------------
	# Stop async inbox watcher
	# ----------------------------
	def stop_inbox_loop(self):
		if not self._loop_running:
			return

		self._loop_running = False

		logger.info(
			"[SEEDBackupEngine] Stopping async inbox loop"
		)
