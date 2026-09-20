# ==========================================================
# FILE: SEED_AI_V.py
# PATH: SEED_ROOT\seed\skills\SEED_AI_V.py
# DESCRIPTION: SEED AI — V0.1.1 (Smarter Action Bias)
# STATUS: Runnable / Enhanced
# ==========================================================

import os
import threading
import time
import queue
import logging
from pathlib import Path
from random import random

# -------------------------------
# Setup Logging
# -------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger("SEED_AI_V0.1.1")

# -------------------------------
# Config / Constants
# -------------------------------
SKILLS_FOLDER = Path("skills_folder")
SKILLS_INBOX = Path("skills_inbox")
FRAME_QUEUE_MAX = 100  # max queued skill frames
EVAL_INTERVAL_NORMAL = 2  # seconds
EVAL_INTERVAL_LIMP = 5    # seconds (slower under limp mode)
CONFIDENCE_DECAY = 0.98   # confidence decay per cycle for old skills

# -------------------------------
# Ensure skill folders exist
# -------------------------------
for folder in [SKILLS_FOLDER, SKILLS_INBOX]:
    folder.mkdir(exist_ok=True)

# -------------------------------
# TransformerBrain Class
# -------------------------------
class TransformerBrain:
    def __init__(self, name, weight=1.0):
        self.name = name
        self.confidence = 1.0
        self.history = []
        self.lock = threading.Lock()
        self.weight = weight  # weight in final skill score

    def evaluate(self, metric_value):
        """Update confidence based on metric input and random variation"""
        delta = (random() - 0.5) * 0.05  # smaller random variation
        new_conf = max(0.0, min(1.0, metric_value + delta))
        with self.lock:
            self.confidence = new_conf
            self.history.append(new_conf)
        logger.debug(f"[{self.name}] Confidence updated: {self.confidence:.3f}")
        return self.confidence

# -------------------------------
# Skill Frame
# -------------------------------
class SkillFrame:
    def __init__(self, skill_name, source):
        self.skill_name = skill_name
        self.source = source
        self.timestamp = time.time()
        self.evaluated = False
        self.score = None
        self.execution_ready = False  # future execution flag

# -------------------------------
# Health Monitor
# -------------------------------
class HealthMonitor:
    def __init__(self):
        self.limp_mode = False
        self.metrics = {"cpu": 1.0, "memory": 1.0}

    def update_metrics(self):
        """Simulate CPU/memory fluctuations"""
        self.metrics["cpu"] = max(0.0, min(1.0, 0.8 + (random() - 0.5) * 0.4))
        self.metrics["memory"] = max(0.0, min(1.0, 0.8 + (random() - 0.5) * 0.4))
        if self.metrics["cpu"] < 0.2 or self.metrics["memory"] < 0.2:
            if not self.limp_mode:
                logger.warning("[HealthMonitor] Entering limp mode due to low metrics")
            self.limp_mode = True
        else:
            if self.limp_mode:
                logger.info("[HealthMonitor] Exiting limp mode")
            self.limp_mode = False
        return self.metrics

# -------------------------------
# Qbit Dialer
# -------------------------------
class QbitDialer(threading.Thread):
    def __init__(self, frame_queue, brains, health_monitor):
        super().__init__(daemon=True)
        self.frame_queue = frame_queue
        self.brains = brains
        self.health_monitor = health_monitor
        self.running = True
        self.processed_skills = set()  # deduplicate skills

    def ingest_skills(self):
        """Read new skills from folder + inbox with priority"""
        skills = []
        for folder in [SKILLS_INBOX, SKILLS_FOLDER]:  # inbox prioritized
            if folder.exists():
                for file in folder.glob("*.skill"):
                    if file.stem not in self.processed_skills:
                        self.processed_skills.add(file.stem)
                        skills.append(SkillFrame(skill_name=file.stem, source=str(folder)))
        return skills

    def evaluate_skills(self, skills):
        """Evaluate skills using brains with weighting and decay"""
        for skill in skills:
            metric = (self.health_monitor.metrics["cpu"] + self.health_monitor.metrics["memory"]) / 2
            # Apply age decay if skill is older than 10 seconds
            age_seconds = time.time() - skill.timestamp
            decay_factor = CONFIDENCE_DECAY ** (age_seconds / 10)
            weighted_conf = sum(brain.evaluate(metric) * brain.weight for brain in self.brains) / len(self.brains)
            skill.score = max(0.0, min(1.0, weighted_conf * decay_factor))
            skill.evaluated = True
            # Decide execution readiness (mock)
            skill.execution_ready = skill.score > 0.75
            try:
                self.frame_queue.put_nowait(skill)
            except queue.Full:
                logger.warning(f"[QbitDialer] Frame queue full, dropping skill: {skill.skill_name}")
            logger.info(f"[QbitDialer] Evaluated: {skill.skill_name}, score: {skill.score:.3f}, ready: {skill.execution_ready}")

    def run(self):
        logger.info("[QbitDialer] Idle processor started")
        while self.running:
            metrics = self.health_monitor.update_metrics()
            interval = EVAL_INTERVAL_LIMP if self.health_monitor.limp_mode else EVAL_INTERVAL_NORMAL
            skills = self.ingest_skills()
            if skills:
                self.evaluate_skills(skills)
            else:
                logger.debug("[QbitDialer] No new skills found")
            time.sleep(interval)

# -------------------------------
# Main SEED AI Class
# -------------------------------
class SEEDAI:
    def __init__(self):
        self.frame_queue = queue.Queue(maxsize=FRAME_QUEUE_MAX)
        self.brains = [
            TransformerBrain("CPU", weight=1.2),
            TransformerBrain("Audio", weight=1.0),
            TransformerBrain("SystemCalc", weight=0.9),
            TransformerBrain("Modem", weight=1.1)
        ]
        self.health_monitor = HealthMonitor()
        self.qbit_dialer = QbitDialer(self.frame_queue, self.brains, self.health_monitor)

    def start(self):
        logger.info("[SEEDAI] Starting SEED AI V0.1.1")
        self.qbit_dialer.start()
        logger.info("[SEEDAI] Qbit Dialer running. Waiting for skills...")

    def stop(self):
        self.qbit_dialer.running = False
        self.qbit_dialer.join()
        logger.info("[SEEDAI] SEED AI stopped")

    def process_frame_queue(self):
        """Process and log frames, simulating execution"""
        processed_count = 0
        while not self.frame_queue.empty():
            frame = self.frame_queue.get()
            status = "EXECUTE" if frame.execution_ready else "EVALUATE_ONLY"
            logger.info(f"[SEEDAI] Frame: {frame.skill_name}, score: {frame.score:.3f}, status: {status}")
            processed_count += 1
        if processed_count > 0:
            logger.info(f"[SEEDAI] Processed {processed_count} frames in this cycle")

# -------------------------------
# Runnable
# -------------------------------
if __name__ == "__main__":
    seed_ai = SEEDAI()
    seed_ai.start()
    try:
        while True:
            seed_ai.process_frame_queue()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("[SEEDAI] KeyboardInterrupt received. Shutting down...")
        seed_ai.stop()
