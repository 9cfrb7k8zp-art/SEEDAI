# =============================================================================
# FILE: authorization_helpers.py
# PATH: seed/core/authorization_helpers.py
#
# SEED MODULE: Authorization / Permissions Engine
# COMPONENT: Permission Management Helpers
#
# VERSION: 0.1.3
# STATUS: Stable / System-ready
# =============================================================================

import os
import json
import logging
from uuid import uuid4
from datetime import datetime
from typing import List, Optional

from seed.core.permission_record import PermissionRecord

logger = logging.getLogger("PermissionManager")
logger.setLevel(logging.INFO)

# ==========================================================
# Helpers
# ==========================================================
def gen_track_id(prefix="AH"):
    return f"{prefix}-{uuid4().hex[:8]}"

# ==========================================================
# Permission Manager
# ==========================================================
class PermissionManager:
    def __init__(self, storage_root: str):
        self.permissions_dir = os.path.join(storage_root, "storage", "permissions")
        os.makedirs(self.permissions_dir, exist_ok=True)
        logger.info("[PermissionManager] Initialized | dir=%s", self.permissions_dir)

    # ------------------------------------------------------
    # Create Permission
    # ------------------------------------------------------
    def create_permission(
        self,
        private_key_bytes: bytes,
        permission_code: str,
        scope_hierarchy: List[str],
        devices: List[str],
        consent_level: str = "blue",
        weight_level: int = 3,
        expiry_iso: Optional[str] = None,
        parent_code: Optional[str] = None,
        overwrite: bool = True,  # <-- default now forces overwrite if exists
    ):
        track_id = gen_track_id()

        if not permission_code:
            raise ValueError("permission_code is required")

        file_path = os.path.join(self.permissions_dir, f"{permission_code}.json")
        if os.path.exists(file_path) and not overwrite:
            raise FileExistsError(
                f"Permission '{permission_code}' already exists (overwrite=False)"
            )

        record_obj = PermissionRecord(
            private_key_bytes=private_key_bytes,
            permission_code=permission_code,
            scope_hierarchy=scope_hierarchy,
            devices=devices,
            consent_level=consent_level,
            weight_level=str(weight_level),
            expiry_iso=expiry_iso,
            parent_code=parent_code,
        )

        record = record_obj.export_record()

        # Engine overlays / metadata
        record.update({
            "weight_level": weight_level,
            "dot_matrix_label": f"{consent_level}-{weight_level}",
            "track_id": track_id,
            "created_iso": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        })

        # Atomic write
        tmp_path = f"{file_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        os.replace(tmp_path, file_path)

        logger.info(
            "[PermissionManager] Permission created | code=%s parent=%s track=%s",
            permission_code,
            parent_code,
            track_id,
        )

        return {
            "status": "created",
            "permission_code": permission_code,
            "path": file_path,
            "track_id": track_id,
        }

    # ------------------------------------------------------
    # Revoke Permission
    # ------------------------------------------------------
    def revoke_permission(self, permission_code: str):
        file_path = os.path.join(self.permissions_dir, f"{permission_code}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("[PermissionManager] Permission revoked: %s", permission_code)
            return {"status": "revoked", "permission_code": permission_code}

        logger.warning("[PermissionManager] Permission not found: %s", permission_code)
        return {"status": "not_found", "permission_code": permission_code}

    # ------------------------------------------------------
    # Check if Permission Exists
    # ------------------------------------------------------
    def permission_exists(self, permission_code: str) -> bool:
        file_path = os.path.join(self.permissions_dir, f"{permission_code}.json")
        return os.path.exists(file_path)
