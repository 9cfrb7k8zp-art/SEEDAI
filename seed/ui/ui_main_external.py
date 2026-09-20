# ==========================================================
# File: ui_main_external.py
# Path: SEED_ROOT/seed/ui/ui_main_external.py
# Version: 1.0 (EXTERNAL UI PROCESS)
# ==========================================================

import tkinter as tk
from seed.ipc.ipc_client import SEEDIPCClient
from seed.core.ipc_permissions import IPCDomain


class SEEDUIMainExternal:
    def __init__(self):
        self.client = SEEDIPCClient(domain=IPCDomain.USER)
        self.root = tk.Tk()
        self.root.title("SEED AI — Main Hub Portal")

        btn = tk.Button(
            self.root,
            text="Request State",
            command=self.request_state
        )
        btn.pack(padx=20, pady=20)

    def request_state(self):
        resp = self.client.send("ui.request_state")
        print("[UI] State:", resp)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SEEDUIMainExternal().run()
