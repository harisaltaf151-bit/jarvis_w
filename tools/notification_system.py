"""
JARVIS Tool — Notification System
Cross-platform desktop notifications + scheduled reminders.
"""

import asyncio
import logging
import platform
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("JARVIS.notify")
PLATFORM = platform.system()


class NotificationSystem:

    def __init__(self):
        self._reminders: list[dict] = []
        self._running = False
        self._thread: threading.Thread | None = None

    # ── SEND NOTIFICATION ─────────────────────────────────────────────────────
    def notify(self, title: str, message: str,
               urgency: str = "normal",
               icon: str = "",
               sound: bool = True) -> dict:
        """
        Send a desktop notification.
        urgency: 'low' | 'normal' | 'critical'
        """
        try:
            if PLATFORM == "Darwin":
                _mac_notify(title, message, sound)
            elif PLATFORM == "Windows":
                _win_notify(title, message)
            elif PLATFORM == "Linux":
                _linux_notify(title, message, urgency, icon)
            return {"ok": True, "title": title}
        except Exception as exc:
            log.warning("Notification failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def alert(self, message: str) -> dict:
        """High-priority JARVIS alert."""
        return self.notify("⚡ JARVIS", message, urgency="critical", sound=True)

    def success(self, message: str) -> dict:
        return self.notify("✅ JARVIS", message, urgency="normal")

    def warning(self, message: str) -> dict:
        return self.notify("⚠️ JARVIS", message, urgency="normal")

    # ── REMINDERS ─────────────────────────────────────────────────────────────
    def remind_in(self, message: str, minutes: float) -> dict:
        """Set a reminder N minutes from now."""
        fire_at = datetime.now() + timedelta(minutes=minutes)
        reminder = {
            "id":      f"r{int(time.time()*1000)}",
            "message": message,
            "fire_at": fire_at,
            "done":    False,
        }
        self._reminders.append(reminder)
        self._ensure_loop()
        return {
            "ok":      True,
            "id":      reminder["id"],
            "fire_at": fire_at.strftime("%H:%M:%S"),
            "message": message,
        }

    def remind_at(self, message: str, time_str: str) -> dict:
        """
        Set a reminder at a specific time today.
        time_str: 'HH:MM' or 'HH:MM:SS'
        """
        now = datetime.now()
        try:
            parts = [int(x) for x in time_str.split(":")]
            fire_at = now.replace(
                hour=parts[0],
                minute=parts[1] if len(parts) > 1 else 0,
                second=parts[2] if len(parts) > 2 else 0,
                microsecond=0,
            )
            if fire_at <= now:
                fire_at += timedelta(days=1)   # assume tomorrow if time passed
        except (ValueError, IndexError):
            return {"error": f"Invalid time format: {time_str}. Use HH:MM"}

        reminder = {
            "id":      f"r{int(time.time()*1000)}",
            "message": message,
            "fire_at": fire_at,
            "done":    False,
        }
        self._reminders.append(reminder)
        self._ensure_loop()
        return {
            "ok":      True,
            "id":      reminder["id"],
            "fire_at": fire_at.strftime("%H:%M"),
        }

    def list_reminders(self) -> list[dict]:
        return [
            {
                "id":      r["id"],
                "message": r["message"],
                "fire_at": r["fire_at"].strftime("%Y-%m-%d %H:%M:%S"),
                "done":    r["done"],
            }
            for r in self._reminders
            if not r["done"]
        ]

    def cancel_reminder(self, reminder_id: str) -> dict:
        for r in self._reminders:
            if r["id"] == reminder_id:
                r["done"] = True
                return {"ok": True, "cancelled": reminder_id}
        return {"error": f"Reminder not found: {reminder_id}"}

    def clear_reminders(self) -> dict:
        count = sum(1 for r in self._reminders if not r["done"])
        self._reminders = []
        return {"ok": True, "cleared": count}

    # ── BACKGROUND LOOP ───────────────────────────────────────────────────────
    def _ensure_loop(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name="jarvis-remind")
        self._thread.start()

    def _loop(self):
        while self._running:
            now = datetime.now()
            for r in self._reminders:
                if not r["done"] and r["fire_at"] <= now:
                    r["done"] = True
                    log.info("Firing reminder: %s", r["message"])
                    self.notify("⏰ JARVIS Reminder", r["message"], urgency="critical")
            time.sleep(5)

    def stop(self):
        self._running = False


# ── platform implementations ───────────────────────────────────────────────────
def _mac_notify(title: str, body: str, sound: bool = True):
    snd = 'sound name "Glass"' if sound else ""
    script = f'display notification "{body}" with title "{title}" {snd}'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _win_notify(title: str, body: str):
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, body, duration=6, threaded=True)
    except ImportError:
        # fallback — PowerShell
        ps = (
            f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null; "
            f"$xml=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(0); "
            f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{title}')) | Out-Null; "
            f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{body}')) | Out-Null; "
            f"$toast=[Windows.UI.Notifications.ToastNotification]::new($xml); "
            f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS').Show($toast)"
        )
        subprocess.run(["powershell", "-Command", ps], capture_output=True)


def _linux_notify(title: str, body: str,
                  urgency: str = "normal", icon: str = ""):
    import shutil
    if shutil.which("notify-send"):
        cmd = ["notify-send", f"--urgency={urgency}", title, body]
        if icon:
            cmd += [f"--icon={icon}"]
        subprocess.run(cmd, capture_output=True)
    else:
        # try zenity
        if shutil.which("zenity"):
            subprocess.run(
                ["zenity", "--notification", f"--text={title}: {body}"],
                capture_output=True
            )
