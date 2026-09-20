# ==========================================================
# FILE: base_fix_skill.py
# PATH: seed/skills/autofix/base_fix_skill.py
# VERSION: 3.2 – SEED AI Integrated (SparkPlug + ModuleRegistry + TrackID)
# UPDATED: 2026-01-02
# ==========================================================

from abc import ABC, abstractmethod
import logging
import asyncio
import importlib
import pkgutil
from pathlib import Path
from typing import Optional, List, Dict, Type

from seed.skills.module_registry import ModuleRegistry, handle_skill_done
from seed.skills.sparkplug import SparkPlug


# ----------------------------------------------------------
# Logger Setup
# ----------------------------------------------------------
logger = logging.getLogger("AutoFix.BaseSkill")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ==========================================================
# Base FixSkill
# ==========================================================
class FixSkill(ABC):
    name = "base_fix"
    priority = 5
    description = "Base AutoFix skill"
    enabled = True  # Can be toggled dynamically

    def __init__(self):
        self.track_id = None
        # Register skill in ModuleRegistry on creation
        self.track_id = handle_skill_done(module_id=self.name)
    
    @abstractmethod
    def match(self, content: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def apply(self, content: str, track_id: Optional[str] = None) -> str:
        raise NotImplementedError

    async def apply_async(self, content: str, track_id: Optional[str] = None) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.apply(content, track_id))

    def log_apply(self, before: str, after: str, track_id: Optional[str] = None):
        track = track_id or self.track_id
        if not self.enabled:
            logger.info(f"[{self.name}] Disabled | TrackID={track}")
            return
        if before != after:
            logger.info(f"[{self.name}] Applied fix | TrackID={track}")
        else:
            logger.info(f"[{self.name}] No changes applied | TrackID={track}")

    def can_apply(self, content: str) -> bool:
        return self.enabled and self.match(content)

    def disable(self):
        self.enabled = False
        logger.info(f"[{self.name}] Disabled")

    def enable(self):
        self.enabled = True
        logger.info(f"[{self.name}] Enabled")


# ==========================================================
# AutoFix Pipeline
# ==========================================================
class AutoFixPipeline:
    def __init__(
        self,
        skills: Optional[List[FixSkill]] = None,
        autofix_folder: str = r"./SEED_ROOT/seed/skills",
        sparkplug = SparkPlug
    ):
        # Ensure we have a list of FixSkill objects
        self.skills: List[FixSkill] = sorted(skills or [], key=lambda s: s.priority)
        self.track_history = {}
        self.sparkplug = sparkplug or SparkPlug(skills_root="./skills", event_bus=None)

        if autofix_folder:
            self._load_skills_from_folder(autofix_folder)

        if autofix_folder:
            self._load_skills_from_folder(autofix_folder)

    def add_skill(self, skill: FixSkill):
        self.skills.append(skill)
        self.skills.sort(key=lambda s: s.priority)
        logger.info(f"[AutoFixPipeline] Skill added: {skill.name}")

    def remove_skill(self, skill_name: str):
        self.skills = [s for s in self.skills if s.name != skill_name]

    async def run_async(self, content: str, track_id: Optional[str] = None) -> str:
        result = content
        for skill in self.skills:
            # SparkPlug override check
            override = None
            if self.sparkplug and hasattr(self.sparkplug, "query_override"):
                try:
                    override = self.sparkplug.query_override({"content": result}, track_id=track_id)
                except Exception:
                    pass

            if override:
                result = override.get("modified_content", result)
                logger.info(f"[AutoFixPipeline] Skill {skill.name} overridden by SparkPlug | TrackID={track_id}")

            if skill.can_apply(result):
                before = result
                result = await skill.apply_async(result, track_id)
                skill.log_apply(before, result, track_id)
                self.track_history[skill.name] = track_id
        return result

    def run(self, content: str, track_id: Optional[str] = None) -> str:
        return asyncio.run(self.run_async(content, track_id))

    def get_track_history(self) -> Dict[str, str]:
        return dict(self.track_history)

    def _load_skills_from_folder(self, folder: str):
        path = Path(folder)
        if not path.exists():
            logger.warning(f"AutoFix folder not found: {folder}")
            return

        for finder, name, ispkg in pkgutil.iter_modules([str(path)]):
            try:
                module_path = str(path).replace("/", ".").replace("\\", ".")
                module = importlib.import_module(f"{module_path}.{name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, FixSkill) and attr != FixSkill:
                        skill_instance = attr()
                        self.add_skill(skill_instance)
                        logger.info(f"AutoFix skill loaded: {skill_instance.name}")
            except Exception as e:
                logger.exception(f"Failed to load skill {name}: {e}")


# ==========================================================
# Example Default Skills
# ==========================================================
class ExampleFixUppercase(FixSkill):
    name = "uppercase_fix"
    priority = 1
    description = "Converts text to uppercase"

    def match(self, content: str) -> bool:
        return any(c.islower() for c in content)

    def apply(self, content: str, track_id: Optional[str] = None) -> str:
        return content.upper()


class ExampleFixRemoveWhitespace(FixSkill):
    name = "remove_whitespace"
    priority = 2
    description = "Removes extra whitespace"

    def match(self, content: str) -> bool:
        return "  " in content or "\n\n" in content

    def apply(self, content: str, track_id: Optional[str] = None) -> str:
        return " ".join(content.split())


# ==========================================================
# Demo / Standalone Test
# ==========================================================
if __name__ == "__main__":
    demo_content = "This   is  a Demo \n\nString"
    pipeline = AutoFixPipeline(
        skills=[ExampleFixUppercase(), ExampleFixRemoveWhitespace()]
    )

    print("=== BEFORE ===")
    print(demo_content)

    fixed = pipeline.run(demo_content, track_id="TRACK-DEMO-123")
    print("\n=== AFTER SYNC ===")
    print(fixed)

    async def demo_async():
        demo_content2 = "Async   Demo text"
        fixed_async = await pipeline.run_async(demo_content2, track_id="TRACK-ASYNC-456")
        print("\n=== AFTER ASYNC ===")
        print(fixed_async)

    asyncio.run(demo_async())
