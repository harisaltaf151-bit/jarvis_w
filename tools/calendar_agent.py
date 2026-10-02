"""
JARVIS Tool — Calendar Agent
Manage calendar events: list, create, delete, search.
Supports: local .ics files + Google Calendar API (optional).
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path


CAL_FILE = Path.home() / ".jarvis" / "calendar.json"


def _load_events() -> list[dict]:
    CAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CAL_FILE.exists():
        return []
    try:
        return json.loads(CAL_FILE.read_text())
    except Exception:
        return []


def _save_events(events: list[dict]) -> None:
    CAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    CAL_FILE.write_text(json.dumps(events, indent=2))


class CalendarAgent:

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def list_events(self, days: int = 7) -> list[dict]:
        """List events in the next N days."""
        events  = _load_events()
        cutoff  = (datetime.now() + timedelta(days=days)).isoformat()
        now_str = datetime.now().isoformat()
        upcoming = [
            e for e in events
            if e.get("start", "") >= now_str and e.get("start", "") <= cutoff
        ]
        return sorted(upcoming, key=lambda x: x.get("start", ""))

    def today(self) -> list[dict]:
        """Events for today."""
        events  = _load_events()
        today   = datetime.now().strftime("%Y-%m-%d")
        return [e for e in events if e.get("start", "").startswith(today)]

    def create_event(self, title: str, start: str, end: str = "",
                     location: str = "", notes: str = "",
                     reminder_minutes: int = 15) -> dict:
        """
        Create an event.
        start/end format: 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'
        """
        start_dt = _parse_dt(start)
        if start_dt is None:
            return {"error": f"Could not parse start time: {start}"}

        if not end:
            end_dt = start_dt + timedelta(hours=1)
        else:
            end_dt = _parse_dt(end) or (start_dt + timedelta(hours=1))

        event: dict = {
            "id":       _new_id(),
            "title":    title,
            "start":    start_dt.isoformat(),
            "end":      end_dt.isoformat(),
            "location": location,
            "notes":    notes,
            "reminder": reminder_minutes,
            "created":  datetime.now().isoformat(),
        }

        events = _load_events()
        events.append(event)
        _save_events(events)

        return {"ok": True, "event": event}

    def delete_event(self, event_id: str) -> dict:
        events = _load_events()
        orig   = len(events)
        events = [e for e in events if e.get("id") != event_id]
        if len(events) == orig:
            return {"error": f"Event not found: {event_id}"}
        _save_events(events)
        return {"ok": True, "deleted": event_id}

    def update_event(self, event_id: str, **kwargs) -> dict:
        events = _load_events()
        for e in events:
            if e.get("id") == event_id:
                for k, v in kwargs.items():
                    e[k] = v
                e["updated"] = datetime.now().isoformat()
                _save_events(events)
                return {"ok": True, "event": e}
        return {"error": f"Event not found: {event_id}"}

    def search(self, query: str) -> list[dict]:
        events = _load_events()
        q = query.lower()
        return [
            e for e in events
            if q in e.get("title", "").lower()
            or q in e.get("notes", "").lower()
            or q in e.get("location", "").lower()
        ]

    # ── Natural language helpers ──────────────────────────────────────────────
    def quick_add(self, natural: str) -> dict:
        """
        Parse a natural language event description.
        Example: "Team meeting tomorrow at 3pm for 1 hour"
        """
        now   = datetime.now()
        lower = natural.lower()

        # date parsing
        if "tomorrow" in lower:
            base = now + timedelta(days=1)
        elif "today" in lower:
            base = now
        elif "next week" in lower:
            base = now + timedelta(days=7)
        elif "monday" in lower:
            base = _next_weekday(now, 0)
        elif "tuesday" in lower:
            base = _next_weekday(now, 1)
        elif "wednesday" in lower:
            base = _next_weekday(now, 2)
        elif "thursday" in lower:
            base = _next_weekday(now, 3)
        elif "friday" in lower:
            base = _next_weekday(now, 4)
        else:
            base = now + timedelta(days=1)

        # time parsing
        import re
        time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lower)
        hour, minute = 9, 0
        if time_match:
            hour   = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            ampm   = time_match.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0

        start = base.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # duration
        dur_match = re.search(r"for\s+(\d+)\s*(hour|hr|minute|min)", lower)
        duration  = timedelta(hours=1)
        if dur_match:
            amount = int(dur_match.group(1))
            unit   = dur_match.group(2)
            if "hour" in unit or "hr" in unit:
                duration = timedelta(hours=amount)
            else:
                duration = timedelta(minutes=amount)

        # title = natural string cleaned up
        title = re.sub(
            r"(tomorrow|today|next week|monday|tuesday|wednesday|thursday|friday|"
            r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?|for \d+ (?:hour|hr|min)\w*)",
            "", natural, flags=re.IGNORECASE
        ).strip(" ,at")

        return self.create_event(
            title=title or natural,
            start=start.isoformat(),
            end=(start + duration).isoformat(),
        )

    def export_ics(self, output_path: str = "") -> dict:
        """Export events to .ics file."""
        try:
            from icalendar import Calendar, Event as ICalEvent
            cal = Calendar()
            cal.add("prodid", "-//JARVIS//AI OS//EN")
            cal.add("version", "2.0")

            for ev in _load_events():
                ical_event = ICalEvent()
                ical_event.add("summary", ev["title"])
                ical_event.add("dtstart", datetime.fromisoformat(ev["start"]))
                ical_event.add("dtend",   datetime.fromisoformat(ev["end"]))
                if ev.get("location"):
                    ical_event.add("location", ev["location"])
                if ev.get("notes"):
                    ical_event.add("description", ev["notes"])
                cal.add_component(ical_event)

            path = Path(output_path).expanduser() if output_path \
                   else Path.home() / "jarvis_calendar.ics"
            path.write_bytes(cal.to_ical())
            return {"ok": True, "file": str(path)}
        except ImportError:
            return {"error": "icalendar not installed. Run: pip install icalendar"}


# ── helpers ────────────────────────────────────────────────────────────────────
def _parse_dt(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return None


def _next_weekday(ref: datetime, weekday: int) -> datetime:
    days = (weekday - ref.weekday() + 7) % 7
    return ref + timedelta(days=days or 7)


def _new_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8]
