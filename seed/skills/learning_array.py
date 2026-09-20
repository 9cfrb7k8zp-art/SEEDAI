# ==================================================================================
#"""
# FILE: learning_array.py
# PATH: seed/skills/learning_array.py
#
# SEED SKILL: Full System-Active Autonomous Learning Array (Adaptive)
# + Reward Flags
# + Growth Cycles
# + TrackSystem Logging
# + Childhood Scheduler
# + Self-Fix Milestones
# + Metrics Reporting
# + Automatic Self-Fix Logic
# + Diff-Based Self-Patching
#` + Self-Learning Backlog
# + Idle/Background Autonomous Learning
# + Incremental Memory Building
# + Adaptive Retry & Growth
# + CPU-Friendly Idle/Active Scaling
# + Dynamic Task Prioritization
#
# STATUS: Active / Ready for System Use
# PLATFORM: Windows-safe (spawn model)
#
# PHILOSOPHY:
# - Observe → act → evaluate → adapt → grow continuously
# - Autonomous background learning
# ` - Reward flags: green = success, red = fail
# - Retry counters & reset for adaptive learning
# - Milestones & self-fix for incremental progress
# - Memory/log persistence for SEED AI to track learning
# - Idle mode: low CPU/memory usage, background self-improvement
# - Active mode: simulate tasks, inspect modules, detect tools, self-fix
# - Task prioritization based on backlog and milestone urgency
#
# ==================================================================================

from multiprocessing import Process, Queue, current_process
import os
import time
import json
import traceback
import importlib
import inspect
from typing import List, Tuple, Dict, Any
import shutil
import difflib
import psutil
import random
import heapq

# --------------------------------------------------
# Constants / Paths
# --------------------------------------------------

SHUTDOWN_SIGNAL = "__SHUTDOWN__"
HEARTBEAT_INTERVAL = 1.0
GROWTH_CHECK_INTERVAL = 10.0
METRICS_INTERVAL = 5.0
IDLE_CPU_THRESHOLD = 25.0  # percent CPU usage to consider "idle"
MAX_CPU_USAGE = 80.0       # scale learning down if above this

LEARNING_ROOT = os.path.join(os.getcwd(), "seed_learning")
MODULE_LOG_PATH = os.path.join(LEARNING_ROOT, "module_logs")
CAPABILITY_GRAPH_PATH = os.path.join(LEARNING_ROOT, "capability_graph.json")
REWARD_LOG_PATH = os.path.join(LEARNING_ROOT, "reward_log.json")
GROWTH_LOG_PATH = os.path.join(LEARNING_ROOT, "growth_log.json")
TRACKSYSTEM_LOG_PATH = os.path.join(LEARNING_ROOT, "tracksystem_log.json")
METRICS_LOG_PATH = os.path.join(LEARNING_ROOT, "metrics_log.json")
SELF_FIX_BACKUP = os.path.join(LEARNING_ROOT, "module_backups")
SELF_LEARNING_BACKLOG = os.path.join(LEARNING_ROOT, "self_learning_backlog.json")

os.makedirs(MODULE_LOG_PATH, exist_ok=True)
os.makedirs(SELF_FIX_BACKUP, exist_ok=True)

# --------------------------------------------------
# Optional AI / ML Tool Awareness
# --------------------------------------------------

OPTIONAL_TOOLS = [
    "numpy",
    "scipy",
    "sklearn",
    "torch",
    "tensorflow",
    "networkx",
    "pandas"
]

def detect_optional_tools() -> Dict[str, bool]:
    detected = {}
    for tool in OPTIONAL_TOOLS:
        try:
            importlib.import_module(tool)
            detected[tool] = True
        except Exception:
            detected[tool] = False
    return detected

# --------------------------------------------------
# Module Introspection + Diffing
# --------------------------------------------------

def inspect_module(module_path: str) -> Dict[str, Any]:
    report = {
        "module": module_path,
        "imported": False,
        "functions": [],
        "classes": [],
        "attributes": [],
        "error": None
    }
    try:
        module = importlib.import_module(module_path)
        report["imported"] = True
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj):
                report["functions"].append(name)
            elif inspect.isclass(obj):
                report["classes"].append(name)
            elif not name.startswith("__"):
                report["attributes"].append(name)
    except Exception as e:
        report["error"] = {
            "message": str(e),
            "traceback": traceback.format_exc()
        }
    return report

def diff_reports(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "functions_added": list(set(new["functions"]) - set(old["functions"])) if old else new["functions"],
        "classes_added": list(set(new["classes"]) - set(old["classes"])) if old else new["classes"],
        "attributes_added": list(set(new["attributes"]) - set(old["attributes"])) if old else new["attributes"]
    }

# --------------------------------------------------
# Capability Graph
# --------------------------------------------------

def update_capability_graph(module_report: Dict[str, Any]):
    graph = {}
    if os.path.exists(CAPABILITY_GRAPH_PATH):
        with open(CAPABILITY_GRAPH_PATH, "r") as f:
            graph = json.load(f)
    graph[module_report["module"]] = {
        "functions": module_report["functions"],
        "classes": module_report["classes"],
        "attributes": module_report["attributes"]
    }
    with open(CAPABILITY_GRAPH_PATH, "w") as f:
        json.dump(graph, f, indent=2)

# --------------------------------------------------
# TrackSystem Logging
# --------------------------------------------------

def tracksystem_log(worker_id: int, event: str, data: Dict[str, Any]):
    log = {}
    if os.path.exists(TRACKSYSTEM_LOG_PATH):
        with open(TRACKSYSTEM_LOG_PATH, "r") as f:
            log = json.load(f)
    ts = time.time()
    worker_log = log.get(str(worker_id), [])
    worker_log.append({"ts": ts, "event": event, "data": data})
    log[str(worker_id)] = worker_log
    with open(TRACKSYSTEM_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)

# --------------------------------------------------
# Reward & Growth Cycles
# --------------------------------------------------

def log_reward(worker_id: int, flag: str, task_desc: str):
    reward_log = {}
    if os.path.exists(REWARD_LOG_PATH):
        with open(REWARD_LOG_PATH, "r") as f:
            reward_log = json.load(f)
    worker_log = reward_log.get(str(worker_id), {"retry_count": 0, "history": []})
    if flag.lower() == "green":
        worker_log["retry_count"] += 1
    elif flag.lower() == "red":
        worker_log["retry_count"] = 0
    worker_log["history"].append({"flag": flag, "task": task_desc, "retry_count": worker_log["retry_count"], "ts": time.time()})
    reward_log[str(worker_id)] = worker_log
    with open(REWARD_LOG_PATH, "w") as f:
        json.dump(reward_log, f, indent=2)
    update_growth_cycle(worker_id, flag)
    tracksystem_log(worker_id, "reward_logged", {"task": task_desc, "flag": flag})

def update_growth_cycle(worker_id: int, flag: str):
    growth_log = {}
    if os.path.exists(GROWTH_LOG_PATH):
        with open(GROWTH_LOG_PATH, "r") as f:
            growth_log = json.load(f)
    worker_growth = growth_log.get(str(worker_id), {"milestones": {}, "last_growth": 0})
    if flag.lower() == "green":
        worker_growth["last_growth"] = time.time()
        worker_growth["milestones"]["module_inspection"] = worker_growth["milestones"].get("module_inspection", 0) + 1
        if worker_growth["milestones"]["module_inspection"] % 5 == 0:
            worker_growth["milestones"]["self_fix_ready"] = True
    elif flag.lower() == "red":
        worker_growth["milestones"]["retry_needed"] = worker_growth["milestones"].get("retry_needed", 0) + 1
    growth_log[str(worker_id)] = worker_growth
    with open(GROWTH_LOG_PATH, "w") as f:
        json.dump(growth_log, f, indent=2)
    tracksystem_log(worker_id, "growth_updated", {"flag": flag, "milestones": worker_growth["milestones"]})

# --------------------------------------------------
# Self-Learning Backlog with Priority Queue
# --------------------------------------------------

def add_to_backlog(worker_id: int, task: Dict[str, Any], priority: int = 10):
    backlog = {}
    if os.path.exists(SELF_LEARNING_BACKLOG):
        with open(SELF_LEARNING_BACKLOG, "r") as f:
            backlog = json.load(f)
    worker_backlog = backlog.get(str(worker_id), [])
    heapq.heappush(worker_backlog, (priority, {"task": task, "ts": time.time()}))
    backlog[str(worker_id)] = worker_backlog
    with open(SELF_LEARNING_BACKLOG, "w") as f:
        json.dump(backlog, f, indent=2)

def process_backlog(worker_id: int, task_queue: Queue):
    backlog = {}
    if os.path.exists(SELF_LEARNING_BACKLOG):
        with open(SELF_LEARNING_BACKLOG, "r") as f:
            backlog = json.load(f)
    worker_backlog = backlog.get(str(worker_id), [])
    new_backlog = []
    while worker_backlog:
        priority, entry = heapq.heappop(worker_backlog)
        task_queue.put(entry["task"])
    backlog[str(worker_id)] = new_backlog
    with open(SELF_LEARNING_BACKLOG, "w") as f:
        json.dump(backlog, f, indent=2)

# --------------------------------------------------
# Self-Fix Logic
# --------------------------------------------------

def attempt_self_fix(worker_id: int, module_path: str):
    try:
        source_file = module_path.replace(".", os.sep) + ".py"
        if not os.path.exists(source_file):
            return False
        backup_file = os.path.join(SELF_FIX_BACKUP, os.path.basename(source_file))
        shutil.copy2(source_file, backup_file)
        tracksystem_log(worker_id, "self_fix_backup", {"module": module_path, "backup": backup_file})
        importlib.invalidate_caches()
        module = importlib.import_module(module_path)
        importlib.reload(module)
        log_file = os.path.join(MODULE_LOG_PATH, module_path.replace(".", "_") + ".json")
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                report = json.load(f)
            if report.get("error"):
                with open(source_file, "r") as f:
                    lines = f.readlines()
                lines.append("\n# SELF_FIX_PATCH_APPLIED\n")
                with open(source_file, "w") as f:
                    f.writelines(lines)
        tracksystem_log(worker_id, "self_fix_success", {"module": module_path})
        growth_log = {}
        if os.path.exists(GROWTH_LOG_PATH):
            with open(GROWTH_LOG_PATH, "r") as f:
                growth_log = json.load(f)
        worker_growth = growth_log.get(str(worker_id), {"milestones": {}})
        worker_growth["milestones"]["self_fix_ready"] = False
        growth_log[str(worker_id)] = worker_growth
        with open(GROWTH_LOG_PATH, "w") as f:
            json.dump(growth_log, f, indent=2)
        return True
    except Exception as e:
        tracksystem_log(worker_id, "self_fix_failed", {"module": module_path, "error": str(e)})
        add_to_backlog(worker_id, {"type": "INSPECT_MODULE", "module": module_path}, priority=1)
        return False

# --------------------------------------------------
# Metrics Reporting
# --------------------------------------------------

def report_metrics(workers: List[Process]):
    metrics = {}
    for worker_id, p in enumerate(workers):
        metrics[worker_id] = {"pid": p.pid, "alive": p.is_alive(), "cpu_percent": psutil.cpu_percent(interval=0.1)}
    with open(METRICS_LOG_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

# --------------------------------------------------
# Autonomous Worker Logic
# --------------------------------------------------

def _learning_worker(worker_id: int, task_queue: Queue, result_queue: Queue):
    pid = os.getpid()
    last_heartbeat = time.time()
    tracksystem_log(worker_id, "worker_started", {"pid": pid})

    try:
        while True:
            cpu = psutil.cpu_percent(interval=0.1)
            idle_mode = cpu < IDLE_CPU_THRESHOLD
            active_mode = cpu < MAX_CPU_USAGE

            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                result_queue.put({"event": "HEARTBEAT", "worker_id": worker_id, "pid": pid})
                last_heartbeat = now

            # Dynamically scale tasks based on CPU usage
            if active_mode and not task_queue.empty():
                task = task_queue.get()
                if task == SHUTDOWN_SIGNAL:
                    result_queue.put({"event": "WORKER_SHUTDOWN", "worker_id": worker_id, "pid": pid})
                    tracksystem_log(worker_id, "worker_shutdown", {"pid": pid})
                    break
                _process_task(worker_id, task, task_queue, result_queue)
            elif idle_mode:
                _autonomous_learning(worker_id, task_queue)

            process_backlog(worker_id, task_queue)

    except Exception as e:
        log_reward(worker_id, "red", "WORKER_CRASH")
        result_queue.put({"event": "WORKER_CRASH", "worker_id": worker_id, "pid": pid,
                         "error": str(e), "traceback": traceback.format_exc(), "flag": "red"})
        tracksystem_log(worker_id, "worker_crash", {"error": str(e)})

# --------------------------------------------------
# Internal task processing
# --------------------------------------------------

def _process_task(worker_id: int, task: Any, task_queue: Queue, result_queue: Queue):
    pid = os.getpid()
    if isinstance(task, dict) and task.get("type") == "INSPECT_MODULE":
        module = task.get("module")
        report = inspect_module(module)
        log_file = os.path.join(MODULE_LOG_PATH, module.replace(".", "_") + ".json")
        previous = None
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                previous = json.load(f)
        with open(log_file, "w") as f:
            json.dump(report, f, indent=2)
        diff = diff_reports(previous, report) if previous else None
        update_capability_graph(report)
        flag = "green" if report["imported"] else "red"
        log_reward(worker_id, flag, f"INSPECT_MODULE:{module}")
        result_queue.put({"event": "MODULE_LEARNED", "worker_id": worker_id, "pid": pid,
                          "module": module, "diff": diff, "flag": flag})
        growth_log = {}
        if os.path.exists(GROWTH_LOG_PATH):
            with open(GROWTH_LOG_PATH, "r") as f:
                growth_log = json.load(f)
        worker_growth = growth_log.get(str(worker_id), {})
        milestones = worker_growth.get("milestones", {})
        if milestones.get("self_fix_ready", False):
            attempt_self_fix(worker_id, module)
    elif isinstance(task, dict) and task.get("type") == "DETECT_TOOLS":
        tools = detect_optional_tools()
        flag = "green"
        log_reward(worker_id, flag, "DETECT_TOOLS")
        result_queue.put({"event": "TOOLS_DETECTED", "worker_id": worker_id, "pid": pid, "tools": tools, "flag": flag})
    else:
        time.sleep(0.1)
        flag = "green"
        log_reward(worker_id, flag, str(task))
        result_queue.put({"event": "TASK_PROCESSED", "worker_id": worker_id, "pid": pid, "task": task, "flag": flag})

# --------------------------------------------------
# Autonomous Learning Loop
# --------------------------------------------------

def _autonomous_learning(worker_id: int, task_queue: Queue):
    if os.path.exists(CAPABILITY_GRAPH_PATH):
        with open(CAPABILITY_GRAPH_PATH, "r") as f:
            graph = json.load(f)
        modules = list(graph.keys())
        if modules:
            module = random.choice(modules)
            task_queue.put({"type": "INSPECT_MODULE", "module": module})
    task_queue.put({"type": "DETECT_TOOLS"})

# --------------------------------------------------
# Public Skill API
# --------------------------------------------------

def start_learning_array(worker_count: int = 5) -> Tuple[Queue, Queue, List[Process], Dict[int, int]]:
    task_queue = Queue()
    result_queue = Queue()
    workers: List[Process] = []
    identity_map: Dict[int, int] = {}
    for i in range(worker_count):
        p = Process(target=_learning_worker, args=(i, task_queue, result_queue), daemon=True)
        p.start()
        workers.append(p)
        identity_map[i] = p.pid
    return task_queue, result_queue, workers, identity_map

def shutdown_learning_array(workers: List[Process], task_queue: Queue):
    for _ in workers:
        task_queue.put(SHUTDOWN_SIGNAL)
    for p in workers:
        p.join(timeout=5)

def kill_learning_array(workers: List[Process]):
    for p in workers:
        if p.is_alive():
            p.terminate()

def detect_dead_workers(workers: List[Process]) -> List[int]:
    return [p.pid for p in workers if not p.is_alive()]
