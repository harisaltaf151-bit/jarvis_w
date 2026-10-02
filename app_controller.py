"""
tools/app_controller.py  -  open, close and list Windows applications.

Used by core/server.py via:  getattr(AppController(), action)(**params)
Every public method returns a dict: {"success": bool, "message": str, ...}
"""

import difflib
import json
import os
import subprocess
import sys
import time

IS_WINDOWS = sys.platform.startswith("win")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class AppController:
    # friendly name -> how to launch it, and which processes to kill on close
    KNOWN = {
        "whatsapp":      {"target": "whatsapp:",        "proc": ["WhatsApp.exe", "WhatsApp.Root.exe"]},
        "spotify":       {"target": "spotify:",         "proc": ["Spotify.exe"]},
        "notepad":       {"target": "notepad.exe",      "proc": ["notepad.exe"]},
        "calculator":    {"target": "calc.exe",         "proc": ["CalculatorApp.exe", "calc.exe"]},
        "paint":         {"target": "mspaint.exe",      "proc": ["mspaint.exe"]},
        "task manager":  {"target": "taskmgr.exe",      "proc": ["Taskmgr.exe"]},
        "settings":      {"target": "ms-settings:",     "proc": ["SystemSettings.exe"]},
        "file explorer": {"target": "explorer.exe",     "proc": []},   # never kill explorer
        "cmd":           {"target": "cmd.exe",          "proc": ["cmd.exe"]},
        "powershell":    {"target": "powershell.exe",   "proc": ["powershell.exe"]},
        "chrome":        {"target": "chrome",           "proc": ["chrome.exe"]},
        "edge":          {"target": "msedge",           "proc": ["msedge.exe"]},
        "firefox":       {"target": "firefox",          "proc": ["firefox.exe"]},
        "vscode":        {"target": "code",             "proc": ["Code.exe"]},
        "word":          {"target": "winword",          "proc": ["WINWORD.EXE"]},
        "excel":         {"target": "excel",            "proc": ["EXCEL.EXE"]},
        "powerpoint":    {"target": "powerpnt",         "proc": ["POWERPNT.EXE"]},
        "discord":       {"target": None,               "proc": ["Discord.exe"]},
        "telegram":      {"target": None,               "proc": ["Telegram.exe"]},
        "zoom":          {"target": None,               "proc": ["Zoom.exe"]},
    }

    # common alternative spellings
    SYNONYMS = {
        "wa": "whatsapp", "whats app": "whatsapp",
        "calc": "calculator", "calculater": "calculator",
        "code": "vscode", "vs code": "vscode", "visual studio code": "vscode",
        "google chrome": "chrome", "browser": "chrome",
        "microsoft edge": "edge",
        "explorer": "file explorer", "files": "file explorer",
        "terminal": "powershell", "command prompt": "cmd",
        "taskmgr": "task manager",
        "ms word": "word", "microsoft word": "word",
        "ms excel": "excel", "microsoft excel": "excel",
        "ms powerpoint": "powerpoint", "microsoft powerpoint": "powerpoint",
    }

    def __init__(self):
        self._start_apps_cache = None

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _pick_name(name, app, app_name, application, target):
        value = name or app or app_name or application or target or ""
        return str(value).strip()

    def _normalize(self, name: str) -> str:
        key = name.lower().strip()
        if key.endswith(".exe"):
            key = key[:-4]
        return self.SYNONYMS.get(key, key)

    def _start_apps(self):
        """Installed apps from the Start menu: [{'Name':..., 'AppID':...}, ...]"""
        if self._start_apps_cache is not None:
            return self._start_apps_cache
        apps = []
        if IS_WINDOWS:
            try:
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-StartApps | ConvertTo-Json -Compress"],
                    capture_output=True, text=True, timeout=25,
                    creationflags=NO_WINDOW,
                ).stdout.strip()
                if out:
                    data = json.loads(out)
                    apps = data if isinstance(data, list) else [data]
            except Exception:
                apps = []
        self._start_apps_cache = apps
        return apps

    def _find_start_app(self, name: str):
        apps = self._start_apps()
        if not apps:
            return None
        wanted = name.lower()
        names = {a["Name"].lower(): a for a in apps if a.get("Name")}
        if wanted in names:
            return names[wanted]
        for n, a in names.items():                      # substring match
            if wanted in n:
                return a
        close = difflib.get_close_matches(wanted, list(names), n=1, cutoff=0.6)
        return names[close[0]] if close else None

    # ------------------------------------------------------------------ actions
    def open_app(self, name=None, app=None, app_name=None, application=None,
                 target=None, **_ignored):
        """Open an application by friendly name, e.g. 'whatsapp', 'chrome'."""
        raw = self._pick_name(name, app, app_name, application, target)
        if not raw:
            return {"success": False, "message": "No app name given."}
        if not IS_WINDOWS:
            return {"success": False, "message": "AppController currently supports Windows only."}

        key = self._normalize(raw)
        errors = []

        # 1) known launch target (exe on PATH, App Paths entry, or URI protocol)
        info = self.KNOWN.get(key)
        if info and info["target"]:
            try:
                os.startfile(info["target"])
                return {"success": True, "message": f"Opened {key}."}
            except OSError as e:
                errors.append(f"direct launch failed: {e}")

        # 2) Start menu lookup (covers Store apps and installed programs)
        match = self._find_start_app(key if key else raw)
        if match:
            try:
                subprocess.Popen(
                    ["explorer.exe", f"shell:AppsFolder\\{match['AppID']}"],
                    creationflags=NO_WINDOW,
                )
                return {"success": True, "message": f"Opened {match['Name']}."}
            except Exception as e:
                errors.append(f"start menu launch failed: {e}")

        # 3) last resort: treat the text as a command / file / URL
        try:
            os.startfile(raw)
            return {"success": True, "message": f"Opened {raw}."}
        except OSError as e:
            errors.append(str(e))

        return {"success": False,
                "message": f"Could not open '{raw}'. " + " | ".join(errors)}

    def close_app(self, name=None, app=None, app_name=None, application=None,
                  target=None, **_ignored):
        """Force-close all processes belonging to an app."""
        raw = self._pick_name(name, app, app_name, application, target)
        if not raw:
            return {"success": False, "message": "No app name given."}
        if not IS_WINDOWS:
            return {"success": False, "message": "AppController currently supports Windows only."}

        key = self._normalize(raw)
        info = self.KNOWN.get(key)
        if info and not info["proc"]:
            return {"success": False, "message": f"Refusing to close '{key}'."}

        procs = list(info["proc"]) if info else []
        if not procs:                                   # guess the process name
            guess = raw if raw.lower().endswith(".exe") else raw.replace(" ", "") + ".exe"
            procs = [guess]

        killed = []
        for p in procs:
            r = subprocess.run(
                ["taskkill", "/F", "/IM", p],
                capture_output=True, text=True, creationflags=NO_WINDOW,
            )
            if r.returncode == 0:
                killed.append(p)

        if killed:
            return {"success": True, "message": f"Closed {key} ({', '.join(killed)})."}
        return {"success": False, "message": f"'{key}' is not running or could not be closed."}

    def list_running(self, **_ignored):
        """Names of apps that currently have a visible window."""
        if not IS_WINDOWS:
            return {"success": False, "message": "AppController currently supports Windows only."}
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle} | "
                 "Select-Object ProcessName,MainWindowTitle | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW,
            ).stdout.strip()
            data = json.loads(out) if out else []
            data = data if isinstance(data, list) else [data]
            apps = [{"process": d["ProcessName"], "title": d["MainWindowTitle"]} for d in data]
            return {"success": True, "message": f"{len(apps)} windows open.", "apps": apps}
        except Exception as e:
            return {"success": False, "message": f"Could not list running apps: {e}"}

    def list_installed(self, **_ignored):
        """Apps available in the Start menu."""
        apps = self._start_apps()
        names = sorted(a["Name"] for a in apps if a.get("Name"))
        return {"success": bool(names), "message": f"{len(names)} apps found.", "apps": names}

    def is_running(self, name=None, app=None, app_name=None, application=None,
                   target=None, **_ignored):
        raw = self._pick_name(name, app, app_name, application, target)
        key = self._normalize(raw)
        info = self.KNOWN.get(key)
        procs = info["proc"] if info and info["proc"] else [raw.replace(" ", "") + ".exe"]
        out = subprocess.run(["tasklist"], capture_output=True, text=True,
                             creationflags=NO_WINDOW).stdout.lower()
        running = any(p.lower() in out for p in procs)
        return {"success": True, "running": running,
                "message": f"{key} is {'running' if running else 'not running'}."}

    def restart_app(self, name=None, **kwargs):
        self.close_app(name=name, **kwargs)
        time.sleep(1.5)
        return self.open_app(name=name, **kwargs)

    # aliases, in case the AI prompt uses different action names
    open = launch = start = open_app
    close = quit = kill = close_app
    list_apps = list_running
    list = list_running
