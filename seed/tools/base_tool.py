# File: SEED_ROOT/seed/tools/base_tool.py
import logging

logger = logging.getLogger("SEED-TOOL")

class BaseTool:
    def __init__(self, name=None):
        self.name = name or self.__class__.__name__
        self.active = False

    def start(self):
        self.active = True
        logger.info(f"[TOOL] {self.name} started")

    def stop(self):
        self.active = False
        logger.info(f"[TOOL] {self.name} stopped")

    def status(self):
        return {"name": self.name, "active": self.active}

    def report(self, msg):
        logger.info(f"[{self.name}] {msg}")
