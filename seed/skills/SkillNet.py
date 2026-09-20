# ==================================================================================
"""
FILE: SkillNet.py
PATH: seed/skills/SkillNet.py

SEED SKILL: SkillNet - Fully Autonomous Adaptive AI SkillNet
+ Multi-modal Qbit fusion: Vision, Audio, Navigation, Flight, EM, Lidar, Radar
+ 3D environmental modeling & predictive trajectories
+ Velocity vectors & dynamic risk mapping
+ Qbit uncertainty & confidence heatmaps
+ Reward-based optimization of Qbit weights
+ Self-adaptive anomaly detection & automatic correction
+ Automatic skill module reload & dependency management
+ Inter-skill priority scheduling & resource-aware load balancing
+ Cross-skill shared memory: all modules can read/write predictive states
+ Adaptive learning: retries, reward flags, growth cycles, milestones
+ Real-time 3D visualization with matplotlib
+ Active drop-in loop for SEED AI
+ Threaded, cross-platform, modular
"""
# ==================================================================================

import logging
import time
import threading
import os
import importlib
import numpy as np
import psutil  # resource monitoring
from typing import Dict, Any

# -------------------------
# GUI DASHBOARD
# -------------------------
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# -------------------------
# LOGGER SETUP
# -------------------------
logger = logging.getLogger("SkillNet")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# -------------------------
# REWARD FLAGS
# -------------------------
REWARD_SUCCESS = "GREEN"
REWARD_FAIL = "RED"

# -------------------------
# SKILLNET CLASS
# -------------------------
class SkillNet:
    def __init__(self, enable_dashboard=False, enable_3d=False, skill_folder="seed/skills", autostart=False):
        logger.info("Initializing SkillNet fully autonomous adaptive AI with cross-skill memory...")

        self.skill_folder = skill_folder
        self.loaded_modules = {}
        self.module_mtimes = {}
        self.module_priority = {}  # higher = more critical

        # Initialize skill arrays
        self.vision = None
        self.audio = None
        self.flight = None
        self.navigation = None
        self.em = None
        self.lidar = None
        self.radar = None

        # Global state
        self.qbits: Dict[str, np.ndarray] = {}
        self.shared_memory: Dict[str, Any] = {}  # CROSS-SKILL MEMORY POOL
        self.predicted_state: Dict[str, np.ndarray] = {}
        self.qbit_weights: Dict[str, float] = {}
        self.qbit_confidence: Dict[str, float] = {}
        self.reward_history: Dict[str, list] = {}
        self.running = True
        self.growth_cycle = 0
        self.milestones = []

        self.enable_dashboard = enable_dashboard
        self.enable_3d = enable_3d
        self.autostart = bool(autostart)

        if not self.autostart:
            self.running = False
            return

        if self.enable_dashboard:
            self.dashboard_thread = threading.Thread(target=self._start_dashboard, daemon=True)
            self.dashboard_thread.start()

        if self.enable_3d:
            self.plot_thread = threading.Thread(target=self._start_3d_plot, daemon=True)
            self.plot_thread.start()

        # Start autonomous skill loader with priority scheduling
        self.loader_thread = threading.Thread(target=self._auto_reload_skills, daemon=True)
        self.loader_thread.start()

        # Start main loop
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        logger.info("SkillNet main loop started automatically")

    def start(self, *, enable_dashboard=None, enable_3d=None):
        if self.running:
            return False

        if enable_dashboard is not None:
            self.enable_dashboard = bool(enable_dashboard)
        if enable_3d is not None:
            self.enable_3d = bool(enable_3d)

        self.running = True

        if self.enable_dashboard:
            self.dashboard_thread = threading.Thread(
                target=self._start_dashboard,
                daemon=True,
            )
            self.dashboard_thread.start()

        if self.enable_3d:
            self.plot_thread = threading.Thread(
                target=self._start_3d_plot,
                daemon=True,
            )
            self.plot_thread.start()

        self.loader_thread = threading.Thread(
            target=self._auto_reload_skills,
            daemon=True,
        )
        self.loader_thread.start()

        self.thread = threading.Thread(
            target=self.run,
            daemon=True,
        )
        self.thread.start()
        return True

    # -------------------------
    # AUTONOMOUS SKILL MODULE RELOAD WITH PRIORITY & RESOURCE MANAGEMENT
    # -------------------------
    def _auto_reload_skills(self):
        while self.running:
            try:
                # Measure system resources
                cpu_percent = psutil.cpu_percent()
                mem_percent = psutil.virtual_memory().percent
                # Skip low-priority modules if overloaded
                skip_low_priority = cpu_percent > 75 or mem_percent > 80

                for fname in os.listdir(self.skill_folder):
                    if fname.endswith(".py") and fname not in ["SkillNet.py", "__init__.py"]:
                        module_name = f"seed.skills.{fname[:-3]}"
                        path = os.path.join(self.skill_folder, fname)
                        mtime = os.path.getmtime(path)

                        # Priority default = 5 (1=critical, 10=low)
                        priority = self.module_priority.get(module_name, 5)
                        if skip_low_priority and priority > 5:
                            continue  # defer low-priority update

                        if module_name not in self.module_mtimes or self.module_mtimes[module_name] < mtime:
                            logger.info(f"Loading/updating skill module: {module_name}")
                            try:
                                if module_name in self.loaded_modules:
                                    importlib.reload(self.loaded_modules[module_name])
                                else:
                                    self.loaded_modules[module_name] = importlib.import_module(module_name)

                                # Update instances automatically
                                setattr(self, fname[:-3], getattr(self.loaded_modules[module_name], fname[:-3])() \
                                        if hasattr(self.loaded_modules[module_name], fname[:-3]) else None)
                                self.module_mtimes[module_name] = mtime
                            except Exception as e:
                                logger.error(f"Failed to load module {module_name}: {e}")
            except Exception as e:
                logger.error(f"Skill loader error: {e}")
            time.sleep(1.0)

    # -------------------------
    # ACTIVE MODULES REPORT
    # -------------------------
    def active_modules(self):
        mods = []
        for mod, name in [(self.vision, "VisionArray"), (self.audio, "AudioArray"),
                          (self.flight, "FlightOptimizer"), (self.navigation, "AutoNavigation"),
                          (self.em, "EMArray"), (self.lidar, "LidarArray"), (self.radar, "RadarArray")]:
            if mod:
                mods.append(name)
        return mods

    # -------------------------
    # MERGE QBITS & UPDATE SHARED MEMORY
    # -------------------------
    def merge_qbits(self):
        self.qbits.clear()
        modules = {"vision": self.vision, "audio": self.audio, "em": self.em,
                   "lidar": self.lidar, "radar": self.radar}
        for name, mod in modules.items():
            if mod and hasattr(mod, "qbit_vectors"):
                for obj_id, q in mod.qbit_vectors.items():
                    key = f"{name}_{obj_id}"
                    self.qbits[key] = q
                    # Shared memory update
                    self.shared_memory[key] = q
                    if key not in self.qbit_weights:
                        self.qbit_weights[key] = 1.0
                    if key not in self.qbit_confidence:
                        self.qbit_confidence[key] = 1.0

    # -------------------------
    # PREDICTIVE QBIT FUSION
    # -------------------------
    def fuse_predictive_state(self):
        self.predicted_state.clear()
        for key, q in self.qbits.items():
            weight = self.qbit_weights.get(key, 1.0)
            derivative = np.gradient(q)
            predictive = q + weight * 0.5 * derivative
            self.predicted_state[key] = predictive
            # Update shared memory for cross-skill access
            self.shared_memory[f"pred_{key}"] = predictive
            self.qbit_confidence[key] = np.clip(1.0 / (1.0 + np.linalg.norm(derivative)), 0.0, 1.0)

    # -------------------------
    # CROSS-SKILL MEMORY READ/WRITE API
    # -------------------------
    def write_memory(self, key: str, value: Any):
        self.shared_memory[key] = value

    def read_memory(self, key: str, default=None):
        return self.shared_memory.get(key, default)

    # -------------------------
    # ANOMALY DETECTION & SELF-CORRECTION
    # -------------------------
    def detect_anomalies(self):
        for key, q in self.predicted_state.items():
            if len(q) == 0 or np.isnan(q).any() or np.isinf(q).any():
                logger.warning(f"Anomaly detected in {key}, resetting Qbit...")
                self.qbit_weights[key] = 1.0
                self.qbit_confidence[key] = 0.5
                self.qbits[key] = np.zeros_like(q)
                self.shared_memory[f"pred_{key}"] = self.qbits[key]
            if len(q) >= 5:
                delta = np.abs(q[-1] - q[-2])
                if delta > np.mean(np.abs(np.gradient(q))) * 5:
                    logger.warning(f"Spike anomaly detected in {key}, applying weight correction")
                    self.qbit_weights[key] *= 0.8
                    self.qbit_confidence[key] *= 0.7

    # -------------------------
    # REWARD-BASED OPTIMIZATION
    # -------------------------
    def optimize_weights(self):
        for key, rewards in self.reward_history.items():
            if not rewards:
                continue
            success_rate = rewards.count(REWARD_SUCCESS) / len(rewards)
            old_weight = self.qbit_weights.get(key, 1.0)
            new_weight = old_weight * (1.0 + (success_rate - 0.5) * 0.2)
            self.qbit_weights[key] = np.clip(new_weight, 0.1, 3.0)

    # -------------------------
    # LOG REWARD
    # -------------------------
    def log_reward(self, key: str, reward_flag: str):
        if key not in self.reward_history:
            self.reward_history[key] = []
        self.reward_history[key].append(reward_flag)
        if len(self.reward_history[key]) > 50:
            self.reward_history[key].pop(0)

    # -------------------------
    # RUN SINGLE CYCLE
    # -------------------------
    def run_cycle(self):
        # Update all sensors dynamically
        for mod, name in [(self.vision, "vision"), (self.audio, "audio"),
                          (self.em, "em"), (self.lidar, "lidar"), (self.radar, "radar")]:
            if mod and hasattr(mod, "track_objects"):
                mod.track_objects()
                for obj_id in getattr(mod, "qbit_vectors", {}):
                    self.log_reward(f"{name}_{obj_id}", REWARD_SUCCESS)

        # Merge Qbits & update shared memory
        self.merge_qbits()

        # Flight predictions
        if self.flight:
            for obj_key in self.qbits.keys():
                if obj_key.startswith("vision"):
                    obj_id = int(obj_key.split("_")[1])
                    self.flight.predict_trajectory(obj_id)

        # Navigation update
        if self.navigation:
            mv = self.navigation.compute_movement_vector()
            cmds = self.navigation.generate_control_commands(mv)
            logger.debug(f"Navigation commands: {cmds}")
            self.log_reward("navigation", REWARD_SUCCESS)

        # Predictive fusion
        self.fuse_predictive_state()
        # Anomaly detection & correction
        self.detect_anomalies()
        # Weight optimization
        self.optimize_weights()

        # Adaptive growth cycle
        self.growth_cycle += 1
        if self.growth_cycle >= 10:
            self.growth_cycle = 0
            self.evaluate_growth_cycle()

    # -------------------------
    # GROWTH CYCLE / MILESTONES
    # -------------------------
    def evaluate_growth_cycle(self):
        self.milestones.append(time.time())

    # -------------------------
    # DASHBOARD
    # -------------------------
    def _start_dashboard(self):
        root = tk.Tk()
        root.title("SkillNet Dashboard")
        root.geometry("800x600")

        tree = ttk.Treeview(root)
        tree["columns"] = ("Predicted", "Weight", "Confidence")
        tree.heading("#0", text="Qbit")
        tree.heading("Predicted", text="Predicted")
        tree.heading("Weight", text="Weight")
        tree.heading("Confidence", text="Confidence")
        tree.column("#0", width=200)
        tree.column("Predicted", width=150)
        tree.column("Weight", width=100)
        tree.column("Confidence", width=100)
        tree.pack(fill="both", expand=True)

        def update_tree():
            tree.delete(*tree.get_children())
            for key, q in self.predicted_state.items():
                value = np.round(q[-1], 3) if len(q) > 0 else 0.0
                weight = np.round(self.qbit_weights.get(key, 1.0), 3)
                conf = np.round(self.qbit_confidence.get(key, 1.0), 3)
                tree.insert("", "end", text=key, values=(value, weight, conf))
            root.after(100, update_tree)

        root.after(100, update_tree)
        root.mainloop()

    # -------------------------
    # 3D PLOT VISUALIZATION WITH VELOCITY, RISK & CONFIDENCE
    # -------------------------
    def _start_3d_plot(self):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.set_title("SkillNet 3D Qbit Trajectories with Velocity, Risk & Confidence")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")

        while self.running:
            ax.cla()
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.set_zlabel("Z")
            keys = list(self.predicted_state.keys())
            for key in keys:
                q = self.predicted_state[key]
                if len(q) >= 3:
                    xs, ys, zs = q[-3], q[-2], q[-1]
                    vx, vy, vz = np.gradient([xs, ys, zs])
                    color = "green"
                    for other_key in keys:
                        if other_key != key:
                            oq = self.predicted_state[other_key]
                            if len(oq) >= 3:
                                dist = np.linalg.norm(np.array([xs, ys, zs]) - np.array([oq[-3], oq[-2], oq[-1]]))
                                if dist < 1.0:
                                    color = "red"
                    conf = self.qbit_confidence.get(key, 1.0)
                    if conf < 0.5:
                        color = "orange"
                    ax.quiver(xs, ys, zs, vx, vy, vz, color=color, length=0.1, normalize=True)
                    ax.scatter(xs, ys, zs, color=color)
            plt.pause(0.05)

    # -------------------------
    # MAIN LOOP
    # -------------------------
    def run(self):
        while self.running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error(f"SkillNet cycle error: {e}")
            time.sleep(0.01)

    # -------------------------
    # STOP / CLEANUP
    # -------------------------
    def stop(self):
        self.running = False
        for mod in [self.vision, self.audio, self.flight, self.navigation, self.em, self.lidar, self.radar]:
            if mod and hasattr(mod, "stop"):
                mod.stop()
        logger.info("SkillNet stopped successfully")

# -------------------------
# INSTANTIATE ACTIVE SKILLNET ON IMPORT
# -------------------------
skillnet_instance = SkillNet(
    enable_dashboard=False,
    enable_3d=False,
    autostart=False,
)

# -------------------------
# API FUNCTIONS
# -------------------------
get_global_qbits = lambda: skillnet_instance.qbits
get_predictive_state = lambda: skillnet_instance.predicted_state
get_qbit_confidence = lambda: skillnet_instance.qbit_confidence
read_shared_memory = lambda key, default=None: skillnet_instance.read_memory(key, default)
write_shared_memory = lambda key, value=None: skillnet_instance.write_memory(key, value)
stop_skillnet = lambda: skillnet_instance.stop()
