#!/usr/bin/env python3
"""
JARVIS — Master Launcher
Run this file to start everything:
  python jarvis.py            # start server + open UI
  python jarvis.py --setup    # run first-time setup wizard
  python jarvis.py --check    # check dependencies only
  python jarvis.py --server   # server only (no browser)
"""

import argparse
import os
import platform
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT    = Path(__file__).parent
UI_FILE = ROOT / "ui" / "index.html"
ENV_FILE = ROOT / ".env"
PLATFORM = platform.system()

# ── ANSI colours ──────────────────────────────────────────────────────────────
G  = "\033[92m";  B  = "\033[94m";  Y  = "\033[93m"
R  = "\033[91m";  C  = "\033[96m";  W  = "\033[97m"
DIM = "\033[2m";  RST = "\033[0m";  BOLD = "\033[1m"

def p(s=""):   print(s)
def ok(s):     print(f"  {G}✓{RST}  {s}")
def warn(s):   print(f"  {Y}⚠{RST}  {s}")
def err(s):    print(f"  {R}✗{RST}  {s}")
def info(s):   print(f"  {C}›{RST}  {s}")
def head(s):   print(f"\n{BOLD}{C}{s}{RST}\n{'─'*len(s)}")


# ── BANNER ─────────────────────────────────────────────────────────────────────
BANNER = f"""
{C}
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
{RST}{DIM}  Personal AI Operating System  ·  v3.0{RST}
"""


# ── DEPENDENCY CHECK ──────────────────────────────────────────────────────────
REQUIRED = ["websockets", "aiohttp", "psutil"]
OPTIONAL = {
    "selenium":        "Browser automation (open/control Chrome)",
    "pyautogui":       "Screen capture & mouse/keyboard control",
    "icalendar":       "Calendar .ics export",
    "webdriver_manager": "Auto-install ChromeDriver",
    "pillow":          "Image processing for screenshots",
    "pydantic":        "Data validation",
}

def check_deps() -> tuple[list, list]:
    missing_req, missing_opt = [], []
    for pkg in REQUIRED:
        try:
            __import__(pkg.replace("-","_"))
        except ImportError:
            missing_req.append(pkg)
    for pkg in OPTIONAL:
        try:
            __import__(pkg.replace("-","_"))
        except ImportError:
            missing_opt.append(pkg)
    return missing_req, missing_opt


def install_deps(packages: list, label=""):
    if not packages:
        return
    info(f"Installing {label}: {', '.join(packages)}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet"] + packages,
        check=True
    )


# ── ENV LOADER ────────────────────────────────────────────────────────────────
def load_env():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ── SETUP WIZARD ──────────────────────────────────────────────────────────────
def setup_wizard():
    print(BANNER)
    head("JARVIS FIRST-TIME SETUP WIZARD")
    p("This wizard configures your JARVIS installation.")
    p("Press ENTER to skip any optional field.\n")

    cfg = {}

    # Groq key
    p(f"{W}1. Groq API Key{RST}  (required for AI brain — FREE at console.groq.com)")
    p(f"   → Sign up free at: https://console.groq.com/")
    p(f"   → Click 'API Keys' → 'Create API Key'")
    key = input(f"   {C}GROQ_API_KEY{RST}: ").strip()
    if key:
        cfg["GROQ_API_KEY"] = key
        ok("Groq key saved ✓")
    else:
        warn("No API key — AI brain will not work without it.")

    # Email
    p(f"\n{W}2. Email Configuration{RST}  (optional — for email tools)")
    p(f"   For Gmail: enable 2FA → create App Password at myaccount.google.com/apppasswords")
    email_addr = input(f"   {C}EMAIL_ADDRESS{RST} (e.g. you@gmail.com): ").strip()
    if email_addr:
        cfg["EMAIL_ADDRESS"] = email_addr
        email_pass = input(f"   {C}EMAIL_PASSWORD{RST} (app password): ").strip()
        if email_pass:
            cfg["EMAIL_PASSWORD"] = email_pass

        provider = email_addr.split("@")[-1].lower()
        if "gmail" in provider:
            cfg.update({"SMTP_HOST":"smtp.gmail.com","SMTP_PORT":"587",
                        "IMAP_HOST":"imap.gmail.com","IMAP_PORT":"993"})
            ok("Gmail defaults applied")
        elif "outlook" in provider or "hotmail" in provider:
            cfg.update({"SMTP_HOST":"smtp.office365.com","SMTP_PORT":"587",
                        "IMAP_HOST":"outlook.office365.com","IMAP_PORT":"993"})
            ok("Outlook defaults applied")
        else:
            cfg["SMTP_HOST"] = input(f"   {C}SMTP_HOST{RST}: ").strip() or "smtp.gmail.com"
            cfg["SMTP_PORT"] = input(f"   {C}SMTP_PORT{RST}: ").strip() or "587"
            cfg["IMAP_HOST"] = input(f"   {C}IMAP_HOST{RST}: ").strip() or "imap.gmail.com"
            cfg["IMAP_PORT"] = input(f"   {C}IMAP_PORT{RST}: ").strip() or "993"

    # Ports
    p(f"\n{W}3. Server Ports{RST}  (defaults: WS=8765, HTTP=8766)")
    ws_port   = input(f"   {C}WebSocket port{RST} [8765]: ").strip() or "8765"
    http_port = input(f"   {C}HTTP port{RST}     [8766]: ").strip() or "8766"
    cfg["JARVIS_WS_PORT"]   = ws_port
    cfg["JARVIS_HTTP_PORT"] = http_port

    # Write .env
    lines = ["# JARVIS Configuration — generated by setup wizard", ""]
    for k, v in cfg.items():
        lines.append(f'{k}="{v}"')
    ENV_FILE.write_text("\n".join(lines) + "\n")
    ok(f".env written to {ENV_FILE}")

    # Install deps
    p(f"\n{W}4. Installing dependencies…{RST}")
    mr, mo = check_deps()
    if mr:
        install_deps(mr, "required")
    install_deps(["websockets","aiohttp","anthropic","psutil","pillow","selenium",
                  "webdriver-manager","pyautogui","icalendar","python-dotenv"], "all")
    ok("Dependencies installed")

    # Jarvis config dir
    cfg_dir = Path.home() / ".jarvis"
    cfg_dir.mkdir(exist_ok=True)
    ok(f"Config directory: {cfg_dir}")

    p(f"\n{G}{BOLD}Setup complete! Run:  python jarvis.py{RST}\n")


# ── DEPENDENCY REPORT ─────────────────────────────────────────────────────────
def print_check():
    print(BANNER)
    head("DEPENDENCY CHECK")
    mr, mo = check_deps()

    p(f"{W}Required packages:{RST}")
    for pkg in REQUIRED:
        if pkg not in mr:
            ok(pkg)
        else:
            err(f"{pkg}  ← missing — run: pip install {pkg}")

    p(f"\n{W}Optional packages:{RST}")
    for pkg, desc in OPTIONAL.items():
        if pkg not in mo:
            ok(f"{pkg:30s} {DIM}{desc}{RST}")
        else:
            warn(f"{pkg:30s} {DIM}not installed — {desc}{RST}")

    p(f"\n{W}Environment:{RST}")
    api_key = os.getenv("GROQ_API_KEY","")
    if api_key:
        ok(f"GROQ_API_KEY       {DIM}{'*'*8}{api_key[-4:]}{RST}")
    else:
        err("GROQ_API_KEY       not set — run: python jarvis.py --setup")

    p(f"\n{W}Platform:{RST}")
    ok(f"{platform.system()} {platform.release()} · Python {sys.version.split()[0]}")
    p()


# ── MAIN LAUNCHER ─────────────────────────────────────────────────────────────
def launch(open_browser: bool = True):
    print(BANNER)

    # load .env
    load_env()

    # quick dep check
    mr, _ = check_deps()
    if mr:
        err(f"Missing required packages: {', '.join(mr)}")
        info("Run:  pip install -r requirements.txt")
        info("  or: python jarvis.py --setup")
        sys.exit(1)

    api_key = os.getenv("GROQ_API_KEY","")
    if not api_key:
        warn("GROQ_API_KEY not set — AI brain disabled")
        warn("Run: python jarvis.py --setup  to configure")
    else:
        ok(f"Groq API key loaded ({api_key[:8]}…)")

    ok(f"Platform: {PLATFORM} · Python {sys.version.split()[0]}")

    # open UI in browser
    if open_browser and UI_FILE.exists():
        def _open():
            time.sleep(1.2)
            webbrowser.open(UI_FILE.as_uri())
        import threading
        threading.Thread(target=_open, daemon=True).start()
        ok(f"UI: {UI_FILE}")

    info("Starting JARVIS server…")
    p()

    # hand off to the async server
    server_path = ROOT / "core" / "server.py"
    subprocess.run([sys.executable, str(server_path)], cwd=str(ROOT))


# ── ENTRY ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="JARVIS Personal AI OS Launcher")
    ap.add_argument("--setup",  action="store_true", help="Run setup wizard")
    ap.add_argument("--check",  action="store_true", help="Check dependencies")
    ap.add_argument("--server", action="store_true", help="Start server only (no browser)")
    args = ap.parse_args()

    if args.setup:
        setup_wizard()
    elif args.check:
        print_check()
    elif args.server:
        load_env()
        p(BANNER)
        info("Server-only mode")
        subprocess.run([sys.executable, str(ROOT / "core" / "server.py")], cwd=str(ROOT))
    else:
        launch(open_browser=not args.server)
