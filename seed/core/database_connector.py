# ==========================================================
# FILE: database_connector.py
# PATH: SEED_ROOT/seed/core/database_connector.py
# VERSION: 1.1.0
# BUILD: SUPABASE / SERVICE-SIDE / DYNAMIC-RECORDS
#
# PURPOSE:
#   Connectivity layer between SEED runtime and the existing
#   Supabase seed schema. Storage only; never command authority.
#
# AUTHORITY:
#   EventBus = event authority
#   TrackSystem = track/context authority
#   ModuleRegistry / Nodes = discovery authority
#   QbitDialer = command authority
#   Database = persistent connectivity/record layer
#
# DYNAMIC MODEL:
#   runtime_records accepts new record_type values without
#   requiring a new table.
#
# SECURITY:
#   Credentials are environment variables only.
# ==========================================================

from __future__ import annotations

import json
import logging
import os
import platform
import socket
import time
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError
from seed.core.network_data_plane import NetworkDataPlane

logger = logging.getLogger("SEED.Database")
class SEEDDatabaseConnector:
    VERSION = "1.2.0"
    SCHEMA = "seed"

    def __init__(self, url=None, api_key=None, timeout=5.0):
        self.url = (url or os.getenv("SUPABASE_URL") or self._windows_registry_url() or self._config_url() or "").rstrip("/")
        self.api_key = api_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.timeout = float(timeout)
        self.enabled = bool(self.url and self.api_key)
        self.last_error = None
        self.outbox = NetworkDataPlane(os.getenv("SEED_ROOT", "C:/SEED_ROOT"))
        self._network_session_id = None
        self._network_session_epoch = None
        self._network_last_heartbeat = 0.0
        self._network_heartbeat_interval = 15.0


    @staticmethod
    def _windows_registry_url():
        if os.name != "nt":
            return ""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\SEED AI OS") as key:
                value, _ = winreg.QueryValueEx(key, "SupabaseUrl")
                return str(value or "")
        except Exception:
            return ""

    @staticmethod
    def _config_url():
        try:
            root = Path(os.getenv("SEED_ROOT", "C:/SEED_ROOT"))
            path = root / "config" / "seed_connection.json"
            if not path.exists():
                return ""
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return str(data.get("url") or "")
        except Exception:
            return ""

    def status(self):
        return {
            "enabled": self.enabled,
            "configured": bool(self.url and self.api_key),
            "provider": "supabase",
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "last_error": self.last_error,
        }

    def _headers(self):
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept-Profile": self.SCHEMA,
            "Content-Profile": self.SCHEMA,
            "Prefer": "return=representation",
        }

    def _request(self, table, method="POST", payload=None, params=None, queue_on_fail=True):
        if not self.enabled:
            return None
        query = f"?{params}" if params else ""
        url = f"{self.url}/rest/v1/{table}{query}"
        body = None if payload is None else json.dumps(payload, default=str).encode("utf-8")
        req = request.Request(url, data=body, headers=self._headers(), method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else True
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            self.last_error = str(exc)
            logger.warning(
                "[Database] request failed | table=%s | %s",
                table,
                exc,
            )
            if queue_on_fail and method == "POST" and payload is not None:
                self.outbox.enqueue(table, payload)
            return None

    def upsert(self, table, row, conflict=None):
        if not self.enabled:
            return None
        headers = self._headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        url = f"{self.url}/rest/v1/{table}"
        if conflict:
            url = f"{url}?on_conflict={conflict}"
        req = request.Request(
            url,
            data=json.dumps(row, default=str).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else True
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            self.last_error = str(exc)
            logger.warning("[Database] upsert failed | table=%s | %s", table, exc)
            return None

    def network_node_identity(self):
        root = Path(os.getenv("SEED_ROOT", "C:/SEED_ROOT"))
        seed_id = os.getenv("SEED_ID")
        identity_path = root / "seed_identity.json"
        if not seed_id and identity_path.exists():
            try:
                identity = json.loads(identity_path.read_text(encoding="utf-8-sig"))
                seed_id = identity.get("seed_id")
            except Exception:
                seed_id = None
        seed_id = str(seed_id or socket.gethostname()).strip()
        node_id = os.getenv("SEED_NODE_ID") or f"SEED-{seed_id}".upper()
        return {
            "node_id": node_id,
            "seed_id": seed_id,
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "os_version": platform.version(),
            "node_version": os.getenv("SEED_VERSION", "6.0.0"),
        }

    def start_network_session(self, *, metadata=None):
        if not self.enabled:
            return None
        identity = self.network_node_identity()
        self._network_session_epoch = int(time.time() * 1000)
        row = {
            "node_id": identity["node_id"],
            "session_epoch": self._network_session_epoch,
            "status": "OPEN",
            "endpoint_metadata": metadata or {},
            "runtime_metadata": {
                "provider": "SEED_RUNTIME",
                "connector_version": self.VERSION,
            },
        }
        result = self.upsert(
            "network_node_sessions",
            row,
            conflict="node_id,session_epoch",
        )
        if isinstance(result, list) and result:
            self._network_session_id = result[0].get("session_id")
        elif isinstance(result, dict):
            self._network_session_id = result.get("session_id")
        if self._network_session_id:
            self.sync_network_node(status="ONLINE", metadata=metadata)
            self.network_heartbeat(status="ONLINE", force=True)
        return self._network_session_id

    def sync_network_node(self, *, status=None, metadata=None):
        if not self.enabled:
            return None
        identity = self.network_node_identity()
        payload = {
            "node_id": identity["node_id"],
            "seed_id": identity["seed_id"],
            "hostname": identity["hostname"],
            "platform": identity["platform"],
            "os_version": identity["os_version"],
            "status": str(status or "REGISTERED").upper(),
            "node_role": "SEED_NODE",
            "node_version": identity["node_version"],
            "capabilities": {
                "network_node": True,
                "persistent_identity": True,
                "qbit_transport": True,
                "dialer_network_plane": True,
                "platform": identity["platform"],
            },
            "network_metadata": metadata or {},
        }
        return self.upsert("local_node_registry", payload, conflict="node_id")

    def network_heartbeat(
        self,
        *,
        status="ONLINE",
        dialer_state=None,
        queue_state=None,
        qbit_state=None,
        telemetry=None,
        force=False,
    ):
        if not self.enabled:
            return None
        now = time.monotonic()
        if not force and now - self._network_last_heartbeat < self._network_heartbeat_interval:
            return None
        if not self._network_session_id and str(status).upper() == "ONLINE":
            self.start_network_session()
        identity = self.network_node_identity()
        row = {
            "node_id": identity["node_id"],
            "session_id": self._network_session_id,
            "status": str(status).upper(),
            "system_version": identity["node_version"],
            "dialer_state": dialer_state,
            "queue_state": queue_state,
            "qbit_state": qbit_state,
            "telemetry": telemetry or {},
            "metadata": {"hostname": identity["hostname"]},
        }
        result = self._request("network_node_heartbeats", payload=row)
        if result is not None:
            self._network_last_heartbeat = now
        return result

    def stop_network_session(self):
        if not self.enabled:
            return None
        self.network_heartbeat(status="OFFLINE", force=True)
        if self._network_session_id:
            result = self._request(
                "network_node_sessions",
                method="PATCH",
                payload={
                    "status": "CLOSED",
                    "disconnected_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                },
                params=f"session_id=eq.{self._network_session_id}",
                queue_on_fail=False,
            )
        else:
            result = None
        self._network_session_id = None
        return result

    def add_record(self, record_type, data, *, track_id=None, qbit_id=None, owner_identity=None):
        row = {
            "record_type": str(record_type),
            "track_id": track_id,
            "identity_key": (
                f"{owner_identity}:{qbit_id}"
                if owner_identity and qbit_id
                else owner_identity or qbit_id
            ),
            "source": "SEED_RUNTIME",
            "payload": {
                "qbit_id": qbit_id,
                "owner_identity": owner_identity,
                "data": data if isinstance(data, dict) else {"value": data},
            },
        }
        return self._request("runtime_records", payload=row)

    def read_records(self, *, record_type=None, track_id=None, limit=50):
        params = ["select=*&order=created_at.desc", f"limit={int(limit)}"]
        if record_type:
            params.append(f"record_type=eq.{record_type}")
        if track_id:
            params.append(f"track_id=eq.{track_id}")
        return self._request("runtime_records", method="GET", params="&".join(params)) or []

    def analyze_records(self, records=None, *, record_type=None, limit=200):
        rows = records if records is not None else self.read_records(record_type=record_type, limit=limit)
        if not isinstance(rows, list):
            rows = []
        counts = {}
        for row in rows:
            key = str(row.get("record_type", "UNKNOWN")) if isinstance(row, dict) else "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        return {"count": len(rows), "by_type": counts, "latest": rows[0] if rows else None}

    def feed_dialer(self, dialer, records=None, *, record_type=None, limit=20, encoder=None):
        from seed.core.qbit.qbit import Qbit
        from seed.core.qbit.qbit_encoder import QbitEncoder
        rows = records if records is not None else self.read_records(record_type=record_type, limit=limit)
        receive = getattr(dialer, "receive_qbit", None)
        if not callable(receive):
            return {"fed": 0, "reason": "dialer_receive_qbit_unavailable", "records": rows}
        encoder = encoder or QbitEncoder(qbit_dialer=dialer)
        fed = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = row.get("payload") or {}
            qbit = Qbit(payload={"intent": "DATABASE_OBSERVATION", "action": "OBSERVE", "data": payload, "meta": {"record_id": row.get("record_id"), "record_type": row.get("record_type"), "track_id": row.get("track_id"), "source": row.get("source", "SUPABASE")}})
            encoded = encoder.encode(qbit)
            self.record_qbit({"qbit_id": qbit.qbit_id, "track_id": row.get("track_id"), "state": "DATABASE_FEED", "source": "SUPABASE", "payload": {"encoded_hex": encoded.hex(), "record_id": row.get("record_id")}, "metadata": {"record_type": row.get("record_type")}})
            receive(qbit)
            fed += 1
        return {"fed": fed, "records": len(rows), "mode": "qbit_encoded_observation"}

    def sync_module(self, module):
        if isinstance(module, dict):
            row = dict(module)
        else:
            row = {"name": getattr(module, "name", type(module).__name__)}
            for key in ("status", "capabilities", "dependencies", "metadata", "track_id"):
                value = getattr(module, key, None)
                if value is not None:
                    row[key] = value
        return self._request("runtime_modules", payload=row)

    def sync_node(self, node):
        if isinstance(node, dict):
            row = dict(node)
        else:
            row = {"node_id": getattr(node, "node_id", getattr(node, "name", type(node).__name__))}
            for key in ("status", "module_name", "capabilities", "metadata"):
                value = getattr(node, key, None)
                if value is not None:
                    row[key] = value
        return self._request("runtime_nodes", payload=row)

    def record_event(self, event_name, payload=None, *, track_id=None, source=None):
        return self._request(
            "runtime_events",
            payload={
                "event_type": str(event_name),
                "track_id": track_id,
                "source": source,
                "payload": payload or {},
            },
        )

    def record_qbit(self, qbit):
        if isinstance(qbit, dict):
            row = dict(qbit)
        else:
            row = {"qbit_id": getattr(qbit, "qbit_id", None), "track_id": getattr(qbit, "track_id", None), "source": "SEED_RUNTIME"}
            for key in ("state", "metadata", "payload"):
                value = getattr(qbit, key, None)
                if value is not None:
                    row[key] = value
        return self._request("runtime_qbits", payload=row)

    def record_result(self, result):
        row = dict(result) if isinstance(result, dict) else {"result": result}
        return self._request("runtime_results", payload=row)


    def flush_outbox(self, limit=25):
        if not self.enabled:
            return self.outbox.status()
        result = self.outbox.drain(
            lambda table, payload: self._request(table, method="POST", payload=payload, queue_on_fail=False)
            if self.enabled else None,
            limit=limit,
        )
        return result

# One passive connector instance may be attached to the authoritative runtime.
database_connector = SEEDDatabaseConnector()
