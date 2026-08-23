"""Builds a subscribable ICS *feed* (not a one-off event) listing every
gameweek deadline for the season, from bootstrap.json's `events` list.

Unlike reminders.js's client-side "quick add" (one event, one click,
per gameweek), this file is meant to be subscribed to once via
Google Calendar's "Add calendar > From URL" - Google then re-polls
this URL periodically (every 12-24h or so) and keeps the whole
season's deadlines up to date automatically, including any schedule
changes (DGW/BGW re-shuffles change deadline_time too, same UID keyed
by gameweek id so an update - not a duplicate - lands).

No VALARM blocks here on purpose: subscribed/secondary calendars in
Google Calendar ignore reminders embedded in the source feed and only
use whatever notification the user configures for that calendar in
Google Calendar's own settings (a one-time step, done once for the
whole subscription, not per event).
"""
from datetime import datetime, timedelta


def _to_ics_utc(iso_str):
    # bootstrap's deadline_time is already UTC, e.g. "2026-08-21T17:30:00Z"
    # -> "20260821T173000Z"
    return iso_str.replace("-", "").replace(":", "").split(".")[0]


def _ics_escape(text):
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


def build_deadlines_ics(events):
    """events: bootstrap['events'] - a list of {id, name, deadline_time}."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//FPL Analyzer//he",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:דדליינים FPL",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]

    for ev in events:
        deadline = ev.get("deadline_time")
        if not deadline:
            continue
        start = _to_ics_utc(deadline)
        # 15-minute placeholder duration, same convention as the
        # client-side quick-add event in js/ui/reminders.js.
        dt = datetime.strptime(start, "%Y%m%dT%H%M%SZ")
        end = (dt + timedelta(minutes=15)).strftime("%Y%m%dT%H%M%SZ")

        gw_label = f"מחזור {ev['id']}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:fpl-gw{ev['id']}-deadline@fpl-analyzer",
            f"DTSTAMP:{start}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{_ics_escape(f'דדליין FPL - {gw_label}')}",
            f"DESCRIPTION:{_ics_escape(f'דדליין להעברות ובחירת קבוצה ל{gw_label} בפנטזי פרימייר ליג')}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
