"""
JARVIS Automation Scripts
Pre-built automations you can run directly or schedule with cron / Task Scheduler.

Usage:
    python scripts/automations.py morning          # morning briefing
    python scripts/automations.py cleanup          # clean Downloads folder
    python scripts/automations.py backup           # backup Documents
    python scripts/automations.py screenshot-watch # screenshot every 5 min
    python scripts/automations.py email-digest     # summarise unread emails
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# load .env
from jarvis import load_env  # noqa: E402
load_env()

from tools.file_manager      import FileManager    # noqa: E402
from tools.system_monitor    import SystemMonitor  # noqa: E402
from tools.notification_system import NotificationSystem  # noqa: E402
from tools.email_agent       import EmailAgent     # noqa: E402
from tools.terminal_agent    import TerminalAgent  # noqa: E402
from tools.screen_capture    import ScreenCapture  # noqa: E402
from tools.calendar_agent    import CalendarAgent  # noqa: E402

notif   = NotificationSystem()
files   = FileManager()
monitor = SystemMonitor()
email   = EmailAgent()
term    = TerminalAgent()
screen  = ScreenCapture()
cal     = CalendarAgent()


# ── 1. MORNING BRIEFING ───────────────────────────────────────────────────────
def morning_briefing():
    """
    Runs at boot or on demand.
    - System health check
    - Today's calendar events
    - Unread email count
    - Weather (if plugin available)
    """
    print("\n═══ JARVIS MORNING BRIEFING ═══")
    now = datetime.now().strftime("%A, %B %d at %I:%M %p")
    print(f"  {now}\n")

    # system health
    snap = monitor.snapshot()
    cpu  = snap.get("cpu_percent", 0)
    ram  = snap.get("ram_percent", 0)
    disk = snap.get("disk_percent", 0)
    print(f"  🖥  System:  CPU {cpu}%  ·  RAM {ram}%  ·  Disk {disk}%")

    alert_parts = []
    if cpu  > 80: alert_parts.append(f"CPU high ({cpu}%)")
    if ram  > 85: alert_parts.append(f"RAM high ({ram}%)")
    if disk > 90: alert_parts.append(f"Disk almost full ({disk}%)")
    if alert_parts:
        notif.warning("System Alert: " + " · ".join(alert_parts))

    # calendar
    events = cal.today()
    print(f"\n  📅  Today ({len(events)} events):")
    if events:
        for e in events:
            t = e.get("start", "")[-5:] if len(e.get("start","")) >= 5 else ""
            print(f"      {t}  {e['title']}")
    else:
        print("      No events scheduled")

    # emails
    msgs = email.fetch_inbox(count=5, unread_only=True)
    unread = [m for m in msgs if isinstance(m, dict) and "error" not in m]
    print(f"\n  ✉️   Unread emails: {len(unread)}")
    for m in unread[:3]:
        print(f"      · {m.get('from','?')}  —  {m.get('subject','(no subject)')}")

    # disk space warning
    if disk > 85:
        print(f"\n  ⚠️  Disk usage {disk}% — consider cleanup")
        notif.warning(f"Disk {disk}% full. Run cleanup automation.")

    print("\n═══════════════════════════════\n")
    notif.success(f"Morning briefing complete. {len(events)} events today.")


# ── 2. SMART CLEANUP ──────────────────────────────────────────────────────────
def smart_cleanup(dry_run: bool = True):
    """
    Cleans up Downloads folder:
    - Move files older than 30 days into ~/Downloads/Archive/<month>/
    - Delete .tmp, .crdownload, .part files
    - Show summary
    """
    from datetime import timedelta
    import shutil

    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        print("Downloads folder not found"); return

    cutoff   = time.time() - 30 * 86400
    moved    = 0
    deleted  = 0
    junk_ext = {".tmp", ".crdownload", ".part", ".download", ".~tmp"}

    print(f"\n{'DRY RUN — ' if dry_run else ''}CLEANING: {downloads}\n")

    for item in downloads.iterdir():
        if item.is_file():
            stat = item.stat()

            # delete junk
            if item.suffix.lower() in junk_ext:
                print(f"  🗑  DELETE  {item.name}")
                if not dry_run:
                    item.unlink()
                deleted += 1
                continue

            # archive old files
            if stat.st_mtime < cutoff:
                mdate   = datetime.fromtimestamp(stat.st_mtime)
                archive = downloads / "Archive" / mdate.strftime("%Y-%m")
                dest    = archive / item.name
                print(f"  📦  ARCHIVE → {archive.name}/{item.name}")
                if not dry_run:
                    archive.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(item), str(dest))
                moved += 1

    print(f"\n  Summary: {moved} archived, {deleted} deleted")
    if dry_run:
        print("  (dry run — pass dry_run=False to apply changes)")
    notif.success(f"Cleanup: {moved} archived, {deleted} deleted.")


# ── 3. DOCUMENT BACKUP ───────────────────────────────────────────────────────
def backup_documents(dest_path: str = ""):
    """
    Zip ~/Documents and save timestamped backup.
    """
    docs    = Path.home() / "Documents"
    if not docs.exists():
        print("Documents folder not found"); return

    ts      = datetime.now().strftime("%Y%m%d_%H%M")
    dest    = Path(dest_path).expanduser() if dest_path else Path.home() / "Backups"
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / f"documents_backup_{ts}"

    print(f"  📦  Backing up {docs} → {archive}.zip")
    result = files.zip_folder(str(docs), str(archive) + ".zip")

    if result.get("ok"):
        size = Path(result["archive"]).stat().st_size / 1e6
        print(f"  ✅  Backup complete: {result['archive']} ({size:.1f} MB)")
        notif.success(f"Backup saved: {size:.1f} MB")
    else:
        print(f"  ❌  Backup failed: {result.get('error')}")
        notif.warning(f"Backup failed: {result.get('error')}")


# ── 4. SCREENSHOT WATCHER ────────────────────────────────────────────────────
def screenshot_watcher(interval_minutes: float = 5,
                       output_dir: str = "~/Screenshots/jarvis"):
    """
    Takes a screenshot every N minutes.
    Useful for activity logs or time-lapse work sessions.
    """
    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    print(f"  📸  Screenshot watcher started (every {interval_minutes}m → {out})")
    print("      Press Ctrl+C to stop\n")
    count = 0
    try:
        while True:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(out / f"screen_{ts}.png")
            res  = screen.screenshot(save_path=path)
            if res.get("saved"):
                count += 1
                print(f"  [{count}] Saved: {Path(path).name}")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print(f"\n  Stopped. {count} screenshots saved to {out}")


# ── 5. EMAIL DIGEST ──────────────────────────────────────────────────────────
async def email_digest():
    """
    Fetch unread emails and generate an AI summary via Claude.
    """
    import anthropic

    print("\n═══ EMAIL DIGEST ═══")
    msgs = email.fetch_inbox(count=20, unread_only=True)
    real = [m for m in msgs if isinstance(m, dict) and "error" not in m]

    if not real:
        print("  No unread emails."); return

    print(f"  Found {len(real)} unread emails. Summarising with AI…\n")

    text = "\n".join(
        f"FROM: {m.get('from','?')}\nSUBJECT: {m.get('subject','?')}\nBODY: {m.get('body','')[:200]}\n"
        for m in real
    )

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY",""))
    resp   = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": f"Summarise these emails concisely as bullet points. Highlight anything urgent.\n\n{text}"
        }]
    )
    summary = resp.content[0].text
    print(summary)
    notif.notify("📬 JARVIS Email Digest", f"{len(real)} unread emails summarised")


# ── 6. SYSTEM HEALTH REPORT ──────────────────────────────────────────────────
def health_report():
    """Print a full system health report."""
    print("\n═══ SYSTEM HEALTH REPORT ═══")
    snap = monitor.snapshot()
    for k, v in snap.items():
        if k != "timestamp":
            print(f"  {k:25s}  {v}")

    print("\n  Top processes:")
    for p in monitor.top_processes(n=5):
        print(f"  {p['name']:25s}  CPU: {p['cpu']:5.1f}%  MEM: {p['mem']:4.1f}%")

    print("\n  Disk usage:")
    for d in monitor.disk_usage():
        bar = "█" * int(d["percent"] / 5) + "░" * (20 - int(d["percent"] / 5))
        print(f"  {d['mountpoint']:15s}  [{bar}] {d['percent']}%  ({d['free_gb']} GB free)")
    print()


# ── 7. AUTO-ORGANISE DOWNLOADS ───────────────────────────────────────────────
def organise_downloads(dry_run: bool = True):
    """
    Sort files in ~/Downloads into subfolders by type.
    """
    CATEGORIES = {
        "Images":     {".jpg",".jpeg",".png",".gif",".bmp",".webp",".svg",".heic"},
        "Videos":     {".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm"},
        "Audio":      {".mp3",".wav",".flac",".aac",".ogg",".m4a"},
        "Documents":  {".pdf",".doc",".docx",".txt",".md",".odt",".rtf"},
        "Spreadsheets":{".xls",".xlsx",".csv",".ods"},
        "Code":       {".py",".js",".ts",".html",".css",".json",".xml",".sh",".yaml",".toml"},
        "Archives":   {".zip",".tar",".gz",".rar",".7z",".bz2"},
        "Installers": {".exe",".msi",".dmg",".pkg",".deb",".rpm",".appimage"},
    }

    import shutil
    downloads = Path.home() / "Downloads"
    moved = 0

    print(f"\n{'DRY RUN — ' if dry_run else ''}ORGANISING: {downloads}\n")

    for item in downloads.iterdir():
        if item.is_file() and not item.name.startswith("."):
            ext    = item.suffix.lower()
            folder = next((cat for cat, exts in CATEGORIES.items() if ext in exts), None)
            if folder:
                dest_dir  = downloads / folder
                dest_file = dest_dir / item.name
                print(f"  {folder:12s}  ←  {item.name}")
                if not dry_run:
                    dest_dir.mkdir(exist_ok=True)
                    shutil.move(str(item), str(dest_file))
                moved += 1

    print(f"\n  {moved} files {'would be' if dry_run else ''} moved.")
    if dry_run:
        print("  Pass dry_run=False to apply.")


# ── CLI ENTRY ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if   cmd == "morning":          morning_briefing()
    elif cmd == "cleanup":          smart_cleanup(dry_run="--apply" not in sys.argv)
    elif cmd == "backup":           backup_documents(sys.argv[2] if len(sys.argv)>2 else "")
    elif cmd == "screenshot-watch": screenshot_watcher()
    elif cmd == "email-digest":     asyncio.run(email_digest())
    elif cmd == "health":           health_report()
    elif cmd == "organise":         organise_downloads(dry_run="--apply" not in sys.argv)
    else:
        print("\nJARVIS Automation Scripts\n")
        print("  python scripts/automations.py morning              # morning briefing")
        print("  python scripts/automations.py cleanup [--apply]    # clean Downloads")
        print("  python scripts/automations.py organise [--apply]   # sort Downloads by type")
        print("  python scripts/automations.py backup [dest_path]   # zip Documents")
        print("  python scripts/automations.py screenshot-watch     # screenshot every 5 min")
        print("  python scripts/automations.py email-digest         # AI email summary")
        print("  python scripts/automations.py health               # system health report")
        print()
