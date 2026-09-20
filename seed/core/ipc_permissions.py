# ==========================================================
# File: ipc_permissions.py
# Path: SEED_ROOT/seed/core/ipc_permissions.py
# Version: 1.0 (IPC PERMISSION MATRIX)
# ==========================================================

from enum import Enum
from typing import Dict, Set


class IPCDomain(str, Enum):
    SYSTEM = "SYSTEM"
    DEV = "DEV"
    USER = "USER"
    AGENT = "AGENT"
    EXTERNAL = "EXTERNAL"


class IPCPermissionMatrix:
    def __init__(self):
        self.publish_rules: Dict[str, Set[IPCDomain]] = {}
        self.subscribe_rules: Dict[str, Set[IPCDomain]] = {}

    # --------------------------------------------------
    def allow_publish(self, topic: str, *domains: IPCDomain):
        self.publish_rules.setdefault(topic, set()).update(domains)

    def allow_subscribe(self, topic: str, *domains: IPCDomain):
        self.subscribe_rules.setdefault(topic, set()).update(domains)

    # --------------------------------------------------
    def can_publish(self, topic: str, domain: IPCDomain) -> bool:
        allowed = self.publish_rules.get(topic)
        return allowed is not None and domain in allowed

    def can_subscribe(self, topic: str, domain: IPCDomain) -> bool:
        allowed = self.subscribe_rules.get(topic)
        return allowed is not None and domain in allowed
