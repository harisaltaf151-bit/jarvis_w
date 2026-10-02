"""
JARVIS Tool — Screen Capture + GUI Automation
Screenshot, mouse control, keyboard input via PyAutoGUI.
"""

import base64
import io
import platform
import time
from pathlib import Path


PLATFORM = platform.system()


class ScreenCapture:

    def screenshot(self, region: tuple | None = None,
                   save_path: str = "") -> dict:
        """Capture the screen. region = (x, y, w, h) for partial capture."""
        try:
            import pyautogui
            img = pyautogui.screenshot(region=region)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()

            result: dict = {"base64": b64, "width": img.width, "height": img.height}

            if save_path:
                p = Path(save_path).expanduser()
                p.parent.mkdir(parents=True, exist_ok=True)
                img.save(str(p))
                result["saved"] = str(p)
            return result
        except ImportError:
            return {"error": "pyautogui not installed. Run: pip install pyautogui pillow"}
        except Exception as exc:
            return {"error": str(exc)}

    def get_screen_size(self) -> dict:
        try:
            import pyautogui
            w, h = pyautogui.size()
            return {"width": w, "height": h}
        except ImportError:
            return {"error": "pyautogui not installed"}

    def move_mouse(self, x: int, y: int,
                   duration: float = 0.3) -> str:
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=duration)
            return f"✅ Mouse moved to ({x}, {y})"
        except Exception as exc:
            return f"❌ {exc}"

    def click(self, x: int | None = None, y: int | None = None,
              button: str = "left", clicks: int = 1) -> str:
        try:
            import pyautogui
            if x is not None and y is not None:
                pyautogui.click(x, y, clicks=clicks, button=button)
            else:
                pyautogui.click(clicks=clicks, button=button)
            return f"✅ Clicked ({button}) at ({x}, {y})"
        except Exception as exc:
            return f"❌ {exc}"

    def double_click(self, x: int, y: int) -> str:
        return self.click(x, y, clicks=2)

    def right_click(self, x: int, y: int) -> str:
        return self.click(x, y, button="right")

    def drag(self, from_x: int, from_y: int,
             to_x: int, to_y: int, duration: float = 0.5) -> str:
        try:
            import pyautogui
            pyautogui.drag(from_x, from_y, to_x, to_y, duration=duration)
            return f"✅ Dragged from ({from_x},{from_y}) to ({to_x},{to_y})"
        except Exception as exc:
            return f"❌ {exc}"

    def type_text(self, text: str, interval: float = 0.03) -> str:
        try:
            import pyautogui
            pyautogui.write(text, interval=interval)
            return f"✅ Typed: {text[:40]}..."
        except Exception as exc:
            return f"❌ {exc}"

    def hotkey(self, *keys: str) -> str:
        """Press a key combination. e.g. hotkey('ctrl','c') to copy."""
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return f"✅ Hotkey: {'+'.join(keys)}"
        except Exception as exc:
            return f"❌ {exc}"

    def press_key(self, key: str) -> str:
        """Press a single key."""
        try:
            import pyautogui
            pyautogui.press(key)
            return f"✅ Pressed: {key}"
        except Exception as exc:
            return f"❌ {exc}"

    def scroll(self, clicks: int = 3, x: int | None = None,
               y: int | None = None) -> str:
        """Scroll up (positive) or down (negative)."""
        try:
            import pyautogui
            kwargs = {}
            if x is not None: kwargs["x"] = x
            if y is not None: kwargs["y"] = y
            pyautogui.scroll(clicks, **kwargs)
            return f"✅ Scrolled {clicks} clicks"
        except Exception as exc:
            return f"❌ {exc}"

    def find_on_screen(self, image_path: str,
                       confidence: float = 0.8) -> dict:
        """Find an image on screen and return its location."""
        try:
            import pyautogui
            loc = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if loc:
                center = pyautogui.center(loc)
                return {"found": True, "x": center.x, "y": center.y,
                        "box": {"left": loc.left, "top": loc.top,
                                "width": loc.width, "height": loc.height}}
            return {"found": False}
        except Exception as exc:
            return {"error": str(exc)}

    def type_shortcut_open(self, app: str) -> str:
        """Use OS search (Spotlight/Start) to open an app."""
        try:
            import pyautogui
            if PLATFORM == "Darwin":
                pyautogui.hotkey("command", "space")
                time.sleep(0.4)
                pyautogui.write(app, interval=0.05)
                time.sleep(0.5)
                pyautogui.press("enter")
            elif PLATFORM == "Windows":
                pyautogui.hotkey("win")
                time.sleep(0.4)
                pyautogui.write(app, interval=0.05)
                time.sleep(0.5)
                pyautogui.press("enter")
            elif PLATFORM == "Linux":
                pyautogui.hotkey("super")
                time.sleep(0.6)
                pyautogui.write(app, interval=0.05)
                time.sleep(0.5)
                pyautogui.press("enter")
            return f"✅ Opened {app} via system search"
        except Exception as exc:
            return f"❌ {exc}"
