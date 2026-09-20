# ==========================================================
# FILE: bios_module_loader.py
# PATH: SEED_ROOT/seed/core/bios/bios_module_loader.py
# PURPOSE: BIOS Module Discovery & Hot Loader
# NOTES:
# - Thread-safe
# - Supports first-boot initialization
# - TrackID-aware logging for Qbit integration
# - Hot-reload capable
# ==========================================================

import os
import importlib.util
import logging
import threading
import time

logger = logging.getLogger("BIOS.ModuleLoader")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

class BIOSModuleLoader:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.loaded = {}
        self._lock = threading.Lock()

    def discover(self):
        """Recursively discover all Python modules in base_dir."""
        modules = []
        for root, _, files in os.walk(self.base_dir):
            for f in files:
                if f.endswith(".py") and not f.startswith("_"):
                    modules.append(os.path.join(root, f))
        logger.info(f"[BIOS] Discovered {len(modules)} modules")
        return modules

    def load(self, path: str, force_reload=False):
        """
        Load a module from a path.
        - force_reload: reload even if already loaded (hot-reload)
        """
        name = f"bios_mod_{os.path.basename(path).replace('.py','')}"
        with self._lock:
            if name in self.loaded and not force_reload:
                logger.info(f"[BIOS] Module already loaded: {path}")
                return self.loaded[name]

            try:
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.loaded[name] = module
                logger.info(f"[BIOS] Module loaded: {path}")
                return module
            except Exception as e:
                logger.error(f"[BIOS] Failed to load module {path}: {e}")
                return None

    def load_all(self, force_reload=False):
        """
        Discover and load all modules in base_dir.
        Returns a dict: {module_name: module_object}
        """
        modules = self.discover()
        results = {}
        for m in modules:
            loaded_mod = self.load(m, force_reload=force_reload)
            if loaded_mod:
                results[m] = loaded_mod
        logger.info(f"[BIOS] Loaded {len(results)} modules successfully")
        return results

    def reload_module(self, path: str):
        """Force reload a specific module (hot-reload)."""
        return self.load(path, force_reload=True)
