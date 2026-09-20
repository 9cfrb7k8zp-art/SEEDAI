"""
FILE: authorization.py
PATH: seed/core/authorization.py

SEED MODULE: Authorization / Permissions Engine
COMPONENT: Hierarchical Permission Validator & Engine

VERSION: 0.1.0
STATUS: Alpha
PLATFORM: Cross-platform (Windows / macOS / Linux)

RESPONSIBILITY:
- Validate requested actions against hierarchical permissions
- Use numeric weight overlay (3/6/9) for AI-local decision-making
- Map numeric weight to dot matrix colors: Red, Yellow, Blue
- Track device-specific permissions dynamically
- Return structured error codes on violations
- Log all validation attempts with full metadata

LABELS:
- SEED_AUTH_ENGINE
- HIERARCHICAL
- NUMERIC_OVERLAY
- DOT_MATRIX_MAPPING
- LOCAL_ONLY

LEGAL NOTE:
All permissions and logs are local.
No network dependency required.
"""

import os
import json
import datetime
from seed.core.permission_record import PermissionRecord

# Error code definitions
ERROR_CODES = {
    "AUTH001": "Scope Violation",
    "AUTH002": "Revoked",
    "AUTH003": "Expired",
    "AUTH004": "Invalid Device",
    "AUTH005": "Storage Error",
    "AUTH006": "Signature Invalid",
    "AUTH007": "Conflict",
    "AUTH008": "Unknown"
}

# Dot matrix mapping
CONSENT_COLOR_MAP = {
    "red": "High-Risk / Denied",
    "yellow": "Temporary / Conditional",
    "blue": "Safe / Standard"
}

NUMERIC_WEIGHT_MAP = {
    3: "Low-Level / Basic Permission",
    6: "Intermediate / Elevated",
    9: "High-Level / Critical"
}

class AuthorizationEngine:
    def __init__(self, storage_root: str, device_id: str):
        self.storage_root = storage_root
        self.permissions_dir = os.path.join(storage_root, "storage", "permissions")
        os.makedirs(self.permissions_dir, exist_ok=True)
        self.device_id = device_id
        self.permission_records = self._load_permissions()

    def _load_permissions(self) -> dict:
        records = {}
        try:
            for fname in os.listdir(self.permissions_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(self.permissions_dir, fname)
                    with open(fpath, "r") as f:
                        record = json.load(f)
                        records[record["permission_code"]] = record
        except Exception:
            pass
        return records

    def _is_expired(self, record: dict) -> bool:
        expiry = record.get("expiry")
        if not expiry:
            return False
        now = datetime.datetime.utcnow()
        try:
            expiry_dt = datetime.datetime.fromisoformat(expiry.replace("Z",""))
            return now > expiry_dt
        except Exception:
            return True

    def _validate_device(self, record: dict) -> bool:
        return self.device_id in record.get("devices", [])

    def _map_numeric_to_color(self, weight: int) -> str:
        if weight <= 3:
            return "blue"
        elif weight <= 6:
            return "yellow"
        else:
            return "red"

    def validate_action(self, permission_code: str, requested_scope: list, requested_weight: int):
        record = self.permission_records.get(permission_code)
        metadata = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "device": self.device_id,
            "requested_scope": requested_scope,
            "requested_weight": requested_weight
        }

        if not record:
            return False, "AUTH001", metadata

        if self._is_expired(record):
            return False, "AUTH003", metadata

        if not self._validate_device(record):
            return False, "AUTH004", metadata

        # Hierarchical scope check
        granted_scope = record.get("scope_hierarchy", [])
        if not all(scope in granted_scope for scope in requested_scope):
            return False, "AUTH001", metadata

        # Weight check
        weight_level = record.get("weight_level", 3)  # default to 3 if missing
        if requested_weight > weight_level:
            return False, "AUTH001", metadata

        # Add color mapping for visualization
        metadata["consent_color"] = self._map_numeric_to_color(weight_level)
        metadata["weight_level"] = weight_level
        metadata["dot_matrix_label"] = f"{record.get('consent_level')} - {weight_level}"

        # Log validation
        self._log_validation(permission_code, metadata)

        return True, None, metadata

    def _log_validation(self, permission_code: str, metadata: dict):
        log_dir = os.path.join(self.permissions_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{permission_code}_{datetime.datetime.utcnow().isoformat()}.json")
        with open(log_path, "w") as f:
            json.dump(metadata, f, indent=2)
