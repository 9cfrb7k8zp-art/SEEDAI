"""
FILE: identity.py
PATH: seed/core/identity.py

SEED MODULE: Identity Core
COMPONENT: Cryptographic Identity Generator

VERSION: 0.1.0
STATUS: Stable (Foundational)
PLATFORM: Cross-platform (Windows / macOS / Linux)

RESPONSIBILITY:
- Generate asymmetric keypair for SEED instance
- Derive public fingerprint (SEED_ID)
- Provide non-sensitive identity metadata
- NO storage
- NO encryption
- NO device binding

AUTHORSHIP:
- System: SEED Personal AI OS
- Owner: Human-authorized (external to code)

LEGAL NOTE:
This file does NOT collect personal data.
All outputs are cryptographic material only.
"""

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
import hashlib
import datetime
import platform
import uuid


class SeedIdentity:
    """
    LABEL: SEED_IDENTITY_OBJECT

    Represents a single sovereign SEED identity instance.
    """

    def __init__(self):
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

        self.created_at_utc = datetime.datetime.utcnow().isoformat() + "Z"
        self.platform = platform.system()
        self.platform_release = platform.release()

        self.seed_uuid = str(uuid.uuid4())
        self.seed_id = self._derive_seed_id()

    def _derive_seed_id(self) -> str:
        """
        Derives a stable fingerprint from the public key.
        This becomes the SEED_ID (non-secret).
        """
        public_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        digest = hashlib.sha256(public_bytes).hexdigest()
        return digest

    def export_public_identity(self) -> dict:
        """
        LABEL: PUBLIC_IDENTITY_EXPORT

        Safe to share.
        """
        return {
            "seed_id": self.seed_id,
            "created_at": self.created_at_utc,
            "platform_origin": self.platform,
            "platform_release": self.platform_release,
            "seed_uuid": self.seed_uuid,
            "algorithm": "Ed25519",
            "hash": "SHA-256",
            "version": "0.1.0"
        }

    def export_private_key_bytes(self) -> bytes:
        """
        LABEL: PRIVATE_KEY_EXPORT

        WARNING:
        - Raw private key bytes
        - MUST be encrypted immediately
        - Never write directly to disk
        """
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

    def export_public_key_bytes(self) -> bytes:
        """
        LABEL: PUBLIC_KEY_EXPORT
        """
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
