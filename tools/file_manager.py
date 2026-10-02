"""
JARVIS Tool — File Manager
Search, read, write, copy, move, delete, and organise files.
"""

import os
import shutil
import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path


class FileManager:

    def list_dir(self, path: str = "~", show_hidden: bool = False) -> dict:
        """List directory contents."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"error": f"Path not found: {path}"}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}

        entries = []
        try:
            for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
                if not show_hidden and item.name.startswith("."):
                    continue
                stat = item.stat()
                entries.append({
                    "name":     item.name,
                    "type":     "dir" if item.is_dir() else "file",
                    "size":     _fmt_size(stat.st_size) if item.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "ext":      item.suffix.lower() if item.is_file() else None,
                })
        except PermissionError:
            return {"error": f"Permission denied: {path}"}

        return {"path": str(p), "entries": entries, "count": len(entries)}

    def search(self, query: str, path: str = "~",
               recursive: bool = True, file_type: str = "") -> list[dict]:
        """Search for files matching a query (name or extension)."""
        root = Path(path).expanduser().resolve()
        results = []
        pattern = f"**/{query}*" if recursive else f"{query}*"

        try:
            for item in root.glob(pattern):
                if file_type and item.suffix.lower() != f".{file_type.lstrip('.')}":
                    continue
                stat = item.stat()
                results.append({
                    "path":     str(item),
                    "name":     item.name,
                    "size":     _fmt_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
                if len(results) >= 100:
                    break
        except (PermissionError, OSError):
            pass

        return results

    def read_file(self, path: str, max_chars: int = 8000) -> dict:
        """Read a text file."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if p.stat().st_size > 10_000_000:
            return {"error": "File too large to read directly (>10 MB)"}

        mime, _ = mimetypes.guess_type(str(p))
        if mime and not mime.startswith("text"):
            return {"error": f"Binary file ({mime}) — cannot display as text"}

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            truncated = len(content) > max_chars
            return {
                "path":      str(p),
                "content":   content[:max_chars],
                "truncated": truncated,
                "lines":     content.count("\n"),
                "size":      _fmt_size(p.stat().st_size),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def write_file(self, path: str, content: str,
                   mode: str = "overwrite") -> dict:
        """Write or append to a text file. mode: overwrite | append"""
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        try:
            flag = "a" if mode == "append" else "w"
            with open(p, flag, encoding="utf-8") as f:
                f.write(content)
            return {"ok": True, "path": str(p), "size": _fmt_size(p.stat().st_size)}
        except Exception as exc:
            return {"error": str(exc)}

    def create_folder(self, path: str) -> dict:
        """Create a new directory (and parents)."""
        p = Path(path).expanduser().resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
            return {"ok": True, "path": str(p)}
        except Exception as exc:
            return {"error": str(exc)}

    def copy(self, src: str, dst: str) -> dict:
        """Copy a file or directory."""
        s, d = Path(src).expanduser(), Path(dst).expanduser()
        try:
            if s.is_dir():
                shutil.copytree(str(s), str(d))
            else:
                shutil.copy2(str(s), str(d))
            return {"ok": True, "src": str(s), "dst": str(d)}
        except Exception as exc:
            return {"error": str(exc)}

    def move(self, src: str, dst: str) -> dict:
        """Move / rename a file or directory."""
        try:
            shutil.move(str(Path(src).expanduser()), str(Path(dst).expanduser()))
            return {"ok": True, "src": src, "dst": dst}
        except Exception as exc:
            return {"error": str(exc)}

    def delete(self, path: str, confirm: bool = False) -> dict:
        """Delete a file or directory. confirm must be True."""
        if not confirm:
            return {"error": "Set confirm=True to delete. This is irreversible."}
        p = Path(path).expanduser().resolve()
        try:
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink()
            return {"ok": True, "deleted": str(p)}
        except Exception as exc:
            return {"error": str(exc)}

    def recent_files(self, path: str = "~",
                     days: int = 7, limit: int = 30) -> list[dict]:
        """Find files modified within the last N days."""
        import time
        root  = Path(path).expanduser().resolve()
        cutoff = time.time() - days * 86400
        results = []
        try:
            for item in root.rglob("*"):
                if item.is_file() and not any(p.startswith(".") for p in item.parts):
                    try:
                        mtime = item.stat().st_mtime
                        if mtime >= cutoff:
                            results.append({
                                "path":     str(item),
                                "name":     item.name,
                                "modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
                                "size":     _fmt_size(item.stat().st_size),
                            })
                    except OSError:
                        pass
                if len(results) >= limit * 3:   # gather more, sort, slice
                    break
        except (PermissionError, OSError):
            pass

        results.sort(key=lambda x: x["modified"], reverse=True)
        return results[:limit]

    def get_info(self, path: str) -> dict:
        """Get detailed metadata about a file or directory."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"error": f"Not found: {path}"}
        stat = p.stat()
        info = {
            "path":      str(p),
            "name":      p.name,
            "type":      "directory" if p.is_dir() else "file",
            "size":      _fmt_size(stat.st_size),
            "created":   datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified":  datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": p.suffix,
        }
        if p.is_file():
            mime, _ = mimetypes.guess_type(str(p))
            info["mime"] = mime
            if stat.st_size < 5_000_000:
                info["md5"] = hashlib.md5(p.read_bytes()).hexdigest()
        return info

    def zip_folder(self, path: str, output: str = "") -> dict:
        """Compress a folder to .zip."""
        p   = Path(path).expanduser().resolve()
        out = Path(output).expanduser() if output else p.parent / f"{p.name}.zip"
        try:
            shutil.make_archive(str(out.with_suffix("")), "zip", str(p.parent), p.name)
            return {"ok": True, "archive": str(out)}
        except Exception as exc:
            return {"error": str(exc)}

    def unzip(self, path: str, destination: str = "") -> dict:
        """Extract a .zip archive."""
        p   = Path(path).expanduser().resolve()
        dst = Path(destination).expanduser() if destination else p.parent / p.stem
        try:
            shutil.unpack_archive(str(p), str(dst))
            return {"ok": True, "extracted_to": str(dst)}
        except Exception as exc:
            return {"error": str(exc)}


# ── helpers ────────────────────────────────────────────────────────────────────
def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
