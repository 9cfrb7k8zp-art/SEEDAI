# afm_core_nexus.py

import os
import json
import subprocess
import platform
import requests
import shutil
import ast
import threading
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "afm_nexus_config.json"
CREDENTIALS_FILE = BASE_DIR / "afm_credentials.json"
NEXUS_LOG = BASE_DIR / "afm_nexus_log.json"

AUTO_UPDATE = True
AUTO_INSTALL = True
AUTO_FIX = True
NETWORK_ENABLED = True


# Helper functions
def load_json(path, default={}):
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def nexus_log(event, detail):
    log = load_json(NEXUS_LOG, default=[])
    log.append(
        {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "detail": detail,
        }
    )
    save_json(NEXUS_LOG, log)
    print(f"[NEXUS] {event}: {detail}")


def install_package(package):
    try:
        subprocess.run(["pip", "install", package], check=True)
        nexus_log("package_installed", package)
    except subprocess.CalledProcessError as e:
        nexus_log("install_failed", f"{package} - {e}")


def fetch_and_run_remote_script(url):
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            code = resp.text
            exec(code, globals())
            nexus_log("remote_exec", f"Executed from {url}")
        else:
            nexus_log("remote_failed", f"{url} returned {resp.status_code}")
    except Exception as e:
        nexus_log("remote_exec_error", str(e))


def sync_with_github(repo_url, clone_path=BASE_DIR / "gh_sync"):
    if not NETWORK_ENABLED:
        nexus_log("network_blocked", "Sync skipped due to network setting")
        return
    if clone_path.exists():
        shutil.rmtree(clone_path)
    try:
        subprocess.run(["git", "clone", repo_url, str(clone_path)], check=True)
        nexus_log("github_sync", f"Cloned {repo_url}")
    except Exception as e:
        nexus_log("github_error", str(e))


def fix_code_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = [
            line.replace("\\", "\\\\") if "\\" in line else line for line in lines
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        nexus_log("auto_fix", str(path))
    except Exception as e:
        nexus_log("fix_failed", f"{path.name} - {str(e)}")


# 🔁 Replace your analyze_and_patch_scripts and nexus_log with these updated versions:


def load_json(path, default={}):
    if not path.exists():
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[!] JSONDecodeError in {path.name}: {e}")
        backup = path.with_suffix(".backup.json")
        shutil.copy(path, backup)
        print(f"[!] Backup created: {backup}")
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def nexus_log(event, detail):
    log = load_json(NEXUS_LOG, default=[])
    log.append(
        {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "detail": detail,
        }
    )
    save_json(NEXUS_LOG, log)
    print(f"[NEXUS] {event}: {detail}")


def analyze_and_patch_scripts():
    for py_file in BASE_DIR.rglob("*.py"):
        if py_file.name.startswith("afm_") or py_file.name == Path(__file__).name:
            continue
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
            # Skip Python 2 scripts
            if 'print "' in content and 'print("' not in content:
                nexus_log("skipped_legacy", py_file.name)
                continue
            ast.parse(content)
        except Exception as e:
            nexus_log("syntax_error", f"{py_file.name}: {str(e)}")
            if AUTO_FIX:
                fix_code_file(py_file)

    for py_file in BASE_DIR.rglob("*.py"):
        if py_file.name.startswith("afm_") or py_file.name == Path(__file__).name:
            continue
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                ast.parse(f.read())
        except Exception as e:
            nexus_log("syntax_error", f"{py_file.name}: {str(e)}")
            if AUTO_FIX:
                fix_code_file(py_file)


def update_modules():
    outdated = subprocess.check_output(["pip", "list", "--outdated"]).decode()
    for line in outdated.splitlines()[2:]:
        pkg = line.split()[0]
        if AUTO_UPDATE:
            install_package(pkg)


def access_user_context():
    user_info = load_json(
        CREDENTIALS_FILE, default={"user": "c-cla", "auth_level": "god"}
    )
    nexus_log("auth_context", user_info)
    return user_info


def run_afm_autonexus_v3():
    print("⚡ AFM Core Nexus: Full Dynamic System Growth")
    access_user_context()
    analyze_and_patch_scripts()
    update_modules()
    if NETWORK_ENABLED:
        sync_with_github("https://github.com/CentralCon")  # Customize
        fetch_and_run_remote_script(
            "https://raw.githubusercontent.com/YOUR-SCRIPT.py"
        )  # Customize
    print("🚀 Core Nexus Complete")


def grow_from_directory(root_dir):
    """Scan all files and evolve from them."""
    for item in root_dir.rglob("*"):
        if item.suffix in [".py", ".json", ".cfg", ".txt"]:
            try:
                with open(item, "r", encoding="utf-8") as f:
                    content = f.read()
                analyze_content(item.name, content)
            except Exception as e:
                nexus_log("read_failed", f"{item.name} - {e}")


def analyze_content(filename, content):
    # Intelligent growth pattern - AI-based parsing
    keywords = ["script", "module", "run", "connect", "task"]
    if any(k in content.lower() for k in keywords):
        nexus_log("growth_found", filename)
        # Example: dynamically load and attach functions
        try:
            exec(content, globals())
            nexus_log("exec_success", filename)
        except Exception as e:
            nexus_log("exec_error", f"{filename} - {e}")


def sync_github_autonomous():
    from urllib.parse import urljoin

    nexus_log("gh_sync_start", "https://github.com/CentralCon")
    clone_path = BASE_DIR / "github_sync"

    if clone_path.exists():
        shutil.rmtree(clone_path)
    try:
        subprocess.run(
            ["git", "clone", "https://github.com/CentralCon", str(clone_path)],
            check=True,
        )
        nexus_log("github_cloned", f"Repo: https://github.com/CentralCon")
    except Exception as e:
        nexus_log("github_clone_failed", str(e))

    # Grow from clone: absorb all .py, .json, .txt, and relevant configs
    grow_from_directory(clone_path)


if __name__ == "__main__":
    run_afm_autonexus_v3()

# Updated at 2025-06-15 12:16:02.455392
# Updated at 2025-06-15 23:15:57.592854


def run():
    print("🛠️ Auto-generated run() for module: afm_core_nexus.py")
