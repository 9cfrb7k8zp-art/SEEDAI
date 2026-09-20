# ==========================================================
# FILE: fix_sekf.py
# PURPOSE: Scan and fix 'self' typos in SEED modules
# MODULES SCANNED: ActuatorEngine, QbitDialer, SparkPlugLoader
# ==========================================================

import os
import re

# Base path for SEED_ROOT (adjust if needed)
SEED_ROOT = r"C:\SEED_ROOT\seed\core"

# Modules to scan
modules = [
    "actuator_engine.py",
    "qbit_dialer.py",
    "sparkplug_loader.py"
]

def fix_sekf_in_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "self" in content:
        fixed_content = re.sub(r"\bsekf\b", "self", content)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(fixed_content)
        print(f"[FIXED] {file_path}")
    else:
        print(f"[OK] No 'self' found in {file_path}")

def main():
    for module in modules:
        file_path = os.path.join(SEED_ROOT, module)
        if os.path.isfile(file_path):
            fix_sekf_in_file(file_path)
        else:
            print(f"[ERROR] Module not found: {file_path}")

if __name__ == "__main__":
    main()
