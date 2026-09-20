# ==========================================================
# FILE: tmp_setup.py
# PATH: SEED_ROOT/seed/skills/tmp_setup.py
# VERSION: 2.0
# PURPOSE: Multi-channel build for py_seed C++ extension
#          Handles build, move, patch imports, verify module, retries
# UPDATED: 2025-12-29
# ==========================================================

from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext
import os
import sys
import shutil
import importlib.util
import subprocess
import time

# -------------------------
# Paths
# -------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src").replace("\\", "/")
CORE_DIR = os.path.join(ROOT_DIR, "seed", "core").replace("\\", "/")
MODULE_NAME = "py_seed"
SOURCE_FILE = os.path.join(SRC_DIR, "py_seed_bindings.cpp").replace("\\", "/")

# -------------------------
# Channels (multi-target build)
# -------------------------
CHANNELS = [
    {"name": "main", "build_type": "Release"},
    {"name": "debug", "build_type": "Debug"},
]

# -------------------------
# MSVC detection
# -------------------------
def check_msvc():
    if os.name != "nt":
        return True
    try:
        result = subprocess.run(["cl"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            print("⚠️ MSVC compiler not detected. Install Microsoft C++ Build Tools v14+")
            return False
    except FileNotFoundError:
        print("⚠️ MSVC compiler not found. Install Microsoft C++ Build Tools v14+")
        return False
    return True

if not check_msvc():
    sys.exit(1)

# -------------------------
# Build function for one channel
# -------------------------
def build_channel(channel):
    print(f"\n=== Building channel '{channel['name']}' ({channel['build_type']}) ===")
    ext_modules = [
        Pybind11Extension(
            name=MODULE_NAME,
            sources=[SOURCE_FILE],
            include_dirs=[SRC_DIR],
            language="c++",
            extra_compile_args=["-std=c++17"],
        )
    ]
    setup(
        name=MODULE_NAME,
        version="1.0",
        ext_modules=ext_modules,
        cmdclass={"build_ext": build_ext},
        script_args=["build_ext", "--inplace"],
    )

# -------------------------
# Move compiled module
# -------------------------
def move_module():
    built_module = None
    for file in os.listdir(ROOT_DIR):
        if file.startswith(MODULE_NAME) and file.endswith(".pyd"):
            built_module = os.path.join(ROOT_DIR, file)
            break
    if not built_module:
        print(f"❌ Compiled module {MODULE_NAME} not found in {ROOT_DIR}")
        return False
    os.makedirs(CORE_DIR, exist_ok=True)
    dest_path = os.path.join(CORE_DIR, os.path.basename(built_module))
    shutil.move(built_module, dest_path)
    print(f"✅ Moved compiled module to: {dest_path}")
    return True

# -------------------------
# Patch imports
# -------------------------
def patch_imports(folder):
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                new_content = content.replace("import py_seed_bindings", f"import {MODULE_NAME}")
                new_content = new_content.replace("from py_seed_bindings import", f"from {MODULE_NAME} import")
                if new_content != content:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Patched imports in: {path}")

# -------------------------
# Verify module
# -------------------------
def verify_module(retries=3, delay=0.5):
    for attempt in range(1, retries+1):
        try:
            spec = importlib.util.find_spec(MODULE_NAME)
            if spec is None:
                raise ImportError(f"Module {MODULE_NAME} not found.")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print(f"✅ Module '{MODULE_NAME}' loaded successfully on attempt {attempt}!")
            return True
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}")
            time.sleep(delay)
    print(f"❌ Failed to load module '{MODULE_NAME}' after {retries} attempts.")
    return False

# -------------------------
# Main multi-channel build
# -------------------------
if __name__ == "__main__":
    for channel in CHANNELS:
        build_channel(channel)
        if move_module():
            patch_imports(CORE_DIR)
            verify_module()
