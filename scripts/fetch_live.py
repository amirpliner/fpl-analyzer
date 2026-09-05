#!/usr/bin/env python3
"""Lightweight, frequent-polling companion to fetch_data.py - built to
run every few minutes during matchday windows (see
.github/workflows/update-live.yml) to power the site's "live" tab:
live fixture scores, a live per-player squad breakdown, and a live
mini-league table.

Deliberately separate from fetch_data.py's heavy daily pipeline (which
also does ~200 element-summary calls, price history, player history,
etc. - too slow to run every 5 minutes). Writes to its own files
(live_fixtures.json, live_event.json) rather than touching
fixtures.json, and only re-fetches league_<id>.json + each manager's
picks (files fetch_data.py already owns) - never bootstrap.json, which
doesn't change during a gameweek.

No-ops (zero API calls) once every fixture in the gameweek is fully
finished, since nothing about the live view can change again until the
next gameweek's deadline passes.
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

from live_score import trim_live_elements, trim_fixtures, all_settled
from notify_telegram import check_goal_events

BASE = "https://fantasy.premierleague.com/api"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


def main():
    meta = load("meta.json")
    gw = meta.get("gw_current") if meta else None
    if not gw:
        print("no current gameweek yet - nothing live to fetch")
        return

    prior = load("live_fixtures.json")
    if prior and prior.get("gameweek") == gw and all_settled(prior.get("fixtures", [])):
        print(f"gameweek {gw} is fully settled already - skipping")
        return

    fixtures = get_json(f"{BASE}/fixtures/?event={gw}")
    generated_at = datetime.now(timezone.utc).isoformat()
    save("live_fixtures.json", {
        "generated_at": generated_at,
        "gameweek": gw,
        "fixtures": trim_fixtures(fixtures),
    })

    if not fixtures:
        print(f"no fixtures found for gameweek {gw} yet")
        return

    live = get_json(f"{BASE}/event/{gw}/live/")
    live_elements = trim_live_elements(live)
    save("live_event.json", {
        "generated_at": generated_at,
        "gameweek": gw,
        "elements": live_elements,
    })

    bootstrap = load("bootstrap.json")
    my_squad = load("my_squad.json")
    my_entry_id = my_squad.get("entry_id") if my_squad else None
    # This gameweek's own picks file (frozen once the deadline passes) -
    # not my_squad.json's picks, which only reflect whatever squad was
    # true whenever that file was last hand-edited.
    my_picks_gw = load(f"entry_{my_entry_id}_picks_gw{gw}.json") if my_entry_id else None
    my_player_ids = {pk["element"] for pk in my_picks_gw["picks"]} if my_picks_gw else None
    if bootstrap and my_player_ids:
        elements_by_id = {e["id"]: e for e in bootstrap["elements"]}
        notify_state = check_goal_events(
            {"gameweek": gw, "elements": live_elements}, my_player_ids, elements_by_id,
            load("notify_state.json") or {},
        )
        save("notify_state.json", notify_state)

    config = load("config.json") or {}
    league_id = config.get("league_id")
    if league_id:
        try:
            league = get_json(f"{BASE}/leagues-classic/{league_id}/standings/")
            save(f"league_{league_id}.json", league)
        except Exception as e:
            print(f"could not refresh live league standings: {e}")

    for m in config.get("managers", []):
        try:
            picks = get_json(f"{BASE}/entry/{m['id']}/event/{gw}/picks/")
            save(f"entry_{m['id']}_picks_gw{gw}.json", picks)
        except Exception as e:
            print(f"could not refresh live picks for entry {m['id']}: {e}")
        time.sleep(0.15)


if __name__ == "__main__":
    main()
