# ==============================================================
# FILE: SEED_ROOT/seed/tools/causal_chain.py
#
# PURPOSE:
#   Autonomous causal-analysis node for SEED-AI.
#
# ROLE:
#   Reconstruct cause/effect relationships, detect repeated
#   failures and mutations, generate system reports, and issue
#   recommendations to the appropriate SEED system components.
#
# AUTHORITY:
#   OBSERVATION / ANALYSIS / RECOMMENDATION ONLY.
#
#   This module NEVER directly executes SEED commands.
#   QbitDialer remains the authoritative command admission and
#   execution authority.
#
# ARCHITECTURE:
#
#   SYSTEM EVENTS
#        ↓
#   CausalChainTracer
#        ↓
#   causal reconstruction
#        ↓
#   analysis
#        ↓
#   report + recommendation
#        ↓
#   EventBus / TrackSystem / SRegistry / QbitDialer
#        ↓
#   QbitDialer command authority
#
# ==============================================================

import inspect
import logging
import threading
import time
import uuid
from collections import Counter, deque
from copy import deepcopy

logger = logging.getLogger("CausalChainTracer")
logger.setLevel(logging.INFO)


# ==============================================================
# NODE LIFECYCLE
# ==============================================================

NODE_DISCOVERED = "DISCOVERED"
NODE_REGISTERED = "REGISTERED"
NODE_LOADING = "LOADING"
NODE_AVAILABLE = "AVAILABLE"
NODE_ACTIVE = "ACTIVE"
NODE_READY = "READY"
NODE_DEGRADED = "DEGRADED"
NODE_FAILED = "FAILED"
NODE_DISABLED = "DISABLED"


# ==============================================================
# RECOMMENDATION TYPES
# ==============================================================

RECOMMEND_ACTIVATE = "activate"
RECOMMEND_DEACTIVATE = "deactivate"
RECOMMEND_REPAIR = "repair"
RECOMMEND_RESTART = "restart"
RECOMMEND_REBIND = "rebind"
RECOMMEND_UPDATE = "update"
RECOMMEND_REBUILD = "rebuild"
RECOMMEND_RETRY = "retry"
RECOMMEND_QUARANTINE = "quarantine"
RECOMMEND_INVESTIGATE = "investigate"
RECOMMEND_MONITOR = "monitor"


# ==============================================================
# CAUSAL CHAIN TRACER
# ==============================================================

class CausalChainTracer:

    name = "causal_chain"

    role = "causal-analysis"

    node_type = "tool-node"

    authority = "observation-recommendation"

    version = "2.0.0"

    # ----------------------------------------------------------
    # INITIALIZATION
    # ----------------------------------------------------------

    def __init__(
        self,
        max_chains=512,
        max_reports=256,
        max_recommendations=256,
        analysis_window=32,
        auto_start=True,
        analysis_interval=2.0,
    ):

        self.max_chains = max_chains
        self.max_reports = max_reports
        self.max_recommendations = max_recommendations
        self.analysis_window = analysis_window
        self.analysis_interval = analysis_interval

        # ------------------------------------------------------
        # CORE STORAGE
        # ------------------------------------------------------

        self._chains = deque(maxlen=max_chains)

        self._reports = deque(maxlen=max_reports)

        self._recommendations = deque(
            maxlen=max_recommendations
        )

        self._errors = deque(maxlen=128)

        # ------------------------------------------------------
        # INDEXES
        # ------------------------------------------------------

        self._event_index = {}
        self._handler_index = {}
        self._mutation_index = {}

        # ------------------------------------------------------
        # STATE
        # ------------------------------------------------------

        self._lock = threading.RLock()

        self._running = False

        self._monitor_thread = None

        self._analysis_cycle = 0

        self._sequence = 0

        self._last_analysis = None

        self._last_report = None

        self._last_recommendation = None

        self.state = NODE_DISCOVERED

        # ------------------------------------------------------
        # RUNTIME REFERENCES
        #
        # These are references only.
        #
        # This tool does not construct these systems.
        # ------------------------------------------------------

        self.event_bus = None

        self.track_system = None

        self.registry = None

        self.registry_runtime = None

        self.qbit_dialer = None

        self.tools_orchestrator = None

        self.tool_network = None

        # ------------------------------------------------------
        # TELEMETRY
        # ------------------------------------------------------

        self.stats = {
            "links_added": 0,
            "events_seen": 0,
            "analysis_cycles": 0,
            "reports_generated": 0,
            "recommendations_generated": 0,
            "recommendations_sent": 0,
            "recommendations_failed": 0,
            "errors": 0,
        }

        if auto_start:
            self.start()

    # ==========================================================
    # START / STOP
    # ==========================================================

    def start(self):

        with self._lock:

            if self._running:
                return

            self._running = True

            self.state = NODE_ACTIVE

            self._monitor_thread = threading.Thread(
                target=self._analysis_loop,
                name="CausalChainTracer",
                daemon=True,
            )

            self._monitor_thread.start()

        logger.info(
            "[%s] Started | independent causal-analysis node",
            self.name,
        )

    def stop(self):

        with self._lock:

            self._running = False

            self.state = NODE_DISABLED

        logger.info(
            "[%s] Stopped",
            self.name,
        )

    # ==========================================================
    # RUNTIME ATTACHMENT
    # ==========================================================

    def attach_runtime(
        self,
        event_bus=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        qbit_dialer=None,
        tools_orchestrator=None,
        tool_network=None,
    ):


        with self._lock:

            if event_bus is not None:
                self.event_bus = event_bus

            if track_system is not None:
                self.track_system = track_system

            if registry is not None:
                self.registry = registry

            if registry_runtime is not None:
                self.registry_runtime = registry_runtime

            if qbit_dialer is not None:
                self.qbit_dialer = qbit_dialer

            if tools_orchestrator is not None:
                self.tools_orchestrator = tools_orchestrator

            if tool_network is not None:
                self.tool_network = tool_network

            self.state = NODE_READY

        logger.info(
            "[%s] Runtime attached | "
            "event_bus=%s | "
            "track_system=%s | "
            "registry=%s | "
            "qbit_dialer=%s",
            self.name,
            type(self.event_bus).__name__
            if self.event_bus else "NONE",
            type(self.track_system).__name__
            if self.track_system else "NONE",
            type(self.registry).__name__
            if self.registry else "NONE",
            type(self.qbit_dialer).__name__
            if self.qbit_dialer else "NONE",
        )

        return self.status()

    # ==========================================================
    # SEQUENCE
    # ==========================================================

    def _next_sequence(self):

        with self._lock:

            self._sequence += 1

            return self._sequence

    # ==========================================================
    # ADD CAUSAL LINK
    # ==========================================================

    def add_link(
        self,
        event,
        handler,
        mutation=None,
        side_effect=None,
        source=None,
        target=None,
        status=None,
        error=None,
        metadata=None,
        track_id=None,
        qbit_id=None,
        generation=None,
        parent_id=None,
    ):
        """
        Add one causal relationship to the chain.

        This is intentionally data-oriented.

        It does not execute anything.
        """

        link = {
            "sequence": self._next_sequence(),

            "timestamp": time.time(),

            "event": event,

            "handler": handler,

            "mutation": mutation,

            "side_effect": side_effect,

            "source": source,

            "target": target,

            "status": status,

            "error": error,

            "track_id": track_id,

            "qbit_id": qbit_id,

            "generation": generation,

            "parent_id": parent_id,

            "metadata": deepcopy(
                metadata
                if isinstance(metadata, dict)
                else {}
            ),
        }

        with self._lock:

            self._chains.append(link)

            self.stats["links_added"] += 1

            self.stats["events_seen"] += 1

            self._event_index.setdefault(
                str(event),
                [],
            ).append(link["sequence"])

            self._handler_index.setdefault(
                str(handler),
                [],
            ).append(link["sequence"])

            if mutation is not None:

                self._mutation_index.setdefault(
                    str(mutation),
                    [],
                ).append(link["sequence"])

        return deepcopy(link)

    # ==========================================================
    # RECORD SYSTEM EVENT
    # ==========================================================

    def record_event(
        self,
        event,
        handler=None,
        mutation=None,
        side_effect=None,
        **kwargs,
    ):

        return self.add_link(
            event=event,
            handler=handler or "unknown",
            mutation=mutation,
            side_effect=side_effect,
            **kwargs,
        )

    # ==========================================================
    # LATEST
    # ==========================================================

    def latest(self, n=1):

        if n <= 0:
            return []

        with self._lock:

            return deepcopy(
                list(self._chains)[-n:]
            )

    # ==========================================================
    # FULL CHAIN
    # ==========================================================

    def full_chain(self):

        with self._lock:

            return deepcopy(
                list(self._chains)
            )

    # ==========================================================
    # TRACE EVENT
    # ==========================================================

    def trace_event(self, event_name):

        with self._lock:

            return [
                deepcopy(link)
                for link in self._chains
                if link.get("event") == event_name
            ]

    # ==========================================================
    # TRACE HANDLER
    # ==========================================================

    def trace_handler(self, handler_name):

        with self._lock:

            return [
                deepcopy(link)
                for link in self._chains
                if link.get("handler") == handler_name
            ]

    # ==========================================================
    # TRACE TRACK
    # ==========================================================

    def trace_track(self, track_id):

        with self._lock:

            return [
                deepcopy(link)
                for link in self._chains
                if link.get("track_id") == track_id
            ]

    # ==========================================================
    # TRACE QBIT
    # ==========================================================

    def trace_qbit(self, qbit_id):

        with self._lock:

            return [
                deepcopy(link)
                for link in self._chains
                if link.get("qbit_id") == qbit_id
            ]

    # ==========================================================
    # ERROR ANALYSIS
    # ==========================================================

    def _find_errors(self, links):

        errors = []

        for link in links:

            error = link.get("error")

            if error:

                errors.append(link)

                continue

            status = str(
                link.get("status") or ""
            ).upper()

            if status in {
                "ERROR",
                "FAILED",
                "FAILURE",
                "EXCEPTION",
            }:

                errors.append(link)

        return errors

    # ==========================================================
    # FAILURE PATTERN DETECTION
    # ==========================================================

    def _analyze_failure_patterns(self, links):

        errors = self._find_errors(links)

        if not errors:
            return []

        patterns = []

        event_counts = Counter(
            str(link.get("event"))
            for link in errors
        )

        handler_counts = Counter(
            str(link.get("handler"))
            for link in errors
        )

        mutation_counts = Counter(
            str(link.get("mutation"))
            for link in errors
            if link.get("mutation") is not None
        )

        for event, count in event_counts.items():

            if count >= 2:

                patterns.append(
                    {
                        "type": "repeated_event_failure",
                        "event": event,
                        "count": count,
                    }
                )

        for handler, count in handler_counts.items():

            if count >= 2:

                patterns.append(
                    {
                        "type": "repeated_handler_failure",
                        "handler": handler,
                        "count": count,
                    }
                )

        for mutation, count in mutation_counts.items():

            if count >= 2:

                patterns.append(
                    {
                        "type": "repeated_mutation_failure",
                        "mutation": mutation,
                        "count": count,
                    }
                )

        return patterns

    # ==========================================================
    # CAUSAL ANALYSIS
    # ==========================================================

    def analyze(self):

        with self._lock:

            links = list(
                self._chains
            )[-self.analysis_window:]

            self._analysis_cycle += 1

            cycle = self._analysis_cycle

        errors = self._find_errors(links)

        patterns = self._analyze_failure_patterns(
            links
        )

        handlers = Counter(
            str(link.get("handler"))
            for link in links
            if link.get("handler")
        )

        events = Counter(
            str(link.get("event"))
            for link in links
            if link.get("event")
        )

        mutations = Counter(
            str(link.get("mutation"))
            for link in links
            if link.get("mutation")
        )

        analysis = {
            "analysis_cycle": cycle,

            "timestamp": time.time(),

            "window_size": len(links),

            "total_links": len(self._chains),

            "errors": len(errors),

            "patterns": patterns,

            "top_events": events.most_common(10),

            "top_handlers": handlers.most_common(10),

            "top_mutations": mutations.most_common(10),

            "latest": deepcopy(
                links[-1]
                if links
                else None
            ),
        }

        with self._lock:

            self._last_analysis = deepcopy(
                analysis
            )

            self.stats[
                "analysis_cycles"
            ] += 1

        return analysis

    # ==========================================================
    # RECOMMENDATION ENGINE
    # ==========================================================

    def _build_recommendations(
        self,
        analysis,
    ):

        recommendations = []

        patterns = analysis.get(
            "patterns",
            [],
        )

        for pattern in patterns:

            pattern_type = pattern.get(
                "type"
            )

            if pattern_type == "repeated_handler_failure":

                recommendations.append(
                    self._recommend(
                        RECOMMEND_REPAIR,
                        target=pattern.get(
                            "handler"
                        ),
                        reason=(
                            "Handler has produced "
                            "repeated failures"
                        ),
                        evidence=pattern,
                    )
                )

            elif pattern_type == "repeated_mutation_failure":

                recommendations.append(
                    self._recommend(
                        RECOMMEND_INVESTIGATE,
                        target=pattern.get(
                            "mutation"
                        ),
                        reason=(
                            "Mutation repeatedly "
                            "failed"
                        ),
                        evidence=pattern,
                    )
                )

            elif pattern_type == "repeated_event_failure":

                recommendations.append(
                    self._recommend(
                        RECOMMEND_MONITOR,
                        target=pattern.get(
                            "event"
                        ),
                        reason=(
                            "Event repeatedly "
                            "entered failure state"
                        ),
                        evidence=pattern,
                    )
                )

        return recommendations

    # ==========================================================
    # BUILD RECOMMENDATION
    # ==========================================================

    def _recommend(
        self,
        action,
        target=None,
        reason=None,
        evidence=None,
        priority="normal",
        confidence=0.5,
    ):

        recommendation = {
            "recommendation_id": (
                f"CREC-{uuid.uuid4().hex[:12]}"
            ),

            "timestamp": time.time(),

            "source": self.name,

            "type": "command-recommendation",

            "action": action,

            "target": target,

            "reason": reason,

            "priority": priority,

            "confidence": confidence,

            "evidence": deepcopy(
                evidence
                if isinstance(evidence, dict)
                else {}
            ),

            # Explicit authority boundary.
            "execution": "QbitDialer",

            "executed": False,

            "requires_authority": True,
        }

        with self._lock:

            self._recommendations.append(
                recommendation
            )

            self.stats[
                "recommendations_generated"
            ] += 1

            self._last_recommendation = (
                deepcopy(recommendation)
            )

        return recommendation

    # ==========================================================
    # PUBLISH
    # ==========================================================

    def _publish(self, event_name, payload):

        bus = self.event_bus

        if bus is None:
            return False

        try:

            emit = getattr(
                bus,
                "emit",
                None,
            )

            if callable(emit):

                result = emit(
                    event_name,
                    payload,
                )

                if inspect.isawaitable(result):
                    return False

                return True

            publish = getattr(
                bus,
                "publish",
                None,
            )

            if callable(publish):

                result = publish(
                    event_name,
                    payload,
                )

                if inspect.isawaitable(result):
                    return False

                return True

            send = getattr(
                bus,
                "send",
                None,
            )

            if callable(send):

                result = send(
                    event_name,
                    payload,
                )

                if inspect.isawaitable(result):
                    return False

                return True

        except Exception as exc:

            self._record_error(
                f"EventBus publish failed: {exc}"
            )

        return False

    # ==========================================================
    # REPORT
    # ==========================================================

    def _build_report(
        self,
        analysis,
        recommendations,
    ):

        report = {
            "report_id": (
                f"CREPORT-{uuid.uuid4().hex[:12]}"
            ),

            "timestamp": time.time(),

            "source": self.name,

            "node": {
                "name": self.name,
                "role": self.role,
                "state": self.state,
                "version": self.version,
            },

            "analysis": deepcopy(
                analysis
            ),

            "recommendations": deepcopy(
                recommendations
            ),

            "authority": {
                "observer": self.name,
                "command_authority": "QbitDialer",
                "execution_allowed": False,
            },
        }

        with self._lock:

            self._reports.append(
                report
            )

            self._last_report = deepcopy(
                report
            )

            self.stats[
                "reports_generated"
            ] += 1

        return report

    # ==========================================================
    # SEND REPORT
    # ==========================================================

    def send_report(self, report):

        sent = False

        # ------------------------------------------------------
        # EventBus
        # ------------------------------------------------------

        if self._publish(
            "CAUSAL_REPORT",
            report,
        ):
            sent = True

        # ------------------------------------------------------
        # TrackSystem
        #
        # Data/telemetry only.
        # ------------------------------------------------------

        track = self.track_system

        if track is not None:

            try:

                method = getattr(
                    track,
                    "record",
                    None,
                )

                if callable(method):

                    result = method(
                        "CAUSAL_REPORT",
                        report,
                    )

                    if not inspect.isawaitable(
                        result
                    ):
                        sent = True

            except Exception as exc:

                self._record_error(
                    f"TrackSystem report failed: {exc}"
                )

        # ------------------------------------------------------
        # Registry
        #
        # Registry receives state/knowledge,
        # not commands.
        # ------------------------------------------------------

        registry = self.registry

        if registry is not None:

            try:

                method = getattr(
                    registry,
                    "register_service",
                    None,
                )

                if callable(method):

                    # Do NOT blindly register the report
                    # as a service. Only use explicit report
                    # recording APIs when available.

                    method = getattr(
                        registry,
                        "record_event",
                        None,
                    )

                    if callable(method):

                        result = method(
                            "CAUSAL_REPORT",
                            report,
                        )

                        if not inspect.isawaitable(
                            result
                        ):
                            sent = True

            except Exception as exc:

                self._record_error(
                    f"Registry report failed: {exc}"
                )

        return sent

    # ==========================================================
    # SEND RECOMMENDATIONS
    # ==========================================================

    def send_recommendations(
        self,
        recommendations,
    ):

        sent = 0

        dialer = self.qbit_dialer

        for recommendation in recommendations:

            delivered = False

            # --------------------------------------------------
            # Preferred proposal interfaces
            # --------------------------------------------------

            if dialer is not None:

                for method_name in (
                    "propose_command",
                    "recommend_command",
                    "submit_recommendation",
                    "receive_recommendation",
                ):

                    method = getattr(
                        dialer,
                        method_name,
                        None,
                    )

                    if callable(method):

                        try:

                            result = method(
                                deepcopy(
                                    recommendation
                                )
                            )

                            if inspect.isawaitable(
                                result
                            ):
                                delivered = False
                            else:
                                delivered = True

                            if delivered:
                                break

                        except Exception as exc:

                            self._record_error(
                                f"Dialer recommendation "
                                f"failed via {method_name}: "
                                f"{exc}"
                            )

            # --------------------------------------------------
            # EventBus fallback
            # --------------------------------------------------

            if not delivered:

                delivered = self._publish(
                    "COMMAND_RECOMMENDATION",
                    recommendation,
                )

            if delivered:

                sent += 1

                with self._lock:

                    self.stats[
                        "recommendations_sent"
                    ] += 1

            else:

                with self._lock:

                    self.stats[
                        "recommendations_failed"
                    ] += 1

        return sent

    # ==========================================================
    # COMPLETE ANALYSIS CYCLE
    # ==========================================================

    def run_analysis_cycle(self):

        try:

            analysis = self.analyze()

            recommendations = (
                self._build_recommendations(
                    analysis
                )
            )

            report = self._build_report(
                analysis,
                recommendations,
            )

            self.send_report(
                report
            )

            if recommendations:

                self.send_recommendations(
                    recommendations
                )

            return {
                "analysis": analysis,
                "recommendations": recommendations,
                "report": report,
            }

        except Exception as exc:

            self._record_error(
                f"Analysis cycle failed: {exc}"
            )

            return {
                "status": "failed",
                "error": str(exc),
            }

    # ==========================================================
    # INDEPENDENT ANALYSIS LOOP
    # ==========================================================

    def _analysis_loop(self):

        while True:

            with self._lock:

                if not self._running:
                    break

            try:

                self.run_analysis_cycle()

                with self._lock:

                    self._last_analysis = (
                        self._last_analysis
                        or time.time()
                    )

                    self._last_analysis = (
                        time.time()
                    )

            except Exception as exc:

                self._record_error(
                    f"Independent loop failed: {exc}"
                )

            time.sleep(
                self.analysis_interval
            )

    # ==========================================================
    # ERROR RECORDING
    # ==========================================================

    def _record_error(self, message):

        with self._lock:

            self._errors.append(
                {
                    "timestamp": time.time(),
                    "message": str(message),
                }
            )

            self.stats["errors"] += 1

        logger.warning(
            "[%s] %s",
            self.name,
            message,
        )

    # ==========================================================
    # VISUALIZATION
    # ==========================================================

    def visualize(self, last_n=None):

        with self._lock:

            chain = list(
                self._chains
            )

        if last_n:
            chain = chain[-last_n:]

        for link in chain:

            ts = link.get(
                "timestamp",
                0,
            )

            logger.info(
                "[%s] EVENT:%s → HANDLER:%s "
                "→ MUTATION:%s → SIDE_EFFECT:%s "
                "→ STATUS:%s",
                f"{ts:.3f}",
                link.get("event"),
                link.get("handler"),
                link.get("mutation"),
                link.get("side_effect"),
                link.get("status"),
            )

    # ==========================================================
    # REPORT HISTORY
    # ==========================================================

    def reports(self, n=None):

        with self._lock:

            reports = list(
                self._reports
            )

        if n is not None:
            reports = reports[-n:]

        return deepcopy(reports)

    # ==========================================================
    # RECOMMENDATION HISTORY
    # ==========================================================

    def recommendations(self, n=None):

        with self._lock:

            recommendations = list(
                self._recommendations
            )

        if n is not None:
            recommendations = (
                recommendations[-n:]
            )

        return deepcopy(
            recommendations
        )

    # ==========================================================
    # STATUS
    # ==========================================================

    def status(self):

        with self._lock:

            return {
                "name": self.name,

                "role": self.role,

                "node_type": self.node_type,

                "authority": self.authority,

                "version": self.version,

                "state": self.state,

                "running": self._running,

                "links_stored": len(
                    self._chains
                ),

                "reports_stored": len(
                    self._reports
                ),

                "recommendations_stored": len(
                    self._recommendations
                ),

                "analysis_cycle": (
                    self._analysis_cycle
                ),

                "last_analysis": (
                    self._last_analysis
                ),

                "last_report": (
                    self._last_report
                    is not None
                ),

                "last_recommendation": (
                    self._last_recommendation
                    is not None
                ),

                "runtime": {
                    "event_bus": (
                        type(
                            self.event_bus
                        ).__name__
                        if self.event_bus
                        else None
                    ),

                    "track_system": (
                        type(
                            self.track_system
                        ).__name__
                        if self.track_system
                        else None
                    ),

                    "registry": (
                        type(
                            self.registry
                        ).__name__
                        if self.registry
                        else None
                    ),

                    "registry_runtime": (
                        type(
                            self.registry_runtime
                        ).__name__
                        if self.registry_runtime
                        else None
                    ),

                    "qbit_dialer": (
                        type(
                            self.qbit_dialer
                        ).__name__
                        if self.qbit_dialer
                        else None
                    ),

                    "tools_orchestrator": (
                        type(
                            self.tools_orchestrator
                        ).__name__
                        if self.tools_orchestrator
                        else None
                    ),

                    "tool_network": (
                        type(
                            self.tool_network
                        ).__name__
                        if self.tool_network
                        else None
                    ),
                },

                "stats": deepcopy(
                    self.stats
                ),

                "errors": list(
                    self._errors
                )[-10:],
            }


# ==============================================================
# SINGLE TOOL INSTANCE
# ==============================================================

causal_chain = CausalChainTracer(
    auto_start=True
)


# ==============================================================
# COMPATIBILITY HELPERS
# ==============================================================

def add_causal_link(
    event,
    handler,
    mutation=None,
    side_effect=None,
    **kwargs,
):
    return causal_chain.add_link(
        event=event,
        handler=handler,
        mutation=mutation,
        side_effect=side_effect,
        **kwargs,
    )


def record_causal_event(
    event,
    handler=None,
    mutation=None,
    side_effect=None,
    **kwargs,
):
    return causal_chain.record_event(
        event=event,
        handler=handler,
        mutation=mutation,
        side_effect=side_effect,
        **kwargs,
    )


def get_causal_status():
    return causal_chain.status()


# ==============================================================
# EXPORTS
# ==============================================================

__all__ = [
    "CausalChainTracer",
    "causal_chain",
    "add_causal_link",
    "record_causal_event",
    "get_causal_status",
]