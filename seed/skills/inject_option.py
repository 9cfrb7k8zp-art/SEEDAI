# ==========================================================
# FILE: inject_option.py
# PATH: SEED_ROOT/seed/skills/inject_option.py
# VERSION: 0.1 
# Notes: dictionary to hold options
# Provides a method to dynamically add entries to that dictionary
# ==========================================================

from typing import Callable, Dict

class OptionRegistry:
    def __init__(self):
        # Dictionary to hold option name -> callback
        self._options: Dict[str, Callable] = {}

    def inject_option(self, name: str, callback: Callable):
        if not callable(callback):
            raise ValueError(f"Callback for '{name}' must be callable")
        self._options[name] = callback
        print(f"[OptionRegistry] Injected option: {name}")

    def get_option(self, name: str):
        return self._options.get(name, None)

    def list_options(self):
        return list(self._options.keys())

    def run_option(self, name: str, *args, **kwargs):
        callback = self.get_option(name)
        if callback is None:
            print(f"[OptionRegistry] Option '{name}' not found")
            return None
        return callback(*args, **kwargs)
