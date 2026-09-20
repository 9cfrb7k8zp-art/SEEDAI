# ==========================================================
# FILE: track_action_permissions.py
# PATH: SEED_ROOT/seed/core/track_action_permissions.py
# VERSION: 1.0 (ACTION PERMISSION GATE | LAYER SAFE)
# UPDATED: 2026-01-03
# ==========================================================

from typing import Dict, Any, Optional, Set

# ==========================================================
# Permission Levels
# ==========================================================
PERMISSION_LEVELS = {
    "VIEW": 0,
    "INTERACT": 1,
    "CONTROL": 2,
    "ADMIN": 3,
    "SYSTEM": 4,
}

# ==========================================================
# Action Permission Descriptor
# ==========================================================
class ActionPermission:
    """
    Defines who may execute a Track action.
    """

    def __init__(
        self,
        *,
        level: int,
        allowed_domains: Optional[Set[str]] = None,
        allowed_channels: Optional[Set[str]] = None,
        description: Optional[str] = None,
    ):
        self.level = int(level)
        self.allowed_domains = {d.upper() for d in allowed_domains} if allowed_domains else None
        self.allowed_channels = {c.upper() for c in allowed_channels} if allowed_channels else None
        self.description = description or ""

    def allows(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate permission against caller context.
        """
        ctx_level = int(context.get("permission_level", -1))
        if ctx_level < self.level:
            return False

        domain = context.get("domain")
        channel = context.get("channel")

        if self.allowed_domains and domain not in self.allowed_domains:
            return False

        if self.allowed_channels and channel not in self.allowed_channels:
            return False

        return True


# ==========================================================
# Permission Registry (per Track)
# ==========================================================
class TrackActionPermissions:
    """
    Stores permission rules for Track actions.
    """

    def __init__(self):
        self._rules: Dict[str, ActionPermission] = {}

    def register(
        self,
        action: str,
        *,
        level: int,
        allowed_domains: Optional[Set[str]] = None,
        allowed_channels: Optional[Set[str]] = None,
        description: Optional[str] = None,
    ) -> None:
        self._rules[action] = ActionPermission(
            level=level,
            allowed_domains=allowed_domains,
            allowed_channels=allowed_channels,
            description=description,
        )

    def check(self, action: str, context: Dict[str, Any]) -> bool:
        rule = self._rules.get(action)
        if not rule:
            return False
        return rule.allows(context)

    def describe(self, action: str) -> Dict[str, Any]:
        rule = self._rules.get(action)
        if not rule:
            return {}
        return {
            "level": rule.level,
            "allowed_domains": list(rule.allowed_domains) if rule.allowed_domains else None,
            "allowed_channels": list(rule.allowed_channels) if rule.allowed_channels else None,
            "description": rule.description,
        }

# ==========================================================
# END OF FILE
# ==========================================================
