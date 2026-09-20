# ==========================================================
# FILE: security.py
# PATH: SEED_ROOT/seed/core/security.py
# VERSION: 2.0.0
# BUILD: ACTION-AWARE / TRACK-AWARE / AUDIT-FIRST
#
# PURPOSE:
#   Evaluate the actual action SEED is about to admit.
#   User intent supplies authorization context, but does not
#   manufacture authority over resources the actor cannot own.
#
# ==========================================================

import datetime


class SEEDSecurityManager:
    """Action authorization and audit boundary."""

    def __init__(self):
        self.roles = {
            "SYSTEM": {"all": True},
            "ADMIN": {"all": True},
            "OPERATOR": {"execute_command": True, "view_dashboard": True},
            "MONITOR": {"view_dashboard": True},
        }
        self.audit_log = []
        self.current_actor = "SYSTEM"

    def set_actor(self, actor_name):
        self.current_actor = str(actor_name or "SYSTEM")

    def authorize(self, action):
        permissions = self.roles.get(self.current_actor, {})
        allowed = bool(permissions.get(action, permissions.get("all", False)))
        self._log(action, allowed)
        return allowed

    def evaluate_action(self, action, *, track_id=None, qbit_id=None,
                        source=None, target=None, reason=None,
                        user_authorized=False):
        """Evaluate an action envelope without executing it."""
        if not isinstance(action, dict):
            return {"allowed": False, "reason": "invalid_action_envelope"}

        name = str(action.get("name") or action.get("command") or action.get("action") or "").strip().upper()
        if not name:
            return {"allowed": False, "reason": "empty_action"}

        allowed = self.authorize(name)
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "actor": self.current_actor,
            "action": name,
            "track_id": track_id,
            "qbit_id": qbit_id,
            "source": source,
            "target": target,
            "reason": reason,
            "user_authorized": bool(user_authorized),
            "allowed": bool(allowed),
        }
        self.audit_log.append(entry)
        return {
            "allowed": bool(allowed),
            "action": name,
            "actor": self.current_actor,
            "track_id": track_id,
            "qbit_id": qbit_id,
            "audit": entry,
        }

    def _log(self, action, allowed):
        self.audit_log.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "actor": self.current_actor,
            "action": action,
            "allowed": bool(allowed),
        })

    def get_audit_log(self):
        return list(self.audit_log)

    def secure_execute(self, action, callable_func, *args, **kwargs):
        decision = self.evaluate_action(action)
        if decision.get("allowed"):
            return callable_func(*args, **kwargs)
        raise PermissionError(
            f"Actor '{self.current_actor}' is not authorized to perform '{decision.get('action')}'"
        )


__all__ = ["SEEDSecurityManager"]
