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


def fetch_entry_picks(team_id, pick_gw):
    """Fetches and saves one manager's entry info + picks. Returns a
    manager summary dict for config.json, or None if picks aren't public
    yet (e.g. before the gameweek deadline has passed)."""
    try:
        entry = get_json(f"{BASE}/entry/{team_id}/")
        picks = get_json(f"{BASE}/entry/{team_id}/event/{pick_gw}/picks/")
    except Exception as e:
        print(f"no picks available for entry {team_id} gw {pick_gw}: {e}")
        return None
    save(f"entry_{team_id}.json", entry)
    save(f"entry_{team_id}_picks_gw{pick_gw}.json", picks)
    return {
        "id": team_id,
        "name": f"{entry['player_first_name']} {entry['player_last_name']}",
        "team_name": entry["name"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id", type=int, action="append", default=[],
                         help="Extra FPL team (entry) ID to fetch, repeatable. "
                              "Not needed for members of --league-id, who are all fetched automatically.")
    parser.add_argument("--league-id", type=int, default=None,
                         help="Classic mini-league ID; every manager in it gets fetched")
    args = parser.parse_args()

    bootstrap = get_json(f"{BASE}/bootstrap-static/")
    save("bootstrap.json", bootstrap)

    fixtures = get_json(f"{BASE}/fixtures/")
    save("fixtures.json", fixtures)

    gw, is_upcoming = current_event(bootstrap)
    print(f"gameweek: {gw} (upcoming={is_upcoming})")
    pick_gw = gw - 1 if is_upcoming and gw and gw > 1 else gw

    config = {"managers": [], "league_id": args.league_id, "picks_gw": pick_gw}

    team_ids = list(args.team_id)

    if args.league_id:
        league = get_json(f"{BASE}/leagues-classic/{args.league_id}/standings/")
        save(f"league_{args.league_id}.json", league)
        league_entries = [row["entry"] for row in league["standings"]["results"]] \
            or [row["entry"] for row in league["new_entries"]["results"]]
        team_ids += [t for t in league_entries if t not in team_ids]

    if pick_gw:
        for team_id in team_ids:
            manager = fetch_entry_picks(team_id, pick_gw)
            if manager:
                config["managers"].append(manager)

    save("config.json", config)
    save("meta.json", {"gameweek": gw, "is_upcoming": is_upcoming})


if __name__ == "__main__":
    main()
