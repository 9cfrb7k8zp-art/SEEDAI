# ==========================================================
# FILE: bios_tool_registry.py
# PATH: SEED_ROOT/seed/core/bios/bios_tool_registry.py
# PURPOSE: BIOS Tool Registry (authoritative, boot-safe)
# NOTES:
# - Thread-safe
# - TrackID-aware logging
# - Safe first-boot initialization
# - Supports bulk registration, unregister, and strict retrieval
# - Tracks tool versions with full semantic versioning (major.minor.patch)
# - Automatically bumps patch/minor/major on overwrite
# - Maintains version history for each tool
# - Supports rollback to previous versions
# ==========================================================

import logging
import threading
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

# --------------------------
# Logger setup (boot-safe)
# --------------------------
logger = logging.getLogger("BIOS.ToolRegistry")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --------------------------
# Helper function: semantic version bump
# --------------------------
def bump_version(version: Optional[str], bump_type: str = "patch") -> str:
    if not version:
        return "1.0.0"
    try:
        parts = [int(x) for x in version.split(".")]
        while len(parts) < 3:
            parts.append(0)
        if bump_type == "patch":
            parts[2] += 1
        elif bump_type == "minor":
            parts[1] += 1
            parts[2] = 0
        elif bump_type == "major":
            parts[0] += 1
            parts[1] = 0
            parts[2] = 0
        else:
            parts[2] += 1
        return ".".join(map(str, parts))
    except Exception:
        return "1.0.0"

# --------------------------
# BIOS Tool Registry Class
# --------------------------
class BIOSToolRegistry:
    def __init__(self):
        # Stores tools as {name: {"tool": object, "version": str, "history": [versions], "history_objects": [tool_versions]}}
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        logger.info("[BIOS] Tool registry initialized")

    # ----------------------
    # Register single tool
    # ----------------------
    def register(
        self,
        name: str,
        tool: Any,
        version: Optional[str] = None,
        overwrite: bool = False,
        bump_type: str = "patch",
    ):
        """
        Register a tool by name with optional version.
        Automatically bumps version on overwrite.
        Maintains version history.
        """
        with self._lock:
            if name in self._tools:
                if overwrite:
                    current_version = self._tools[name]["version"]
                    new_version = bump_version(version or current_version, bump_type)
                    self._tools[name]["tool"] = tool
                    self._tools[name]["version"] = new_version
                    self._tools[name]["history"].append(new_version)
                    self._tools[name]["history_objects"].append(tool)
                    logger.info(f"[BIOS] Tool overwritten: {name} (version={new_version})")
                else:
                    logger.warning(
                        f"[BIOS] Tool already registered: {name} (version={self._tools[name]['version']})"
                    )
                    return
            else:
                init_version = version or "1.0.0"
                self._tools[name] = {
                    "tool": tool,
                    "version": init_version,
                    "history": [init_version],
                    "history_objects": [tool],
                }
                logger.info(f"[BIOS] Tool registered: {name} (version={init_version})")

    # ----------------------
    # Register multiple tools
    # ----------------------
    def register_bulk(
        self,
        tools: Dict[str, Any],
        versions: Optional[Dict[str, str]] = None,
        overwrite: bool = False,
        bump_types: Optional[Dict[str, str]] = None,
    ):
        """
        Register multiple tools at once with optional versions and bump types.
        bump_types dict: {tool_name: "patch"/"minor"/"major"}
        """
        for name, tool in tools.items():
            version = versions.get(name) if versions else None
            bump_type = bump_types.get(name) if bump_types else "patch"
            self.register(name, tool, version=version, overwrite=overwrite, bump_type=bump_type)

    # ----------------------
    # Retrieve tool safely
    # ----------------------
    def get(self, name: str):
        """Retrieve a registered tool by name, returns None if not found."""
        with self._lock:
            entry = self._tools.get(name)
            return entry["tool"] if entry else None

    def get_version(self, name: str) -> Optional[str]:
        """Retrieve the current version of a registered tool."""
        with self._lock:
            entry = self._tools.get(name)
            return entry["version"] if entry else None

    def get_history(self, name: str) -> Optional[List[str]]:
        """Retrieve the version history of a tool."""
        with self._lock:
            entry = self._tools.get(name)
            return entry["history"] if entry else None

    def get_or_raise(self, name: str):
        """Retrieve a tool, raise KeyError if not registered."""
        with self._lock:
            if name in self._tools:
                return self._tools[name]["tool"]
            raise KeyError(f"[BIOS] Tool not registered: {name}")

    # ----------------------
    # Rollback tool to previous version
    # ----------------------
    def rollback(self, name: str, version: Optional[str] = None):
        """
        Rollback a tool to a previous version.
        If version is None, rollback to previous (last) version.
        """
        with self._lock:
            if name not in self._tools:
                raise KeyError(f"[BIOS] Tool not registered: {name}")
            history = self._tools[name]["history"]
            objects = self._tools[name]["history_objects"]

            if len(history) < 2:
                logger.warning(f"[BIOS] Cannot rollback {name}: only one version exists")
                return

            if version:
                if version not in history:
                    raise ValueError(f"[BIOS] Version {version} not found for {name}")
                index = history.index(version)
            else:
                index = -2  # previous version

            # Rollback
            self._tools[name]["tool"] = objects[index]
            self._tools[name]["version"] = history[index]
            # Remove newer history entries
            self._tools[name]["history"] = history[: index + 1]
            self._tools[name]["history_objects"] = objects[: index + 1]
            logger.info(f"[BIOS] Tool rolled back: {name} to version {history[index]}")

    # ----------------------
    # Unregister tool
    # ----------------------
    def unregister(self, name: str):
        """Remove a registered tool by name."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.info(f"[BIOS] Tool unregistered: {name}")
            else:
                logger.warning(f"[BIOS] Tool not found for unregister: {name}")

    # ----------------------
    # Check tool existence
    # ----------------------
    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        with self._lock:
            return name in self._tools

    # ----------------------
    # List all tool names
    # ----------------------
    def list_tools(self):
        """List all registered tool names."""
        with self._lock:
            return list(self._tools.keys())

    # ----------------------
    # List all tools with current versions
    # ----------------------
    def list_tools_with_versions(self):
        """List all registered tools with their current versions."""
        with self._lock:
            return {name: entry["version"] for name, entry in self._tools.items()}

    # ----------------------
    # List all tools with full history
    # ----------------------
    def list_tools_with_history(self):
        """List all registered tools with full version history."""
        with self._lock:
            return {name: entry["history"] for name, entry in self._tools.items()}

    # ----------------------
    # Context-managed access
    # ----------------------
    @contextmanager
    def tool_access(self):
        """Provide thread-safe direct access to the tool dictionary."""
        with self._lock:
            yield self._tools
