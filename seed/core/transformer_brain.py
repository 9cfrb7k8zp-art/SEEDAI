# ==========================================================
# FILE: transformer_brain.py
# PATH: SEED_ROOT/seed/core/transformer_brain.py
# VERSION: 25.0.4-FACADE
# BUILD: LEGACY-IMPORT-COMPATIBILITY / SINGLE-BRAIN-AUTHORITY
#
# The former v4.9 implementation is preserved as
# transformer_brain_legacy_blueprint.py.
# The active TransformerBrain lives under dialers.
# ==========================================================

from seed.core.dialers.transformerbrain import (
    TransformerBrain,
    QuantumMathEngine,
)

__all__ = ["TransformerBrain", "QuantumMathEngine"]
