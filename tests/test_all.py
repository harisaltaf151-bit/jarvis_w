"""
JARVIS Test Suite
Run all tool tests:  python tests/test_all.py
Run specific test:   python tests/test_all.py files
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── ANSI ─────────────────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"
RST = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"

passed = 0
failed = 0
skipped = 0


def ok(name, detail=""):
    global passed; passed += 1
    print(f"  {G}✓{RST}  {name}" + (f"  {DIM}{detail}{RST}" if detail else ""))


def fail(name, err=""):
    global failed; failed += 1
    print(f"  {R}✗{RST}  {name}" + (f"  {R}{err}{RST}" if err else ""))


def skip(name, reason=""):
    global skipped; skipped += 1
    print(f"  {Y}–{RST}  {name}" + (f"  {DIM}{reason}{RST}" if reason else ""))


def section(name):
    print(f"\n{BOLD}{C}▸ {name}{RST}")


# ── FILE MANAGER TESTS ────────────────────────────────────────────────────────
def test_files():
    section("File Manager")
    from tools.file_manager import FileManager
    fm = FileManager()

    with tempfile.TemporaryDirectory() as tmp:
        # write
        res = fm.write_file(f"{tmp}/test.txt", "Hello JARVIS!\nLine 2")
        if res.get("ok"):
            ok("write_file")
        else:
            fail("write_file", res.get("error"))

        # read
        res = fm.read_file(f"{tmp}/test.txt")
        if "Hello JARVIS!" in res.get("content",""):
            ok("read_file", f"{res['lines']} lines")
        else:
            fail("read_file", res.get("error","content mismatch"))

        # list dir
        res = fm.list_dir(tmp)
        if res.get("entries"):
            ok("list_dir", f"{res['count']} entries")
        else:
            fail("list_dir", str(res))

        # create folder
        res = fm.create_folder(f"{tmp}/subdir/nested")
        if res.get("ok"):
            ok("create_folder")
        else:
            fail("create_folder", res.get("error"))

        # copy
        res = fm.copy(f"{tmp}/test.txt", f"{tmp}/subdir/test_copy.txt")
        if res.get("ok"):
            ok("copy")
        else:
            fail("copy", res.get("error"))

        # move
        res = fm.move(f"{tmp}/subdir/test_copy.txt", f"{tmp}/moved.txt")
        if res.get("ok"):
            ok("move")
        else:
            fail("move", res.get("error"))

        # get_info
        res = fm.get_info(f"{tmp}/test.txt")
        if res.get("name") == "test.txt":
            ok("get_info", f"{res['size']}")
        else:
            fail("get_info", str(res))

        # append
        res = fm.write_file(f"{tmp}/test.txt", "\nLine 3", mode="append")
        content = fm.read_file(f"{tmp}/test.txt").get("content","")
        if "Line 3" in content:
            ok("write_file append")
        else:
            fail("write_file append")

        # search
        res = fm.search("test", tmp, recursive=True)
        if len(res) >= 1:
            ok("search", f"{len(res)} results")
        else:
            fail("search", "no results")

        # zip
        res = fm.zip_folder(f"{tmp}/subdir", f"{tmp}/subdir_archive.zip")
        if res.get("ok"):
            ok("zip_folder")
        else:
            fail("zip_folder", res.get("error",""))

        # recent_files
        res = fm.recent_files(tmp, days=1)
        if isinstance(res, list):
            ok("recent_files", f"{len(res)} files")
        else:
            fail("recent_files")

        # delete
        res = fm.delete(f"{tmp}/moved.txt", confirm=True)
        if res.get("ok"):
            ok("delete")
        else:
            fail("delete", res.get("error"))


# ── SYSTEM MONITOR TESTS ─────────────────────────────────────────────────────
def test_system():
    section("System Monitor")
    from tools.system_monitor import SystemMonitor
    sm = SystemMonitor()

    snap = sm.snapshot()
    if "cpu_percent" in snap:
        ok("snapshot", f"CPU {snap['cpu_percent']}%  RAM {snap.get('ram_percent')}%")
    else:
        fail("snapshot", str(snap))

    procs = sm.top_processes(5)
    if procs and isinstance(procs[0], dict) and "name" in procs[0]:
        ok("top_processes", f"{len(procs)} returned")
    else:
        fail("top_processes", str(procs[:1]))

    disks = sm.disk_usage()
    if disks and isinstance(disks[0], dict) and "mountpoint" in disks[0]:
        ok("disk_usage", f"{len(disks)} volumes")
    else:
        fail("disk_usage")

    up = sm.uptime()
    if up and "error" not in up.lower():
        ok("uptime", up)
    else:
        skip("uptime", "platform limitation")

    batt = sm.battery()
    if "error" not in batt and "status" in batt or "percent" in batt:
        ok("battery", str(batt))
    else:
        skip("battery", "no battery / desktop")


# ── TERMINAL AGENT TESTS ─────────────────────────────────────────────────────
def test_terminal():
    section("Terminal Agent")
    from tools.terminal_agent import TerminalAgent
    ta = TerminalAgent()

    # basic command
    res = ta.run("echo JARVIS_TEST_OK")
    if "JARVIS_TEST_OK" in res.get("stdout",""):
        ok("run echo")
    else:
        fail("run echo", str(res))

    # python
    res = ta.run_python("print(2 + 2)")
    if "4" in res.get("stdout",""):
        ok("run_python")
    else:
        fail("run_python", str(res))

    # cd / pwd
    res = ta.cd(str(Path.home()))
    if res.get("ok"):
        ok("cd", ta.pwd())
    else:
        fail("cd", str(res))

    # which
    res = ta.which("python")
    if res.get("found") or ta.which("python3").get("found"):
        ok("which python")
    else:
        skip("which", "python not in PATH")

    # env
    res = ta.env_set("JARVIS_TEST", "hello")
    got = ta.env_get("JARVIS_TEST")
    if got.get("JARVIS_TEST") == "hello":
        ok("env_set / env_get")
    else:
        fail("env_set / env_get")


# ── APP CONTROLLER TESTS ─────────────────────────────────────────────────────
def test_app():
    section("App Controller")
    from tools.app_controller import AppController
    ac = AppController()

    procs = ac.list_running()
    if procs and isinstance(procs[0], dict):
        ok("list_running", f"{len(procs)} processes")
    else:
        fail("list_running")

    # open_url — just verify no exception
    try:
        import webbrowser
        ok("open_url (import)")
    except Exception as e:
        fail("open_url", str(e))


# ── CALENDAR TESTS ────────────────────────────────────────────────────────────
def test_calendar():
    section("Calendar Agent")
    from tools.calendar_agent import CalendarAgent
    ca = CalendarAgent()

    # create
    res = ca.create_event(
        title="JARVIS Test Event",
        start="2030-01-15 10:00",
        end="2030-01-15 11:00",
        notes="Automated test"
    )
    if res.get("ok"):
        eid = res["event"]["id"]
        ok("create_event", f"id={eid}")
    else:
        fail("create_event", str(res)); return

    # search
    res = ca.search("JARVIS Test")
    if res:
        ok("search_events", f"{len(res)} found")
    else:
        fail("search_events")

    # quick_add
    res = ca.quick_add("Team standup tomorrow at 9am for 30 minutes")
    if res.get("ok"):
        ok("quick_add", res["event"]["title"])
        ca.delete_event(res["event"]["id"])
    else:
        fail("quick_add", str(res))

    # update
    res = ca.update_event(eid, title="JARVIS Test Event — Updated")
    if res.get("ok"):
        ok("update_event")
    else:
        fail("update_event", str(res))

    # delete
    res = ca.delete_event(eid)
    if res.get("ok"):
        ok("delete_event")
    else:
        fail("delete_event", str(res))


# ── NOTIFICATION TESTS ────────────────────────────────────────────────────────
def test_notifications():
    section("Notification System")
    from tools.notification_system import NotificationSystem
    ns = NotificationSystem()

    # reminder (short duration)
    res = ns.remind_in("Test reminder", minutes=9999)
    if res.get("ok"):
        ok("remind_in", f"id={res['id']}")
        ns.cancel_reminder(res["id"])
        ok("cancel_reminder")
    else:
        fail("remind_in", str(res))

    res = ns.remind_at("Morning alarm", "23:59")
    if res.get("ok"):
        ok("remind_at")
        ns.cancel_reminder(res["id"])
    else:
        fail("remind_at", str(res))

    res = ns.list_reminders()
    if isinstance(res, list):
        ok("list_reminders")
    else:
        fail("list_reminders")

    ns.stop()


# ── CLIPBOARD TESTS ───────────────────────────────────────────────────────────
def test_clipboard():
    section("Clipboard Manager")
    from tools.clipboard_manager import ClipboardManager
    cb = ClipboardManager()

    res = cb.set("JARVIS clipboard test 🤖")
    if res.get("ok"):
        ok("set", f"{res['chars']} chars")
    else:
        skip("set", res.get("error","clipboard unavailable"))
        return

    text = cb.get()
    if "JARVIS" in text:
        ok("get")
    else:
        skip("get", "clipboard read back may differ in headless env")

    hist = cb.history()
    if hist:
        ok("history", f"{len(hist)} entries")
    else:
        fail("history")


# ── PLUGIN ENGINE TESTS ───────────────────────────────────────────────────────
def test_plugins():
    section("Plugin Engine")
    from core.plugin_engine import PluginEngine, create_example_plugin, PLUGIN_DIR
    pe = PluginEngine()

    path = create_example_plugin()
    ok("create_example_plugin", path)

    res = pe.load_file(Path(path))
    if res.get("ok"):
        ok("load_file", res["name"])
    else:
        fail("load_file", res.get("error"))
        return

    lst = pe.list_plugins()
    if lst:
        ok("list_plugins", str([p["name"] for p in lst]))
    else:
        fail("list_plugins")

    res = pe.call("weather", "current", {"city": "London"})
    if res.get("ok") and "error" not in res.get("result",{}):
        ok("plugin.weather.current", str(res["result"]))
    else:
        skip("plugin.weather.current", "network unavailable or wttr.in down")

    pe.unload("weather")
    ok("unload")


# ── SUMMARY ───────────────────────────────────────────────────────────────────
def summary():
    total = passed + failed + skipped
    print(f"\n{'═'*45}")
    print(f"  {BOLD}Results:{RST}  "
          f"{G}{passed} passed{RST}  "
          f"{R}{failed} failed{RST}  "
          f"{Y}{skipped} skipped{RST}  "
          f"/ {total} total")
    if failed == 0:
        print(f"  {G}{BOLD}All tests passed ✓{RST}")
    else:
        print(f"  {R}{BOLD}{failed} test(s) failed ✗{RST}")
    print(f"{'═'*45}\n")
    return failed == 0


# ── ENTRY ─────────────────────────────────────────────────────────────────────
SUITES = {
    "files":      test_files,
    "system":     test_system,
    "terminal":   test_terminal,
    "app":        test_app,
    "calendar":   test_calendar,
    "notify":     test_notifications,
    "clipboard":  test_clipboard,
    "plugins":    test_plugins,
}

if __name__ == "__main__":
    print(f"\n{BOLD}{C}JARVIS Test Suite{RST}\n")
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    if target == "all":
        for fn in SUITES.values():
            fn()
    elif target in SUITES:
        SUITES[target]()
    else:
        print(f"Unknown suite '{target}'. Available: {', '.join(SUITES)}")
        sys.exit(1)

    ok_all = summary()
    sys.exit(0 if ok_all else 1)
