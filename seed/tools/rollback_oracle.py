# ==============================================================
# FILE: SEED_ROOT/seed/tools/rollback_oracle.py
# PURPOSE: Decide when SEED-AI should consider rollback
# VERSION: 2.0.0
# ROLE: Oracle-facing rollback assessment / recovery observer
# ==============================================================

import logging
import threading
import time
import uuid
from copy import deepcopy

from seed.tools.base_tool import BaseTool


logger = logging.getLogger("RollbackOracle")


class RollbackOracle(BaseTool):

    NODE_TYPE = "tool"
    NODE_VERSION = "2.0.0"

    def __init__(
        self,
        name="rollback_oracle",
        capabilities=None,
        dependencies=None,
        role="oracle-rollback-observer",
        version="2.0.0",
        always_on=False,
        check_interval=1.0,
        oracle=None,
    ):
        default_capabilities = {
            "rollback_assessment",
            "rollback_detection",
            "recovery_analysis",
            "failure_correlation",
            "entropy_analysis",
            "invariant_analysis",
            "capability_degradation_analysis",
            "oracle_governance_link",
            "recovery_recommendation",
        }

        if capabilities:
            default_capabilities.update(capabilities)

        super().__init__(
            name=name,
            capabilities=default_capabilities,
            dependencies=dependencies,
            role=role,
            version=version,
            always_on=always_on,
        )

        self._lock = threading.RLock()

        self._check_interval = max(
            float(check_interval),
            0.01,
        )

        # Existing Oracle reference only.
        # This node never constructs Oracle.
        self._oracle = None

        # State history.
        self._history = []

        # Assessment history.
        self._assessments = []

        # Compatibility/history for rollback requests.
        self._rollback_actions = []

        self._last_state = {}
        self._last_assessment = None

        self._running = False
        self._monitor_thread = None

        self._evaluation_count = 0
        self._rollback_trigger_count = 0

        self._last_error = None

        self._thresholds = {
            "error_slope": 0.5,
            "entropy_rise": 0.7,
            "invariant_violations": 1,
            "degraded_metrics": 0.6,
        }

        if oracle is not None:
            self.bind_oracle(oracle)

    # ----------------------------------------------------------
    # Oracle binding
    # ----------------------------------------------------------

    def bind_oracle(self, oracle):

        if oracle is None:
            self._oracle = None
            self.unbind("oracle")
            return False

        self._oracle = oracle
        self.bind("oracle", oracle)

        logger.info(
            f"[{self.name}] Oracle governance link bound"
        )

        return True

    def unbind_oracle(self):
        self._oracle = None
        self.unbind("oracle")

        logger.info(
            f"[{self.name}] Oracle governance link unbound"
        )

    def get_oracle(self):
        return self._oracle

    # ----------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------

    def start(self):
        with self._lock:
            if self._running:
                return self.status()

            self._running = True
            self.active = True

            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="RollbackOracleMonitor",
                daemon=True,
            )

            self._monitor_thread.start()

        logger.info(
            f"[{self.name}] Started monitoring"
        )

        return self.status()

    def stop(self):
        with self._lock:
            self._running = False
            self.active = False
            self._monitor_thread = None

        logger.info(
            f"[{self.name}] Stopped monitoring"
        )

        return self.status()

    # ----------------------------------------------------------
    # Threshold configuration
    # ----------------------------------------------------------

    def set_threshold(self, name, value):
        if name not in self._thresholds:
            raise KeyError(
                f"Unknown rollback threshold: {name}"
            )

        with self._lock:
            self._thresholds[name] = float(value)

        return {
            "threshold": name,
            "value": float(value),
            "timestamp": time.time(),
        }

    def thresholds(self):
        with self._lock:
            return deepcopy(self._thresholds)

    # ----------------------------------------------------------
    # Feed state into rollback observer
    # ----------------------------------------------------------

    def feed_state(self, state_snapshot):
        if not isinstance(state_snapshot, dict):
            raise TypeError(
                "state_snapshot must be a dict"
            )

        timestamp = time.time()

        record = {
            "type": "rollback_observation",
            "observation_id": (
                f"OBS.{uuid.uuid4().hex[:12]}"
            ),
            "source_node": self.node_id,
            "time": timestamp,
            "state": deepcopy(state_snapshot),
        }

        with self._lock:
            self._history.append(record)
            self._last_state = deepcopy(
                state_snapshot
            )

        return deepcopy(record)

    # ----------------------------------------------------------
    # Evaluate rollback conditions
    # ----------------------------------------------------------

    def evaluate(self):
        with self._lock:
            state = deepcopy(self._last_state)
            thresholds = deepcopy(self._thresholds)

            self._evaluation_count += 1

        if not state:
            assessment = {
                "type": "rollback_assessment",
                "assessment_id": (
                    f"ASSESS.{uuid.uuid4().hex[:12]}"
                ),
                "source_node": self.node_id,
                "rollback_recommended": False,
                "decision": "INSUFFICIENT_DATA",
                "triggers": [],
                "evidence": {},
                "authority": {
                    "required": True,
                    "owner": "Oracle",
                    "executed": False,
                },
                "execution": {
                    "executed": False,
                    "execution_owner": "QbitDialer",
                },
                "timestamp": time.time(),
            }

            with self._lock:
                self._last_assessment = deepcopy(
                    assessment
                )
                self._assessments.append(
                    deepcopy(assessment)
                )

            return assessment

        triggers = []
        evidence = {}

        # ------------------------------------------------------
        # Error rate
        # ------------------------------------------------------

        errors = state.get(
            "error_rate",
            state.get("error_slope", 0),
        )

        try:
            errors = float(errors)
        except (TypeError, ValueError):
            errors = 0.0

        evidence["error_rate"] = errors

        if errors > thresholds["error_slope"]:
            triggers.append(
                "ERROR_RATE_THRESHOLD"
            )

        # ------------------------------------------------------
        # Entropy
        # ------------------------------------------------------

        entropy = state.get(
            "entropy",
            state.get("entropy_score", 0),
        )

        try:
            entropy = float(entropy)
        except (TypeError, ValueError):
            entropy = 0.0

        evidence["entropy"] = entropy

        if entropy > thresholds["entropy_rise"]:
            triggers.append(
                "ENTROPY_THRESHOLD"
            )

        # ------------------------------------------------------
        # Invariant violations
        # ------------------------------------------------------

        violations = state.get(
            "invariant_violations",
            state.get("invariant_violation_count", 0),
        )

        try:
            violations = int(violations)
        except (TypeError, ValueError):
            violations = 0

        evidence["invariant_violations"] = violations

        if violations >= thresholds[
            "invariant_violations"
        ]:
            triggers.append(
                "INVARIANT_VIOLATION"
            )

        # ------------------------------------------------------
        # Capability
        # ------------------------------------------------------

        capability = state.get(
            "capability",
            state.get("capability_score", 1.0),
        )

        try:
            capability = float(capability)
        except (TypeError, ValueError):
            capability = 1.0

        evidence["capability"] = capability

        if capability < thresholds[
            "degraded_metrics"
        ]:
            triggers.append(
                "CAPABILITY_DEGRADATION"
            )

        rollback_recommended = bool(triggers)

        if rollback_recommended:
            decision = "ROLLBACK_RECOMMENDED"

            with self._lock:
                self._rollback_trigger_count += 1
        else:
            decision = "NO_ROLLBACK"

        assessment = {
            "type": "rollback_assessment",
            "assessment_id": (
                f"ASSESS.{uuid.uuid4().hex[:12]}"
            ),
            "source_node": self.node_id,
            "rollback_recommended": (
                rollback_recommended
            ),
            "decision": decision,
            "triggers": triggers,
            "evidence": evidence,
            "thresholds": thresholds,
            "authority": {
                "required": True,
                "owner": "Oracle",
                "executed": False,
            },
            "execution": {
                "executed": False,
                "execution_owner": "QbitDialer",
            },
            "timestamp": time.time(),
        }

        with self._lock:
            self._last_assessment = deepcopy(
                assessment
            )
            self._assessments.append(
                deepcopy(assessment)
            )
            self._last_error = None

        if rollback_recommended:
            logger.warning(
                f"[{self.name}] "
                f"Rollback recommended | "
                f"triggers={triggers}"
            )
        else:
            logger.debug(
                f"[{self.name}] "
                f"No rollback recommended"
            )

        return deepcopy(assessment)

    # ----------------------------------------------------------
    # Build Oracle recommendation
    # ----------------------------------------------------------

    def build_recommendation(self):
        with self._lock:
            assessment = deepcopy(
                self._last_assessment
            )

        if assessment is None:
            assessment = self.evaluate()

        recommended = bool(
            assessment.get(
                "rollback_recommended",
                False,
            )
        )

        return {
            "type": "rollback_recommendation",
            "recommendation_id": (
                f"ROLLBACK.{uuid.uuid4().hex[:12]}"
            ),
            "source_node": self.node_id,
            "decision": (
                "REVIEW_ROLLBACK"
                if recommended
                else "CONTINUE"
            ),
            "rollback_recommended": recommended,
            "triggers": deepcopy(
                assessment.get(
                    "triggers",
                    [],
                )
            ),
            "evidence": deepcopy(
                assessment.get(
                    "evidence",
                    {},
                )
            ),
            "assessment_id": assessment.get(
                "assessment_id"
            ),
            "oracle": {
                "linked": self._oracle is not None,
                "governance_required": True,
            },
            "authority": {
                "owner": "Oracle",
                "required": True,
                "executed": False,
            },
            "execution": {
                "owner": "QbitDialer",
                "executed": False,
                "command_submitted": False,
            },
            "timestamp": time.time(),
        }

    # ----------------------------------------------------------
    # Rollback request
    # ----------------------------------------------------------

    def request_rollback(
        self,
        reason=None,
        evidence=None,
        target=None,
    ):

        with self._lock:
            assessment = deepcopy(
                self._last_assessment
            )

        recommendation = self.build_recommendation()

        request = {
            "type": "rollback_request",
            "request_id": (
                f"REQ.{uuid.uuid4().hex[:12]}"
            ),
            "source_node": self.node_id,
            "target": target,
            "reason": reason,
            "evidence": (
                deepcopy(evidence)
                if isinstance(
                    evidence,
                    (dict, list),
                )
                else evidence
            ),
            "assessment": assessment,
            "recommendation": recommendation,
            "authority": {
                "required": True,
                "owner": "Oracle",
                "approved": False,
                "executed": False,
            },
            "execution": {
                "owner": "QbitDialer",
                "command_submitted": False,
                "executed": False,
            },
            "timestamp": time.time(),
        }

        with self._lock:
            self._rollback_actions.append(
                deepcopy(request)
            )

        logger.warning(
            f"[{self.name}] "
            f"Rollback request created | "
            f"target={target}"
        )

        return request

    # ----------------------------------------------------------
    # Compatibility-safe rollback method
    # ----------------------------------------------------------

    def rollback(
        self,
        action_callable=None,
        *args,
        **kwargs,
    ):

        action_name = None

        if action_callable is not None:
            action_name = getattr(
                action_callable,
                "__name__",
                action_callable.__class__.__name__,
            )

        request = self.request_rollback(
            reason="rollback_callable_requested",
            evidence={
                "requested_action": action_name,
                "argument_count": len(args),
                "keyword_names": list(
                    kwargs.keys()
                ),
            },
        )

        request["execution"][
            "callable_executed"
        ] = False

        logger.warning(
            f"[{self.name}] "
            f"Rollback callable NOT executed | "
            f"action={action_name}"
        )

        return request

    # ----------------------------------------------------------
    # Background monitoring
    # ----------------------------------------------------------

    def _monitor_loop(self):
        while True:
            with self._lock:
                if not self._running:
                    break

            try:
                self.evaluate()
            except Exception as exc:
                with self._lock:
                    self._last_error = {
                        "error": str(exc),
                        "error_type": (
                            type(exc).__name__
                        ),
                        "timestamp": time.time(),
                    }

                logger.error(
                    f"[{self.name}] "
                    f"Monitoring error: {exc}"
                )

            time.sleep(
                self._check_interval
            )

    # ----------------------------------------------------------
    # History
    # ----------------------------------------------------------

    def history(self, last_n=None):
        with self._lock:
            records = list(
                self._history
            )

            if last_n is not None:
                if last_n < 0:
                    raise ValueError(
                        "last_n must be >= 0"
                    )

                records = records[-last_n:]

            return deepcopy(records)

    def assessment_history(self, last_n=None):
        with self._lock:
            records = list(
                self._assessments
            )

            if last_n is not None:
                if last_n < 0:
                    raise ValueError(
                        "last_n must be >= 0"
                    )

                records = records[-last_n:]

            return deepcopy(records)

    # ----------------------------------------------------------
    # Display
    # ----------------------------------------------------------

    def show_history(self, last_n=5):
        records = self.history(last_n)

        for entry in records:
            logger.info(
                f"[{self.name}] "
                f"{entry.get('time', 0):.3f} | "
                f"state keys="
                f"{list(entry.get('state', {}).keys())}"
            )

        return records

    # ----------------------------------------------------------
    # Status
    # ----------------------------------------------------------

    def status(self):
        with self._lock:
            return {
                "node_id": self.node_id,
                "name": self.name,
                "role": self.role,
                "version": self.version,
                "running": self._running,
                "active": self.active,
                "ready": self.ready,
                "degraded": self.degraded,
                "failed": self.failed,
                "oracle_linked": (
                    self._oracle is not None
                ),
                "history_len": len(
                    self._history
                ),
                "assessment_count": len(
                    self._assessments
                ),
                "rollback_request_count": len(
                    self._rollback_actions
                ),
                "evaluation_count": (
                    self._evaluation_count
                ),
                "rollback_trigger_count": (
                    self._rollback_trigger_count
                ),
                "last_state_keys": list(
                    self._last_state.keys()
                ),
                "last_assessment": deepcopy(
                    self._last_assessment
                ),
                "last_error": deepcopy(
                    self._last_error
                ),
            }

    # ----------------------------------------------------------
    # Health
    # ----------------------------------------------------------

    def health(self):
        with self._lock:
            if self.failed:
                state = "FAILED"
            elif self._last_error is not None:
                state = "DEGRADED"
            elif self._running:
                state = "HEALTHY"
            else:
                state = "STOPPED"

            return {
                "state": state,
                "running": self._running,
                "oracle_linked": (
                    self._oracle is not None
                ),
                "evaluation_count": (
                    self._evaluation_count
                ),
                "rollback_trigger_count": (
                    self._rollback_trigger_count
                ),
                "timestamp": time.time(),
            }

    # ----------------------------------------------------------
    # Representation
    # ----------------------------------------------------------

    def __repr__(self):
        with self._lock:
            return (
                f"<RollbackOracle "
                f"name={self.name!r} "
                f"running={self._running} "
                f"oracle_linked="
                f"{self._oracle is not None} "
                f"assessments="
                f"{len(self._assessments)}>"
            )