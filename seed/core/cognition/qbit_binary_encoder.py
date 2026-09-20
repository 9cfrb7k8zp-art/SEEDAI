# ==========================================================
# FILE: qbit_binary_encoder.py
# PATH: seed/core/cognition/qbit_binary_encoder.py
#
# SYSTEM: SEED AI OS
# COMPONENT: QbitBinaryEncoder
# VERSION: 2.0.0
# BUILD: SAFE-SERIALIZATION / DETERMINISTIC / NON-BLOCKING
#
# PURPOSE:
# ----------------------------------------------------------
# Convert a Qbit-like object into a compact, JSON-backed
# binary representation.
#
# DESIGN RULES:
#   - NEVER mutate the Qbit
#   - NEVER execute Qbit code
#   - NEVER start threads/tasks
#   - NEVER access EventBus
#   - NEVER control QbitDialer
#   - NEVER create runtime side effects
#   - tolerate dict/object Qbits
#   - tolerate non-JSON-native values
#   - deterministic output
#   - preserve Track/Channel metadata when available
#
# ==========================================================

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional


log = logging.getLogger("QbitBinaryEncoder")


class QbitBinaryEncoder:


    VERSION = "2.0.0"

    # ------------------------------------------------------
    # Dual-pi metadata
    # ------------------------------------------------------

    PI_STD = 3.14159
    PI_ALT = 3.33

    # ------------------------------------------------------
    # Initialization
    # ------------------------------------------------------

    def __init__(
        self,
        *,
        ensure_ascii: bool = False,
        sort_keys: bool = True,
    ) -> None:

        self.ensure_ascii = bool(ensure_ascii)
        self.sort_keys = bool(sort_keys)

    # ======================================================
    # PUBLIC API
    # ======================================================

    def encode(self, qbit: Any) -> bytes:
    

        payload = self.to_dict(qbit)

        try:

            encoded = json.dumps(
                payload,
                ensure_ascii=self.ensure_ascii,
                sort_keys=self.sort_keys,
                separators=(",", ":"),
                default=self._json_default,
            )

            return encoded.encode("utf-8")

        except Exception as exc:

            log.error(
                "[QbitBinaryEncoder] "
                "Encoding failed: %s",
                exc,
            )

            # Last-resort safe payload.
            fallback = {
                "version": self.VERSION,
                "encoding": "qbit-json-utf8",
                "error": "serialization_failed",
                "error_type": type(exc).__name__,
            }

            return json.dumps(
                fallback,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")

    # ======================================================
    # DECODE
    # ======================================================

    def decode(
        self,
        data: bytes,
    ) -> Optional[Dict[str, Any]]:
        

        if not isinstance(data, (bytes, bytearray)):
            return None

        try:

            text = bytes(data).decode("utf-8")

            value = json.loads(text)

            if not isinstance(value, dict):
                return None

            return value

        except Exception as exc:

            log.debug(
                "[QbitBinaryEncoder] "
                "Decode failed: %s",
                exc,
            )

            return None

    # ======================================================
    # QBIT -> DICT
    # ======================================================

    def to_dict(
        self,
        qbit: Any,
    ) -> Dict[str, Any]:
        

        payload = {
            "version": self.VERSION,
            "encoding": "qbit-json-utf8",

            # ------------------------------------------------
            # Identity
            # ------------------------------------------------

            "id": self._get(
                qbit,
                "id",
            ),

            "task_id": self._get(
                qbit,
                "task_id",
            ),

            # ------------------------------------------------
            # Intent
            # ------------------------------------------------

            "intent": self._get(
                qbit,
                "intent",
            ),

            "skill": self._get(
                qbit,
                "skill",
            ),

            "command": self._get(
                qbit,
                "command",
            ),

            "command_type": self._get(
                qbit,
                "command_type",
            ),

            "priority": self._get(
                qbit,
                "priority",
            ),

            # ------------------------------------------------
            # State
            # ------------------------------------------------

            "state": self._safe_value(
                self._get(
                    qbit,
                    "state",
                )
            ),

            # ------------------------------------------------
            # Payload
            # ------------------------------------------------

            "data": self._safe_value(
                self._get(
                    qbit,
                    "payload",
                    fallback=self._get(
                        qbit,
                        "data",
                    ),
                )
            ),

            # ------------------------------------------------
            # Track metadata
            # ------------------------------------------------

            "track": self._safe_value(
                self._get(
                    qbit,
                    "track",
                )
            ),

            "track_id": self._get(
                qbit,
                "track_id",
            ),

            "channel_id": self._get(
                qbit,
                "channel_id",
            ),

            "parent_id": self._get(
                qbit,
                "parent_id",
            ),

            # ------------------------------------------------
            # Source metadata
            # ------------------------------------------------

            "source": self._get(
                qbit,
                "source",
            ),

            "module": self._get(
                qbit,
                "module",
            ),

            "component": self._get(
                qbit,
                "component",
            ),

            # ------------------------------------------------
            # Timing
            # ------------------------------------------------

            "timestamp": self._get(
                qbit,
                "timestamp",
            ),

            # ------------------------------------------------
            # Diagnostic flags
            # ------------------------------------------------

            "flags": self._safe_value(
                self._get(
                    qbit,
                    "flags",
                    fallback={},
                )
            ),

            # ------------------------------------------------
            # Dual-pi metadata
            # ------------------------------------------------

            "pi_std": self.PI_STD,
            "pi_alt": self.PI_ALT,
        }

        return self._safe_value(payload)

    # ======================================================
    # FIELD ACCESS
    # ======================================================

    @staticmethod
    def _get(
        qbit: Any,
        key: str,
        fallback: Any = None,
    ) -> Any:
        

        if qbit is None:
            return fallback

        if isinstance(qbit, dict):

            return qbit.get(
                key,
                fallback,
            )

        try:

            value = getattr(
                qbit,
                key,
            )

            return value

        except AttributeError:

            return fallback

        except Exception:

            return fallback

    # ======================================================
    # SAFE VALUE CONVERSION
    # ======================================================

    def _safe_value(
        self,
        value: Any,
    ) -> Any:
       

        if value is None:
            return None

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):
            return value

        if isinstance(value, bytes):

            return {
                "__type__": "bytes",
                "encoding": "base64",
                "data": value.hex(),
            }

        if isinstance(value, dict):

            result = {}

            for key, item in value.items():

                safe_key = str(key)

                result[safe_key] = (
                    self._safe_value(item)
                )

            return result

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return [
                self._safe_value(item)
                for item in value
            ]

        # ----------------------------------------------
        # Enum-like objects
        # ----------------------------------------------

        enum_value = getattr(
            value,
            "value",
            None,
        )

        if enum_value is not None:

            if enum_value is not value:

                return self._safe_value(
                    enum_value
                )

        # ----------------------------------------------
        # Objects with __dict__
        # ----------------------------------------------

        attributes = getattr(
            value,
            "__dict__",
            None,
        )

        if isinstance(
            attributes,
            dict,
        ):

            return {
                str(key): self._safe_value(item)
                for key, item in attributes.items()
                if not str(key).startswith("_")
            }

        # ----------------------------------------------
        # Final safe representation
        # ----------------------------------------------

        return str(value)

    # ======================================================
    # JSON FALLBACK
    # ======================================================

    @staticmethod
    def _json_default(
        value: Any,
    ) -> Any:
        

        if isinstance(value, bytes):

            return {
                "__type__": "bytes",
                "encoding": "hex",
                "data": value.hex(),
            }

        enum_value = getattr(
            value,
            "value",
            None,
        )

        if enum_value is not None:

            return enum_value

        return str(value)

    # ======================================================
    # SIZE
    # ======================================================

    def encoded_size(
        self,
        qbit: Any,
    ) -> int:
        
        return len(
            self.encode(qbit)
        )

    # ======================================================
    # VALIDATION
    # ======================================================

    def validate(
        self,
        qbit: Any,
    ) -> bool:
        

        try:

            encoded = self.encode(qbit)

            decoded = self.decode(
                encoded
            )

            return isinstance(
                decoded,
                dict,
            )

        except Exception:

            return False

    # ======================================================
    # REPRESENTATION
    # ======================================================

    def __repr__(self) -> str:

        return (
            "QbitBinaryEncoder("
            f"version={self.VERSION!r}, "
            f"pi_std={self.PI_STD}, "
            f"pi_alt={self.PI_ALT}"
            ")"
        )


# ==========================================================
# MODULE EXPORTS
# ==========================================================

__all__ = [
    "QbitBinaryEncoder",
]