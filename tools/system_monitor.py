"""
JARVIS Tool — System Monitor
Real-time CPU, RAM, GPU, disk, network, and process stats.
"""

import os
import platform
import socket
import subprocess
from datetime import datetime
from pathlib import Path


class SystemMonitor:

    def snapshot(self) -> dict:
        """Full system snapshot for the HUD."""
        try:
            import psutil
            cpu   = psutil.cpu_percent(interval=0.2)
            mem   = psutil.virtual_memory()
            disk  = psutil.disk_usage(str(Path.home()))
            net   = psutil.net_io_counters()
            boot  = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M")
            temps = {}
            try:
                raw = psutil.sensors_temperatures()
                for k, v in raw.items():
                    if v:
                        temps[k] = round(v[0].current, 1)
            except Exception:
                pass

            return {
                "cpu_percent":     round(cpu, 1),
                "cpu_count":       psutil.cpu_count(),
                "ram_used_gb":     round(mem.used / 1e9, 2),
                "ram_total_gb":    round(mem.total / 1e9, 2),
                "ram_percent":     mem.percent,
                "disk_used_gb":    round(disk.used / 1e9, 1),
                "disk_total_gb":   round(disk.total / 1e9, 1),
                "disk_percent":    round(disk.percent, 1),
                "net_sent_mb":     round(net.bytes_sent / 1e6, 1),
                "net_recv_mb":     round(net.bytes_recv / 1e6, 1),
                "boot_time":       boot,
                "temperatures":    temps,
                "platform":        f"{platform.system()} {platform.release()}",
                "hostname":        socket.gethostname(),
                "timestamp":       datetime.now().isoformat(),
            }
        except ImportError:
            return self._snapshot_no_psutil()

    def _snapshot_no_psutil(self) -> dict:
        """Fallback when psutil not installed."""
        info = {
            "platform":  f"{platform.system()} {platform.release()}",
            "hostname":  socket.gethostname(),
            "timestamp": datetime.now().isoformat(),
        }
        if platform.system() == "Linux":
            try:
                with open("/proc/meminfo") as f:
                    lines = {l.split(":")[0]: l.split(":")[1].strip() for l in f}
                total = int(lines["MemTotal"].split()[0])
                avail = int(lines["MemAvailable"].split()[0])
                info["ram_used_gb"]  = round((total - avail) / 1e6, 2)
                info["ram_total_gb"] = round(total / 1e6, 2)
            except Exception:
                pass
        return info

    def top_processes(self, n: int = 15) -> list[dict]:
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
                try:
                    procs.append({
                        "pid":     p.info["pid"],
                        "name":    p.info["name"],
                        "cpu":     round(p.info["cpu_percent"] or 0, 1),
                        "mem":     round(p.info["memory_percent"] or 0, 1),
                        "status":  p.info["status"],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda x: x["cpu"], reverse=True)
            return procs[:n]
        except ImportError:
            return [{"error": "psutil not installed"}]

    def disk_usage(self) -> list[dict]:
        try:
            import psutil
            result = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    result.append({
                        "device":     part.device,
                        "mountpoint": part.mountpoint,
                        "fstype":     part.fstype,
                        "total_gb":   round(usage.total / 1e9, 1),
                        "used_gb":    round(usage.used / 1e9, 1),
                        "free_gb":    round(usage.free / 1e9, 1),
                        "percent":    usage.percent,
                    })
                except PermissionError:
                    pass
            return result
        except ImportError:
            return [{"error": "psutil not installed"}]

    def network_connections(self) -> list[dict]:
        try:
            import psutil
            conns = []
            for c in psutil.net_connections(kind="inet"):
                if c.status == "ESTABLISHED":
                    conns.append({
                        "local":   f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                        "remote":  f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                        "status":  c.status,
                        "pid":     c.pid,
                    })
            return conns[:30]
        except Exception as exc:
            return [{"error": str(exc)}]

    def battery(self) -> dict:
        try:
            import psutil
            batt = psutil.sensors_battery()
            if batt is None:
                return {"status": "No battery (desktop)"}
            return {
                "percent":    round(batt.percent, 1),
                "plugged_in": batt.power_plugged,
                "time_left":  str(int(batt.secsleft / 60)) + " min" if batt.secsleft > 0 else "Charging",
            }
        except Exception as exc:
            return {"error": str(exc)}

    def uptime(self) -> str:
        try:
            import psutil
            diff = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
            h, rem = divmod(int(diff.total_seconds()), 3600)
            m = rem // 60
            return f"{h}h {m}m"
        except Exception:
            if platform.system() != "Windows":
                out = subprocess.check_output(["uptime", "-p"], text=True).strip()
                return out
            return "unknown"

    def kill_process(self, pid: int) -> dict:
        try:
            import psutil
            p = psutil.Process(pid)
            name = p.name()
            p.terminate()
            return {"ok": True, "killed": name, "pid": pid}
        except Exception as exc:
            return {"error": str(exc)}
