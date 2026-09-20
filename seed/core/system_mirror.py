# ==========================================================
# FILE: system_mirror.py
# PATH: SEED_ROOT/seed/core/system_mirror.py
# SYSTEM: SEED AI OS
# COMPONENT: Database System Mirror
# VERSION: 1.0.0
# PURPOSE: Publish a non-blocking architecture/runtime mirror
#          to Supabase without making the database a boot dependency.
# AUTHORITY: Observer / telemetry only.
# ==========================================================
from __future__ import annotations

import hashlib
import json
import os
import platform
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


class SEEDSystemMirror:
    VERSION = "1.0.0"

    def __init__(self, project_url: Optional[str] = None):
        self.project_url = project_url or os.environ.get("SUPABASE_URL")
        self.service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        self.enabled = bool(self.project_url and self.service_key)
        self.last_status: Dict[str, Any] = {"status": "disabled" if not self.enabled else "ready"}

    def _client(self):
        if not self.enabled:
            return None
        try:
            from supabase import create_client
            return create_client(self.project_url, self.service_key)
        except Exception as exc:
            self.last_status = {"status": "client_error", "error": str(exc)}
            return None

    @staticmethod
    def architecture() -> Dict[str, Any]:
        return {
            "spine": [
                "Identity", "Track", "Registry ↔ Nodes", "Qbit",
                "Cognition", "Security", "QbitDialer", "QueueLoop",
                "Result", "Memory / Telemetry", "HUD",
            ],
            "core": "SeedCore",
            "controller": "QbitDialer",
            "input": ["init_event", "oracle", "qbit"],
            "adaptive": "AdaptiveEngine",
            "authority_rules": {
                "qbit": "lineage_data_not_command",
                "action_engine": "proposal_only",
                "qbit_dialer": "sole_command_admission",
                "devhud": "observer_input_bridge",
                "database": "mirror_telemetry_not_boot_dependency",
            },
        }

    @staticmethod
    def sha256_file(path: Path) -> Optional[str]:
        try:
            h = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    def publish(self, *, runtime: Dict[str, Any], model: Dict[str, Any],
                components: Iterable[Dict[str, Any]], health_state: str = "unknown") -> Dict[str, Any]:
        client = self._client()
        if client is None:
            return dict(self.last_status)

        try:
            mirror_key = "SEED_PRIMARY"
            row = {
                "mirror_key": mirror_key,
                "system_name": "SEED AI",
                "schema_version": self.VERSION,
                "runtime_id": runtime.get("runtime_id"),
                "device_id": runtime.get("device_id") or platform.node(),
                "boot_session_id": runtime.get("boot_session_id"),
                "git_remote": runtime.get("git_remote"),
                "git_branch": runtime.get("git_branch"),
                "git_commit": runtime.get("git_commit"),
                "architecture": self.architecture(),
                "runtime_snapshot": runtime,
                "model_snapshot": model,
                "tool_snapshot": {"desktop_commander": "optional_adapter"},
                "update_policy": {
                    "mode": "staged",
                    "health_gate_required": True,
                    "rollback_checkpoint_required": True,
                    "kill_switch": False,
                },
                "recovery_policy": {
                    "actions": ["checkpoint", "restore", "defer", "restart", "resume"],
                    "kill_switch": False,
                },
                "health_state": health_state,
            }
            result = (
                client.table("seed_system_mirror")
                .upsert(row, on_conflict="mirror_key")
                .execute()
            )
            mirror_id = (result.data[0].get("mirror_id") if result.data else None)
            if mirror_id:
                for item in components:
                    item = dict(item)
                    item["mirror_id"] = mirror_id
                    client.table("seed_system_components").upsert(
                        item,
                        on_conflict="mirror_id,component_key",
                    ).execute()
            self.last_status = {"status": "published", "mirror_id": mirror_id}
            return dict(self.last_status)
        except Exception as exc:
            self.last_status = {
                "status": "publish_error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            return dict(self.last_status)

    def publish_async(self, **kwargs):
        threading.Thread(
            target=self.publish,
            kwargs=kwargs,
            name="SEEDSystemMirror",
            daemon=True,
        ).start()
