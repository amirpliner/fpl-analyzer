#!/usr/bin/env python3
"""Pulls fresh data from the official Fantasy Premier League API and
saves it as local JSON files under ../data/, since the FPL API blocks
CORS and can't be called directly from the browser.

Usage:
    python3 fetch_data.py --team-id 123456 --league-id 987654
    python3 fetch_data.py               # bootstrap + fixtures only
"""
import argparse
import json
import os
import urllib.request

BASE = "https://fantasy.premierleague.com/api"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def save(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


def current_event(bootstrap):
    for ev in bootstrap["events"]:
        if ev["is_current"]:
            return ev["id"], False
    for ev in bootstrap["events"]:
        if ev["is_next"]:
            return ev["id"], True
    return None, False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id", type=int, action="append", default=[],
                         help="Your FPL team (entry) ID, repeatable for multiple managers")
    parser.add_argument("--league-id", type=int, default=None,
                         help="Classic mini-league ID")
    args = parser.parse_args()

    bootstrap = get_json(f"{BASE}/bootstrap-static/")
    save("bootstrap.json", bootstrap)

    fixtures = get_json(f"{BASE}/fixtures/")
    save("fixtures.json", fixtures)

    gw, is_upcoming = current_event(bootstrap)
    print(f"gameweek: {gw} (upcoming={is_upcoming})")

    config = {"team_ids": [], "league_id": args.league_id, "picks_gw": None}

    if args.league_id:
        league = get_json(f"{BASE}/leagues-classic/{args.league_id}/standings/")
        save(f"league_{args.league_id}.json", league)

    for team_id in args.team_id:
        entry = get_json(f"{BASE}/entry/{team_id}/")
        save(f"entry_{team_id}.json", entry)
        # picks for a future gameweek don't exist yet; fall back to the
        # last finished one (or the previous season's final squad) if needed
        pick_gw = gw - 1 if is_upcoming and gw and gw > 1 else gw
        if pick_gw:
            try:
                picks = get_json(f"{BASE}/entry/{team_id}/event/{pick_gw}/picks/")
                save(f"entry_{team_id}_picks_gw{pick_gw}.json", picks)
                config["team_ids"].append(team_id)
                config["picks_gw"] = pick_gw
            except Exception as e:
                print(f"no picks available for entry {team_id} gw {pick_gw}: {e}")

    save("config.json", config)
    save("meta.json", {"gameweek": gw, "is_upcoming": is_upcoming})


if __name__ == "__main__":
    main()
