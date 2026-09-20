# ==========================================================
# FILE: autofix_skill_loader.py
# PATH: seed/core/integration/autofix_skill_loader.py
#
# PURPOSE:
# - Dynamically load AutoFix intelligence modules
# - Hot-reload capable
# - Deterministic priority ordering
# - Tracks skill manifest for first-boot
# - Supports BuildManager and limp mode-aware loading
# ==========================================================

import os
import sys
import time
import json
import inspect
import logging
import importlib.util
import traceback
from threading import Lock
from seed.skills.autofix.base_fix_skill import FixSkill

# -------------------------
# Logger Setup
# -------------------------
logger = logging.getLogger("AutoFixSkillLoader")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# -------------------------
# Manifest registration (thread-safe)
# -------------------------
manifest_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'manifest.json'))
lock_path = manifest_path + '.lock'

_manifest_lock = Lock()

def acquire_lock():
    while True:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            return lock_fd
        except FileExistsError:
            time.sleep(0.05)

def release_lock(lock_fd):
    try:
        os.close(lock_fd)
    except Exception:
        pass
    if os.path.exists(lock_path):
        os.remove(lock_path)

# Register this loader in manifest.json
try:
    lock_fd = acquire_lock()
    try:
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r+') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {"files": []}
                filename = os.path.basename(__file__)
                if filename not in data.get("files", []):
                    data["files"].append(filename)
                    f.seek(0)
                    json.dump(data, f, indent=4)
                    f.truncate()
    finally:
        release_lock(lock_fd)
except Exception as e:
    logger.warning(f"[AutoFix] Manifest registration failed: {e}")

# -------------------------
# AutoFixSkillLoader
# -------------------------
class AutoFixSkillLoader:
    def __init__(self, skills_dir, build_manager=None, limp_mode=False):
        self.skills_dir = os.path.abspath(skills_dir)
        self.skills = []
        self.build_manager = build_manager
        self.limp_mode = limp_mode
        self._loaded_modules = {}
        self.event_bus = None  # To be injected dynamically

    # -------------------------
    # Inject EventBus dynamically
    # -------------------------
    def set_event_bus(self, event_bus):
        self.event_bus = event_bus
        try:
            from seed.core.track_system import TrackSystem
            TrackSystem.set_event_bus(event_bus)
        except Exception as e:
            logger.warning(f"[AutoFix] Failed to set EventBus in TrackSystem: {e}")

    # -------------------------
    # Load FixSkill subclasses
    # -------------------------
    def load(self):
        self.skills.clear()

        if not os.path.exists(self.skills_dir):
            logger.warning(f"[AutoFix] Skills dir missing: {self.skills_dir}")
            return []

        for fname in os.listdir(self.skills_dir):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue

            path = os.path.join(self.skills_dir, fname)
            module_name = f"autofix_{fname[:-3]}_{int(time.time()*1000)}"

            try:
                # Hot reload: remove from sys.modules if already loaded
                if module_name in sys.modules:
                    del sys.modules[module_name]

                spec = importlib.util.spec_from_file_location(module_name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._loaded_modules[module_name] = module

                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, FixSkill) and obj is not FixSkill:
                        skill_instance = obj()
                        if self.limp_mode and hasattr(skill_instance, 'priority'):
                            skill_instance.priority += 10  # lower priority in limp mode
                        self.skills.append(skill_instance)
                        logger.info(f"[AutoFix] Loaded skill: {skill_instance.name}")
                        if self.event_bus:
                            self.event_bus.publish("skill_loaded", name=skill_instance.name)

            except Exception as e:
                logger.error(f"[AutoFix] Failed loading {fname}: {e}")
                logger.error(traceback.format_exc())

        # Deterministic ordering by priority attribute
        self.skills.sort(key=lambda s: getattr(s, "priority", 0))
        logger.info(f"[AutoFix] Total skills loaded: {[getattr(s, 'name', 'unknown') for s in self.skills]}")
        return self.skills

    # -------------------------
    # Reload a specific skill module
    # -------------------------
    def reload_skill(self, skill_name: str):
        for module_name, module in list(self._loaded_modules.items()):
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, FixSkill) and obj is not FixSkill and getattr(obj, "name", None) == skill_name:
                    logger.info(f"[AutoFix] Reloading skill: {skill_name}")
                    try:
                        new_module_name = f"{module_name}_{int(time.time()*1000)}"
                        spec = importlib.util.spec_from_file_location(new_module_name, module.__file__)
                        new_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(new_module)
                        self._loaded_modules[new_module_name] = new_module

                        # Replace old instances in self.skills
                        self.skills = [s for s in self.skills if getattr(s, "name", None) != skill_name]
                        for _, obj in inspect.getmembers(new_module, inspect.isclass):
                            if issubclass(obj, FixSkill) and obj is not FixSkill:
                                skill_instance = obj()
                                self.skills.append(skill_instance)
                                if self.event_bus:
                                    self.event_bus.publish("skill_reloaded", name=skill_instance.name)

                        # Sort by priority
                        self.skills.sort(key=lambda s: getattr(s, "priority", 0))
                        logger.info(f"[AutoFix] Reload successful: {skill_name}")
                        return True
                    except Exception as e:
                        logger.error(f"[AutoFix] Failed to reload {skill_name}: {e}")
                        logger.error(traceback.format_exc())
                        return False
        logger.warning(f"[AutoFix] Skill not found for reload: {skill_name}")
        return False

# -------------------------
# Minimal self-test
# -------------------------
def self_test():
    logger.info("[AutoFixSkillLoader] Running self-test...")
    test_dir = os.path.join(os.path.dirname(__file__), "test_skills")
    os.makedirs(test_dir, exist_ok=True)

    dummy_skill_file = os.path.join(test_dir, "dummy_skill.py")
    try:
        if not os.path.exists(dummy_skill_file):
            with open(dummy_skill_file, "w", encoding="utf-8") as f:
                f.write("""from seed.skills.autofix.base_fix_skill import FixSkill
class TestFixSkill(FixSkill):
    name = "test_fix"
    priority = 1
    def apply(self, content, track_id=None):
        return content.replace("TODO_FIX", "# FIXED")
""")
        loader = AutoFixSkillLoader(test_dir, limp_mode=True)
        skills = loader.load()
        if skills:
            logger.info(f"[AutoFixSkillLoader] Self-test loaded {len(skills)} skill(s).")
        else:
            logger.warning("[AutoFixSkillLoader] Self-test failed: No skills loaded.")
    finally:
        # Clean up test skill
        if os.path.exists(dummy_skill_file):
            os.remove(dummy_skill_file)
        if os.path.exists(test_dir):
            os.rmdir(test_dir)

if __name__ == "__main__":
    logger.info("[AutoFixSkillLoader] Module loaded.")
    self_test()
