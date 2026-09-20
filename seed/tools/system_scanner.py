# ==============================================================
#
# File: system_scanner.py
# Path: SEED_ROOT/seed/tools/system_scanner.py
#
# Purpose:
#   System intelligence, invariant validation, architecture
#   analysis, runtime safety, and AI-readiness certification.
#
# VERSION: 2.0.0
# ROLE: oracle-certification-observer
#
# ==============================================================
#
# ARCHITECTURE:
#
#   SystemScanner
#        |
#        +---- filesystem / AST observation
#        |
#        +---- EventBus integrity
#        |
#        +---- architecture ownership analysis
#        |
#        +---- command-plane boundary validation
#        |
#        +---- runtime safety validation
#        |
#        v
#   certification evidence
#        |
#        +---- TrackSystem
#        +---- SRegistry
#        +---- registry_runtime
#        +---- NeuralBridge
#        +---- Oracle
#        +---- EventBus
#        +---- QbitDialer
#
# AUTHORITY:
#   Certification / observation only.
#
# SystemScanner NEVER:
#   - executes repairs
#   - executes commands
#   - calls QbitDialer.submit_command()
#   - creates QbitDialer
#   - creates QbitQueueLoop
#   - creates EventBus
#   - creates TrackSystem
#   - creates SRegistry
#   - creates NeuralBridge
#   - creates Oracle
#   - starts a competing SEED runtime
#
# Oracle = governance / certification authority
# QbitDialer = command / execution authority
#
# ==============================================================

import ast
import inspect
import logging
import os
import sys
import threading
import time
import traceback
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from types import ModuleType
from typing import Dict, List, Optional, Set, Tuple
from uuid import uuid4


# ==============================================================
# BaseTool
# ==============================================================

try:
    from seed.tools.base_tool import BaseTool
except Exception:
    BaseTool = object


logger = logging.getLogger("SystemScanner")


# ==============================================================
# Track ID
# ==============================================================

def gen_track_id(prefix="SEEDCore_in"):
    """
    Generate a unique track ID.

    Format:
        <prefix>-<8 hex characters>
    """
    return f"{prefix}-{uuid4().hex[:8]}"


# ==============================================================
# SEED ROOT
# ==============================================================

SEED_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
    )
)


# ==============================================================
# CLI COLOR
# ==============================================================

def c(text, color="red"):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "magenta": "\033[95m",
        "end": "\033[0m",
    }

    return (
        f"{colors.get(color, '')}"
        f"{text}"
        f"{colors['end']}"
    )


# ==============================================================
# Scanner
# ==============================================================

class SystemScanner(BaseTool):

    NODE_TYPE = "tool"
    NODE_VERSION = "2.0.0"

    TOOL_NAME = "system_scanner"
    TOOL_ROLE = "oracle-certification-observer"

    TOOL_CAPABILITIES = (
        "system_scanning",
        "boot_sanity",
        "syntax_validation",
        "event_bus_integrity",
        "invariant_validation",
        "ast_hazard_detection",
        "architecture_analysis",
        "control_plane_validation",
        "runtime_safety_analysis",
        "ai_readiness_certification",
        "oracle_certification",
        "registry_evidence",
        "track_telemetry",
        "neural_bridge_evidence",
        "dialer_evidence",
        "dependency_observation",
    )

    TOOL_DEPENDENCIES = (
        "TrackSystem",
        "SRegistry",
        "registry_runtime",
        "NeuralBridge",
        "Oracle",
        "EventBus",
        "QbitDialer",
    )

    TOOL_ALWAYS_ON = False

    # ----------------------------------------------------------
    # Directories that should not be recursively scanned.
    # ----------------------------------------------------------

    SKIP_DIRECTORIES = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "venv",
        ".venv",
        "env",
        ".env",
        "site-packages",
        "dist",
        "build",
    }

    # ----------------------------------------------------------
    # Symbols that represent sensitive execution/control paths.
    # ----------------------------------------------------------

    CONTROL_SYMBOLS = {
        "submit_command",
        "dispatch",
        "execute",
        "schedule",
        "start",
        "shutdown",
        "restart",
        "kill",
        "terminate",
    }

    AUTHORITATIVE_SYMBOLS = {
        "QbitDialer",
        "QbitQueueLoop",
        "SRegistry",
        "SEEDEventBus",
        "EventBus",
        "TrackSystem",
        "NeuralBridge",
        "Oracle",
    }

    # ----------------------------------------------------------
    # Suspicious constructors that may indicate duplicate
    # authoritative infrastructure.
    # ----------------------------------------------------------

    FORBIDDEN_CONSTRUCTORS = {
        "QbitDialer",
        "QbitQueueLoop",
        "SEEDEventBus",
        "EventBus",
        "TrackSystem",
        "SRegistry",
        "NeuralBridge",
        "Oracle",
    }

    # ==========================================================
    # Constructor
    # ==========================================================

    def __init__(
        self,
        targets=None,
        track_system=None,
        registry=None,
        registry_runtime=None,
        neural_bridge=None,
        oracle=None,
        event_bus=None,
        qbit_dialer=None,
        always_on=False,
    ):
        try:
            super().__init__(
                name=self.TOOL_NAME,
                role=self.TOOL_ROLE,
                capabilities=self.TOOL_CAPABILITIES,
                dependencies=self.TOOL_DEPENDENCIES,
                version=self.NODE_VERSION,
                always_on=always_on,
            )
        except TypeError:
            try:
                super().__init__(
                    self.TOOL_NAME
                )
            except TypeError:
                super().__init__()

        self._lock = threading.RLock()

        self.targets = list(
            targets
            if targets is not None
            else [SEED_ROOT]
        )

        self._bindings = {}

        self._running = False
        self._scan_count = 0

        self._last_scan = None
        self._last_report = None
        self._last_error = None

        self._history = []

        self._state = {
            "fatal": [],
            "critical": [],
            "warning": [],
            "info": [],
            "architecture_conflicts": [],
            "control_plane_conflicts": [],
            "runtime_hazards": [],
        }

        if track_system is not None:
            self.bind(
                "TrackSystem",
                track_system,
            )

        if registry is not None:
            self.bind(
                "SRegistry",
                registry,
            )

        if registry_runtime is not None:
            self.bind(
                "registry_runtime",
                registry_runtime,
            )

        if neural_bridge is not None:
            self.bind(
                "NeuralBridge",
                neural_bridge,
            )

        if oracle is not None:
            self.bind(
                "Oracle",
                oracle,
            )

        if event_bus is not None:
            self.bind(
                "EventBus",
                event_bus,
            )

        if qbit_dialer is not None:
            self.bind(
                "QbitDialer",
                qbit_dialer,
            )

        self._update_ready_state()

    # ==========================================================
    # Binding
    # ==========================================================

    def bind(self, name, obj):
        """
        Bind an existing SEED system component.

        No system component is constructed here.
        """
        if obj is None:
            return False

        with self._lock:
            self._bindings[str(name)] = obj

        self._update_ready_state()

        logger.info(
            "[SystemScanner] Bound | %s",
            name,
        )

        return True

    def unbind(self, name):
        with self._lock:
            removed = self._bindings.pop(
                str(name),
                None,
            )

        self._update_ready_state()

        return removed is not None

    def get_binding(self, name):
        with self._lock:
            return self._bindings.get(
                str(name)
            )

    def bindings(self):
        with self._lock:
            return dict(self._bindings)

    def _update_ready_state(self):
        if hasattr(self, "set_ready"):
            try:
                self.set_ready()
                return
            except Exception:
                pass

        if hasattr(self, "ready"):
            self.ready = True

    # ==========================================================
    # Lifecycle
    # ==========================================================

    def start(self):

        with self._lock:
            if self._running:
                return {
                    "status": "already_running"
                }

            self._running = True

        logger.info(
            "[SystemScanner] Started"
        )

        return {
            "status": "started",
            "node_id": getattr(
                self,
                "node_id",
                None,
            ),
        }

    def stop(self):
        with self._lock:
            self._running = False

        logger.info(
            "[SystemScanner] Stopped"
        )

        return {
            "status": "stopped"
        }

    # ==========================================================
    # State management
    # ==========================================================

    def reset_state(self):
        with self._lock:
            self._state = {
                "fatal": [],
                "critical": [],
                "warning": [],
                "info": [],
                "architecture_conflicts": [],
                "control_plane_conflicts": [],
                "runtime_hazards": [],
            }

            self._last_error = None

        return True

    def record(
        self,
        level,
        msg,
        path=None,
        line=None,
        evidence=None,
    ):
        """
        Record scanner evidence.

        This only records an observation.
        """
        level = str(level)

        if level not in self._state:
            level = "info"

        record = {
            "message": str(msg),
            "timestamp": self._utc_now(),
        }

        if path is not None:
            record["path"] = path

        if line is not None:
            record["line"] = line

        if evidence is not None:
            record["evidence"] = self._safe_copy(
                evidence
            )

        with self._lock:
            self._state[level].append(record)

        color = (
            "red"
            if level in {
                "fatal",
                "critical",
            }
            else "yellow"
            if level == "warning"
            else "cyan"
        )

        logger.info(
            c(
                f"[{level.upper()}] "
                f"{msg}",
                color,
            )
        )

    # ==========================================================
    # 1. BOOT / STRUCTURAL SANITY
    # ==========================================================

    def scan_boot_sanity(
        self,
        targets=None,
    ):
        logger.info(
            c(
                "\n[SCAN] "
                "Boot & Structural Sanity",
                "blue",
            )
        )

        targets = (
            list(targets)
            if targets is not None
            else list(self.targets)
        )

        for base in targets:
            if not base:
                continue

            base = os.path.abspath(base)

            if not os.path.exists(base):
                self.record(
                    "fatal",
                    "Scan target does not exist",
                    path=base,
                )
                continue

            if os.path.isfile(base):
                if base.endswith(".py"):
                    self._scan_python_file(
                        base
                    )
                continue

            for root, dirs, files in os.walk(
                base
            ):
                dirs[:] = [
                    directory
                    for directory in dirs
                    if directory
                    not in self.SKIP_DIRECTORIES
                ]

                for filename in files:
                    if not filename.endswith(
                        ".py"
                    ):
                        continue

                    path = os.path.join(
                        root,
                        filename,
                    )

                    self._scan_python_file(
                        path
                    )

        return self._copy_state()

    def _scan_python_file(self, path):
        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as handle:
                source = handle.read()

        except Exception as exc:
            self.record(
                "warning",
                "Unable to read Python source",
                path=path,
                evidence={
                    "error": str(exc)
                },
            )
            return

        # ------------------------------------------------------
        # Triple-quote sanity
        # ------------------------------------------------------

        if (
            source.count('"""') % 2 != 0
            or source.count("'''") % 2 != 0
        ):
            self.record(
                "fatal",
                "Unterminated triple-quoted string",
                path=path,
            )

        # ------------------------------------------------------
        # Mixed indentation
        # ------------------------------------------------------

        for line_number, line in enumerate(
            source.splitlines(),
            1,
        ):
            if (
                "\t" in line
                and line.startswith(" ")
            ):
                self.record(
                    "critical",
                    "Indentation corruption",
                    path=path,
                    line=line_number,
                )

        # ------------------------------------------------------
        # Compile validation
        # ------------------------------------------------------

        try:
            compile(
                source,
                path,
                "exec",
            )

        except SyntaxError as exc:
            self.record(
                "fatal",
                f"Syntax error: {exc.msg}",
                path=path,
                line=exc.lineno,
                evidence={
                    "offset": exc.offset,
                    "text": exc.text,
                },
            )

    # ==========================================================
    # 2. EVENTBUS & INVARIANT INTEGRITY
    # ==========================================================

    def scan_eventbus_integrity(self):
        logger.info(
            c(
                "\n[SCAN] "
                "EventBus & Invariants",
                "blue",
            )
        )

        bus = self.get_binding(
            "EventBus"
        )

        if bus is None:
            bus = self._discover_loaded_event_bus()

        if bus is None:
            self.record(
                "warning",
                "EventBus instance not bound or discoverable",
            )
            return

        if not callable(
            getattr(
                bus,
                "emit",
                None,
            )
        ):
            self.record(
                "fatal",
                "EventBus.emit is not callable",
            )

        if not hasattr(
            bus,
            "_subscribers",
        ):
            self.record(
                "warning",
                "EventBus._subscribers missing",
            )

        # ------------------------------------------------------
        # Check the bound bus type.
        # ------------------------------------------------------

        bus_type = type(bus).__name__

        if bus_type not in {
            "SEEDEventBus",
            "EventBus",
            "SEEDEventBus",
        }:
            self.record(
                "info",
                f"EventBus implementation observed: "
                f"{bus_type}",
            )

        # ------------------------------------------------------
        # Detect module-level emit corruption.
        # ------------------------------------------------------

        for (
            mod_name,
            module,
        ) in list(
            sys.modules.items()
        ):
            if not isinstance(
                module,
                ModuleType,
            ):
                continue

            if not mod_name.startswith(
                "seed"
            ):
                continue

            if hasattr(
                module,
                "emit",
            ):
                emit = getattr(
                    module,
                    "emit",
                )

                if (
                    emit is not None
                    and not callable(emit)
                ):
                    self.record(
                        "critical",
                        "Module emit symbol "
                        "is shadowed or corrupted",
                        evidence={
                            "module": mod_name
                        },
                    )

    def _discover_loaded_event_bus(self):
        for module in list(
            sys.modules.values()
        ):
            if not isinstance(
                module,
                ModuleType,
            ):
                continue

            for attr_name in (
                "SEEDEventBus",
                "EventBus",
            ):
                candidate = getattr(
                    module,
                    attr_name,
                    None,
                )

                if candidate is None:
                    continue

                instance = getattr(
                    candidate,
                    "_instance",
                    None,
                )

                if instance is not None:
                    return instance

                if (
                    not inspect.isclass(
                        candidate
                    )
                    and callable(
                        getattr(
                            candidate,
                            "emit",
                            None,
                        )
                    )
                ):
                    return candidate

        return None

    # ==========================================================
    # 3. AST SYSTEM HAZARDS
    # ==========================================================

    def scan_ast_system_hazards(
        self,
        targets=None,
    ):
        logger.info(
            c(
                "\n[SCAN] "
                "Deep System Hazards (AST)",
                "blue",
            )
        )

        targets = (
            list(targets)
            if targets is not None
            else list(self.targets)
        )

        for base in targets:
            if not base:
                continue

            base = os.path.abspath(base)

            if not os.path.isdir(base):
                continue

            for root, dirs, files in os.walk(
                base
            ):
                dirs[:] = [
                    directory
                    for directory in dirs
                    if directory
                    not in self.SKIP_DIRECTORIES
                ]

                for filename in files:
                    if not filename.endswith(
                        ".py"
                    ):
                        continue

                    path = os.path.join(
                        root,
                        filename,
                    )

                    self._scan_ast_file(
                        path
                    )

        return self._copy_state()

    def _scan_ast_file(self, path):
        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as handle:
                source = handle.read()

            tree = ast.parse(
                source,
                filename=path,
            )

        except Exception:
            return

        self._attach_ast_parents(
            tree
        )

        for node in ast.walk(tree):
            self._inspect_ast_node(
                node,
                path,
            )

    def _attach_ast_parents(self, tree):
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(
                parent
            ):
                child.parent = parent

    def _inspect_ast_node(
        self,
        node,
        path,
    ):
        # ------------------------------------------------------
        # Dead emit assignments
        # ------------------------------------------------------

        if isinstance(
            node,
            ast.Assign,
        ):
            for target in node.targets:
                if (
                    isinstance(
                        target,
                        ast.Attribute,
                    )
                    and target.attr == "emit"
                ):
                    if isinstance(
                        node.value,
                        (
                            ast.Constant,
                            ast.Lambda,
                        ),
                    ):
                        self.record(
                            "critical",
                            "Potential emit shadowing",
                            path=path,
                            line=node.lineno,
                        )

        # ------------------------------------------------------
        # Import-time execution
        # ------------------------------------------------------

        if isinstance(
            node,
            ast.Call,
        ):
            function_name = self._ast_call_name(
                node
            )

            if function_name in {
                "run",
                "start",
                "loop",
                "main",
            }:
                if not self._inside_function(
                    node
                ):
                    self.record(
                        "critical",
                        "Potential import-time "
                        "execution",
                        path=path,
                        line=node.lineno,
                        evidence={
                            "call": function_name
                        },
                    )

        # ------------------------------------------------------
        # Duplicate authoritative constructors
        # ------------------------------------------------------

        if isinstance(
            node,
            ast.Call,
        ):
            constructor_name = (
                self._ast_call_name(
                    node
                )
            )

            if (
                constructor_name
                in self.FORBIDDEN_CONSTRUCTORS
            ):
                self.record(
                    "runtime_hazards",
                    "Potential duplicate "
                    "authoritative component "
                    "construction",
                    path=path,
                    line=node.lineno,
                    evidence={
                        "constructor":
                            constructor_name,
                    },
                )

        # ------------------------------------------------------
        # Direct control-path calls
        # ------------------------------------------------------

        if isinstance(
            node,
            ast.Call,
        ):
            call_name = self._ast_call_name(
                node
            )

            if call_name in {
                "submit_command",
                "execute",
                "dispatch",
                "schedule",
            }:
                self._inspect_control_call(
                    node,
                    path,
                    call_name,
                )

        # ------------------------------------------------------
        # Async definitions are not automatically hazards.
        # Only flag them when they lack an obvious await
        # discipline.
        # ------------------------------------------------------

        if isinstance(
            node,
            ast.AsyncFunctionDef,
        ):
            has_await = any(
                isinstance(
                    child,
                    ast.Await,
                )
                for child in ast.walk(node)
            )

            if not has_await:
                self.record(
                    "info",
                    "Async function contains "
                    "no await expression",
                    path=path,
                    line=node.lineno,
                    evidence={
                        "function": node.name
                    },
                )

    def _inspect_control_call(
        self,
        node,
        path,
        call_name,
    ):

        if call_name == "submit_command":
            self.record(
                "info",
                "submit_command reference observed",
                path=path,
                line=node.lineno,
                evidence={
                    "authority": "QbitDialer",
                    "execution": "not performed",
                },
            )

    @staticmethod
    def _ast_call_name(node):
        function = getattr(
            node,
            "func",
            None,
        )

        if isinstance(
            function,
            ast.Name,
        ):
            return function.id

        if isinstance(
            function,
            ast.Attribute,
        ):
            return function.attr

        return None

    @staticmethod
    def _inside_function(node):
        parent = getattr(
            node,
            "parent",
            None,
        )

        while parent is not None:
            if isinstance(
                parent,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Lambda,
                ),
            ):
                return True

            parent = getattr(
                parent,
                "parent",
                None,
            )

        return False

    # ==========================================================
    # 4. ARCHITECTURE CONFLICT ANALYSIS
    # ==========================================================

    def scan_architecture_conflicts(self):
        logger.info(
            c(
                "\n[SCAN] "
                "Architectural Conflict Analysis",
                "blue",
            )
        )

        ownership = defaultdict(set)

        for (
            mod_name,
            module,
        ) in list(
            sys.modules.items()
        ):
            if not isinstance(
                module,
                ModuleType,
            ):
                continue

            if not mod_name.startswith(
                "seed"
            ):
                continue

            for symbol in (
                "emit",
                "dispatch",
                "route",
                "schedule",
                "submit_command",
            ):
                if hasattr(
                    module,
                    symbol,
                ):
                    ownership[
                        symbol
                    ].add(mod_name)

        for (
            symbol,
            owners,
        ) in ownership.items():
            if len(owners) > 3:
                self.record(
                    "architecture_conflicts",
                    f"Symbol '{symbol}' "
                    f"appears across multiple "
                    f"modules",
                    evidence={
                        "symbol": symbol,
                        "owners": sorted(
                            owners
                        ),
                    },
                )

        # ------------------------------------------------------
        # Authoritative runtime ownership
        # ------------------------------------------------------

        authoritative_modules = defaultdict(
            set
        )

        for (
            mod_name,
            module,
        ) in list(
            sys.modules.items()
        ):
            if not isinstance(
                module,
                ModuleType,
            ):
                continue

            if not mod_name.startswith(
                "seed"
            ):
                continue

            for symbol in (
                "QbitDialer",
                "QbitQueueLoop",
                "SRegistry",
                "NeuralBridge",
                "Oracle",
                "TrackSystem",
            ):
                if hasattr(
                    module,
                    symbol,
                ):
                    authoritative_modules[
                        symbol
                    ].add(mod_name)

        for (
            symbol,
            owners,
        ) in authoritative_modules.items():
            if len(owners) > 1:
                self.record(
                    "architecture_conflicts",
                    f"Authoritative symbol "
                    f"'{symbol}' exposed by "
                    f"multiple loaded modules",
                    evidence={
                        "symbol": symbol,
                        "owners": sorted(
                            owners
                        ),
                    },
                )

    # ==========================================================
    # 5. CONTROL PLANE VALIDATION
    # ==========================================================

    def scan_control_plane(self):
        logger.info(
            c(
                "\n[SCAN] "
                "Command Plane Boundary",
                "blue",
            )
        )

        dialer = self.get_binding(
            "QbitDialer"
        )

        if dialer is None:
            self.record(
                "warning",
                "QbitDialer not bound; "
                "command-plane ownership "
                "cannot be runtime-verified",
            )
        else:
            submit = getattr(
                dialer,
                "submit_command",
                None,
            )

            if not callable(submit):
                self.record(
                    "critical",
                    "QbitDialer.submit_command "
                    "is not callable",
                )
            else:
                self.record(
                    "info",
                    "QbitDialer command authority "
                    "verified",
                    evidence={
                        "owner":
                            "QbitDialer",
                        "submit_command":
                            True,
                    },
                )

        # ------------------------------------------------------
        # Ensure this scanner itself does not expose a command
        # submission path.
        # ------------------------------------------------------

        if callable(
            getattr(
                self,
                "submit_command",
                None,
            )
        ):
            self.record(
                "fatal",
                "SystemScanner exposes "
                "submit_command",
            )

        # ------------------------------------------------------
        # Verify dependencies are bindings, not constructors.
        # ------------------------------------------------------

        for dependency in (
            "TrackSystem",
            "SRegistry",
            "registry_runtime",
            "NeuralBridge",
            "Oracle",
            "EventBus",
            "QbitDialer",
        ):
            if (
                self.get_binding(
                    dependency
                )
                is not None
            ):
                self.record(
                    "info",
                    f"{dependency} bound",
                )

    # ==========================================================
    # 6. RUNTIME HAZARD VALIDATION
    # ==========================================================

    def scan_runtime_hazards(self):
        logger.info(
            c(
                "\n[SCAN] "
                "Runtime Hazard Analysis",
                "blue",
            )
        )

        # ------------------------------------------------------
        # Multiple QbitDialer instances
        # ------------------------------------------------------

        dialers = []

        for module in list(
            sys.modules.values()
        ):
            if not isinstance(
                module,
                ModuleType,
            ):
                continue

            for value in vars(
                module
            ).values():
                if value is None:
                    continue

                if (
                    type(value).__name__
                    == "QbitDialer"
                ):
                    dialers.append(
                        value
                    )

        unique_dialers = {
            id(dialer)
            for dialer in dialers
        }

        if len(unique_dialers) > 1:
            self.record(
                "runtime_hazards",
                "Multiple QbitDialer "
                "instances observed",
                evidence={
                    "count":
                        len(unique_dialers)
                },
            )

        # ------------------------------------------------------
        # Multiple QbitQueueLoop instances
        # ------------------------------------------------------

        queue_loops = []

        for module in list(
            sys.modules.values()
        ):
            if not isinstance(
                module,
                ModuleType,
            ):
                continue

            for value in vars(
                module
            ).values():
                if value is None:
                    continue

                if (
                    type(value).__name__
                    == "QbitQueueLoop"
                ):
                    queue_loops.append(
                        value
                    )

        unique_loops = {
            id(loop)
            for loop in queue_loops
        }

        if len(unique_loops) > 1:
            self.record(
                "runtime_hazards",
                "Multiple QbitQueueLoop "
                "instances observed",
                evidence={
                    "count":
                        len(unique_loops)
                },
            )

        # ------------------------------------------------------
        # Warning capture
        # ------------------------------------------------------

        with warnings.catch_warnings(
            record=True
        ) as captured:
            warnings.simplefilter(
                "always"
            )

            # No code execution here.
            # We only establish that the scanner can safely
            # interact with Python's warning subsystem.

            warning_count = len(
                captured
            )

        self.record(
            "info",
            "Runtime warning subsystem "
            "available",
            evidence={
                "captured": warning_count
            },
        )

    # ==========================================================
    # 7. ORACLE CERTIFICATION
    # ==========================================================

    def oracle_certification_report(self):
        logger.info(
            c(
                "\n[ORACLE] "
                "System Certification Summary",
                "blue",
            )
        )

        with self._lock:
            state = self._copy_state()

        fatal = len(
            state["fatal"]
        )

        critical = len(
            state["critical"]
        )

        warning = len(
            state["warning"]
        )

        architecture = len(
            state[
                "architecture_conflicts"
            ]
        )

        control = len(
            state[
                "control_plane_conflicts"
            ]
        )

        runtime = len(
            state[
                "runtime_hazards"
            ]
        )

        if fatal > 0:
            certification = (
                "NOT_CERTIFIABLE"
            )
            display = (
                "❌ SYSTEM NOT CERTIFIABLE"
            )
            color = "red"

        elif (
            critical > 0
            or control > 0
            or runtime > 0
        ):
            certification = (
                "UNSTABLE"
            )
            display = (
                "⚠️ SYSTEM UNSTABLE "
                "– NOT AI-SAFE"
            )
            color = "yellow"

        elif architecture > 0:
            certification = (
                "ARCHITECTURAL_REVIEW_REQUIRED"
            )
            display = (
                "⚠️ ARCHITECTURE REQUIRES "
                "REVIEW"
            )
            color = "yellow"

        else:
            certification = (
                "AI_READY_MONITORED"
            )
            display = (
                "✅ SYSTEM AI-READY "
                "(WITH MONITORING)"
            )
            color = "green"

        print(
            c(
                display,
                color,
            )
        )

        print(
            c(
                "Fatal: "
                f"{fatal} | "
                "Critical: "
                f"{critical} | "
                "Warnings: "
                f"{warning} | "
                "Architecture: "
                f"{architecture} | "
                "Control: "
                f"{control} | "
                "Runtime: "
                f"{runtime}",
                "cyan",
            )
        )

        report = {
            "type":
                "oracle_certification_report",

            "track_id":
                gen_track_id(
                    "CERT"
                ),

            "node_id":
                getattr(
                    self,
                    "node_id",
                    None,
                ),

            "scanner":
                self.TOOL_NAME,

            "timestamp":
                self._utc_now(),

            "certification":
                certification,

            "certifiable":
                certification
                == "AI_READY_MONITORED",

            "counts": {
                "fatal": fatal,
                "critical": critical,
                "warning": warning,
                "architecture_conflicts":
                    architecture,
                "control_plane_conflicts":
                    control,
                "runtime_hazards":
                    runtime,
            },

            "authority": {
                "certification_owner":
                    "Oracle",
                "execution_owner":
                    "QbitDialer",
                "scanner_execution":
                    False,
                "command_submitted":
                    False,
            },

            "advice": (
                "Do NOT accelerate "
                "feature development."
                if (
                    fatal
                    or critical
                    or control
                    or runtime
                )
                else
                "Continue controlled "
                "development with "
                "runtime monitoring."
            ),

            "state":
                state,
        }

        with self._lock:
            self._last_report = (
                self._safe_copy(
                    report
                )
            )

        self._publish_certification(
            report
        )

        return report

    # ==========================================================
    # 8. FULL SCAN
    # ==========================================================

    def run_full_scan(
        self,
        targets=None,
    ):
        """
        Execute one complete certification scan.

        This performs observation only.
        """
        track_id = gen_track_id(
            "SCAN"
        )

        logger.info(
            c(
                "\n==== "
                "SEED-AI ORACLE "
                "SYSTEM SCANNER "
                "====",
                "blue",
            )
        )

        self.reset_state()

        started = time.monotonic()

        try:
            self.scan_boot_sanity(
                targets
            )

            self.scan_eventbus_integrity()

            self.scan_ast_system_hazards(
                targets
            )

            self.scan_architecture_conflicts()

            self.scan_control_plane()

            self.scan_runtime_hazards()

            report = (
                self.oracle_certification_report()
            )

            report["scan_track_id"] = (
                track_id
            )

            elapsed = (
                time.monotonic()
                - started
            )

            report["duration_seconds"] = (
                elapsed
            )

            with self._lock:
                self._scan_count += 1
                self._last_scan = (
                    self._utc_now()
                )

                self._history.append(
                    self._safe_copy(
                        report
                    )
                )

                if len(
                    self._history
                ) > 50:
                    self._history.pop(0)

                self._last_error = None

            logger.info(
                c(
                    "\n[SCAN COMPLETE]",
                    "green",
                )
            )

            return report

        except Exception as exc:
            self._last_error = {
                "type":
                    type(exc).__name__,
                "message":
                    str(exc),
                "traceback":
                    traceback.format_exc(),
                "timestamp":
                    self._utc_now(),
            }

            self.record(
                "fatal",
                "System scanner execution "
                "failed",
                evidence={
                    "error":
                        str(exc),
                },
            )

            raise

    # ==========================================================
    # 9. SYSTEM EVIDENCE PUBLICATION
    # ==========================================================

    def _publish_certification(
        self,
        report,
    ):

        observation = {
            "type":
                "oracle_certification_evidence",

            "track_id":
                report.get(
                    "track_id"
                ),

            "source_node":
                getattr(
                    self,
                    "node_id",
                    None,
                ),

            "certification":
                report.get(
                    "certification"
                ),

            "counts":
                report.get(
                    "counts",
                    {},
                ),

            "state":
                report.get(
                    "state",
                    {},
                ),

            "authority": {
                "owner":
                    "Oracle",
                "execution":
                    False,
                "command_submitted":
                    False,
            },
        }

        self._publish_event_bus(
            observation
        )

        self._publish_track_system(
            observation
        )

        self._publish_registry(
            observation
        )

        self._publish_registry_runtime(
            observation
        )

        self._publish_neural_bridge(
            observation
        )

        self._publish_oracle(
            observation
        )

        self._publish_dialer_evidence(
            observation
        )

    # ==========================================================
    # EventBus
    # ==========================================================

    def _publish_event_bus(
        self,
        observation,
    ):
        bus = self.get_binding(
            "EventBus"
        )

        if bus is None:
            return False

        emit = getattr(
            bus,
            "emit",
            None,
        )

        if not callable(emit):
            return False

        try:
            emit(
                "ORACLE_CERTIFICATION",
                observation,
            )
            return True

        except Exception as exc:
            logger.debug(
                "[SystemScanner] "
                "EventBus publication skipped: %s",
                exc,
            )

        return False

    # ==========================================================
    # TrackSystem
    # ==========================================================

    def _publish_track_system(
        self,
        observation,
    ):
        track_system = self.get_binding(
            "TrackSystem"
        )

        if track_system is None:
            return False

        methods = (
            "record_observation",
            "record_telemetry",
            "ingest_observation",
            "track",
        )

        for method_name in methods:
            method = getattr(
                track_system,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(observation)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[SystemScanner] "
                    "TrackSystem publication "
                    "skipped via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # SRegistry
    # ==========================================================

    def _publish_registry(
        self,
        observation,
    ):
        registry = self.get_binding(
            "SRegistry"
        )

        if registry is None:
            return False

        evidence = {
            "type":
                "oracle_certification_evidence",

            "source":
                self.TOOL_NAME,

            "track_id":
                observation.get(
                    "track_id"
                ),

            "certification":
                observation.get(
                    "certification"
                ),

            "counts":
                observation.get(
                    "counts",
                    {},
                ),
        }

        methods = (
            "record_runtime_evidence",
            "record_observation",
            "update_runtime_state",
        )

        for method_name in methods:
            method = getattr(
                registry,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[SystemScanner] "
                    "Registry publication skipped "
                    "via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # Registry Runtime
    # ==========================================================

    def _publish_registry_runtime(
        self,
        observation,
    ):
        runtime = self.get_binding(
            "registry_runtime"
        )

        if runtime is None:
            return False

        evidence = {
            "type":
                "oracle_certification_evidence",

            "source":
                self.TOOL_NAME,

            "track_id":
                observation.get(
                    "track_id"
                ),

            "certification":
                observation.get(
                    "certification"
                ),
        }

        methods = (
            "record_observation",
            "record_runtime_evidence",
            "ingest_observation",
            "record_telemetry",
        )

        for method_name in methods:
            method = getattr(
                runtime,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[SystemScanner] "
                    "Registry runtime publication "
                    "skipped via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # NeuralBridge
    # ==========================================================

    def _publish_neural_bridge(
        self,
        observation,
    ):
        bridge = self.get_binding(
            "NeuralBridge"
        )

        if bridge is None:
            return False

        evidence = {
            "type":
                "oracle_certification_evidence",

            "track_id":
                observation.get(
                    "track_id"
                ),

            "certification":
                observation.get(
                    "certification"
                ),

            "lifecycle": {
                "observed":
                    True,
                "execution":
                    False,
            },
        }

        methods = (
            "record_observation",
            "ingest_observation",
            "observe",
            "record_telemetry",
        )

        for method_name in methods:
            method = getattr(
                bridge,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[SystemScanner] "
                    "NeuralBridge publication "
                    "skipped via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # Oracle
    # ==========================================================

    def _publish_oracle(
        self,
        observation,
    ):
        oracle = self.get_binding(
            "Oracle"
        )

        if oracle is None:
            return False

        evidence = {
            "type":
                "system_certification_evidence",

            "source_node":
                getattr(
                    self,
                    "node_id",
                    None,
                ),

            "track_id":
                observation.get(
                    "track_id"
                ),

            "certification":
                observation.get(
                    "certification"
                ),

            "counts":
                observation.get(
                    "counts",
                    {},
                ),

            "state":
                observation.get(
                    "state",
                    {},
                ),

            "authority": {
                "owner":
                    "Oracle",
                "executed":
                    False,
            },
        }

        methods = (
            "record_evidence",
            "record_observation",
            "ingest_observation",
            "observe",
        )

        for method_name in methods:
            method = getattr(
                oracle,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[SystemScanner] "
                    "Oracle publication skipped "
                    "via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # QbitDialer
    # ==========================================================

    def _publish_dialer_evidence(
        self,
        observation,
    ):

        dialer = self.get_binding(
            "QbitDialer"
        )

        if dialer is None:
            return False

        evidence = {
            "type":
                "system_certification_evidence",

            "source":
                self.TOOL_NAME,

            "track_id":
                observation.get(
                    "track_id"
                ),

            "certification":
                observation.get(
                    "certification"
                ),

            "counts":
                observation.get(
                    "counts",
                    {},
                ),

            "authority": {
                "required":
                    True,
                "owner":
                    "QbitDialer",
                "executed":
                    False,
                "command_submitted":
                    False,
            },
        }

        methods = (
            "record_runtime_evidence",
            "record_observation",
            "ingest_telemetry",
        )

        for method_name in methods:
            method = getattr(
                dialer,
                method_name,
                None,
            )

            if not callable(method):
                continue

            try:
                method(evidence)
                return True

            except TypeError:
                continue

            except Exception as exc:
                logger.debug(
                    "[SystemScanner] "
                    "QbitDialer evidence skipped "
                    "via %s: %s",
                    method_name,
                    exc,
                )
                return False

        return False

    # ==========================================================
    # History
    # ==========================================================

    def certification_history(self):
        with self._lock:
            return self._safe_copy(
                self._history
            )

    def last_report(self):
        with self._lock:
            return self._safe_copy(
                self._last_report
            )

    # ==========================================================
    # State
    # ==========================================================

    def _copy_state(self):
        with self._lock:
            return self._safe_copy(
                self._state
            )

    # ==========================================================
    # Status
    # ==========================================================

    def status(self):
        with self._lock:
            return {
                "node_id":
                    getattr(
                        self,
                        "node_id",
                        None,
                    ),

                "tool":
                    self.TOOL_NAME,

                "role":
                    self.TOOL_ROLE,

                "version":
                    self.NODE_VERSION,

                "running":
                    self._running,

                "scan_count":
                    self._scan_count,

                "last_scan":
                    self._last_scan,

                "last_error":
                    self._safe_copy(
                        self._last_error
                    ),

                "bindings":
                    sorted(
                        self._bindings.keys()
                    ),

                "targets":
                    list(self.targets),

                "authority": {
                    "type":
                        "certification_observer",
                    "oracle":
                        True,
                    "command_execution":
                        False,
                    "command_submission":
                        False,
                },
            }

    # ==========================================================
    # Health
    # ==========================================================

    def health(self):
        with self._lock:
            if self._last_error:
                state = "degraded"
            elif not self._running:
                state = "standby"
            else:
                state = "healthy"

            return {
                "state":
                    state,
                "running":
                    self._running,
                "scan_count":
                    self._scan_count,
                "last_error":
                    self._safe_copy(
                        self._last_error
                    ),
            }

    # ==========================================================
    # Utilities
    # ==========================================================

    @staticmethod
    def _safe_copy(value):
        try:
            import copy
            return copy.deepcopy(
                value
            )
        except Exception:
            try:
                if isinstance(
                    value,
                    dict,
                ):
                    return dict(value)

                if isinstance(
                    value,
                    (list, tuple),
                ):
                    return list(value)

                return repr(value)

            except Exception:
                return "<unserializable>"

    @staticmethod
    def _utc_now():
        return datetime.now(
            timezone.utc
        ).isoformat()

    # ==========================================================
    # Representation
    # ==========================================================

    def __repr__(self):
        return (
            f"<SystemScanner "
            f"node_id="
            f"{getattr(self, 'node_id', None)!r} "
            f"running={self._running} "
            f"scans={self._scan_count}>"
        )


# ==============================================================
# Compatibility helpers
#
# Existing code may still call the old module-level functions.
# These create no global runtime and are intentionally thin.
# ==============================================================

_default_scanner = None
_default_scanner_lock = threading.RLock()


def _get_default_scanner():
    global _default_scanner

    with _default_scanner_lock:
        if _default_scanner is None:
            _default_scanner = SystemScanner()

        return _default_scanner


ORACLE_STATE = {
    "fatal": [],
    "critical": [],
    "warning": [],
    "info": [],
    "architecture_conflicts": [],
    "control_plane_conflicts": [],
    "runtime_hazards": [],
}


def record(
    level,
    msg,
):
    scanner = _get_default_scanner()

    scanner.record(
        level,
        msg,
    )

    ORACLE_STATE.setdefault(
        level,
        [],
    ).append(msg)


def scan_boot_sanity(
    targets: List[str],
):
    scanner = _get_default_scanner()

    scanner.scan_boot_sanity(
        targets
    )

    return scanner._copy_state()


def scan_eventbus_integrity():
    scanner = _get_default_scanner()

    scanner.scan_eventbus_integrity()

    return scanner._copy_state()


def scan_ast_system_hazards(
    targets: List[str],
):
    scanner = _get_default_scanner()

    scanner.scan_ast_system_hazards(
        targets
    )

    return scanner._copy_state()


def scan_architecture_conflicts():
    scanner = _get_default_scanner()

    scanner.scan_architecture_conflicts()

    return scanner._copy_state()


def oracle_certification_report():
    scanner = _get_default_scanner()

    return (
        scanner.oracle_certification_report()
    )


def run_full_scan():
    scanner = _get_default_scanner()

    return scanner.run_full_scan()


# ==============================================================
# Dynamic Tool Discovery Metadata
# ==============================================================

TOOL_NAME = SystemScanner.TOOL_NAME
TOOL_ROLE = SystemScanner.TOOL_ROLE
TOOL_VERSION = SystemScanner.NODE_VERSION
TOOL_CAPABILITIES = (
    SystemScanner.TOOL_CAPABILITIES
)
TOOL_DEPENDENCIES = (
    SystemScanner.TOOL_DEPENDENCIES
)
TOOL_CLASS = "SystemScanner"
TOOL_ALWAYS_ON = False


# ==============================================================
# CLI ENTRYPOINT
# ==============================================================

if __name__ == "__main__":
    run_full_scan()