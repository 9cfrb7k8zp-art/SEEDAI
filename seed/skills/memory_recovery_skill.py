# ==========================================================
# FILE: memory_recovery_skill.py
# PATH: SEED_ROOT/seed/skills/memory_recovery_skill.py
# PURPOSE: Proactive memory recovery with dependency graph,
#          cross-file function tracing, cyclic detection,
#          broken-link auto-resolution, AutoFix, Qbit prioritization
# VERSION: 5.0
# UPDATED: 2025-12-31
# ==========================================================

import asyncio
import logging
import os
import re
from pathlib import Path
from seed.core.track_id_manager import TrackIDManager
from seed.core.sparkplug import TrackContext, track
from seed.skills.action_registry import queue_action, get_registered_actions

logger = logging.getLogger("MemoryRecoverySkill")
logger.setLevel(logging.INFO)

CHANNEL = "MEMORY_RECOVERY"

# -----------------------------
# Memory Importance Scoring
# -----------------------------
def score_memory(entry):
    score = 0.0
    issues = entry.get("issues", [])
    suggestions = entry.get("suggestions", [])
    stubs = entry.get("stubs", [])
    broken_paths = entry.get("broken_paths", [])
    cross_conflicts = entry.get("cross_conflicts", [])

    score += min(len(issues) * 0.2, 0.4)
    score += min(len(suggestions) * 0.2, 0.3)
    score += min(len(stubs) * 0.1, 0.1)
    score += min(len(broken_paths) * 0.2, 0.3)
    score += min(len(cross_conflicts) * 0.2, 0.3)

    return min(score, 1.0)

# -----------------------------
# Recursive Broken Path & Function Detection
# -----------------------------
def detect_broken_paths_and_functions(content, base_dir="."):
    broken_paths = set()
    unresolved_functions = set()
    cross_conflicts = set()

    # Detect Python imports
    imports = re.findall(r"import\s+([a-zA-Z0-9_.]+)|from\s+([a-zA-Z0-9_.]+)\s+import", content)
    modules = [m[0] or m[1] for m in imports]
    for mod in modules:
        try:
            mod_path = Path(base_dir) / (mod.replace(".", "/") + ".py")
            if not mod_path.exists():
                broken_paths.add(str(mod_path))
        except Exception:
            continue

    # Detect literal file paths
    file_paths = re.findall(r"['\"]([a-zA-Z0-9_\-/\\]+\.py)['\"]", content)
    for f in file_paths:
        f_path = Path(base_dir) / f
        if not f_path.exists():
            broken_paths.add(str(f_path))

    # Detect function calls
    func_calls = re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", content)
    builtins = dir(__builtins__)
    keywords = set([
        "if", "else", "for", "while", "return", "class", "def",
        "import", "from", "with", "try", "except", "async", "await"
    ])
    for func in func_calls:
        if func not in builtins and func not in keywords:
            unresolved_functions.add(func)

    return list(broken_paths), list(unresolved_functions), list(cross_conflicts)

# -----------------------------
# MemoryRecoverySkill with Dependency Graph
# -----------------------------
class MemoryRecoverySkill:
    def __init__(self, memory_manager, build_manager=None, notify_operator=None, qbit_dialer=None):
        self.memory_manager = memory_manager
        self.build_manager = build_manager
        self.notify_operator = notify_operator
        self.qbit_dialer = qbit_dialer
        self.visited_files = set()  # prevent cyclic recursion
        self.dependency_graph = {}  # track linked memory entries

    async def scan_and_recover(self, max_events=50, limp_mode=False):
        recovered_events = []
        recent_memories = self.memory_manager.short_term[-max_events:]
        scored_memories = sorted(recent_memories, key=lambda x: score_memory(x), reverse=True)

        for entry in scored_memories:
            track_id = entry.get("track_id")
            TrackContext.push(channel=CHANNEL, skill="MemoryRecoverySkill")
            importance = score_memory(entry) * (0.5 if limp_mode else 1.0)

            if limp_mode and importance < 0.3:
                TrackContext.pop()
                continue

            # Qbit Dialer prioritization
            if self.qbit_dialer:
                try:
                    self.qbit_dialer.report_memory_priority(track_id, importance)
                except Exception as e:
                    logger.warning(f"[MemoryRecovery] Qbit priority failed | TrackID={track_id} | {e}")

            # Build dependency graph for memory linking
            linked_ids = entry.get("linked_memories", [])
            self.dependency_graph[track_id] = linked_ids

            # Recursive broken path and function resolution
            if "content" in entry.get("payload", {}):
                content = entry["payload"]["content"]
                broken_paths, unresolved_funcs, cross_conflicts = detect_broken_paths_and_functions(content)
                entry["broken_paths"] = broken_paths
                entry["unresolved_functions"] = unresolved_funcs
                entry["cross_conflicts"] = cross_conflicts
                for path in broken_paths:
                    await self._resolve_file_recursively(path, entry)

            # AutoFix integration
            if hasattr(self.memory_manager, "autofix_pipeline") and "content" in entry.get("payload", {}):
                try:
                    entry["payload"]["content"] = await self.memory_manager.autofix_pipeline.run_async(
                        entry["payload"]["content"], track_id=track_id
                    )
                    track(CHANNEL, "AUTO_FIX_APPLIED", note=track_id)
                except Exception as e:
                    logger.warning(f"[MemoryRecovery] AutoFix failed | TrackID={track_id} | {e}")

            # Generate stubs for missing paths
            for stub_path in entry.get("stubs", []) + entry.get("broken_paths", []):
                try:
                    os.makedirs(os.path.dirname(stub_path), exist_ok=True)
                    if not os.path.exists(stub_path):
                        with open(stub_path, "w", encoding="utf-8") as f:
                            f.write("# AUTOGENERATED STUB FILE\n")
                        track(CHANNEL, "STUB_CREATED", note=f"{track_id}:{stub_path}")
                except Exception as e:
                    logger.warning(f"[MemoryRecovery] Stub creation failed: {stub_path} | {e}")

            # Queue BuildManager actions based on dependencies
            if self.build_manager:
                for action_name in get_registered_actions().keys():
                    if action_name.startswith("run_") or action_name.startswith("assemble_"):
                        queue_action(action_name, payload=entry.get("payload", {}), sparkplug=self.build_manager, priority=importance)

            # Notify operator
            if self.notify_operator:
                try:
                    await self.notify_operator(
                        {"avg_intensity": 100 * importance, "motion_level": len(entry.get("issues", []))},
                        limp_mode=limp_mode
                    )
                except Exception as e:
                    logger.warning(f"[MemoryRecovery] NotifyOperator failed | TrackID={track_id} | {e}")

            recovered_events.append(track_id)
            TrackContext.pop()

        # Resolve memory dependencies in order
        await self._resolve_dependency_graph()
        return recovered_events

    async def _resolve_file_recursively(self, path, entry):
        if path in self.visited_files:
            return
        self.visited_files.add(path)
        try:
            if not os.path.exists(path):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write("# AUTOGENERATED MISSING FILE\n")
                track(CHANNEL, "STUB_CREATED", note=f"{entry.get('track_id')}:{path}")
            else:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    broken_paths, _, _ = detect_broken_paths_and_functions(content)
                    for bp in broken_paths:
                        await self._resolve_file_recursively(bp, entry)
        except Exception as e:
            logger.warning(f"[MemoryRecovery] Recursive resolution failed: {path} | {e}")

    async def _resolve_dependency_graph(self):
        resolved = set()
        def resolve_node(node_id, stack=set()):
            if node_id in resolved:
                return
            if node_id in stack:
                logger.warning(f"[MemoryRecovery] Cyclic dependency detected: {node_id}")
                return
            stack.add(node_id)
            for child_id in self.dependency_graph.get(node_id, []):
                resolve_node(child_id, stack)
            resolved.add(node_id)
            stack.remove(node_id)
        for node in self.dependency_graph.keys():
            resolve_node(node)

# -----------------------------
# Loader for SparkPlug
# -----------------------------
def run(memory_manager, build_manager=None, notify_operator=None, qbit_dialer=None, max_events=50, limp_mode=False):
    skill = MemoryRecoverySkill(memory_manager, build_manager=build_manager, notify_operator=notify_operator, qbit_dialer=qbit_dialer)
    return skill.scan_and_recover(max_events=max_events, limp_mode=limp_mode)

# -----------------------------
# Self-Test
# -----------------------------
if __name__ == "__main__":
    import asyncio
    from seed.core.memory_manager import SEEDMemoryManager

    mm = SEEDMemoryManager(storage_root="./memory_test")
    recovery_skill = MemoryRecoverySkill(mm)

    recovered = asyncio.run(recovery_skill.scan_and_recover(max_events=10))
    logger.info(f"[SelfTest] Recovered events: {recovered}")
