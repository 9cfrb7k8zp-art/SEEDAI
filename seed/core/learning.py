"""
FILE: learning.py
PATH: seed/core/learning.py

SEED MODULE: AI Local Learning / Experience Engine
COMPONENT: Action Log Parser & Knowledge Builder

VERSION: 0.1.0
STATUS: Alpha
PLATFORM: Cross-platform (Windows / macOS / Linux)

RESPONSIBILITY:
- Parse Module 3 action logs
- Track success/failure per device, action, permission
- Analyze numeric overlay (3/6/9) + dot matrix (Red/Yellow/Blue)
- Build structured hierarchical knowledge base for AI learning
- Store experience locally for organic growth
- Fully offline, self-contained

LABELS:
- SEED_LEARNING_CORE
- AI_LOCAL_GROWTH
- HIERARCHICAL_ANALYSIS
- DOT_MATRIX
- LOCAL_ONLY
"""

import os
import json
import datetime
from collections import defaultdict

class LearningEngine:
    """
    LABEL: SEED_LEARNING_ENGINE_OBJECT
    """

    def __init__(self, storage_root: str):
        self.storage_root = storage_root
        self.actions_log_dir = os.path.join(storage_root, "storage", "actions")
        self.knowledge_base_path = os.path.join(storage_root, "storage", "ai_knowledge.json")
        self.knowledge = self._load_knowledge()

    def _load_knowledge(self):
        if os.path.exists(self.knowledge_base_path):
            with open(self.knowledge_base_path, "r") as f:
                return json.load(f)
        else:
            return {"devices": {}, "actions": {}, "permissions": {}, "timestamp": datetime.datetime.utcnow().isoformat()}

    def _save_knowledge(self):
        self.knowledge["timestamp"] = datetime.datetime.utcnow().isoformat()
        with open(self.knowledge_base_path, "w") as f:
            json.dump(self.knowledge, f, indent=2)

    def parse_action_logs(self):
        """
        Parse all JSON action logs and update the knowledge base.
        """
        for fname in os.listdir(self.actions_log_dir):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(self.actions_log_dir, fname)
            with open(filepath, "r") as f:
                log = json.load(f)
            self._update_knowledge(log)
        self._save_knowledge()

    def _update_knowledge(self, log: dict):
        """
        Update hierarchical knowledge base with a single log entry.
        """
        device_id = log.get("device_identifier")
        action_code = log.get("action_code")
        outcome = log.get("outcome")
        permission_code = log.get("metadata", {}).get("permission_code")
        weight_level = log.get("weight_level")
        consent_color = log.get("consent_color")

        # Track device stats
        if device_id not in self.knowledge["devices"]:
            self.knowledge["devices"][device_id] = {"actions": {}, "success": 0, "failure": 0}

        device_stats = self.knowledge["devices"][device_id]
        if outcome == "success":
            device_stats["success"] += 1
        else:
            device_stats["failure"] += 1

        # Track action stats
        if action_code not in device_stats["actions"]:
            device_stats["actions"][action_code] = {"attempts": 0, "success": 0, "failure": 0, "weight": [], "consent": []}
        action_stats = device_stats["actions"][action_code]
        action_stats["attempts"] += 1
        if outcome == "success":
            action_stats["success"] += 1
        else:
            action_stats["failure"] += 1
        action_stats["weight"].append(weight_level)
        action_stats["consent"].append(consent_color)

        # Track permissions usage
        if permission_code:
            if permission_code not in self.knowledge["permissions"]:
                self.knowledge["permissions"][permission_code] = {"attempts": 0, "success": 0, "failure": 0}
            perm_stats = self.knowledge["permissions"][permission_code]
            perm_stats["attempts"] += 1
            if outcome == "success":
                perm_stats["success"] += 1
            else:
                perm_stats["failure"] += 1

    def summarize_knowledge(self):
        """
        Generate a summary of AI learning for inspection.
        """
        summary = {}
        for device_id, stats in self.knowledge["devices"].items():
            total_attempts = stats["success"] + stats["failure"]
            device_success_rate = stats["success"] / total_attempts if total_attempts else 0
            summary[device_id] = {
                "success_rate": device_success_rate,
                "total_attempts": total_attempts,
                "actions": {}
            }
            for action_code, action_stats in stats["actions"].items():
                action_total = action_stats["attempts"]
                action_success_rate = action_stats["success"] / action_total if action_total else 0
                avg_weight = sum(action_stats["weight"])/len(action_stats["weight"]) if action_stats["weight"] else 0
                summary[device_id]["actions"][action_code] = {
                    "success_rate": action_success_rate,
                    "avg_weight": avg_weight,
                    "attempts": action_total
                }
        return summary
