# ==========================================================
# FILE: instruction_decoder.py
# PATH: SEED_ROOT/seed/systemutils/instruction_decoder.py
# VERSION: 5.6 (FULL QBIT + VECTOR | LIMPMODE | ASYNC-SAFE | EVENTBUS-DEFERRED)
# UPDATED: 2026-01-04
# ==========================================================

from __future__ import annotations

import asyncio
import time
import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger("InstructionDecoder")
logger.setLevel(logging.INFO)


# ==========================================================
# INSTRUCTION SHAPE
# ==========================================================

class DecodedInstruction(dict):
    pass


# ==========================================================
# INSTRUCTION DECODER
# ==========================================================

class InstructionDecoder:
    def __init__(
        self,
        *,
        memory_crystallizer=None,
        event_bus=None,
        limp_mode: bool = False,
        confidence_floor: float = 0.25,
    ):
        self.event_bus = event_bus
        self.limp_mode = limp_mode
        self.confidence_floor = confidence_floor
        self.memory_crystallizer = memory_crystallizer
        self._lock = asyncio.Lock()

        logger.info("[InstructionDecoder] Initialized")

    # ------------------------------------------------------
    # ENTRY POINT
    # ------------------------------------------------------


    def decode(self, payload):
        if not payload:
            return

        # record for learning
        if self.memory_crystallizer:
            self.memory_crystallizer.record(payload)

        # act if it contains an event
        if isinstance(payload, dict) and "event" in payload:
            try:
                self.event_bus.emit(
                    payload["event"],
                    payload.get("data", payload)
                )
            except Exception as e:
                logger.warning(f"[InstructionDecoder] emit failed: {e}")
    async def decode(self, qbit) -> List[DecodedInstruction]:
        if self.limp_mode or not qbit:
            return []

        async with self._lock:
            instructions = self._extract(qbit)
            self._emit(instructions, qbit)
            return instructions

    # ------------------------------------------------------
    # EXTRACTION LOGIC (NON-BINARY)
    # ------------------------------------------------------

    def _extract(self, qbit) -> List[DecodedInstruction]:
        instructions: List[DecodedInstruction] = []

        payload = getattr(qbit, "payload", None)
        vector = getattr(qbit, "vector", None)
        flags = getattr(qbit, "flags", {})
        track = getattr(qbit, "track", {})

        # ---- payload driven decoding ----
        if isinstance(payload, dict):
            for k, v in payload.items():
                confidence = self._estimate_confidence(v)
                if confidence >= self.confidence_floor:
                    instructions.append(
                        self._build_instruction(
                            kind="payload",
                            verb=str(k),
                            target=v,
                            confidence=confidence,
                            track=track,
                        )
                    )

        # ---- vector driven decoding ----
        if isinstance(vector, dict):
            qval = vector.get("qbit_value")
            if qval is not None:
                instructions.append(
                    self._build_instruction(
                        kind="vector",
                        verb="adjust",
                        target="state",
                        confidence=0.3 + (abs(qval) % 100) / 500.0,
                        track=track,
                        meta={"qbit_value": qval},
                    )
                )

        # ---- flag driven decoding ----
        if flags:
            instructions.append(
                self._build_instruction(
                    kind="flag",
                    verb="observe",
                    target=list(flags.keys()),
                    confidence=min(0.2 + len(flags) * 0.1, 0.6),
                    track=track,
                )
            )

        return instructions

    # ------------------------------------------------------
    # CONFIDENCE ESTIMATOR
    # ------------------------------------------------------

    def _estimate_confidence(self, value: Any) -> float:
        try:
            if isinstance(value, bool):
                return 0.6
            if isinstance(value, (int, float)):
                return min(abs(value) / 10.0, 0.7)
            if isinstance(value, str):
                return min(len(value) / 100.0, 0.5)
            if isinstance(value, (list, tuple, dict)):
                return min(len(value) * 0.1, 0.6)
        except Exception:
            return 0.2

        return 0.15

    # ------------------------------------------------------
    # INSTRUCTION BUILDER
    # ------------------------------------------------------

    def _build_instruction(
        self,
        *,
        kind: str,
        verb: str,
        target: Any,
        confidence: float,
        track: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
    ) -> DecodedInstruction:
        return DecodedInstruction(
            {
                "kind": kind,
                "verb": verb,
                "target": target,
                "confidence": round(confidence, 3),
                "track_id": track.get("track_id"),
                "timestamp": time.time(),
                "meta": meta or {},
            }
        )

    # ------------------------------------------------------
    # SAFE EMIT
    # ------------------------------------------------------

    def _emit(self, instructions: List[DecodedInstruction], qbit) -> None:
        if not self.event_bus or not instructions:
            return

        try:
            self.event_bus.publish(
                "INSTRUCTION_DECODED",
                payload={
                    "instructions": instructions,
                    "track_id": getattr(qbit, "track", {}).get("track_id"),
                    "timestamp": time.time(),
                },
                source="InstructionDecoder",
            )
        except Exception as e:
            logger.debug(f"[InstructionDecoder] emit failed: {e}")

    # ------------------------------------------------------

    def __repr__(self):
        return (
            f"InstructionDecoder("
            f"confidence_floor={self.confidence_floor}, "
            f"limp_mode={self.limp_mode}"
            f")"
        )
