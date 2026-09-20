# ==========================================================
# FILE: qbit_compiler.py
# PATH: seed/core/compiler/qbit_compiler.py
# SYSTEM: COMPILER / QBIT / COGNITION
# VERSION: 2.0.0
# BUILD: QBIT-PIPELINE / DIALER-BRIDGED / BRAIN-AWARE
# PURPOSE: compile canonical Qbit cognition into deterministic binary
#          while preserving identity, provenance, classification,
#          intent, lineage, and cognitive-stage metadata.
# AUTHORITY: Qbit data -> compiler -> QbitEncoder -> cognition
#            -> TransformerBrain -> Intent/Action -> QbitDialer
# ==========================================================

from __future__ import annotations

import json
import struct
import time
import logging
from typing import Any, Dict, Optional

log = logging.getLogger("QbitCompiler")

INTENT_OPCODES = {
    "SCAN_ENVIRONMENT": 0x01,
    "ANALYZE_MEMORY": 0x02,
    "PLAN_ACTION": 0x03,
    "EXECUTE_TASK": 0x04,
    "REFLECT": 0x05,
    "OPTIMIZE_PIPELINE": 0x06,
    "DISCOVER_PATTERNS": 0x07,
    "HANDLE_ERROR": 0x08,
    "IDLE": 0x09,
    "OBSERVE_SYSTEM": 0x0A,
    "STATUS": 0x0B,
}

PRIORITY_CODES = {
    "LOW": 1,
    "NORMAL": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class QbitCompiler:

    VERSION = 2

    def __init__(
        self,
        *,
        qbit_dialer=None,
        qbit_queue_loop=None,
        qbit_encoder=None,
        qbit_decoder=None,
        compute_brain=None,
        transformer_brain=None,
        intent_engine=None,
        action_engine=None,
        analytics_engine=None,
        adaptive_engine=None,
        adaptive_priority_engine=None,
        event_bus=None,
        track_system=None,
        registry=None,
        node_registry=None,
    ):
        self.qbit_dialer = qbit_dialer
        self.qbit_queue_loop = qbit_queue_loop
        self.qbit_encoder = qbit_encoder
        self.qbit_decoder = qbit_decoder
        self.compute_brain = compute_brain
        self.transformer_brain = transformer_brain
        self.intent_engine = intent_engine
        self.action_engine = action_engine
        self.analytics_engine = analytics_engine
        self.adaptive_engine = adaptive_engine
        self.adaptive_priority_engine = adaptive_priority_engine
        self.event_bus = event_bus
        self.track_system = track_system
        self.registry = registry
        self.node_registry = node_registry
        self.compile_count = 0
        self.last_frame = None
        self.last_context = None

        self.intent_map = dict(INTENT_OPCODES)

    def bind_runtime(self, **runtime):
        fields = (
            "qbit_dialer", "qbit_queue_loop", "qbit_encoder",
            "qbit_decoder", "compute_brain", "transformer_brain",
            "intent_engine", "action_engine", "analytics_engine",
            "adaptive_engine", "adaptive_priority_engine", "event_bus",
            "track_system", "registry", "node_registry",
        )
        for name in fields:
            value = runtime.get(name)
            if value is not None:
                setattr(self, name, value)

        if self.qbit_encoder is not None:
            binder = getattr(self.qbit_encoder, "attach_runtime", None)
            if callable(binder):
                binder(
                    qbit_dialer=self.qbit_dialer,
                    qbit_queue_loop=self.qbit_queue_loop,
                    track_system=self.track_system,
                )

        self.last_context = self.runtime_status()
        return self

    def _field(self, value, name, default=None):
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    def _metadata(self, qbit, metadata=None):
        result = {}
        supplied = metadata if isinstance(metadata, dict) else {}
        qbit_meta = self._field(qbit, "metadata", {})
        if isinstance(qbit_meta, dict):
            result.update(qbit_meta)
        result.update(supplied)

        provenance = self._field(qbit, "provenance", {})
        if isinstance(provenance, dict):
            result.setdefault("provenance", provenance)

        source = self._field(qbit, "source", None)
        if source is None and isinstance(provenance, dict):
            source = provenance.get("source") or provenance.get("source_mode")

        classification = self._field(qbit, "classification", None)
        if classification is None:
            carrier_meta = self._field(qbit, "meta", {})
            if isinstance(carrier_meta, dict):
                classification = carrier_meta.get("classification")
        intent = self._field(qbit, "intent", None)
        track_id = self._field(qbit, "track_id", None)
        qbit_id = self._field(qbit, "qbit_id", None)
        parent_id = self._field(qbit, "parent_qbit_id", None)

        result.setdefault("qbit_id", qbit_id)
        result.setdefault("track_id", track_id)
        result.setdefault("parent_qbit_id", parent_id)
        result.setdefault("source", source or "UNKNOWN")
        result.setdefault("classification", classification or "UNKNOWN")
        result.setdefault("intent", intent or "IDLE")
        result.setdefault("generation", self._field(qbit, "generation", 0))
        return result

    def _resolve_intent(self, qbit, metadata):
        intent = self._field(qbit, "intent", None)
        if isinstance(intent, str) and intent.strip():
            return intent.strip().upper()
        candidate = metadata.get("intent")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().upper()

        engine = self.intent_engine
        for name in ("resolve_intent", "resolve", "normalize_intent", "get_intent"):
            method = getattr(engine, name, None) if engine is not None else None
            if callable(method):
                try:
                    result = method(qbit)
                    if isinstance(result, dict):
                        result = result.get("intent") or result.get("dominant")
                    if isinstance(result, str) and result.strip():
                        return result.strip().upper()
                except Exception:
                    log.debug("Intent resolution failed", exc_info=True)
        return "IDLE"

    def _resolve_classification(self, qbit, metadata):
        value = self._field(qbit, "classification", None)
        if value is None:
            value = metadata.get("classification")
        if value is None:
            value = metadata.get("class")
        return str(value).strip().upper() if value is not None else "UNKNOWN"

    def _build_context(self, qbit, metadata):
        provenance = self._field(qbit, "provenance", {})
        return {
            "qbit_id": self._field(qbit, "qbit_id", None),
            "task_id": self._field(qbit, "task_id", self._field(qbit, "id", None)),
            "track_id": self._field(qbit, "track_id", None),
            "parent_qbit_id": self._field(qbit, "parent_qbit_id", None),
            "source": metadata.get("source", "UNKNOWN"),
            "source_of_start": metadata.get("source_of_start", metadata.get("source", "UNKNOWN")),
            "classification": self._resolve_classification(qbit, metadata),
            "intent": self._resolve_intent(qbit, metadata),
            "provenance": provenance if isinstance(provenance, dict) else {},
            "generation": self._field(qbit, "generation", 0),
            "timestamp": self._field(qbit, "timestamp", time.time()),
        }

    def _encoder_frame(self, qbit, metadata):
        encoder = self.qbit_encoder
        if encoder is None:
            return None
        method = getattr(encoder, "process_qbit", None)
        if not callable(method):
            method = getattr(encoder, "encode", None)
        if not callable(method):
            return None
        try:
            return method(qbit, metadata=metadata)
        except TypeError:
            return method(qbit)
        except Exception:
            log.debug("QbitEncoder frame generation failed", exc_info=True)
            return None

    def compile(self, qbit, *, metadata=None):
        if qbit is None:
            raise ValueError("QbitCompiler requires an existing Qbit")

        meta = self._metadata(qbit, metadata)
        context = self._build_context(qbit, meta)
        intent = context["intent"]
        opcode = self.intent_map.get(intent, 0)
        priority = self.encode_priority(qbit)
        timestamp = float(context["timestamp"] or time.time())

        payload = self.encode_metadata({
            **meta,
            "source_of_start": context["source_of_start"],
            "classification": context["classification"],
            "intent": intent,
            "provenance": context["provenance"],
        })
        binary = struct.pack("!I I I d", opcode, self.VERSION, priority, timestamp)
        frame = binary + payload
        self.compile_count += 1
        self.last_frame = frame
        self.last_context = context
        self._observe("QBIT_COMPILED", context)
        return frame

    def compile_qbit(self, qbit, *, metadata=None):
        return self.compile(qbit, metadata=metadata)

    def encode_priority(self, qbit):
        priority = self._field(qbit, "priority", "NORMAL")
        if isinstance(priority, int):
            return max(1, min(4, priority))
        return PRIORITY_CODES.get(str(priority).upper(), 2)

    def encode_metadata(self, metadata):
        safe = self._json_safe(metadata if isinstance(metadata, dict) else {"value": metadata})
        data = json.dumps(safe, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
        return struct.pack("!I", len(data)) + data

    def decode(self, frame):
        if not isinstance(frame, (bytes, bytearray)):
            raise TypeError("Compiled Qbit frame must be bytes")
        if len(frame) < struct.calcsize("!I I I d") + 4:
            raise ValueError("Compiled Qbit frame is incomplete")
        opcode, version, priority, timestamp = struct.unpack("!I I I d", frame[:20])
        size = struct.unpack("!I", frame[20:24])[0]
        end = 24 + size
        if end > len(frame):
            raise ValueError("Compiled Qbit metadata exceeds frame size")
        metadata = json.loads(frame[24:end].decode("utf-8"))
        intent = next((name for name, value in self.intent_map.items() if value == opcode), "UNKNOWN")
        return {
            "compiler_version": version,
            "opcode": opcode,
            "intent": intent,
            "priority": priority,
            "timestamp": timestamp,
            "metadata": metadata if isinstance(metadata, dict) else {},
        }

    def process_qbit(self, qbit, *, metadata=None):
        meta = self._metadata(qbit, metadata)
        context = self._build_context(qbit, meta)
        compiled = self.compile(qbit, metadata=meta)
        decoded = self.decode(compiled)
        encoder_packet = self._encoder_frame(qbit, meta)
        return {
            "type": "CompiledQbit",
            "stage": "COMPILER",
            "qbit": qbit,
            "compiled": compiled,
            "decoded": decoded,
            "qbit_frame": encoder_packet,
            "qbit_id": context["qbit_id"],
            "task_id": context["task_id"],
            "track_id": context["track_id"],
            "source": context["source"],
            "source_of_start": context["source_of_start"],
            "classification": context["classification"],
            "intent": context["intent"],
            "provenance": context["provenance"],
            "command_authority": "QbitDialer",
            "queue_authority": "QbitQueueLoop",
            "command_admitted": False,
            "command_executed": False,
        }

    def send_to_dialer(self, qbit, *, metadata=None):
        dialer = self.qbit_dialer
        if dialer is None:
            raise RuntimeError("QbitDialer is not bound")
        packet = self.process_qbit(qbit, metadata=metadata)
        receiver = getattr(dialer, "receive_qbit", None)
        if not callable(receiver):
            receiver = getattr(dialer, "_process_received_qbit", None)
        if not callable(receiver):
            raise RuntimeError("QbitDialer exposes no Qbit receive path")
        return packet, receiver(qbit)

    def _observe(self, event, payload):
        analytics = self.analytics_engine
        for name in ("record", "observe", "track", "record_event"):
            method = getattr(analytics, name, None) if analytics is not None else None
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
        emit = getattr(bus, "emit", None) if bus is not None else None
        if callable(emit):
            try:
                emit(event, payload)
            except Exception:
                pass

    @staticmethod
    def _json_safe(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): QbitCompiler._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [QbitCompiler._json_safe(v) for v in value]
        enum_value = getattr(value, "value", None)
        if enum_value is not None:
            return QbitCompiler._json_safe(enum_value)
        return str(value)

    def runtime_status(self):
        return {
            "version": self.VERSION,
            "compile_count": self.compile_count,
            "dialer_bound": self.qbit_dialer is not None,
            "queue_loop_bound": self.qbit_queue_loop is not None,
            "encoder_bound": self.qbit_encoder is not None,
            "decoder_bound": self.qbit_decoder is not None,
            "compute_brain_bound": self.compute_brain is not None,
            "transformer_brain_bound": self.transformer_brain is not None,
            "intent_engine_bound": self.intent_engine is not None,
            "action_engine_bound": self.action_engine is not None,
            "analytics_engine_bound": self.analytics_engine is not None,
            "adaptive_engine_bound": self.adaptive_engine is not None,
            "adaptive_priority_bound": self.adaptive_priority_engine is not None,
            "registry_bound": self.registry is not None,
            "node_registry_bound": self.node_registry is not None,
            "track_system_bound": self.track_system is not None,
        }


def create_qbit_compiler(**runtime):
    return QbitCompiler(**runtime)
