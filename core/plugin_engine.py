"""
JARVIS Plugin Engine
Drop a .py file into ~/.jarvis/plugins/ and JARVIS loads it automatically.
Each plugin is a class with a name, description, and action methods.

Example plugin structure:
─────────────────────────
class MyPlugin:
    name = "myplugin"
    description = "Does something awesome"
    version = "1.0"

    def hello(self, name: str = "world") -> str:
        return f"Hello, {name}!"
─────────────────────────
"""

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

log = logging.getLogger("JARVIS.plugins")

PLUGIN_DIR = Path.home() / ".jarvis" / "plugins"
BUILTIN_DIR = Path(__file__).parent   # tools/ folder


class PluginEngine:

    def __init__(self):
        self._plugins: dict[str, object] = {}

    # ── LOADING ───────────────────────────────────────────────────────────────
    def load_all(self, extra_dirs: list[Path] | None = None) -> dict:
        """Load plugins from ~/.jarvis/plugins/ and any extra directories."""
        PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        dirs = [PLUGIN_DIR] + (extra_dirs or [])
        results = {"loaded": [], "failed": []}

        for d in dirs:
            for py_file in sorted(Path(d).glob("plugin_*.py")):
                result = self.load_file(py_file)
                if result.get("ok"):
                    results["loaded"].append(result["name"])
                else:
                    results["failed"].append({"file": py_file.name, "error": result.get("error")})

        log.info("Plugins loaded: %s", results["loaded"])
        return results

    def load_file(self, path: Path) -> dict:
        """Load a single plugin file."""
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if not spec or not spec.loader:
                return {"ok": False, "error": "Cannot load spec"}

            module: ModuleType = importlib.util.module_from_spec(spec)
            sys.modules[path.stem] = module
            spec.loader.exec_module(module)

            # find plugin class (first class with a 'name' attribute)
            plugin_cls = None
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if isinstance(obj, type) and hasattr(obj, "name"):
                    plugin_cls = obj
                    break

            if not plugin_cls:
                return {"ok": False, "error": "No plugin class found (needs 'name' attribute)"}

            instance = plugin_cls()
            plugin_name = instance.name
            self._plugins[plugin_name] = instance
            log.info("Loaded plugin: %s (%s)", plugin_name, path.name)
            return {"ok": True, "name": plugin_name}

        except Exception as exc:
            log.error("Failed to load %s: %s", path.name, exc)
            return {"ok": False, "error": str(exc)}

    def reload(self, plugin_name: str) -> dict:
        """Reload a specific plugin."""
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            return {"error": f"Plugin not found: {plugin_name}"}

        # find the source file
        module = sys.modules.get(f"plugin_{plugin_name}")
        if module and hasattr(module, "__file__"):
            return self.load_file(Path(module.__file__))
        return {"error": "Cannot locate plugin source file"}

    # ── REGISTRY ─────────────────────────────────────────────────────────────
    def list_plugins(self) -> list[dict]:
        result = []
        for name, inst in self._plugins.items():
            actions = [
                m for m in dir(inst)
                if not m.startswith("_") and callable(getattr(inst, m))
                and m not in ("name", "description", "version")
            ]
            result.append({
                "name":        name,
                "description": getattr(inst, "description", ""),
                "version":     getattr(inst, "version", "1.0"),
                "actions":     actions,
            })
        return result

    def get_plugin(self, name: str) -> object | None:
        return self._plugins.get(name)

    def call(self, plugin_name: str, action: str, params: dict = None) -> dict:
        """Call a plugin action."""
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            return {"error": f"Plugin not found: {plugin_name}"}

        handler = getattr(plugin, action, None)
        if not handler or not callable(handler):
            return {"error": f"Action '{action}' not found in plugin '{plugin_name}'"}

        try:
            result = handler(**(params or {}))
            return {"ok": True, "result": result}
        except Exception as exc:
            return {"error": str(exc)}

    def unload(self, plugin_name: str) -> dict:
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            return {"ok": True}
        return {"error": f"Plugin not found: {plugin_name}"}

    def install_from_url(self, url: str) -> dict:
        """Download and install a plugin from a URL."""
        try:
            import urllib.request
            PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
            filename = url.split("/")[-1]
            if not filename.endswith(".py"):
                filename += ".py"
            dest = PLUGIN_DIR / filename
            urllib.request.urlretrieve(url, str(dest))
            return self.load_file(dest)
        except Exception as exc:
            return {"error": str(exc)}


# ── EXAMPLE PLUGIN GENERATOR ──────────────────────────────────────────────────
EXAMPLE_PLUGIN = '''"""
Example JARVIS Plugin — Weather
Copy to ~/.jarvis/plugins/plugin_weather.py
"""

class WeatherPlugin:
    name = "weather"
    description = "Get current weather for any city"
    version = "1.0"

    def current(self, city: str = "London") -> dict:
        """Get current weather for a city."""
        import urllib.request, json
        url = f"https://wttr.in/{city}?format=j1"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            cur = data["current_condition"][0]
            return {
                "city":        city,
                "temp_c":      cur["temp_C"],
                "feels_like":  cur["FeelsLikeC"],
                "description": cur["weatherDesc"][0]["value"],
                "humidity":    cur["humidity"],
                "wind_kmph":   cur["windspeedKmph"],
            }
        except Exception as e:
            return {"error": str(e)}

    def forecast(self, city: str = "London", days: int = 3) -> list:
        """Get N-day forecast."""
        import urllib.request, json
        url = f"https://wttr.in/{city}?format=j1"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            result = []
            for day in data.get("weather", [])[:days]:
                result.append({
                    "date":    day["date"],
                    "max_c":   day["maxtempC"],
                    "min_c":   day["mintempC"],
                    "desc":    day["hourly"][4]["weatherDesc"][0]["value"],
                })
            return result
        except Exception as e:
            return [{"error": str(e)}]
'''


def create_example_plugin():
    PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    dest = PLUGIN_DIR / "plugin_weather.py"
    if not dest.exists():
        dest.write_text(EXAMPLE_PLUGIN)
        print(f"Example plugin created: {dest}")
    return str(dest)


if __name__ == "__main__":
    engine = PluginEngine()
    path   = create_example_plugin()
    result = engine.load_file(Path(path))
    print("Load result:", result)
    print("Plugins:", engine.list_plugins())
    weather = engine.call("weather", "current", {"city": "London"})
    print("Weather:", weather)
