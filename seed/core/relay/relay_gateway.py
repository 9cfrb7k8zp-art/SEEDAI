# ==========================================================
# FILE: relay_gateway.py
# PATH: SEED_ROOT/seed/core/relay/relay_gateway.py
# VERSION: 2.0.0
# PURPOSE: Single controlled entrance to SEED Relay
# ==========================================================

from __future__ import annotations

from typing import Optional

from .relay_auth import RelayAuth
from .relay_emergency_stop import RelayEmergencyStop
from .relay_operations import RelayOperations
from .relay_protocol import RelayRequest
from .relay_rate_limiter import RelayRateLimiter


MODULE_ID = "CORE_RELAY_GATEWAY"
MODULE_VERSION = "2.0.0"


class RelayGateway:


    def __init__(
        self,
        *,
        auth: RelayAuth,
        rate_limiter: RelayRateLimiter,
        emergency_stop: RelayEmergencyStop,
    ):
        self.auth = auth
        self.rate_limiter = rate_limiter
        self.emergency_stop = emergency_stop

    def admit(
        self,
        request: RelayRequest,
        *,
        token: Optional[str] = None,
    ) -> tuple[bool, str]:

        # --------------------------------------------------
        # Emergency stop
        # --------------------------------------------------

        allowed, reason = self.emergency_stop.allow()

        if not allowed:
            return False, reason

        # --------------------------------------------------
        # Identity
        # --------------------------------------------------

        if request.seed_id != self.auth.seed_id:
            return False, "Unknown SEED identity."

        # --------------------------------------------------
        # Authentication
        # --------------------------------------------------

        if not self.auth.authenticate(token):
            return False, "Relay authentication failed."

        # --------------------------------------------------
        # Operation validation
        # --------------------------------------------------

        valid, reason = RelayOperations.validate(
            request.operation,
            request.target,
        )

        if not valid:
            return False, reason

        # --------------------------------------------------
        # Rate limit
        # --------------------------------------------------

        if not self.rate_limiter.allow():
            return False, "Relay rate limit exceeded."

        return True, "RELAY_ADMITTED"

    def status(self) -> dict:
        return {
            "module": MODULE_ID,
            "version": MODULE_VERSION,
            "auth": self.auth.status(),
            "rate_limiter": self.rate_limiter.status(),
            "emergency_stop": self.emergency_stop.status(),
        }