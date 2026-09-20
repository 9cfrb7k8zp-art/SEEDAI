# =============================================================
# SEED Skills Package Bootstrap
# File: SEED_ROOT/seed/skills/__init__.py
# =============================================================
import time
import logging
import threading
import json
from pathlib import Path
import importlib
import pkgutil
from SRegistry import register_node

# ------------------------------
# Paths and registry
# ------------------------------
THIS_PATH = Path(__file__).parent

register_node(
    name="seed.skills",
    path=THIS_PATH,
    parent=THIS_PATH.parent,
    group="core",
    role="kernel-skills",
    update_domain="core-runtime",
)

logger = logging.getLogger("SEED-SKILLS")
logger.setLevel(logging.INFO)

STATE_FILE = THIS_PATH / "skills_runtime_state.json"

# ------------------------------
# Skill store
# ------------------------------
SKILLS = {}
_skills_lock = threading.Lock()


def register_skill(name: str, skill_cls, path: Path | None = None):
    """Register a skill with metadata"""
    with _skills_lock:
        SKILLS[name] = {
            "class": skill_cls,
            "status": "initialized",
            "boot_time": time.time(),
            "path": str(path) if path else None,
            "instance": None,
        }
        logger.info(f"[SEED-SKILLS] Registered skill: {name}")
        _export_state()


def _export_state():
    """Persist SKILLS snapshot to JSON"""
    try:
        with _skills_lock:
            snapshot = {k: v.copy() for k, v in SKILLS.items()}
            snapshot["timestamp"] = time.time()
            with STATE_FILE.open("w") as f:
                json.dump(snapshot, f, indent=2)
    except Exception as e:
        logger.warning(f"[SEED-SKILLS] Failed to export state: {e}")


# ------------------------------
# Recursive discovery
# ------------------------------
def discover_skills(base_path: Path = THIS_PATH, package_prefix: str = "seed.skills"):
    """Recursively discover skills in subfolders"""
    try:
        for finder, mod_name, ispkg in pkgutil.iter_modules([str(base_path)]):
            if mod_name == "__init__":
                continue
            fq_module = f"{package_prefix}.{mod_name}"
            module = importlib.import_module(fq_module)

            # Scan for classes with `execute()`
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and callable(getattr(attr, "execute", None)):
                    register_skill(attr_name, attr, path=base_path / mod_name)

            # Recurse into subpackages
            if ispkg:
                discover_skills(base_path / mod_name, fq_module)

    except Exception as e:
        logger.warning(f"[SEED-SKILLS] Skill discovery failed: {e}")


# ------------------------------
# Autonomous monitor
# ------------------------------
def _monitor_loop(interval: float = 5.0):
    while True:
        try:
            with _skills_lock:
                for name, info in SKILLS.items():
                    instance = info.get("instance")
                    # Instantiate skill if not done yet
                    if instance is None:
                        try:
                            instance = info["class"]()
                            info["instance"] = instance
                        except Exception as e:
                            logger.warning(f"[SEED-SKILLS] Failed to instantiate {name}: {e}")
                            info["status"] = "init_error"
                            continue

                    # Update skill status if available
                    if hasattr(instance, "status") and callable(getattr(instance, "status")):
                        try:
                            info["status"] = instance.status()
                        except Exception as e:
                            info["status"] = f"status_error: {e}"

            _export_state()
        except Exception as e:
            logger.warning(f"[SEED-SKILLS] Monitor error: {e}")
        finally:
            time.sleep(interval)


_monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
_monitor_thread.start()

# ------------------------------
# Shortcut for AI / external modules
# ------------------------------
__all__ = ["register_skill", "discover_skills", "SKILLS"]
