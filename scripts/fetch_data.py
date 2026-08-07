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
from datetime import datetime, timezone

from analysis import build_analysis
from build_static import build_teams, build_players, compute_dgw_bgw, append_price_snapshot, enrich_with_history
from player_history import build_player_history

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


def meta_generated_at():
    return datetime.now(timezone.utc).isoformat()


def current_event(bootstrap):
    for ev in bootstrap["events"]:
        if ev["is_current"]:
            return ev["id"], False
    for ev in bootstrap["events"]:
        if ev["is_next"]:
            return ev["id"], True
    return None, False


def season_state(bootstrap):
    events = bootstrap["events"]
    if any(ev["finished"] for ev in events):
        if all(ev["finished"] for ev in events):
            return "offseason"
        return "in_season"
    return "preseason"


def build_meta(bootstrap, gw, is_upcoming):
    events_by_id = {ev["id"]: ev for ev in bootstrap["events"]}
    next_ev = next((ev for ev in bootstrap["events"] if ev["is_next"]), None)
    return {
        "generated_at": meta_generated_at(),
        "gameweek": gw,
        "is_upcoming": is_upcoming,
        "gw_current": gw if not is_upcoming else None,
        "gw_next": gw if is_upcoming else (next_ev["id"] if next_ev else None),
        "deadline_time": events_by_id.get(gw, {}).get("deadline_time") if gw else None,
        "season_state": season_state(bootstrap),
    }


def fetch_entry_picks(team_id, pick_gw):
    """Fetches and saves one manager's entry info + picks. Returns a
    (manager_summary, element_ids) tuple, or (None, []) if picks aren't
    public yet (e.g. before the gameweek deadline has passed)."""
    try:
        entry = get_json(f"{BASE}/entry/{team_id}/")
        picks = get_json(f"{BASE}/entry/{team_id}/event/{pick_gw}/picks/")
    except Exception as e:
        print(f"no picks available for entry {team_id} gw {pick_gw}: {e}")
        return None, []
    save(f"entry_{team_id}.json", entry)
    save(f"entry_{team_id}_picks_gw{pick_gw}.json", picks)
    manager = {
        "id": team_id,
        "name": f"{entry['player_first_name']} {entry['player_last_name']}",
        "team_name": entry["name"],
    }
    element_ids = [pk["element"] for pk in picks["picks"]]
    return manager, element_ids


def load_json_file(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_my_squad(gw):
    """Tries the real FPL picks endpoint first (only public after the
    gameweek deadline); falls back to the manually-filled my_squad.json."""
    manual = load_json_file("my_squad.json")
    entry_id = manual.get("entry_id") if manual else None

    if entry_id and gw:
        try:
            picks = get_json(f"{BASE}/entry/{entry_id}/event/{gw}/picks/")
            return {
                "entry_id": entry_id,
                "gameweek": gw,
                "bank": picks["entry_history"]["bank"] / 10,
                "free_transfers": picks.get("entry_history", {}).get("event_transfers", None),
                "picks": [
                    {"id": pk["element"], "is_captain": pk["is_captain"],
                     "is_vice": pk["is_vice_captain"], "on_bench": pk["position"] > 11}
                    for pk in picks["picks"]
                ],
            }
        except Exception as e:
            print(f"my_squad: real picks not available yet ({e}), falling back to my_squad.json")

    if manual and len(manual.get("picks", [])) == 15:
        return manual

    print("my_squad: no valid squad found (fill in data/my_squad.json)")
    return None


def fetch_element_summaries(player_ids):
    summaries = {}
    for pid in player_ids:
        try:
            summaries[pid] = get_json(f"{BASE}/element-summary/{pid}/")
        except Exception as e:
            print(f"could not fetch element-summary for {pid}: {e}")
    return summaries


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

    league_squads = []
    if pick_gw:
        for team_id in team_ids:
            manager, element_ids = fetch_entry_picks(team_id, pick_gw)
            if manager:
                config["managers"].append(manager)
                league_squads.append(element_ids)

    save("config.json", config)
    save("meta.json", build_meta(bootstrap, gw, is_upcoming))

    my_squad = resolve_my_squad(pick_gw)

    # --- Stage A1: enriched static files, built before analysis_mine.json
    # since Stage A5's captain recommendations need players.json's xG90/
    # xA90/ICT percentiles. ---
    teams = build_teams(bootstrap)
    save("teams.json", teams)

    dgw_bgw = compute_dgw_bgw(fixtures, teams)
    save("dgw_bgw.json", dgw_bgw)

    prior_price_history = load_json_file("price_history.json")
    price_history = append_price_snapshot(prior_price_history, bootstrap, meta_generated_at())
    save("price_history.json", price_history)

    extra_squads = league_squads + ([my_squad["picks"]] if my_squad else [])
    player_history = build_player_history(bootstrap, extra_squads, gw or 0)
    save("player_history.json", player_history)

    players = enrich_with_history(build_players(bootstrap), player_history)
    save("players.json", players)
    print(f"players.json: {len(players)} players, {os.path.getsize(os.path.join(DATA_DIR, 'players.json')) / 1024:.0f} KB")

    has_mine_analysis = False
    if my_squad:
        player_ids = [pk["id"] for pk in my_squad["picks"]]
        summaries = fetch_element_summaries(player_ids)
        analysis = build_analysis(my_squad, bootstrap, fixtures, summaries, from_event=gw, players_pool=players)
        save("analysis_mine.json", analysis)
        has_mine_analysis = True

    config["has_mine_analysis"] = has_mine_analysis
    save("config.json", config)


if __name__ == "__main__":
    main()
