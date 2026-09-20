# ==========================================================
# FILE: qbit_evolution_engine.py
# PATH: seed/core/evolution/qbit_evolution_engine.py
# VERSION: 2.1.0
# SYSTEM: EVOLUTION / QBIT COGNITION / ADAPTIVE GROWTH
# AUTHORITY: QbitDialer -> QbitQueueLoop
# ROLE: bounded evolution proposal engine
# ==========================================================

import logging
import threading
import time
import uuid
from typing import Any

from seed.core.qbit.qbit import Qbit

log = logging.getLogger("QbitEvolution")


class QbitEvolutionEngine:

    def __init__(
        self,
        queue_loop=None,
        memory_graph=None,
        *,
        qbit_dialer=None,
        event_bus=None,
        track_system=None,
        track_context=None,
        registry=None,
        node_registry=None,
        intent_engine=None,
        action_engine=None,
        analytics_engine=None,
        adaptive_engine=None,
        adaptive_priority_engine=None,
        encoder=None,
        decoder=None,
        heartbeat=None,
        module_registry=None,
        seedcore=None,
        skill_registry=None,
    ):
        self.queue_loop = queue_loop
        self.memory_graph = memory_graph
        self.qbit_dialer = qbit_dialer
        self.event_bus = event_bus
        self.track_system = track_system
        self.track_context = track_context
        self.registry = registry
        self.node_registry = node_registry
        self.intent_engine = intent_engine
        self.action_engine = action_engine
        self.analytics_engine = analytics_engine
        self.adaptive_engine = adaptive_engine
        self.adaptive_priority_engine = adaptive_priority_engine
        self.encoder = encoder
        self.decoder = decoder
        self.heartbeat = heartbeat
        self.module_registry = module_registry
        self.seedcore = seedcore
        self.skill_registry = skill_registry
        self.interval = 30.0
        self.last_run = time.time()
        self.running = False
        self.thread = None
        self.total_proposals = 0
        self.total_rejected = 0

    def bind_runtime(self, **runtime):
        for name in (
            "queue_loop", "memory_graph", "qbit_dialer", "event_bus",
            "track_system", "track_context", "registry", "node_registry",
            "intent_engine", "action_engine", "analytics_engine",
            "adaptive_engine", "adaptive_priority_engine", "encoder", "decoder",
            "heartbeat", "module_registry", "seedcore", "skill_registry",
        ):
            value = runtime.get(name)
            if value is not None:
                setattr(self, name, value)
        return self

    def _memory_stats(self):
        graph = self.memory_graph
        if graph is None:
            return {"nodes": 0, "edges": 0}
        stats = getattr(graph, "stats", None)
        if not callable(stats):
            return {"nodes": 0, "edges": 0}
        try:
            value = stats()
            return value if isinstance(value, dict) else {"nodes": 0, "edges": 0}
        except Exception as exc:
            log.debug("[QbitEvolution] memory stats failed | error=%s", exc)
            return {"nodes": 0, "edges": 0}

    def tick(self):
        now = time.time()
        if now - self.last_run < self.interval:
            return None
        self.last_run = now
        return self.evaluate_system(self._memory_stats())

    def evaluate_system(self, stats):
        nodes = int((stats or {}).get("nodes", 0) or 0)
        if nodes < 500:
            return self.spawn_exploration_qbit()
        if nodes < 2000:
            return self.spawn_optimization_qbit()
        return self.spawn_reflection_qbit()

    def _current_track_id(self):
        context = self.track_context
        for name in ("current", "get_current") if context else ():
            getter = getattr(context, name, None)
            if callable(getter):
                try:
                    value = getter()
                    if value:
                        return str(value)
                except Exception:
                    pass
        track = self.track_system
        getter = getattr(track, "current_track_id", None) if track else None
        if callable(getter):
            try:
                value = getter()
                if value:
                    return str(value)
            except Exception:
                pass
        return f"EVOLUTION-{uuid.uuid4().hex[:8]}"

    def _resolve_intent(self, proposed_intent):
        engine = self.intent_engine
        if engine is None:
            return proposed_intent
        for name in ("resolve_intent", "resolve", "normalize_intent", "get_intent"):
            resolver = getattr(engine, name, None)
            if not callable(resolver):
                continue
            try:
                value = resolver(proposed_intent)
                if isinstance(value, dict):
                    value = value.get("intent") or value.get("name")
                if value:
                    return str(value).upper()
            except Exception:
                continue
        return proposed_intent
    def _build_qbit(self, intent, priority, stats):
        qbit_id = f"QBIT.{uuid.uuid4().hex[:12]}"
        track_id = self._current_track_id()
        resolved_intent = self._resolve_intent(intent)
        metadata = {
            "origin": "EVOLUTION_ENGINE",
            "source": "EVOLUTION_ENGINE",
            "source_of_start": "EVOLUTION_ENGINE",
            "classification": "EVOLUTION",
            "intent": resolved_intent,
            "priority": priority,
            "memory_stats": dict(stats or {}),
        }
        return Qbit(
            qbit_id=qbit_id,
            payload={
                "intent": resolved_intent,
                "action": "NOOP",
                "data": {
                    "evolution": True,
                    "classification": "EVOLUTION",
                    "priority": priority,
                    "memory_stats": dict(stats or {}),
                },
                "meta": metadata,
            },
            upstream_track={
                "track_id": track_id,
                "origin": "EVOLUTION_ENGINE",
            },
            source="EVOLUTION_ENGINE",
            producer="QbitEvolutionEngine",
            creation_reason="bounded_evolution_proposal",
        )

    def _emit_observation(self, qbit):
        payload = {
            "qbit_id": getattr(qbit, "qbit_id", None),
            "track_id": getattr(getattr(qbit, "track", {}), "get", lambda *_: None)("track_id"),
            "source": "EVOLUTION_ENGINE",
            "classification": "EVOLUTION",
            "intent": getattr(qbit, "intent", None),
        }
        bus = self.event_bus
        if bus is not None:
            try:
                emitter = getattr(bus, "publish", None) or getattr(bus, "emit", None)
                if callable(emitter):
                    emitter("EVOLUTION_QBIT_PROPOSED", payload)
            except Exception:
                pass
        analytics = self.analytics_engine
        if analytics is not None:
            for name in ("record", "observe", "track", "record_event"):
                method = getattr(analytics, name, None)
                if not callable(method):
                    continue
                try:
                    method("EVOLUTION_QBIT_PROPOSED", payload)
                    break
                except TypeError:
                    try:
                        method(payload)
                        break
                    except Exception:
                        pass
                except Exception:
                    pass

    def _submit_qbit(self, qbit):
        dialer = self.qbit_dialer
        if dialer is not None:
            receive = getattr(dialer, "receive_qbit", None)
            if callable(receive):
                try:
                    result = receive(
                        qbit,
                        source="EVOLUTION_ENGINE",
                        source_of_start="EVOLUTION_ENGINE",
                    )
                    self.total_proposals += 1
                    return result
                except TypeError:
                    try:
                        result = receive(qbit)
                        self.total_proposals += 1
                        return result
                    except Exception:
                        pass
                except Exception:
                    pass
        loop = self.queue_loop
        authoritative_queue = getattr(loop, "queue_loop", None) if loop else None
        if authoritative_queue is None:
            self.total_rejected += 1
            log.warning("[QbitEvolution] no authoritative QbitQueueLoop bound")
            return False
        try:
            authoritative_queue.put(qbit)
            self.total_proposals += 1
            return True
        except Exception as exc:
            self.total_rejected += 1
            log.warning("[QbitEvolution] Qbit admission failed | error=%s", exc)
            return False

    def _spawn(self, intent, priority):
        qbit = self._build_qbit(intent, priority, self._memory_stats())
        self._emit_observation(qbit)
        return self._submit_qbit(qbit)

    def spawn_exploration_qbit(self):
        return self._spawn("DISCOVER_PATTERNS", "LOW")

    def spawn_optimization_qbit(self):
        return self._spawn("OPTIMIZE_PIPELINE", "NORMAL")

    def spawn_reflection_qbit(self):
        return self._spawn("SELF_REFLECT", "LOW")
    def start(self, interval=2.0):
        if self.running:
            return True
        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            args=(float(interval),),
            daemon=True,
            name="EvolutionEngine",
        )
        self.thread.start()
        return True

    def _run(self, interval):
        while self.running:
            try:
                self.tick()
            except Exception as exc:
                log.debug("[QbitEvolution] tick failed | error=%s", exc)
            time.sleep(max(0.1, interval))

    def stop(self, timeout=1.0):
        self.running = False
        thread = self.thread
        if thread is not None and thread.is_alive():
            thread.join(max(0.0, float(timeout)))
        self.thread = None
        return True

    def status(self):
        return {
            "module": "QbitEvolutionEngine",
            "system": "EVOLUTION",
            "running": self.running,
            "queue_loop_bound": self.queue_loop is not None,
            "dialer_bound": self.qbit_dialer is not None,
            "track_bound": self.track_system is not None,
            "registry_bound": self.registry is not None,
            "nodes_bound": self.node_registry is not None,
            "intent_bound": self.intent_engine is not None,
            "action_bound": self.action_engine is not None,
            "analytics_bound": self.analytics_engine is not None,
            "adaptive_bound": self.adaptive_engine is not None,
            "encoder_bound": self.encoder is not None,
            "decoder_bound": self.decoder is not None,
            "heartbeat_bound": self.heartbeat is not None,
            "module_registry_bound": self.module_registry is not None,
            "seedcore_bound": self.seedcore is not None,
            "skill_registry_bound": self.skill_registry is not None,
            "total_proposals": self.total_proposals,
            "total_rejected": self.total_rejected,
        }


def start_evolution_engine(queue_loop, memory_graph, **runtime):
    engine = QbitEvolutionEngine(queue_loop, memory_graph, **runtime)
    engine.start()
    return engine
