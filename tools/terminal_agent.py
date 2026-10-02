"""
JARVIS Tool — Terminal Agent
Execute shell commands, run scripts, manage working directory.
"""

import os
import platform
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path


PLATFORM = platform.system()
_CWD     = Path.home()          # session working directory


class TerminalAgent:

    def __init__(self):
        self._cwd = Path.home()
        self._env = os.environ.copy()

    def run(self, command: str, timeout: int = 30,
            shell: bool = True) -> dict:
        """Execute a shell command and return stdout/stderr."""
        try:
            result = subprocess.run(
                command if shell else shlex.split(command),
                shell=shell,
                cwd=str(self._cwd),
                env=self._env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "command":  command,
                "stdout":   result.stdout[-4000:] if result.stdout else "",
                "stderr":   result.stderr[-2000:] if result.stderr else "",
                "exit_code": result.returncode,
                "cwd":      str(self._cwd),
            }
        except subprocess.TimeoutExpired:
            return {"command": command, "error": f"Timed out after {timeout}s"}
        except Exception as exc:
            return {"command": command, "error": str(exc)}

    def run_python(self, code: str, timeout: int = 30) -> dict:
        """Run Python code and return output."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp = f.name
        try:
            result = subprocess.run(
                [sys.executable, tmp],
                cwd=str(self._cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout":    result.stdout[-4000:],
                "stderr":    result.stderr[-2000:],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Python script timed out after {timeout}s"}
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def run_script(self, path: str, interpreter: str = "") -> dict:
        """Run a script file."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"error": f"Script not found: {path}"}

        if not interpreter:
            ext_map = {
                ".py":   sys.executable,
                ".sh":   "bash",
                ".bash": "bash",
                ".zsh":  "zsh",
                ".js":   "node",
                ".ts":   "ts-node",
                ".rb":   "ruby",
            }
            interpreter = ext_map.get(p.suffix, "bash")

        return self.run(f'"{interpreter}" "{p}"', timeout=60)

    def cd(self, path: str) -> dict:
        """Change working directory."""
        new = (self._cwd / path).resolve() if not Path(path).is_absolute() \
              else Path(path).expanduser().resolve()
        if not new.exists():
            return {"error": f"Directory not found: {path}"}
        if not new.is_dir():
            return {"error": f"Not a directory: {path}"}
        self._cwd = new
        return {"ok": True, "cwd": str(self._cwd)}

    def pwd(self) -> str:
        return str(self._cwd)

    def which(self, program: str) -> dict:
        import shutil
        path = shutil.which(program)
        return {"program": program, "path": path, "found": path is not None}

    def env_get(self, key: str = "") -> dict:
        if key:
            return {key: self._env.get(key, "")}
        # return safe subset
        safe = {k: v for k, v in self._env.items()
                if k not in ("PASSWORD", "SECRET", "TOKEN", "KEY", "API_KEY")}
        return safe

    def env_set(self, key: str, value: str) -> dict:
        self._env[key] = value
        return {"ok": True, "key": key}

    def install_package(self, package: str, manager: str = "pip") -> dict:
        """Install a package via pip, npm, brew, etc."""
        cmds = {
            "pip":   f"{sys.executable} -m pip install {package}",
            "npm":   f"npm install -g {package}",
            "brew":  f"brew install {package}",
            "apt":   f"sudo apt-get install -y {package}",
            "choco": f"choco install {package} -y",
        }
        cmd = cmds.get(manager, cmds["pip"])
        return self.run(cmd, timeout=120)

    def open_terminal_window(self) -> str:
        """Open a new interactive terminal window."""
        try:
            if PLATFORM == "Windows":
                subprocess.Popen("start cmd", shell=True)
            elif PLATFORM == "Darwin":
                subprocess.Popen(["open", "-a", "Terminal"])
            else:
                for term in ("gnome-terminal", "konsole", "xterm", "x-terminal-emulator"):
                    import shutil
                    if shutil.which(term):
                        subprocess.Popen([term])
                        return f"✅ Opened {term}"
            return "✅ Opened terminal window"
        except Exception as exc:
            return f"❌ {exc}"

    def ping(self, host: str) -> dict:
        flag = "-n" if PLATFORM == "Windows" else "-c"
        return self.run(f"ping {flag} 3 {host}", timeout=10)

    def curl(self, url: str, method: str = "GET",
             data: str = "", headers: dict | None = None) -> dict:
        cmd = ["curl", "-s", "-o", "-", "-w", "\n%{http_code}", "-X", method.upper()]
        if data:
            cmd += ["-d", data]
        for k, v in (headers or {}).items():
            cmd += ["-H", f"{k}: {v}"]
        cmd.append(url)
        return self.run(" ".join(f'"{c}"' if " " in c else c for c in cmd), timeout=15)
