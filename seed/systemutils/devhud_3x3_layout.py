# ==========================================================
# FILE: devhud_3x3_layout.py
# PATH: SEED_ROOT/seed/systemutils/devhud_3x3_layout.py
# VERSION: 1.0.0
# PURPOSE: DEVHUD authoritative 3x3 presentation layout
# AUTHORITY: DEVHUD presentation; QbitDialer remains command authority
# ==========================================================

import html
import re
import threading
import webbrowser
from html.parser import HTMLParser

import tkinter as tk
from tkinter import ttk

try:
    import requests
except Exception:
    requests = None


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3"):
            self.parts.append("\\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "li", "h1", "h2", "h3"):
            self.parts.append("\\n")

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())

    def text(self):
        value = html.unescape(" ".join(self.parts))
        value = re.sub(r"[ \\t]+", " ", value)
        value = re.sub(r"\\n[ \\n]+", "\\n", value)
        return value.strip()


def build_3x3(devhud):
    """Replace the competing legacy geometry with one deterministic 3x3 shell."""
    root = devhud
    for child in root.winfo_children():
        try:
            child.destroy()
        except Exception:
            pass

    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=1)
    root.grid_rowconfigure(2, weight=0)
    root.grid_columnconfigure(0, weight=0, minsize=250)
    root.grid_columnconfigure(1, weight=1, minsize=560)
    root.grid_columnconfigure(2, weight=0, minsize=330)

    _build_top(devhud)
    _build_left(devhud)
    _build_center(devhud)
    _build_right(devhud)
    _build_footer(devhud)

    try:
        devhud._wire_events()
    except Exception:
        pass

    try:
        devhud.status = "READY"
        devhud.status_var.set("SEED DEVHUD • 3×3 • runtime attached • QbitDialer authority")
    except Exception:
        pass

    return root


def _frame(parent, row, column, **kw):
    f = ttk.Frame(parent, **kw)
    f.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
    f.grid_columnconfigure(0, weight=1)
    f.grid_rowconfigure(0, weight=1)
    return f


def _build_top(d):
    bar = ttk.Frame(d)
    bar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=4, pady=(4, 2))
    for c in range(8):
        bar.grid_columnconfigure(c, weight=0)
    bar.grid_columnconfigure(7, weight=1)
    ttk.Label(bar, text="SEED DEVHUD", font=("Consolas", 13, "bold")).grid(row=0, column=0, padx=8)
    for i, (label, command) in enumerate((
        ("SEED", getattr(d, "request_status", lambda: d._emit_seed_input("STATUS"))),
        ("SYSTEM", getattr(d, "request_status", lambda: d._emit_seed_input("GET_STATE"))),
        ("COGNITION", lambda: d._emit_seed_input("COGNITION_STATUS")),
        ("QUEUE", lambda: d._emit_seed_input("QUEUE_STATUS")),
        ("TOOLS", lambda: d._emit_seed_input("STATUS")),
        ("DATABASE", lambda: d._emit_seed_input("DB_STATUS")),
        ("WEB", lambda: _select_center(d, "Web")),
    )):
        ttk.Button(bar, text=label, command=command).grid(row=0, column=i+1, padx=2)
    ttk.Label(bar, text="LIVE", anchor="e").grid(row=0, column=7, sticky="e", padx=8)


def _build_left(d):
    panel = _frame(d, 1, 0)
    panel.grid_rowconfigure(1, weight=1)
    ttk.Label(panel, text="NAVIGATION / TOOLS", font=("Consolas", 10, "bold")).grid(row=0, column=0, sticky="w")
    book = ttk.Notebook(panel)
    book.grid(row=1, column=0, sticky="nsew", pady=4)
    nav = ttk.Frame(book); design = ttk.Frame(book); learn = ttk.Frame(book); inputs = ttk.Frame(book)
    book.add(nav, text="Navigation"); book.add(design, text="Design"); book.add(learn, text="Learning"); book.add(inputs, text="Input")
    for frame in (nav, design, learn, inputs):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(99, weight=1)
    for i, (name, cmd) in enumerate((
        ("SEED Status", "STATUS"), ("System State", "GET_STATE"), ("Cognition", "COGNITION_STATUS"),
        ("Heartbeat", "HEARTBEAT_STATUS"), ("Measure", "MEASURE"), ("Queue", "QUEUE_STATUS"),
        ("Snapshot", "SNAPSHOT"), ("Pause", "PAUSE_BACKGROUND"),
    )):
        ttk.Button(nav, text=name, command=lambda c=cmd: d._emit_seed_input(c, "DEVHUD_NAV")).grid(row=i, column=0, sticky="ew", pady=2)
    for i, name in enumerate(("Web content", "System map", "Qbit view", "HUD layout")):
        ttk.Button(design, text=name, command=lambda n=name: _select_center(d, n if n != "Web content" else "Web")).grid(row=i, column=0, sticky="ew", pady=2)
    for i, cmd in enumerate(("LEARN_STATUS", "LESSONS", "MEMORY", "ADAPTIVE_STATUS")):
        ttk.Button(learn, text=cmd.replace("_", " ").title(), command=lambda c=cmd: d._emit_seed_input(c, "DEVHUD_LEARNING")).grid(row=i, column=0, sticky="ew", pady=2)
    for i, mode in enumerate(("Text / CLI", "Voice", "Files", "Web", "Camera", "Audio / Video")):
        ttk.Button(inputs, text=mode, command=lambda m=mode: _set_input_mode(d, m)).grid(row=i, column=0, sticky="ew", pady=2)


def _build_center(d):
    panel = _frame(d, 1, 1)
    panel.grid_rowconfigure(1, weight=1)
    ttk.Label(panel, text="CONTENT", font=("Consolas", 10, "bold")).grid(row=0, column=0, sticky="w")
    tabs = ttk.Notebook(panel)
    tabs.grid(row=1, column=0, sticky="nsew")
    d.center_tabs = tabs
    web = ttk.Frame(tabs); system = ttk.Frame(tabs); db = ttk.Frame(tabs); apps = ttk.Frame(tabs)
    tabs.add(web, text="Web"); tabs.add(system, text="System"); tabs.add(db, text="Database"); tabs.add(apps, text="Apps / Email")
    _build_web(d, web); _build_system(d, system); _build_db(d, db); _build_apps(d, apps)


def _build_web(d, parent):
    parent.grid_columnconfigure(0, weight=1); parent.grid_rowconfigure(1, weight=1)
    row = ttk.Frame(parent); row.grid(row=0, column=0, sticky="ew", pady=4); row.grid_columnconfigure(1, weight=1)
    ttk.Label(row, text="URL").grid(row=0, column=0, padx=4)
    d.web_url = tk.StringVar(value="https://www.google.com")
    ttk.Entry(row, textvariable=d.web_url).grid(row=0, column=1, sticky="ew")
    ttk.Button(row, text="LOAD", command=lambda: _fetch_web(d)).grid(row=0, column=2, padx=3)
    ttk.Button(row, text="OPEN BROWSER", command=lambda: webbrowser.open(d.web_url.get())).grid(row=0, column=3, padx=3)
    d.web_content = tk.Text(parent, wrap="word", font=("Consolas", 10))
    d.web_content.grid(row=1, column=0, sticky="nsew")
    d.web_content.insert("end", "Web content window ready. LOAD fetches readable page content; OPEN BROWSER launches the full interactive site.")


def _fetch_web(d):
    url = d.web_url.get().strip()
    if not url: return
    if not url.startswith(("http://", "https://")): url = "https://" + url
    d.web_url.set(url)
    d.web_content.delete("1.0", "end")
    d.web_content.insert("end", "Loading…\\n")
    def worker():
        try:
            if requests is None: raise RuntimeError("requests package unavailable")
            r = requests.get(url, timeout=8, headers={"User-Agent": "SEED-DEVHUD/1.0"})
            r.raise_for_status()
            parser = _TextExtractor(); parser.feed(r.text)
            text = parser.text()[:100000]
            result = "HTTP %s\\n\\n%s" % (r.status_code, text)
        except Exception as exc:
            result = "WEB ERROR: %s\\n\\nUse OPEN BROWSER for full interactive browsing." % exc
        try:
            d.after(0, lambda: _set_web_text(d, result))
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()


def _set_web_text(d, text):
    try:
        d.web_content.delete("1.0", "end"); d.web_content.insert("end", text)
    except Exception: pass


def _build_system(d, parent):
    parent.grid_columnconfigure(0, weight=1); parent.grid_rowconfigure(1, weight=1)
    ttk.Label(parent, text="Runtime controls remain routed through QbitDialer.").grid(row=0, column=0, sticky="w", pady=4)
    d.system_view = tk.Text(parent, wrap="word", font=("Consolas", 10)); d.system_view.grid(row=1, column=0, sticky="nsew")
    buttons = ttk.Frame(parent)
    buttons.grid(row=2, column=0, sticky="ew", pady=3)
    for i, cmd in enumerate(("STATUS", "GET_STATE", "COGNITION_STATUS", "HEARTBEAT_STATUS", "QUEUE_STATUS", "MEASURE")):
        ttk.Button(buttons, text=cmd, command=lambda c=cmd: _system_command(d, c)).grid(row=0, column=i, padx=2)


def _system_command(d, cmd):
    try: d._emit_seed_input(cmd, "DEVHUD_SYSTEM")
    finally:
        try: d.system_view.insert("end", "\\n> " + cmd)
        except Exception: pass


def _build_db(d, parent):
    parent.grid_columnconfigure(0, weight=1); parent.grid_rowconfigure(1, weight=1)
    ttk.Label(parent, text="SEED DATABASE — mirror, runtime state, updates, recovery, components").grid(row=0, column=0, sticky="w", pady=4)
    d.db_view = tk.Text(parent, wrap="word", font=("Consolas", 10)); d.db_view.grid(row=1, column=0, sticky="nsew")
    for i, cmd in enumerate(("DB_STATUS", "DB_STATS", "DB_COMPONENTS", "DB_RUNTIME", "DB_UPDATES", "DB_RECOVERY")):
        ttk.Button(parent, text=cmd, command=lambda c=cmd: _db_command(d, c)).grid(row=2, column=i, padx=2, pady=3)


def _db_command(d, cmd):
    try: d._emit_seed_input(cmd, "DEVHUD_DATABASE")
    finally:
        try: d.db_view.insert("end", "\\n> " + cmd)
        except Exception: pass
def _build_apps(d, parent):
    parent.grid_columnconfigure(1, weight=1); parent.grid_rowconfigure(2, weight=1)
    ttk.Label(parent, text="MESSAGING / CONTACTS").grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
    ttk.Label(parent, text="App").grid(row=1, column=0, sticky="w")
    d.app_var = tk.StringVar(value="Facebook")
    ttk.Combobox(parent, textvariable=d.app_var, values=("Facebook", "Instagram", "X", "TikTok"), state="readonly").grid(row=1, column=1, sticky="ew")
    ttk.Label(parent, text="Contact").grid(row=2, column=0, sticky="w")
    d.contact_var = tk.StringVar(); ttk.Entry(parent, textvariable=d.contact_var).grid(row=2, column=1, sticky="ew")
    ttk.Label(parent, text="Message").grid(row=3, column=0, sticky="nw")
    d.message_box = tk.Text(parent, height=7, wrap="word"); d.message_box.grid(row=3, column=1, sticky="nsew")
    ttk.Button(parent, text="SEND VIA SEED", command=lambda: _send_social(d)).grid(row=4, column=1, sticky="e", pady=4)
    ttk.Separator(parent).grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)
    ttk.Label(parent, text="EMAIL").grid(row=6, column=0, columnspan=2, sticky="w")
    d.email_to = tk.StringVar(); d.email_subject = tk.StringVar()
    ttk.Label(parent, text="To").grid(row=7, column=0, sticky="w"); ttk.Entry(parent, textvariable=d.email_to).grid(row=7, column=1, sticky="ew")
    ttk.Label(parent, text="Subject").grid(row=8, column=0, sticky="w"); ttk.Entry(parent, textvariable=d.email_subject).grid(row=8, column=1, sticky="ew")
    d.email_box = tk.Text(parent, height=6, wrap="word"); d.email_box.grid(row=9, column=1, sticky="nsew")
    ttk.Button(parent, text="OPEN / SEND EMAIL", command=lambda: _send_email(d)).grid(row=10, column=1, sticky="e", pady=4)


def _send_social(d):
    app = d.app_var.get(); contact = d.contact_var.get().strip(); message = d.message_box.get("1.0", "end").strip()
    if not contact or not message: return
    payload = "SEND_MESSAGE app=%s contact=%s message=%s" % (app, contact, message)
    d._emit_seed_input(payload, "DEVHUD_APP_MESSAGE")
    try: d._log_output("[APP MESSAGE PROPOSAL] " + app + " -> " + contact)
    except Exception: pass


def _send_email(d):
    import urllib.parse
    to = d.email_to.get().strip(); subject = d.email_subject.get().strip(); body = d.email_box.get("1.0", "end").strip()
    if not to: return
    uri = "mailto:%s?%s" % (to, urllib.parse.urlencode({"subject": subject, "body": body}))
    webbrowser.open(uri)
    try: d._log_output("[EMAIL] Opened default mail composer for " + to)
    except Exception: pass


def _build_right(d):
    panel = _frame(d, 1, 2)
    panel.grid_rowconfigure(1, weight=1)
    ttk.Label(panel, text="SEED OUTPUT", font=("Consolas", 10, "bold")).grid(row=0, column=0, sticky="w")
    tabs = ttk.Notebook(panel); tabs.grid(row=1, column=0, sticky="nsew")
    cli = ttk.Frame(tabs); media = ttk.Frame(tabs); stats = ttk.Frame(tabs)
    tabs.add(cli, text="CLI I/O"); tabs.add(media, text="A/V • DOT MATRIX"); tabs.add(stats, text="STATS")
    _build_cli(d, cli); _build_media(d, media); _build_stats(d, stats)


def _build_cli(d, parent):
    parent.grid_columnconfigure(0, weight=1); parent.grid_rowconfigure(0, weight=1)
    d.console = tk.Text(parent, state="disabled", wrap="word", font=("Consolas", 9)); d.console.grid(row=0, column=0, sticky="nsew")
    d.command_var = tk.StringVar()
    entry = ttk.Entry(parent, textvariable=d.command_var); entry.grid(row=1, column=0, sticky="ew", pady=3); entry.bind("<Return>", d._submit_command)
    d.command_entry = entry
    ttk.Label(parent, text="CLI accepts SEED commands, natural input, and package requests such as: pip install seedtoolsbox").grid(row=2, column=0, sticky="w")


def _build_media(d, parent):
    parent.grid_columnconfigure(0, weight=1); parent.grid_rowconfigure(1, weight=1)
    ttk.Label(parent, text="AUDIO / VIDEO / DOT MATRIX OUTPUT").grid(row=0, column=0, sticky="w")
    d.media_output = tk.Text(parent, wrap="none", font=("Consolas", 8)); d.media_output.grid(row=1, column=0, sticky="nsew")
    d.media_output.insert("end", "SEED DOT MATRIX\n\n[ output stream ready ]\n[ audio: runtime-linked ]\n[ video: runtime-linked ]")


def _build_stats(d, parent):
    parent.grid_columnconfigure(0, weight=1); parent.grid_rowconfigure(0, weight=1)
    d.stats_view = tk.Text(parent, wrap="word", font=("Consolas", 9)); d.stats_view.grid(row=0, column=0, sticky="nsew")
    ttk.Button(parent, text="REFRESH STATS", command=lambda: _refresh_stats(d)).grid(row=1, column=0, sticky="e", pady=3)
    _refresh_stats(d)


def _refresh_stats(d):
    registry = getattr(getattr(d, "qbit_dialer", None), "command_registry", {}) or {}
    qbit = getattr(d, "qbit", None)
    lines = ["DEVHUD STATS", "", "QbitDialer: " + type(getattr(d, "qbit_dialer", None)).__name__, "Commands: %s" % len(registry), "Qbit: %s" % getattr(qbit, "qbit_id", "n/a"), "Device: %s" % getattr(getattr(d, "device", None), "device_id", "n/a"), "Authority: QbitDialer", "UI: observer / input bridge"]
    try: d.stats_view.delete("1.0", "end"); d.stats_view.insert("end", "\\n".join(lines))
    except Exception: pass
def _build_footer(d):
    bar = ttk.Frame(d)
    bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=(2, 4))
    bar.grid_columnconfigure(0, weight=1)
    bar.grid_columnconfigure(1, weight=0)
    d.status_var = tk.StringVar(value="SEED DEVHUD • READY")
    ttk.Label(bar, textvariable=d.status_var, anchor="w").grid(row=0, column=0, sticky="ew", padx=6)
    ttk.Label(bar, text="Identity • Track • Registry/Nodes • Qbit • Cognition • Security • Dialer • Queue • Result • Memory/Telemetry").grid(row=0, column=1, padx=6)


def _select_center(d, tab_name):
    tabs = getattr(d, "center_tabs", None)
    if tabs is None: return
    names = [tabs.tab(i, "text") for i in range(tabs.index("end"))]
    if tab_name in names: tabs.select(names.index(tab_name))


def _set_input_mode(d, mode):
    try:
        d.seed_input_mode.set(mode.upper())
    except Exception:
        pass
    try:
        d._log_output("[INPUT MODE] " + mode)
    except Exception:
        pass
