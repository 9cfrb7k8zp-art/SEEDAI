# ==========================================================
# FILE: module_registry.py
# PATH: SEED_ROOT/seed/skills/module_registry.py
# MODULE: SEED Module Registry (SEED AI-ready)
# VERSION: 0.4 (TrackID + Async-safe + Unknown Handling + Lineage)
# UPDATED: 2026-01-02
# ==========================================================

import logging
import time
import uuid
from typing import Optional, Dict, List

logger = logging.getLogger("ModuleRegistry")


class ModuleRegistry:
    _modules: Dict[str, Dict] = {}  # module_id -> metadata dict

    @classmethod
    def register(cls, module_id = (), name = None, parent_id = None):
        if module_id not in cls._modules:
            cls._modules[module_id] = {
                "name": name or module_id,
                "parent_id": parent_id,
                "registered_at": time.time(),
                "lineage": [parent_id] if parent_id else [],
            }
            logger.info(f"[ModuleRegistry] Registered module: {module_id}")
        else:
            # Update metadata if provided
            meta = cls._modules[module_id]
            if name:
                meta["name"] = name
            if parent_id and parent_id not in meta["lineage"]:
                meta["lineage"].append(parent_id)
                meta["parent_id"] = parent_id
            logger.debug(f"[ModuleRegistry] Updated module metadata: {module_id}")

    @classmethod
    def list_all(cls) -> List[str]:
        return list(cls._modules.keys())

    @classmethod
    def get_metadata(cls, module_id: str) -> Optional[Dict]:
        return cls._modules.get(module_id)

    @classmethod
    def exists(cls, module_id: str) -> bool:
        return module_id in cls._modules


# ----------------------------------------------------------
# Track unknown modules safely with optional TrackID fallback
# ----------------------------------------------------------
def handle_skill_done(module_id = None, note = [], parent_id = []):

    if module_id is None or not ModuleRegistry.exists(module_id):
        temp_id = f"UNK-{str(uuid.uuid4())[:8]}"
        logger.warning(
            f"[TRACK-FREEZE] SKILL-DONE called for unknown module '{module_id}' | assigned temp TrackID={temp_id} | note={note}"
        )
        # Register unknown module to prevent repeated warnings
        ModuleRegistry.register(temp_id, name="UNKNOWN_MODULE", parent_id=parent_id)
        return temp_id

    logger.info(f"[ModuleRegistry] SKILL-DONE confirmed for module {module_id} | note={note}")
    return module_id


# ----------------------------------------------------------
# Optional: helper to batch register modules with parent linkage
# ----------------------------------------------------------
def register_modules_bulk(modules: List[Dict]):
    for mod in modules:
        ModuleRegistry.register(
            module_id=mod.get("module_id"),
            name=mod.get("name"),
            parent_id=mod.get("parent_id")
        )


# ==========================================================
# END OF FILE
# ==========================================================
