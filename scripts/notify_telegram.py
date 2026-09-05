"""Sends Telegram notifications for the two "reach me even when the
site isn't open" events the original idea called for: a goal/red card
the moment it happens to a squad player, and a transfer-deadline
reminder - both bypass js/ui/reminders.js's Notification API limit
(only fires while a browser tab is open).

No-ops (prints and returns) whenever TELEGRAM_BOT_TOKEN/
TELEGRAM_CHAT_ID aren't set as env vars, so this is safe to ship before
those secrets exist in the repo.
"""
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


# .strip() guards against a trailing newline sneaking into the secret's
# value from a copy-paste (e.g. BotFather's reply ends with one) -
# urllib rejects control characters in a URL outright otherwise.
BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
CHAT_ID = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

GOAL_EVENT_STATS = {
    "goals_scored": "⚽ שער",
    "assists": "🅰️ בישול",
    "red_cards": "🟥 כרטיס אדום",
    "own_goals": "⚽ שער עצמי (נגד)",
}

DEADLINE_REMINDER_HOURS = 2


def send_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("notify_telegram: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set, skipping")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except urllib.error.HTTPError as e:
        print(f"notify_telegram: failed to send message: {e} - {e.read().decode(errors='replace')}")
    except Exception as e:
        print(f"notify_telegram: failed to send message: {e}")


def check_goal_events(live_event, my_player_ids, elements_by_id, prior_state):
    """live_event: {"gameweek": n, "elements": {pid_str: trimmed live
    stats}} for the CURRENT poll. my_player_ids: this gameweek's 15
    squad player ids (a frozen list once the deadline's passed - reads
    from that gw's own picks file, not the user-maintained my_squad.json,
    which only reflects whatever squad was true when it was last hand-
    edited). prior_state: last saved notify_state.json (or {}). Returns
    the updated state to save - resets the per-player baseline whenever
    the gameweek changes, but never touches unrelated keys (e.g.
    deadline_notified_for)."""
    state = dict(prior_state)
    if not my_player_ids or not live_event:
        return state

    gw = live_event["gameweek"]
    if state.get("gw") != gw:
        state["gw"] = gw
        state["players"] = {}
    players_state = state.setdefault("players", {})

    for pid in my_player_ids:
        current = live_event["elements"].get(str(pid))
        if not current:
            continue
        prev = players_state.get(str(pid))
        # prev is None only the very first time this player's tracked
        # this gameweek (fresh setup mid-gameweek, or a rare mid-gw
        # transfer-in) - seed the baseline silently instead of firing a
        # stale "goal" ping for whatever already happened before we
        # were watching.
        if prev is not None:
            p = elements_by_id.get(pid)
            name = p["web_name"] if p else str(pid)
            for stat, label in GOAL_EVENT_STATS.items():
                delta = (current.get(stat) or 0) - (prev.get(stat) or 0)
                for _ in range(max(delta, 0)):
                    send_message(f"{label}: {name} ({current.get('minutes')}')")
        players_state[str(pid)] = current

    return state


def check_deadline_reminder(meta, prior_state):
    state = dict(prior_state)
    if not meta or not meta.get("deadline_time"):
        return state

    deadline = datetime.fromisoformat(meta["deadline_time"].replace("Z", "+00:00"))
    hours_left = (deadline - datetime.now(timezone.utc)).total_seconds() / 3600

    if 0 < hours_left <= DEADLINE_REMINDER_HOURS and state.get("deadline_notified_for") != meta["deadline_time"]:
        send_message(f"⏰ דדליין למחזור {meta['gw_next']} בעוד פחות מ-{DEADLINE_REMINDER_HOURS} שעות!")
        state["deadline_notified_for"] = meta["deadline_time"]

    return state
