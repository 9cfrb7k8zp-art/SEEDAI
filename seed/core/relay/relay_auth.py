# ==========================================================
# FILE: relay_auth.py
# PATH: SEED_ROOT/seed/core/relay/relay_auth.py
# VERSION: 2.0.0
# PURPOSE: SEED Relay identity and request authentication
# ==========================================================

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass
from typing import Optional


MODULE_ID = "CORE_RELAY_AUTH"
MODULE_VERSION = "2.0.0"


@dataclass(frozen=True)
class RelayIdentity:
    seed_id: str
    relay_id: str
    token_fingerprint: str


class RelayAuth:

    def __init__(
        self,
        *,
        seed_id: str = "SEED-CORE",
        relay_id: str = "SEED-RELAY-2",
        token: Optional[str] = None,
    ):
        self.seed_id = seed_id
        self.relay_id = relay_id

        self._token = token or secrets.token_urlsafe(32)
        self._lock = threading.RLock()

        self._enabled = True

    # ------------------------------------------------------
    # IDENTITY
    # ------------------------------------------------------

    @property
    def identity(self) -> RelayIdentity:
        return RelayIdentity(
            seed_id=self.seed_id,
            relay_id=self.relay_id,
            token_fingerprint=self.fingerprint(),
        )

    def fingerprint(self) -> str:
        digest = hashlib.sha256(
            self._token.encode("utf-8")
        ).hexdigest()

        return digest[:16]

    # ------------------------------------------------------
    # AUTHENTICATION
    # ------------------------------------------------------

    def authenticate(
        self,
        token: Optional[str],
    ) -> bool:

        with self._lock:
            if not self._enabled:
                return False

            if not token:
                return False

            return hmac.compare_digest(
                self._token,
                str(token),
            )

    def authenticate_request(
        self,
        *,
        seed_id: str,
        token: Optional[str],
    ) -> tuple[bool, str]:

        with self._lock:
            if not self._enabled:
                return False, "Authentication disabled."

            if seed_id != self.seed_id:
                return False, "Unknown SEED identity."

            if not self.authenticate(token):
                return False, "Relay authentication failed."

            return True, "AUTHENTICATED"

    def internal_token(self) -> str:

        with self._lock:
            return self._token

    # ------------------------------------------------------
    # CONTROL
    # ------------------------------------------------------

    def disable(self) -> None:
        with self._lock:
            self._enabled = False

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def status(self) -> dict:
        return {
            "module": MODULE_ID,
            "version": MODULE_VERSION,
            "enabled": self.is_enabled(),
            "seed_id": self.seed_id,
            "relay_id": self.relay_id,
            "token_fingerprint": self.fingerprint(),
        }