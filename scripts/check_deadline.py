#!/usr/bin/env python3
"""Lightweight companion to fetch_data.py, built for deadline-watch.yml
to call every few minutes on its own internal timer.

Why this exists: GitHub's schedule cron is not reliable at the
precision a "deadline in under 2 hours" reminder needs - in practice,
scheduled runs on this repo have landed hours later than their cron
time (observed directly: a "0 5 * * *" run once landed at 09:49 UTC).
Instead of trusting cron's granularity, fetch_data.py arms
deadline-watch.yml once a deadline is within ~26h (see
arm_deadline_watch in fetch_data.py), and that workflow loops on a
plain shell `sleep` every few minutes, calling this script each time -
no heavy analysis pipeline, just the one bootstrap fetch + the two
Telegram checks, so looping tightly all day costs almost nothing.

Prints DEADLINE_HANDLED on its last line once both the reminder and
the deadline-passed message for the currently-watched gameweek have
fired, so the workflow's loop knows it can stop early.
"""
from fetch_data import get_json, current_event, build_meta, BASE
from notify_telegram import check_deadline_reminder, check_deadline_passed


def load(name):
    import json
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "data", name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(name, obj):
    import json
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "data", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    # Only bootstrap-static is needed for deadline timing - skip
    # fixtures.json and everything else fetch_data.py's full pipeline
    # pulls, so this stays cheap enough to run every few minutes.
    bootstrap = get_json(f"{BASE}/bootstrap-static/")
    gw, is_upcoming = current_event(bootstrap)
    meta = build_meta(bootstrap, gw, is_upcoming)

    state = load("notify_state.json") or {}
    state = check_deadline_reminder(meta, state)
    state = check_deadline_passed(meta, state)
    save("notify_state.json", state)

    reminder_done = meta.get("deadline_time") and state.get("deadline_notified_for") == meta["deadline_time"]
    passed_done = meta.get("is_upcoming") is False and state.get("last_locked_gw") == meta.get("gameweek")
    print(f"deadline watch: gw={meta.get('gameweek')} is_upcoming={meta.get('is_upcoming')} "
          f"reminder_done={bool(reminder_done)} passed_done={bool(passed_done)}")
    if reminder_done and passed_done:
        print("DEADLINE_HANDLED")


if __name__ == "__main__":
    main()
