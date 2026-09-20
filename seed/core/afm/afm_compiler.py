# =============================================================================
# SEED-AI :: AFM COMPILER (FULL)
# File: afm_compiler_full.py
# Version: 1.0.0
#
# PURPOSE:
#   One-time semantic compilation of AFM (C:\AFM) into SEED-AI usable state.
#
# GUARANTEES / INVARIANTS:
#   - READ-ONLY access to AFM
#   - NO execution of AFM code
#   - NO pip installs
#   - NO OS-level mutations
#   - Originals NEVER modified
#   - Compile ONCE, then seal
#
# OUTPUTS:
#   - afm_manifest.json       (ground truth)
#   - afm_wrappers.json       (execution contracts)
#   - afm_graph.json          (SEED-readable topology)
#
# =============================================================================

from pathlib import Path
import hashlib
import json
import ast
from datetime import datetime
from typing import Dict, List


class AFMCompiler:
    VERSION = "1.0.0"

    def __init__(
        self,
        afm_root: Path,
        seed_root: Path,
        output_dir: str = "afm_runtime",
    ):
        self.afm_root = Path(afm_root)
        self.seed_root = Path(seed_root)
        self.out_root = self.seed_root / output_dir

        self.manifest_path = self.out_root / "afm_manifest.json"
        self.wrapper_path = self.out_root / "afm_wrappers.json"
        self.graph_path = self.out_root / "afm_graph.json"

        self.census: Dict[str, dict] = {}
        self.manifest: Dict[str, dict] = {}
        self.wrappers: Dict[str, dict] = {}
        self.graph: Dict[str, dict] = {}

    # =========================================================================
    # ENTRY POINT
    # =========================================================================

    def compile_once(self):
        if self.manifest_path.exists():
            raise RuntimeError(
                "AFM already compiled. Manifest exists. "
                "Delete output folder manually to recompile."
            )

        self._prepare_output()
        self._run_census()
        self._classify()
        self._learn_from_logs()
        self._build_wrappers()
        self._build_graph()
        self._seal()

        self._write_all()

    # =========================================================================
    # PREP
    # =========================================================================

    def _prepare_output(self):
        self.out_root.mkdir(parents=True, exist_ok=True)

        self.manifest = {
            "meta": {
                "version": self.VERSION,
                "compiled_at": None,
                "afm_root": str(self.afm_root),
                "sealed": False,
            },
            "files": {},
            "groups": {
                "trusted": [],
                "wrapped": [],
                "archived": [],
                "ignored": [],
            },
        }

    # =========================================================================
    # PHASE 1 — CENSUS (READ ONLY)
    # =========================================================================

    def _run_census(self):
        for path in self.afm_root.rglob("*"):
            if not path.is_file():
                continue

            fid = self._hash(path)

            self.census[fid] = {
                "path": str(path),
                "suffix": path.suffix.lower(),
                "size": path.stat().st_size,
                "hash": fid,
                "imports": self._extract_imports(path),
            }

    def _hash(self, path: Path) -> str:
        h = hashlib.sha256()
        try:
            with path.open("rb") as f:
                h.update(f.read())
        except Exception:
            return "unreadable"
        return h.hexdigest()

    def _extract_imports(self, path: Path) -> List[str]:
        if path.suffix.lower() != ".py":
            return []

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            return ["<parse_error>"]

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend([n.name for n in node.names])
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        return imports

    # =========================================================================
    # PHASE 2 — CLASSIFICATION
    # =========================================================================

    def _classify(self):
        for fid, data in self.census.items():
            suf = data["suffix"]

            if suf in [".log", ".tmp", ".bak"]:
                decision = ("artifact", "ignored", "non-functional residue")

            elif suf in [".bat", ".cmd", ".ps1"]:
                decision = ("system-script", "archived", "unsafe to execute")

            elif suf in [".html", ".css", ".js"]:
                decision = ("interface", "wrapped", "ui asset")

            elif suf == ".json":
                decision = ("config", "trusted", "data-only")

            elif suf == ".py":
                if "<parse_error>" in data["imports"]:
                    decision = ("code", "archived", "parse failure")
                else:
                    decision = ("code", "wrapped", "sandbox only")

            else:
                decision = ("unknown", "ignored", "unsupported")

            role, group, reason = decision

            self.manifest["files"][fid] = {
                **data,
                "role": role,
                "decision": group,
                "reason": reason,
            }

            self.manifest["groups"][group].append(fid)

    # =========================================================================
    # PHASE 2.5 — ERROR LOG LEARNING (READ ONLY)
    # =========================================================================

    def _learn_from_logs(self):
        for fid in self.manifest["groups"]["ignored"]:
            path = Path(self.manifest["files"][fid]["path"])
            if path.suffix != ".log":
                continue

            try:
                content = path.read_text(errors="ignore")
            except Exception:
                continue

            self.manifest["files"][fid]["learned_patterns"] = self._extract_errors(
                content
            )

    def _extract_errors(self, text: str) -> List[str]:
        lines = text.splitlines()
        return [l.strip() for l in lines if "error" in l.lower()][:20]

    # =========================================================================
    # PHASE 3 — WRAPPER CONTRACTS (NO EXECUTION)
    # =========================================================================

    def _build_wrappers(self):
        for fid in self.manifest["groups"]["wrapped"]:
            file = self.manifest["files"][fid]

            self.wrappers[fid] = {
                "source": file["path"],
                "role": file["role"],
                "allowed": False,
                "interface": "read-only",
                "notes": "Requires explicit SEED sandbox approval",
            }

    # =========================================================================
    # PHASE 4 — GRAPH TOPOLOGY
    # =========================================================================

    def _build_graph(self):
        nodes = {}
        edges = []

        for fid, file in self.manifest["files"].items():
            nodes[fid] = {
                "role": file["role"],
                "decision": file["decision"],
            }

            for imp in file.get("imports", []):
                if imp:
                    edges.append(
                        {
                            "from": fid,
                            "to": imp,
                        }
                    )

        self.graph = {
            "nodes": nodes,
            "edges": edges,
        }

    # =========================================================================
    # SEAL
    # =========================================================================

    def _seal(self):
        self.manifest["meta"]["compiled_at"] = datetime.utcnow().isoformat()
        self.manifest["meta"]["sealed"] = True

    # =========================================================================
    # WRITE OUTPUTS
    # =========================================================================

    def _write_all(self):
        self._write(self.manifest_path, self.manifest)
        self._write(self.wrapper_path, self.wrappers)
        self._write(self.graph_path, self.graph)

    def _write(self, path: Path, data: dict):
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# =============================================================================
# END OF FILE
# =============================================================================
