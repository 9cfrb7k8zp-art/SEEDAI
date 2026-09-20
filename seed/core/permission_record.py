# ==========================================================
# FILE: permission_record.py
# PATH: seed/core/permission_record.py
# PURPOSE: SEED Permission Record — system-ready defaults
# ==========================================================

import json
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
import asyncio

try:
    import cbor2
    CBOR_AVAILABLE = True
except ImportError:
    CBOR_AVAILABLE = False

logger = logging.getLogger("PermissionRecord")
logger.setLevel(logging.INFO)

# Safe load key: accepts bytes, str (path), or generates 32-byte temporary key
def load_seed_private_key(path_or_bytes: Optional[bytes | str]) -> bytes:
    if path_or_bytes is None:
        # Generate random 32-byte key
        return Ed25519PrivateKey.generate().private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            key_data = f.read()
    elif isinstance(path_or_bytes, (bytes, bytearray)):
        key_data = path_or_bytes
    else:
        # Fallback: generate 32-byte key
        return Ed25519PrivateKey.generate().private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

    if len(key_data) == 32:
        return key_data

    key = serialization.load_pem_private_key(key_data, password=None)
    return key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )

# PermissionRecord
@dataclass
class PermissionRecord:
    permission_code: str
    scope_hierarchy: List[str]
    devices: List[str]
    consent_level: str
    weight_level: str
    expiry_iso: Optional[str]
    parent_code: Optional[str]
    created_iso: str
    suggested: bool
    record: Dict[str, Any]
    signature: str

    def __init__(
        self,
        private_key_bytes: Optional[bytes | str] = None,
        permission_code: str = "ROOT",
        scope_hierarchy: Optional[List[str]] = None,
        devices: Optional[List[str]] = None,
        consent_level: str = "ROOT",
        weight_level: str = "100",
        expiry_iso: Optional[str] = None,
        parent_code: Optional[str] = None,
        parent_permission: Optional["PermissionRecord"] = None,
        allow_suggestion: bool = True,
        event_bus=None
    ):
        self.event_bus = event_bus
        self.records = {}

        self.permission_code = permission_code
        self.scope_hierarchy = scope_hierarchy or ["SYSTEM", "CORE", "AI_OS"]
        self.devices = devices or ["LOCAL", "NETWORK", "HARDWARE"]
        self.consent_level = consent_level
        self.weight_level = weight_level
        self.expiry_iso = expiry_iso
        self.parent_code = parent_code or (parent_permission.permission_code if parent_permission else None)
        self.created_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.suggested = allow_suggestion

        if parent_permission and not self._validate_hierarchy(parent_permission):
            if allow_suggestion:
                logger.warning("[PermissionRecord] Suggested child '%s' under '%s'",
                               permission_code, parent_permission.permission_code)
            else:
                raise ValueError(f"Permission '{permission_code}' violates hierarchy of parent '{parent_permission.permission_code}'")

        self._private_key = Ed25519PrivateKey.from_private_bytes(load_seed_private_key(private_key_bytes))
        self.record = self._generate_record()
        self.signature = self._sign_record()
        self._ai_ready = True

    def _generate_record(self) -> Dict[str, Any]:
        return {
            "label": "SEED_PERMISSION_RECORD",
            "version": "0.7.0",
            "permission_code": self.permission_code,
            "scope_hierarchy": self.scope_hierarchy,
            "parent_code": self.parent_code,
            "devices": self.devices,
            "consent_level": self.consent_level,
            "weight_level": self.weight_level,
            "created_iso": self.created_iso,
            "expiry_iso": self.expiry_iso,
            "suggested": self.suggested,
            "ai_ready": True
        }

    def _sign_record(self) -> str:
        record_bytes = json.dumps(self.record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self._private_key.sign(record_bytes).hex()

    def verify_signature(self, public_key_bytes: bytes) -> bool:
        try:
            pub_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            record_bytes = json.dumps(self.record, sort_keys=True, separators=(",", ":")).encode("utf-8")
            pub_key.verify(bytes.fromhex(self.signature), record_bytes)
            return True
        except Exception as e:
            logger.warning("[PermissionRecord] Signature verification failed: %s", e)
            return False

    async def export_record_async(self) -> Dict[str, Any]:
        await asyncio.sleep(0)
        return self.export_record()

    def export_record(self) -> Dict[str, Any]:
        export = dict(self.record)
        export["signature"] = self.signature
        return export

    def export_cbor(self) -> Optional[bytes]:
        if not CBOR_AVAILABLE:
            logger.warning("[PermissionRecord] CBOR export unavailable (install cbor2)")
            return None
        return cbor2.dumps(self.export_record())

    def is_expired(self) -> bool:
        if not self.expiry_iso:
            return False
        try:
            expiry_dt = datetime.fromisoformat(self.expiry_iso.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > expiry_dt
        except Exception as e:
            logger.error("[PermissionRecord] Invalid expiry format '%s': %s", self.expiry_iso, e)
            return False

    def inherits_from(self, parent_permission: "PermissionRecord") -> bool:
        if not parent_permission:
            return False
        if self.parent_code != parent_permission.permission_code:
            return False
        return all(scope in parent_permission.scope_hierarchy for scope in self.scope_hierarchy)

    def _validate_hierarchy(self, parent_permission: "PermissionRecord") -> bool:
        valid = self.inherits_from(parent_permission)
        if not valid:
            logger.error("[PermissionRecord] Invalid hierarchy: %s -> %s",
                         self.permission_code, parent_permission.permission_code)
        return valid

    def suggest_child_permission(
        self,
        private_key_bytes: Optional[bytes | str],
        permission_code: str,
        scope_hierarchy: List[str],
        devices: List[str],
        consent_level: str,
        expiry_iso: Optional[str] = None,
    ) -> "PermissionRecord":
        return PermissionRecord(
            private_key_bytes=private_key_bytes,
            permission_code=permission_code,
            scope_hierarchy=scope_hierarchy,
            devices=devices,
            consent_level=consent_level,
            weight_level=self.weight_level,
            expiry_iso=expiry_iso,
            parent_permission=self,
            allow_suggestion=True,
            event_bus=self.event_bus
        )
