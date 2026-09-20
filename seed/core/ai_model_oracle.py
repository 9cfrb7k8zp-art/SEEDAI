# ==========================================================
# FILE: ai_model_oracle.py
# PATH: SEED_ROOT/seed/core/ai_model_oracle.py
# SYSTEM: SEED AI OS
# COMPONENT: Basic AI Oracle Adapter
# VERSION: 1.0.0
# PURPOSE: Bind the installed model SDK/local model to SEED
#          without creating a second command authority.
# ==========================================================

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

class AIModelOracle:
    """Small, lifecycle-safe model adapter owned by SEED's Oracle branch."""

    VERSION = "1.0.0"
    DEFAULT_MODEL_ROOT = Path(r"C:\AFM\models")
    DEFAULT_LOCK_ROOT = Path(r"C:\SEED_ROOT\models\oracle")

    def __init__(self, model_root: Optional[str] = None):
        self.model_root = Path(model_root or self.DEFAULT_MODEL_ROOT)
        self.lock_root = self.DEFAULT_LOCK_ROOT
        self.backend = "unavailable"
        self.model_path: Optional[str] = None
        self.model_id: Optional[str] = None
        self.last_prompt: Optional[str] = None
        self.last_response: Optional[str] = None
        self.status = self._discover()

    def _discover(self) -> Dict[str, Any]:
        transformers = importlib.util.find_spec("transformers") is not None
        torch = importlib.util.find_spec("torch") is not None
        safetensors = importlib.util.find_spec("safetensors") is not None
        openai_sdk = importlib.util.find_spec("openai") is not None

        candidates = []
        if self.model_root.exists():
            for path in self.model_root.iterdir():
                if path.is_dir():
                    if any(
                        (path / marker).exists()
                        for marker in ("config.json", "model.safetensors", "pytorch_model.bin")
                    ):
                        candidates.append(path)

        if candidates and transformers and torch:
            self.backend = "transformers-local"
            self.model_path = str(candidates[0])
            self.model_id = candidates[0].name
        elif openai_sdk:
            self.backend = "openai-sdk-ready"
        else:
            self.backend = "package-only"

        return {
            "transformers": transformers,
            "torch": torch,
            "safetensors": safetensors,
            "openai_sdk": openai_sdk,
            "backend": self.backend,
            "model_path": self.model_path,
            "model_id": self.model_id,
            "model_weights_present": bool(candidates),
        }

    def build_input(self, *, user_input: Any, weights: Dict[str, Any]) -> Dict[str, Any]:
        """Build semantic model input; values are system facts, not random numbers."""
        return {
            "type": "SEED_AI_MODEL_INPUT",
            "version": self.VERSION,
            "user_input": user_input,
            "weights": weights,
            "model": dict(self.status),
        }

    def answer(self, user_input: str, weights: Dict[str, Any]) -> Dict[str, Any]:
        """Use a local model only when real local weights are present.

        This method deliberately does not execute commands.  It returns an
        Oracle observation/proposal for the existing Qbit cognitive loop.
        """
        payload = self.build_input(user_input=user_input, weights=weights)
        self.last_prompt = json.dumps(payload, default=str)

        if self.backend == "transformers-local":
            return {
                "status": "MODEL_DISCOVERED_NOT_LOADED",
                "backend": self.backend,
                "model_path": self.model_path,
                "input": payload,
                "response": None,
            }

        if self.backend == "openai-sdk-ready":
            key = os.environ.get("OPENAI_API_KEY")
            key_path = Path(r"C:\AFM\.secrets\openai_key.txt")
            if not key and key_path.exists():
                try:
                    key = key_path.read_text(encoding="utf-8").strip()
                except Exception:
                    key = None
            if key:
                try:
                    from openai import OpenAI
                    model = os.environ.get("SEED_ORACLE_MODEL", "gpt-5.6-luna")
                    client = OpenAI(api_key=key)
                    response = client.responses.create(
                        model=model,
                        input=[
                            {
                                "role": "system",
                                "content": (
                                    "You are the basic AI model inside the SEED Oracle branch. "
                                    "Use only the supplied SEED system facts and user input. "
                                    "Return one concise answer. Do not execute commands."
                                ),
                            },
                            {
                                "role": "user",
                                "content": self.last_prompt,
                            },
                        ],
                    )
                    text = getattr(response, "output_text", None)
                    self.last_response = text
                    return {
                        "status": "MODEL_RESPONSE",
                        "backend": "openai-sdk",
                        "model": model,
                        "input": payload,
                        "response": text,
                    }
                except Exception as exc:
                    return {
                        "status": "MODEL_CALL_FAILED",
                        "backend": "openai-sdk",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "input": payload,
                        "response": None,
                    }

        return {
            "status": "NO_MODEL_BACKEND",
            "backend": self.backend,
            "input": payload,
            "response": None,
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "backend": self.backend,
            "model_path": self.model_path,
            "model_id": self.model_id,
            "status": dict(self.status),
            "last_response": self.last_response,
        }

def build_seed_input_weights(
    *,
    init_event: Any = None,
    seedcore: Any = None,
    oracle: Any = None,
    registry: Any = None,
    nodes: Any = None,
    node_registry: Any = None,
    health_monitor: Any = None,
    system_monitor: Any = None,
) -> Dict[str, Any]:
    """Produce the three SEED brain-input weight branches.

    Branch 1 = initialization/core/oracle.
    Branch 2 = modules/registry/nodes/health/system monitoring.
    Branch 3 = live user/system Qbit input.

    This function intentionally emits related semantic data and state
    descriptors. It does not invent entropy and does not authorize commands.
    """
    def state(obj: Any) -> Dict[str, Any]:
        if obj is None:
            return {"present": False}
        for name in ("status", "snapshot", "get_state"):
            fn = getattr(obj, name, None)
            if callable(fn):
                try:
                    value = fn()
                    if isinstance(value, dict):
                        return {"present": True, "type": type(obj).__name__, "state": value}
                except Exception:
                    pass
        return {"present": True, "type": type(obj).__name__}

    return {
        "weight_schema": "SEED_BRAIN_3_BRANCH_V1",
        "branch_1_init_core_oracle": {
            "init_event": state(init_event),
            "seedcore": state(seedcore),
            "oracle": state(oracle),
        },
        "branch_2_system_graph": {
            "registry": state(registry),
            "nodes": state(nodes),
            "node_registry": state(node_registry),
            "health_monitor": state(health_monitor),
            "system_monitor": state(system_monitor),
        },
        "branch_3_live_qbit": {
            "source": "Qbit",
            "lineage": "Qbit -> ComputeBrain -> TransformerBrain -> QbitDialer",
        },
    }
