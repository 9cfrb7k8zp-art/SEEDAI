# File: forensics.py

import json
import datetime

def write_snapshot(watchdog, path="./SEED_ROOT/forensics"):
    data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "heartbeats": watchdog._heartbeats,
        "failures": watchdog._failures
    }

    fname = f"{path}/snapshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, "w") as f:
        json.dump(data, f, indent=2)
