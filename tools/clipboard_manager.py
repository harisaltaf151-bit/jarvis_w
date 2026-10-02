"""
JARVIS Tool — Clipboard Manager
Read, write, and manage clipboard history.
"""

import platform
import subprocess
import time

PLATFORM = platform.system()
_HISTORY: list[dict] = []
_MAX     = 50


class ClipboardManager:

    def get(self) -> str:
        """Get current clipboard content."""
        try:
            if PLATFORM == "Darwin":
                return subprocess.check_output(["pbpaste"], text=True)
            elif PLATFORM == "Windows":
                import win32clipboard
                win32clipboard.OpenClipboard()
                data = win32clipboard.GetClipboardData()
                win32clipboard.CloseClipboard()
                return data
            else:
                return subprocess.check_output(
                    ["xclip", "-selection", "clipboard", "-o"],
                    text=True
                )
        except Exception:
            try:
                import pyperclip
                return pyperclip.paste()
            except Exception as exc:
                return f"[Error reading clipboard: {exc}]"

    def set(self, text: str) -> dict:
        """Set clipboard content."""
        _HISTORY.insert(0, {"text": text, "ts": time.strftime("%H:%M:%S")})
        if len(_HISTORY) > _MAX:
            _HISTORY.pop()
        try:
            if PLATFORM == "Darwin":
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p.communicate(text.encode())
            elif PLATFORM == "Windows":
                import win32clipboard
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            else:
                p = subprocess.Popen(["xclip", "-selection", "clipboard"],
                                     stdin=subprocess.PIPE)
                p.communicate(text.encode())
            return {"ok": True, "chars": len(text)}
        except Exception:
            try:
                import pyperclip
                pyperclip.copy(text)
                return {"ok": True, "chars": len(text)}
            except Exception as exc:
                return {"error": str(exc)}

    def clear(self) -> dict:
        return self.set("")

    def history(self, n: int = 20) -> list[dict]:
        return _HISTORY[:n]

    def search_history(self, query: str) -> list[dict]:
        q = query.lower()
        return [h for h in _HISTORY if q in h["text"].lower()]
