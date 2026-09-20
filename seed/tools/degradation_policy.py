# =============================================================
# SEED-AI DEGRADATION POLICY NODE
#
# File: SEED_ROOT/seed/tools/degradation_policy.py
#
# ROLE:
#   Graceful degradation / recovery policy neural node.
#
# PURPOSE:
#   - Monitor registered degradation policies
#   - Evaluate system/tool conditions
#   - Rank recovery recommendations
#   - Report degradation state
#   - Provide structured recovery proposals
#
# AUTHORITY:
#   This node is NOT command authority.
#
#   QbitDialer remains the authoritative command admission
#   and system-control layer.
#
# IMPORTANT:
#   Policy actions are NOT executed automatically.
#   Evaluation produces structured recommendations.
#
#   A higher-level SEED control layer may deliver those
#   recommendations toward QbitDialer for command admission.
#
# DOES NOT CREATE:
#   - QbitQueueLoop
#   - QbitDialer
#   - EventBus
#   - TrackSystem
#   - NeuralBridge
#   - Registry
#   - competing command plane
#
# =============================================================

import logging
import threading
import time
import uuid

from seed.tools.base_tool import BaseTool


logger = logging.getLogger("DegradationPolicy")


class DegradationPolicyEngine(BaseTool):
 

    NODE_TYPE = "tool.degradation_policy"
    NODE_VERSION = "2.0.0"

    def __init__(
        self,
        check_interval=1.0,
        name="degradation_policy",
        capabilities=None,
        dependencies=None,
        always_on=False,
    ):
        capabilities = capabilities or [
            "degradation_detection",
            "policy_evaluation",
            "recovery_recommendation",
            "graceful_degradation",
            "failure_analysis",
            "priority_policy_routing",
        ]

        dependencies = dependencies or []

        super().__init__(
            name=name,
            capabilities=capabilities,
            dependencies=dependencies,
            role="degradation-policy",
            version=self.NODE_VERSION,
            always_on=always_on,
        )

        self._policies = {}
        self._lock = threading.RLock()

        self._check_interval = max(
            0.05,
            float(check_interval),
        )

        self._running = False
        self._monitor_thread = None

        self._evaluation_count = 0
        self._recommendation_count = 0
        self._condition_errors = 0

        self._last_evaluation = None
        self._last_recommendation = None

        self._recommendations = []

        self.policy_id = (
            f"POLICY."
            f"{uuid.uuid4().hex[:12]}"
        )

    # =========================================================
    # START / STOP
    # =========================================================

    def start(self):
  

        with self._lock:
            if self._running:
                return self.status()

            self._running = True

            self.active = True
            self.ready = True
            self.failed = False
            self.degraded = False

            self.started_at = time.time()

            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="SEED-DegradationPolicy",
                daemon=True,
            )

            self._monitor_thread.start()

        logger.info(
            "[%s] Started | policy_id=%s",
            self.name,
            self.policy_id,
        )

        return self.status()

    def stop(self):
       

        with self._lock:
            self._running = False
            self.active = False
            self.ready = False
            self.stopped_at = time.time()

        logger.info(
            "[%s] Stopped",
            self.name,
        )

        return self.status()

    # =========================================================
    # POLICY REGISTRATION
    # =========================================================

    def define_policy(
        self,
        module_name,
        action,
        priority=1,
        condition=None,
        metadata=None,
    ):
        

        if not module_name:
            raise ValueError(
                "module_name is required"
            )

        if not callable(action):
            raise ValueError(
                "Action must be callable"
            )

        if condition is not None and not callable(condition):
            raise ValueError(
                "Condition must be callable if provided"
            )

        policy = {
            "module_name": str(module_name),
            "action": action,
            "priority": int(priority),
            "condition": condition,
            "metadata": dict(metadata or {}),
            "created_at": time.time(),
            "evaluation_count": 0,
            "trigger_count": 0,
            "last_triggered": None,
        }

        with self._lock:
            self._policies[str(module_name)] = policy

        logger.info(
            "[%s] Policy defined | module=%s | priority=%s",
            self.name,
            module_name,
            priority,
        )

        return self._policy_snapshot(policy)

    # =========================================================
    # POLICY REMOVAL
    # =========================================================

    def remove_policy(self, module_name):
    
        with self._lock:
            removed = self._policies.pop(
                str(module_name),
                None,
            )

        if removed is not None:
            logger.info(
                "[%s] Removed policy | module=%s",
                self.name,
                module_name,
            )

            return True

        return False

    # =========================================================
    # POLICY LOOKUP
    # =========================================================

    def get_policy(self, module_name):
       
        with self._lock:
            policy = self._policies.get(
                str(module_name)
            )

            if policy is None:
                return None

            return self._policy_snapshot(policy)

    def list_policies(self):
    

        with self._lock:
            return {
                name: self._policy_snapshot(policy)
                for name, policy
                in self._policies.items()
            }

    def _policy_snapshot(self, policy):
    

        return {
            "module_name": policy["module_name"],
            "priority": policy["priority"],
            "metadata": dict(
                policy.get("metadata") or {}
            ),
            "created_at": policy["created_at"],
            "evaluation_count": policy[
                "evaluation_count"
            ],
            "trigger_count": policy[
                "trigger_count"
            ],
            "last_triggered": policy[
                "last_triggered"
            ],
            "has_action": callable(
                policy.get("action")
            ),
            "has_condition": callable(
                policy.get("condition")
            ),
        }

    # =========================================================
    # POLICY EVALUATION
    # =========================================================

    def evaluate(self):
  

        now = time.time()

        with self._lock:
            policies = sorted(
                self._policies.items(),
                key=lambda item: item[1]["priority"],
                reverse=True,
            )

        recommendations = []

        self._evaluation_count += 1
        self._last_evaluation = now

        for module_name, policy in policies:

            condition = policy.get(
                "condition"
            )

            policy["evaluation_count"] += 1

            triggered = False

            try:
                if condition is None:
                    triggered = True
                else:
                    triggered = bool(
                        condition()
                    )

            except Exception as exc:
                self._condition_errors += 1

                logger.error(
                    "[%s] Condition failure | module=%s | error=%s",
                    self.name,
                    module_name,
                    exc,
                )

                continue

            if not triggered:
                continue

            policy["trigger_count"] += 1
            policy["last_triggered"] = now

            recommendation = self._build_recommendation(
                module_name,
                policy,
            )

            recommendations.append(
                recommendation
            )

        with self._lock:
            self._recommendations.extend(
                recommendations
            )

            # Keep local history bounded.
            if len(self._recommendations) > 500:
                del self._recommendations[:-500]

            if recommendations:
                self._recommendation_count += len(
                    recommendations
                )

                self._last_recommendation = (
                    recommendations[-1]
                )

        return recommendations

    # =========================================================
    # RECOMMENDATION CREATION
    # =========================================================

    def _build_recommendation(
        self,
        module_name,
        policy,
    ):
    

        metadata = dict(
            policy.get("metadata") or {}
        )

        requested_action = metadata.get(
            "action",
            "degrade",
        )

        recommendation = {
            "type": "degradation_recommendation",

            "recommendation_id": (
                f"DEGRADE."
                f"{uuid.uuid4().hex[:12]}"
            ),

            "policy_id": self.policy_id,

            "source_node": self.node_id,

            "module_name": module_name,

            "action": str(
                requested_action
            ),

            "priority": int(
                policy.get("priority", 1)
            ),

            "reason": metadata.get(
                "reason",
                "degradation policy triggered",
            ),

            "evidence": metadata.get(
                "evidence"
            ),

            "metadata": metadata,

            "requires_authority": (
                "QbitDialer"
            ),

            "execution": {
                "executed": False,
                "execution_owner": "QbitDialer",
            },

            "timestamp": time.time(),
        }

        logger.warning(
            "[%s] Degradation recommendation | "
            "module=%s | action=%s | priority=%s",
            self.name,
            module_name,
            recommendation["action"],
            recommendation["priority"],
        )

        return recommendation

    # =========================================================
    # RECOMMENDATION HISTORY
    # =========================================================

    def get_recommendations(
        self,
        limit=50,
    ):


        try:
            limit = max(
                1,
                int(limit),
            )
        except Exception:
            limit = 50

        with self._lock:
            return list(
                self._recommendations[-limit:]
            )

    def clear_recommendations(self):

        with self._lock:
            self._recommendations.clear()

    # =========================================================
    # BACKGROUND MONITOR
    # =========================================================

    def _monitor_loop(self):

        while True:

            with self._lock:
                if not self._running:
                    break

            try:
                self.evaluate()

            except Exception as exc:
                logger.error(
                    "[%s] Monitoring error | error=%s",
                    self.name,
                    exc,
                )

                self.last_error = str(
                    exc
                )

            self.last_activity = time.time()

            time.sleep(
                self._check_interval
            )

    # =========================================================
    # MANUAL EVALUATION
    # =========================================================

    def evaluate_once(self):
        """
        Explicit one-shot evaluation.

        Useful when another SEED component wants a policy
        assessment without starting the monitor.
        """

        return self.evaluate()

    # =========================================================
    # CONTROL-FABRIC REPORT
    # =========================================================

    def build_report(self):

        with self._lock:
            return {
                "type": "degradation_policy_report",

                "node_id": self.node_id,

                "policy_id": self.policy_id,

                "tool": self.name,

                "running": self._running,

                "policy_count": len(
                    self._policies
                ),

                "evaluation_count": (
                    self._evaluation_count
                ),

                "recommendation_count": (
                    self._recommendation_count
                ),

                "condition_errors": (
                    self._condition_errors
                ),

                "last_evaluation": (
                    self._last_evaluation
                ),

                "last_recommendation": (
                    self._last_recommendation
                ),

                "timestamp": time.time(),
            }

    # =========================================================
    # STATUS
    # =========================================================

    def status(self):

        base = super().status()

        with self._lock:
            base.update(
                {
                    "running": self._running,

                    "policy_id": self.policy_id,

                    "policy_count": len(
                        self._policies
                    ),

                    "evaluation_count": (
                        self._evaluation_count
                    ),

                    "recommendation_count": (
                        self._recommendation_count
                    ),

                    "condition_errors": (
                        self._condition_errors
                    ),

                    "last_evaluation": (
                        self._last_evaluation
                    ),

                    "last_recommendation": (
                        self._last_recommendation
                    ),
                }
            )

        return base


__all__ = [
    "DegradationPolicyEngine",
]