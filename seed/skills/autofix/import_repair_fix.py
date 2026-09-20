# ==========================================================
# SEED AI OS
# ==========================================================
# FILE: import_repair_fix.py
# PATH: seed/skills/autofix/import_repair_fix.py
#
# VERSION: 2.0.0
# PHASE: CORE STABILITY / AUTOFIX
# CONTRACT: SAFE INTERNAL IMPORT REPAIR
#
# AUTHORITY:
#   - AutoFix skill layer
#   - NO kernel authority
#   - NO QbitDialer ownership
#   - NO boot-order authority
#
# PURPOSE:
#   Detect and conservatively repair malformed internal SEED imports.
#
# DESIGN RULES:
#   1. NEVER import QbitDialer from this module.
#   2. NEVER instantiate QbitDialer.
#   3. NEVER guess third-party package paths.
#   4. NEVER rewrite arbitrary imports.
#   5. Only operate on explicit internal "seed.*" imports.
#   6. Qbit/event integration is dependency-injected.
#   7. Failure to publish telemetry must never break the repair skill.
#   8. Preserve TrackID information whenever supplied.
#
# BOOT ORDER:
#   SEED CORE
#       ↓
#   QbitDialer / EventBus
#       ↓
#   AutoFix Namespace
#       ↓
#   ImportRepairFix
#
# DEPENDENCY DIRECTION:
#
#       AutoFix Skill
#            │
#            ├──> BaseFixSkill
#            ├──> logging
#            └──> optional injected event interface
#
#   AutoFix Skill
#            X
#       DOES NOT IMPORT
#            X
#       QbitDialer
#
# TRACKING:
#   TrackID-aware logging and optional Qbit/EventBus reporting.
#
# SAFETY:
#   Conservative heuristics only.
#   No filesystem mutation.
#   No dynamic module execution.
#   No third-party import rewriting.
#
# ==========================================================

from __future__ import annotations

import logging
import re
from typing import Any, Optional


# ==========================================================
# DEPENDENCIES
# ==========================================================

from seed.skills.autofix.base_fix_skill import FixSkill as BaseFixSkill


# ==========================================================
# LOGGER
# ==========================================================

logger = logging.getLogger("AutoFix.ImportRepair")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(name)s] %(levelname)s: %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

logger.propagate = False


# ==========================================================
# FIX SKILL
# ==========================================================

class FixSkill(BaseFixSkill):


    # ------------------------------------------------------
    # METADATA
    # ------------------------------------------------------

    name = "import_repair_fix"
    priority = 4

    description = (
        "Repairs malformed internal SEED imports using "
        "conservative, non-third-party heuristics."
    )

    version = "2.0.0"
    phase = "CORE_STABILITY"
    authority = "AUTOFIX_SKILL"
    layer = "SKILLS"
    contract = "SAFE_INTERNAL_IMPORT_REPAIR"

    # AutoFix should not become authoritative over Qbit.
    qbit_authority = "OBSERVER"
    mutation_scope = "SOURCE_TEXT_ONLY"
    third_party_repair = False
    filesystem_access = False
    dynamic_imports = False

    # ------------------------------------------------------
    # ERROR DETECTION
    # ------------------------------------------------------

    _pattern = re.compile(
        r"\b(?:ImportError|ModuleNotFoundError)\b"
    )

    # ------------------------------------------------------
    # SAFE INTERNAL IMPORT PATTERNS
    # ------------------------------------------------------

    # Matches:
    #
    #     from seed.foo import Bar
    #
    _from_import_pattern = re.compile(
        r"^(?P<indent>\s*)"
        r"from\s+"
        r"(?P<module>seed(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
        r"\s+import\s+"
        r"(?P<imports>.+?)"
        r"(?P<newline>\s*)$"
    )

    # Matches:
    #
    #     import seed.foo
    #
    _plain_import_pattern = re.compile(
        r"^(?P<indent>\s*)"
        r"import\s+"
        r"(?P<module>seed(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
        r"(?P<rest>\s*)$"
    )

    # ------------------------------------------------------
    # SAFE INTERNAL PATH NORMALIZATION
    # ------------------------------------------------------
    #
    # These mappings are deliberately explicit.
    #
    # IMPORTANT:
    # This skill does NOT attempt to discover arbitrary modules.
    #
    _SAFE_PATH_ALIASES = {
        # Historical / transitional paths can be added here
        # only when the destination is known and verified.
        #
        # Example:
        #
        # "seed.old.path": "seed.new.path",
    }

    # ======================================================
    # MATCH
    # ======================================================

    def match(self, content: str) -> bool:

        if not isinstance(content, str):
            return False

        return bool(self._pattern.search(content))

    # ======================================================
    # APPLY
    # ======================================================

    def apply(
        self,
        content: str,
        track_id: Optional[str] = None,
        qbit_dialer: Any = None,
    ) -> str:

        if not isinstance(content, str):
            logger.warning(
                "[%s] Invalid content type=%s | TrackID=%s",
                self.name,
                type(content).__name__,
                track_id,
            )

            self._publish_result(
                qbit_dialer=qbit_dialer,
                track_id=track_id,
                success=False,
                changed=False,
                reason="invalid_content_type",
            )

            return content

        lines = content.splitlines()
        fixed_lines = []

        applied_fix = False
        repair_count = 0

        # --------------------------------------------------
        # PROCESS EACH LINE
        # --------------------------------------------------

        for line in lines:
            original_line = line
            repaired_line = self._repair_import_line(line)

            if repaired_line != original_line:
                applied_fix = True
                repair_count += 1

                logger.info(
                    "[%s] Fixed import: %s -> %s | "
                    "TrackID=%s",
                    self.name,
                    original_line.strip(),
                    repaired_line.strip(),
                    track_id,
                )

            fixed_lines.append(repaired_line)

        # --------------------------------------------------
        # REPORT RESULT
        # --------------------------------------------------

        self._publish_result(
            qbit_dialer=qbit_dialer,
            track_id=track_id,
            success=True,
            changed=applied_fix,
            repair_count=repair_count,
            reason=(
                "repair_applied"
                if applied_fix
                else "no_safe_repair_available"
            ),
        )

        return "\n".join(fixed_lines)

    # ======================================================
    # IMPORT REPAIR ENGINE
    # ======================================================

    def _repair_import_line(self, line: str) -> str:


        if not isinstance(line, str):
            return line

        # --------------------------------------------------
        # FROM IMPORT
        # --------------------------------------------------

        match = self._from_import_pattern.match(line)

        if match:
            module = match.group("module")

            replacement = self._SAFE_PATH_ALIASES.get(module)

            if replacement:
                return (
                    f"{match.group('indent')}"
                    f"from {replacement} import "
                    f"{match.group('imports')}"
                )

            # No known safe mapping.
            return line

        # --------------------------------------------------
        # PLAIN IMPORT
        # --------------------------------------------------

        match = self._plain_import_pattern.match(line)

        if match:
            module = match.group("module")

            replacement = self._SAFE_PATH_ALIASES.get(module)

            if replacement:
                return (
                    f"{match.group('indent')}"
                    f"import {replacement}"
                )

            # No known safe mapping.
            return line

        return line

    # ======================================================
    # QBIT / EVENT REPORTING
    # ======================================================

    def _publish_result(
        self,
        qbit_dialer: Any,
        track_id: Optional[str],
        success: bool,
        changed: bool,
        repair_count: int = 0,
        reason: str = "",
    ) -> None:


        if qbit_dialer is None:
            logger.debug(
                "[%s] No Qbit interface supplied; "
                "telemetry skipped | TrackID=%s",
                self.name,
                track_id,
            )
            return

        event_bus = getattr(qbit_dialer, "event_bus", None)

        if event_bus is None:
            logger.debug(
                "[%s] Qbit interface has no event_bus; "
                "telemetry skipped | TrackID=%s",
                self.name,
                track_id,
            )
            return

        event_payload = {
            "channel": self.name,
            "skill": self.name,
            "skill_version": self.version,
            "phase": self.phase,
            "authority": self.authority,
            "track_id": track_id,
            "success": success,
            "changed": changed,
            "repair_count": repair_count,
            "reason": reason,
        }

        event_name = (
            "SKILL_SUCCESS"
            if success
            else "SKILL_FAILURE"
        )

        try:
            event_bus.publish(
                event_name,
                payload=event_payload,
            )

        except Exception as exc:
            # Telemetry must NEVER turn into a second boot/runtime
            # failure inside AutoFix.
            logger.warning(
                "[%s] Unable to publish %s: %s | TrackID=%s",
                self.name,
                event_name,
                exc,
                track_id,
            )

    # ======================================================
    # STATUS
    # ======================================================

    def metadata(self) -> dict[str, Any]:

        return {
            "name": self.name,
            "version": self.version,
            "priority": self.priority,
            "description": self.description,
            "phase": self.phase,
            "authority": self.authority,
            "layer": self.layer,
            "contract": self.contract,
            "qbit_authority": self.qbit_authority,
            "mutation_scope": self.mutation_scope,
            "third_party_repair": self.third_party_repair,
            "filesystem_access": self.filesystem_access,
            "dynamic_imports": self.dynamic_imports,
        }


# ==========================================================
# END OF FILE
# ==========================================================
# FILE: seed/skills/autofix/import_repair_fix.py
# VERSION: 2.0.0
# STATUS: SAFE / QBIT-DECOUPLED
# ==========================================================