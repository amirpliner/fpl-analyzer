"""Fetches element-summary for a bounded set of players (not all ~700 -
squad players, mini-league squads, and the top/most-owned players) and
builds player_history.json: the last 5 current-season gameweeks per
player. Caches each player's raw response on disk keyed by gameweek, so
repeated runs within the same (often weeks-long, preseason) gameweek
don't re-hit the API at all.
"""
import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://fantasy.premierleague.com/api"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "element_summary")
REQUEST_DELAY = 0.4
MAX_RETRIES = 3
TOP_N_BY_POINTS = 200
MIN_OWNERSHIP_PERCENT = 1.0
HISTORY_LOOKBACK = 5


def select_player_ids(bootstrap, extra_squads):
    """extra_squads: list of {id, ...} pick lists (my squad + league
    managers' squads) to always include regardless of ownership/points."""
    elements = bootstrap["elements"]
    top_by_points = sorted(elements, key=lambda p: -p["total_points"])[:TOP_N_BY_POINTS]
    owned = [p for p in elements if _pct(p["selected_by_percent"]) > MIN_OWNERSHIP_PERCENT]

    ids = {p["id"] for p in top_by_points} | {p["id"] for p in owned}
    for squad in extra_squads:
        ids.update(pk["id"] if isinstance(pk, dict) else pk for pk in squad)
    return ids


def _pct(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _cache_path(player_id, gw):
    return os.path.join(CACHE_DIR, f"{player_id}_{gw}.json")


def _fetch_with_retry(url):
    delay = 1
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"  retry {attempt}/{MAX_RETRIES} for {url}: {e}")
            time.sleep(delay)
            delay *= 2


def fetch_element_summary_cached(player_id, gw):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(player_id, gw)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    data = _fetch_with_retry(f"{BASE}/element-summary/{player_id}/")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    time.sleep(REQUEST_DELAY)
    return data


def build_player_history(bootstrap, extra_squads, gw):
    teams_by_id = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    player_ids = select_player_ids(bootstrap, extra_squads)
    print(f"player_history: fetching {len(player_ids)} players (gw={gw})")

    result = {}
    for i, pid in enumerate(sorted(player_ids), 1):
        try:
            summary = fetch_element_summary_cached(pid, gw)
        except Exception as e:
            print(f"  could not fetch element-summary for {pid}: {e}")
            continue

        recent = summary.get("history", [])[-HISTORY_LOOKBACK:]
        result[str(pid)] = [
            {
                "gw": h["round"],
                "minutes": h["minutes"],
                "xg": _pct(h.get("expected_goals")),
                "xa": _pct(h.get("expected_assists")),
                "ict": _pct(h.get("ict_index")),
                "opp": teams_by_id.get(h.get("opponent_team"), "?"),
                "was_home": h.get("was_home"),
                "points": h.get("total_points"),
                "value": round(h.get("value", 0) / 10, 1) if h.get("value") is not None else None,
            }
            for h in recent
        ]
        if i % 50 == 0:
            print(f"  ...{i}/{len(player_ids)}")

    return result
