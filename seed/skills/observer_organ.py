# ==========================================================
# FILE: observer_organ.py
# PATH: SEED_ROOT/seed/skills/observer_organ.py
# VERSION: 2.0.0 — BOOT-SAFE / OBSERVER-ONLY
# PURPOSE:
#   Observe inbox/autofix material, score proposals, and write
#   bounded reflection artifacts to outbox.
# AUTHORITY:
#   Observer only. Never executes code or mutates core runtime.
# ==========================================================

import json
import time
from pathlib import Path
from typing import List, Tuple

BASE_DIR = Path(__file__).resolve().parent
AUTOFIX_DIR = BASE_DIR / "autofix"
INBOX_DIR = BASE_DIR / "inbox"
OUTBOX_DIR = BASE_DIR / "outbox"
STATE_FILE = BASE_DIR / "observer_state.json"

MAX_NEW_FILES = 10
OBSERVER_ID = "OBSERVER_ORGAN_V2"


class ObserverOrgan:
    MAX_NEW_FILES = MAX_NEW_FILES
    DECAY_FACTOR = 0.9
    KEYWORD_BOOST = 5

    def __init__(self, logger=None):
        self.logger = logger
        self.created_files = 0
        self.state = self._load_state()
        self.seen_files = {
            Path(p)
            for p in self.state.get("seen_files", [])
        }
        self.written_modules = set(
            self.state.get("outbox_created", [])
        )
        self.module_counter = int(
            self.state.get("module_counter", 0)
        )
        self.keyword_weights = dict(
            self.state.get("keyword_weights", {})
        )
        self.event_bus = None
        self.track_system = None
        self.oracle = None
        OUTBOX_DIR.mkdir(parents=True, exist_ok=True)

    def bind_runtime(
        self,
        *,
        event_bus=None,
        track_system=None,
        oracle=None,
        **_kwargs,
    ):
        self.event_bus = event_bus
        self.track_system = track_system
        self.oracle = oracle
        return True

    def _load_state(self):
        if not STATE_FILE.exists():
            return {
                "seen_files": [],
                "outbox_created": [],
                "module_counter": 0,
                "keyword_weights": {},
            }
        try:
            return json.loads(
                STATE_FILE.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return {
                "seen_files": [],
                "outbox_created": [],
                "module_counter": 0,
                "keyword_weights": {},
            }

    def _save_state(self):
        try:
            self.state["seen_files"] = [
                str(p) for p in self.seen_files
            ]
            self.state["outbox_created"] = list(
                self.written_modules
            )
            self.state["module_counter"] = (
                self.module_counter
            )
            self.state["keyword_weights"] = (
                self.keyword_weights
            )
            STATE_FILE.write_text(
                json.dumps(
                    self.state,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            self._log(
                f"[ObserverOrgan] State save failed: {exc}"
            )

    def tick(self):
        proposals = []
        try:
            self._decay_weights()
            proposals.extend(self._scan_inbox())
            proposals.extend(self._scan_autofix())

            scored = []
            for note, file_path in proposals:
                score, reason = self._score_file(
                    file_path,
                    note,
                )
                scored.append(
                    (
                        score,
                        reason,
                        note,
                        file_path,
                    )
                )

            scored.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            for score, reason, note, file_path in scored:
                if not self._outbox_write_allowed():
                    break
                content, name = self._wrap_as_module(
                    note,
                    file_path,
                    score,
                    reason,
                )
                self._emit_outbox(
                    content,
                    name,
                )

            self._save_state()
            return {
                "ok": True,
                "proposals": len(scored),
                "created": self.created_files,
            }
        except Exception as exc:
            self._log(
                f"[ObserverOrgan] Soft failure: {exc}"
            )
            return {
                "ok": False,
                "error": str(exc),
            }

    def _decay_weights(self):
        for key in list(self.keyword_weights):
            self.keyword_weights[key] *= self.DECAY_FACTOR

    def _scan_directory(self, directory) -> List[Tuple[str, Path]]:
        notes = []
        if not directory.exists():
            return notes
        for file in directory.glob("*.*"):
            if file in self.seen_files:
                continue
            try:
                text = file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
                summary = self._summarize_text(text)
                notes.append(
                    (
                        summary,
                        file,
                    )
                )
                self.seen_files.add(file)
            except Exception as exc:
                self._log(
                    f"[ObserverOrgan] Skip {file.name}: {exc}"
                )
        return notes

    def _scan_inbox(self):
        return self._scan_directory(INBOX_DIR)

    def _scan_autofix(self):
        return self._scan_directory(AUTOFIX_DIR)

    def _summarize_text(self, text: str) -> str:
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]
        return "\n".join(lines[:10])

    def _score_file(self, file_path: Path, note: str):
        score = 0
        reasons = []
        suffix = file_path.suffix.lower()

        if suffix in {".dll", ".so", ".bin"}:
            score += 50
            reasons.append("binary library")
        elif suffix in {".py", ".md"}:
            score += 20
            reasons.append("script / markdown")

        try:
            size_kb = file_path.stat().st_size / 1024
        except Exception:
            size_kb = 0

        if size_kb > 50:
            score += 10
            reasons.append(
                f"large file {int(size_kb)} KB"
            )

        for keyword in (
            "run(",
            "ctypes",
            "class",
            "module",
            "after(",
            "self.ui_enabled",
        ):
            if keyword in note:
                weight = (
                    self.keyword_weights.get(
                        keyword,
                        0,
                    )
                    + self.KEYWORD_BOOST
                )
                self.keyword_weights[keyword] = weight
                score += weight
                reasons.append(
                    f"{keyword} weight={weight}"
                )

        return score, (
            ", ".join(reasons)
            if reasons
            else "default"
        )

    def _wrap_as_module(
        self,
        content,
        file_path,
        score,
        reason,
    ):
        self.module_counter += 1
        module_name = (
            f"{file_path.stem}_mod_"
            f"{self.module_counter:03d}"
        )
        module_content = (
            "# Observer Generated Scaffold\n"
            f"# Source: {file_path.name}\n"
            f"# Score: {score}\n"
            f"# Reason: {reason}\n\n"
            f"class {module_name}:\n"
            f"    source = {file_path.name!r}\n"
            f"    observer_note = {content!r}\n"
            f"    priority_score = {score!r}\n"
            "    def act(self):\n"
            "        # Proposal only; no execution authority.\n"
            "        return None\n"
        )
        return module_content, module_name

    def _outbox_write_allowed(self):
        return (
            self.created_files
            < self.MAX_NEW_FILES
        )

    def _emit_outbox(self, content, module_name):
        filename = (
            f"{module_name}_{int(time.time())}.py"
        )
        if filename in self.written_modules:
            return
        path = OUTBOX_DIR / filename
        try:
            path.write_text(
                content,
                encoding="utf-8",
            )
            self.created_files += 1
            self.written_modules.add(filename)
            self._save_state()
            self._log(
                f"[ObserverOrgan] Wrote {filename}"
            )
        except Exception as exc:
            self._log(
                f"[ObserverOrgan] Write failed: {exc}"
            )

    def _log(self, message):
        if self.logger is not None:
            self.logger.info(message)
        else:
            print(message)


def observer_tick(logger=None):
    return ObserverOrgan(
        logger=logger
    ).tick()


if __name__ == "__main__":
    observer_tick()
