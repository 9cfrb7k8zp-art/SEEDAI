# ==========================================================
# FILE: type_writter.py
# PATH: SEED_ROOT/seed/systemutils/type_writter.py
# VERSION: 3.0.0
# PURPOSE: Notepad-style SEED text/code/artifact writer
# AUTHORITY: existing main3.py runtime only; never creates QbitDialer/EventBus
# OUTPUT: filename extension selects the artifact format (example.py, example.json)
# ==========================================================

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SEED_ROOT = Path(os.environ.get("SEED_ROOT", r"C:\SEED_ROOT")).resolve()
INBOX_PATH = SEED_ROOT / "seed" / "skills" / "inbox"
OUTBOX_PATH = SEED_ROOT / "seed" / "skills" / "outbox"
INBOX_PATH.mkdir(parents=True, exist_ok=True)
OUTBOX_PATH.mkdir(parents=True, exist_ok=True)


class Colors:
    RED = "\\033[91m"
    GREEN = "\\033[92m"
    YELLOW = "\\033[93m"
    CYAN = "\\033[96m"
    MAGENTA = "\\033[95m"
    RESET = "\\033[0m"
    BLINK = "\\033[5m"


class Type_Writter:
    """Small, headless-safe editor modeled on the useful parts of Windows Notepad."""

    REGISTRY: Dict[str, "Type_Writter"] = {}
    panels_registry = REGISTRY
    focused_panel_channel: Optional[str] = None
    panel_positions: Dict[str, tuple] = {}
    panel_objects: Dict[str, Dict[str, Dict[str, Any]]] = {}
    panel_groups: Dict[str, Dict[str, List[str]]] = {}

    def __new__(cls, hud_channel: str = "TYPE_WRITTER"):
        if hud_channel in cls.REGISTRY:
            return cls.REGISTRY[hud_channel]
        inst = super().__new__(cls)
        cls.REGISTRY[hud_channel] = inst
        return inst

    def __init__(self, hud_channel: str = "TYPE_WRITTER"):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.channel = hud_channel
        self.hud_channel = hud_channel
        self.current_file: Optional[Path] = None
        self.buffer: List[str] = []
        self.objects: Dict[str, Dict[str, Any]] = {}
        self.groups: Dict[str, List[str]] = {}
        self.subscribers: List[Any] = []
        self.qbit_dialer = None
        self.event_bus = None
        self.registry = None
        self.node_registry = None
        self.track_system = None
        self.oracle = None
        self.seedcore = None
        self.lines_written = 0
        self.total_lines = 0
        self.new_inbox_files: set[str] = set()
        self.idle_read_enabled = True
        self.hud = None
        self.hud_state = None
        Type_Writter.panel_positions[hud_channel] = (0, 0)
        Type_Writter.panel_objects[hud_channel] = {}
        Type_Writter.panel_groups[hud_channel] = {}

    def bind_runtime(self, *, qbit_dialer=None, event_bus=None, registry=None,
                     node_registry=None, track_system=None, oracle=None, seedcore=None):
        """Attach existing authorities; never instantiate them here."""
        for name, value in (("qbit_dialer", qbit_dialer), ("event_bus", event_bus),
                            ("registry", registry), ("node_registry", node_registry),
                            ("track_system", track_system), ("oracle", oracle),
                            ("seedcore", seedcore)):
            if value is not None:
                setattr(self, name, value)
        return self

    @classmethod
    def focus_panel(cls, hud_channel: str):
        if hud_channel in cls.REGISTRY:
            cls.focused_panel_channel = hud_channel
        return cls.REGISTRY.get(hud_channel)

    @classmethod
    def get_focused_panel(cls):
        return cls.REGISTRY.get(cls.focused_panel_channel) if cls.focused_panel_channel else None

    @classmethod
    def move_panel(cls, hud_channel: str, x: int, y: int):
        if hud_channel in cls.REGISTRY:
            cls.panel_positions[hud_channel] = (x, y)

    def subscribe_panel(self, panel):
        if panel not in self.subscribers:
            self.subscribers.append(panel)
        return panel

    def _notify(self):
        for panel in tuple(self.subscribers):
            try:
                panel.receive_update(self)
            except Exception:
                pass

    def receive_update(self, source_panel):
        self.buffer = list(source_panel.buffer)
        self.lines_written = len(self.buffer)
        self.total_lines = len(self.buffer)

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(str(filename)).name
        if not name or name in {".", ".."}:
            raise ValueError("A filename is required")
        return name

    def _resolve_path(self, filename: str, output: bool = True) -> Path:
        name = self._safe_filename(filename)
        root = OUTBOX_PATH if output else INBOX_PATH
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def new_file(self, filename: Optional[str] = None, filetype: str = "txt", *, output: bool = True):
        if not filename:
            stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = filetype.lstrip(".") or "txt"
            filename = f"SEED_note_{stamp}.{ext}"
        elif "." not in Path(filename).name and filetype:
            filename = f"{filename}.{filetype.lstrip('.') }"
        self.current_file = self._resolve_path(filename, output=output)
        self.buffer = []
        self.objects = {}
        self.groups = {}
        self.lines_written = 0
        self.total_lines = 0
        return self.current_file

    def open_file(self, filename: str, *, output: bool = True) -> Path:
        path = self._resolve_path(filename, output=output)
        text = path.read_text(encoding="utf-8")
        self.current_file = path
        self.buffer = text.splitlines()
        self.lines_written = len(self.buffer)
        self.total_lines = len(self.buffer)
        return path

    def write(self, text: Any):
        if self.current_file is None:
            self.new_file()
        line = str(text)
        self.buffer.append(line)
        self.lines_written += 1
        self.total_lines = max(self.total_lines, self.lines_written)
        obj_id = f"{self.channel}_obj_{self.lines_written}"
        self.objects[obj_id] = {"text": line, "highlight": False}
        Type_Writter.panel_objects[self.channel][obj_id] = self.objects[obj_id]
        self._notify()
        return obj_id

    def set_text(self, text: str):
        self.buffer = str(text).splitlines()
        self.lines_written = len(self.buffer)
        self.total_lines = len(self.buffer)
        self._notify()
        return self

    def append_text(self, text: str):
        return self.write(text)

    def save(self, filename: Optional[str] = None, *, output: bool = True) -> Path:
        if filename is not None:
            self.current_file = self._resolve_path(filename, output=output)
        if self.current_file is None:
            self.new_file(output=output)
        assert self.current_file is not None
        self.current_file.write_text("\n".join(self.buffer), encoding="utf-8")
        return self.current_file

    def save_as(self, filename: str, *, output: bool = True) -> Path:
        return self.save(filename, output=output)

    def write_file(self, filename: str, text: str = "", filetype: str = "", *, output: bool = True) -> Path:
        """Create/save any text format. Extension is authoritative."""
        if "." not in Path(filename).name and filetype:
            filename = f"{filename}.{filetype.lstrip('.') }"
        self.new_file(filename, output=output)
        self.set_text(text)
        return self.save(output=output)

    def new_script(self, name: str, description: str = "", version: str = "0.1.0") -> Path:
        filename = name if Path(name).suffix else f"{name}.py"
        header = ["# ==========================================================", f"# FILE: {Path(filename).name}",
                  f"# CREATED: {_dt.datetime.now().isoformat()}", f"# VERSION: {version}",
                  f"# DESCRIPTION: {description}", "# ==========================================================", ""]
        self.new_file(filename)
        self.set_text("\n".join(header))
        return self.save()

    async def stream_write(self, lines: Iterable[str], delay: float = 0.05):
        for line in lines:
            self.write(line)
            await asyncio.sleep(max(0.0, delay))
        return self.save()

    @staticmethod
    def text_to_binary(text: str = "") -> str:
        return " ".join(format(ord(c), "08b") for c in str(text))

    def write_binary(self, text: str = ""):
        self.write(self.text_to_binary(text))
        return self.save()

    def save_binary_file(self, filename: str, binary_string: str):
        data = "".join(chr(int(bit, 2)) for bit in str(binary_string).split())
        return self.write_file(filename, data)

    def create_group(self, object_ids: Iterable[str], group_name: Optional[str] = None):
        ids = list(object_ids)
        group_id = group_name or f"{self.channel}_group_{len(self.groups) + 1}"
        self.groups[group_id] = ids
        Type_Writter.panel_groups[self.channel][group_id] = ids
        for obj_id in ids:
            if obj_id in self.objects:
                self.objects[obj_id]["highlight"] = True
        return group_id

    def clear_group_highlight(self, group_id: str):
        for obj_id in self.groups.get(group_id, []):
            if obj_id in self.objects:
                self.objects[obj_id]["highlight"] = False
        return True

    def oracle_lesson(self, topic: str = "keyboard and mouse", level: str = "beginner") -> Dict[str, Any]:
        """Generate a bounded lesson plan; execution remains user-controlled."""
        return {"source": "Oracle", "topic": topic, "level": level,
                "steps": self.keyboard_mouse_practice(topic, level),
                "output": "lesson_plan"}

    def keyboard_mouse_practice(self, topic: str, level: str = "beginner") -> List[Dict[str, Any]]:
        t = topic.lower()
        if "mouse" in t:
            return [{"step": 1, "action": "move", "target": "practice area"},
                    {"step": 2, "action": "click", "target": "left button target"},
                    {"step": 3, "action": "double_click", "target": "file target"},
                    {"step": 4, "action": "right_click", "target": "context target"},
                    {"step": 5, "action": "drag", "target": "selection target"}]
        return [{"step": 1, "action": "type", "keys": "hello seed"},
                {"step": 2, "action": "hotkey", "keys": "CTRL+C / CTRL+V"},
                {"step": 3, "action": "hotkey", "keys": "CTRL+S"},
                {"step": 4, "action": "navigation", "keys": "TAB / SHIFT+TAB"},
                {"step": 5, "action": "editing", "keys": "HOME / END / BACKSPACE"}]

    async def on_qbit_event(self, event: Dict[str, Any]):
        if not isinstance(event, dict) or event.get("target") not in (None, self.channel):
            return
        action = event.get("action") or event.get("cmd")
        payload = event.get("payload", event.get("data", ""))
        if action == "new": self.new_file(str(payload) if payload else None)
        elif action == "write": self.write(payload)
        elif action == "save": self.save()
        elif action == "lesson": self.oracle_lesson(str(payload or "keyboard and mouse"))

    async def read_inbox_loop(self, process_func=None, interval: float = 5.0):
        while self.idle_read_enabled:
            files = sorted(INBOX_PATH.glob("*"))
            current = {p.name for p in files}
            new = current - self.new_inbox_files
            self.new_inbox_files = current
            for path in files:
                if process_func:
                    try:
                        await process_func(path, path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
            await asyncio.sleep(max(0.25, interval))


def seed_register_typewritter():
    return Type_Writter()
