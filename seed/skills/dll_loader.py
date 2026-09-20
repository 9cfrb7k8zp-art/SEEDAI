# ==========================================================
# SEED-AI DLL Loader Module (Inbox)
# ----------------------------------------------------------
# File: dll_loader.py
# Path: seed/skills/inbox/dll_loader.py
#
# ROLE:
#   - Passive DLL observer
#   - NEVER executes code
#   - Fingerprints + metadata only
#   - Submits findings to higher authority
# ==========================================================

import os
import json
import hashlib
import logging
import ctypes
from ctypes import wintypes
from datetime import datetime

log = logging.getLogger("DLLLoader")

# ----------------------------------------------------------
# Windows constants (safe-load only)
# ----------------------------------------------------------
LOAD_LIBRARY_AS_DATAFILE = 0x00000002
LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LoadLibraryExW = kernel32.LoadLibraryExW
LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
LoadLibraryExW.restype = wintypes.HMODULE

FreeLibrary = kernel32.FreeLibrary
FreeLibrary.argtypes = [wintypes.HMODULE]
FreeLibrary.restype = wintypes.BOOL


# ==========================================================
# DLLLoader
# ==========================================================
class DLLLoader:

    def __init__(self, state_path="state.json"):
        self.state_path = state_path
        self.state = self._load_state()
        self.event_bus = None
        self.track_system = None
        self.oracle = None
        self.registry = None

    def bind_runtime(
        self,
        *,
        event_bus=None,
        track_system=None,
        oracle=None,
        registry=None,
        **_kwargs,
    ):
        self.event_bus = event_bus
        self.track_system = track_system
        self.oracle = oracle
        self.registry = registry
        return True

    # ------------------------------------------------------
    # Public API
    # ------------------------------------------------------
    def scan_directory(self, directory: str):
        results = []

        for root, _, files in os.walk(directory):
            for f in files:
                if f.lower().endswith(".dll"):
                    path = os.path.join(root, f)
                    try:
                        meta = self.inspect_dll(path)
                        results.append(meta)
                    except Exception as e:
                        log.exception(f"Failed to inspect {path}: {e}")

        self._save_state()
        return results

    def inspect_dll(self, path: str) -> dict:
        fingerprint = self._fingerprint(path)

        if fingerprint in self.state["dlls"]:
            log.debug(f"Already seen DLL: {path}")
            return self.state["dlls"][fingerprint]

        meta = {
            "path": path,
            "filename": os.path.basename(path),
            "size": os.path.getsize(path),
            "sha256": fingerprint,
            "timestamp": datetime.utcnow().isoformat(),
            "exports": [],
            "flags": [],
            "notes": [],
        }

        # Safe load (NO execution)
        hmod = LoadLibraryExW(
            path,
            None,
            LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE
        )

        if not hmod:
            meta["flags"].append("load_failed")
            meta["notes"].append("Could not load as datafile")
        else:
            meta["flags"].append("loaded_as_datafile")
            # We deliberately DO NOT resolve or call symbols
            FreeLibrary(hmod)

        # Heuristics
        self._flag_interesting(meta)

        self.state["dlls"][fingerprint] = meta
        return meta

    # ------------------------------------------------------
    # Internals
    # ------------------------------------------------------
    def _fingerprint(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _flag_interesting(self, meta: dict):
        name = meta["filename"].lower()

        if any(x in name for x in ["crypto", "cuda", "opencl", "vulkan"]):
            meta["flags"].append("compute_related")

        if any(x in name for x in ["ai", "ml", "nn", "tensor"]):
            meta["flags"].append("ml_related")

        if meta["size"] > 50 * 1024 * 1024:
            meta["flags"].append("large_binary")

    # ------------------------------------------------------
    # State handling
    # ------------------------------------------------------
    def _load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "dlls": {},
            "last_scan": None,
        }

    def _save_state(self):
        self.state["last_scan"] = datetime.utcnow().isoformat()
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
