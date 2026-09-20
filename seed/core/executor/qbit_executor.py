# ==========================================================
# FILE: qbit_executor.py
# PATH: seed/core/executor/qbit_executor.py
# VERSION: 2.0.0
# ROLE: Qbit execution boundary
# AUTHORITY: QbitDialer command admission / QbitQueueLoop transport
# PURPOSE: Resolve and execute an admitted Qbit through the router
# ==========================================================

import inspect
import time


class QbitExecutor:

    def __init__(
        self,
        router,
        *,
        qbit_dialer=None,
        qbit_queue_loop=None,
        heartbeat=None,
        event_bus=None,
        registry=None,
        node_registry=None,
        intent_engine=None,
        action_engine=None,
        analytics_engine=None,
        adaptive_engine=None,
        encoder=None,
        decoder=None,
    ):
        self.router = router
        self.qbit_dialer = qbit_dialer
        self.qbit_queue_loop = qbit_queue_loop
        self.heartbeat = heartbeat
        self.event_bus = event_bus
        self.registry = registry
        self.node_registry = node_registry
        self.intent_engine = intent_engine
        self.action_engine = action_engine
        self.analytics_engine = analytics_engine
        self.adaptive_engine = adaptive_engine
        self.encoder = encoder
        self.decoder = decoder
        self.last_result = None
        self.last_error = None
        self.execution_count = 0
        self.failure_count = 0

    def bind_runtime(self, **runtime):
        for name in (
            "qbit_dialer", "qbit_queue_loop", "heartbeat", "event_bus",
            "registry", "node_registry", "intent_engine", "action_engine",
            "analytics_engine", "adaptive_engine", "encoder", "decoder",
        ):
            value = runtime.get(name)
            if value is not None:
                setattr(self, name, value)
        return self

    def _context(self, qbit):
        data = getattr(qbit, "data", None)
        if not isinstance(data, dict):
            data = qbit if isinstance(qbit, dict) else {}
        context = {
            "qbit_id": getattr(qbit, "qbit_id", None),
            "track_id": getattr(qbit, "track_id", None),
            "source": data.get("source", getattr(qbit, "source", None)),
            "source_of_start": data.get("source_of_start"),
            "classification": data.get("classification", getattr(qbit, "classification", None)),
            "intent": data.get("intent", getattr(qbit, "intent", None)),
            "action": data.get("action", getattr(qbit, "action", None)),
        }
        return context

    def execute(self, qbit):
        if qbit is None:
            raise ValueError("QbitExecutor requires a qbit")

        context = self._context(qbit)
        handler = self.router.resolve(qbit)

        if not handler:
            self.failure_count += 1
            self.last_error = f"No handler for {context['intent']}:{context['action']}"
            raise RuntimeError(self.last_error)

        try:
            self.execution_count += 1
            result = handler(qbit)
            if inspect.isawaitable(result):
                self.last_result = result
                return result
            self.last_result = result
            self.last_error = None
            self._observe("QBIT_EXECUTION_RESULT", qbit, result, context)
            return result
        except Exception as exc:
            self.failure_count += 1
            self.last_error = str(exc)
            flags = getattr(qbit, "flags", None)
            if isinstance(flags, dict):
                flags["execution_error"] = str(exc)
                flags["execution_error_type"] = type(exc).__name__
            self._observe("QBIT_EXECUTION_ERROR", qbit, None, context)
            return None

    def _observe(self, event, qbit, result, context):
        payload = {
            "event": event,
            "timestamp": time.time(),
            **context,
            "result": result,
        }
        analytics = self.analytics_engine
        if analytics is not None:
            for name in ("record", "observe", "track", "record_event"):
                method = getattr(analytics, name, None)
                if callable(method):
                    try:
                        method(payload)
                        break
                    except TypeError:
                        try:
                            method(event, payload)
                            break
                        except Exception:
                            pass
                    except Exception:
                        pass
        bus = self.event_bus
        if bus is not None:
            for name in ("publish", "emit"):
                method = getattr(bus, name, None)
                if callable(method):
                    try:
                        method(event, payload)
                        break
                    except Exception:
                        pass

    def status(self):
        return {
            "router_bound": self.router is not None,
            "qbit_dialer_bound": self.qbit_dialer is not None,
            "qbit_queue_loop_bound": self.qbit_queue_loop is not None,
            "heartbeat_bound": self.heartbeat is not None,
            "sregistry_bound": self.registry is not None,
            "node_registry_bound": self.node_registry is not None,
            "intent_engine_bound": self.intent_engine is not None,
            "action_engine_bound": self.action_engine is not None,
            "analytics_engine_bound": self.analytics_engine is not None,
            "adaptive_engine_bound": self.adaptive_engine is not None,
            "encoder_bound": self.encoder is not None,
            "decoder_bound": self.decoder is not None,
            "execution_count": self.execution_count,
            "failure_count": self.failure_count,
        }
