"""Mini-league insights: ownership/EO *within your league* (not global
FPL), template vs differential players, captain distribution, and
squad-overlap between managers.

Needs real picks for every manager, which FPL only makes public after
the gameweek deadline (same constraint as everything squad-related in
this project - see PLAN.md). Returns None until then instead of
guessing from partial data. When only some managers' picks are public
(e.g. right after a deadline, before every fetch has succeeded), still
computes with whichever set is available and reports the actual count
used - never silently assumes the full league.
"""

TEMPLATE_THRESHOLD_PCT = 50.0
DIFFERENTIAL_THRESHOLD_PCT = 20.0


def build_league_insights(managers_picks, players_by_id):
    if not managers_picks:
        return None

    n = len(managers_picks)
    ownership_count = {}
    captain_count = {}
    for m in managers_picks:
        for pk in m["picks"]:
            ownership_count[pk["id"]] = ownership_count.get(pk["id"], 0) + 1
            if pk["is_captain"]:
                captain_count[pk["id"]] = captain_count.get(pk["id"], 0) + 1

    league_players = []
    for pid, count in ownership_count.items():
        p = players_by_id.get(pid)
        if not p:
            continue
        league_own_pct = round(count / n * 100, 1)
        cap_count = captain_count.get(pid, 0)
        eo_pct = round((count + cap_count) / n * 100, 1)
        global_own = p.get("owned")
        league_players.append({
            "id": pid,
            "name": p["name"],
            "league_ownership_pct": league_own_pct,
            "captain_count": cap_count,
            "eo_pct": eo_pct,
            "global_ownership_pct": global_own,
            "is_template": league_own_pct >= TEMPLATE_THRESHOLD_PCT,
            "is_league_differential": league_own_pct < DIFFERENTIAL_THRESHOLD_PCT,
        })
    league_players.sort(key=lambda x: -x["eo_pct"])

    captains_by_manager = [
        {
            "manager": m["manager"]["name"],
            "team_name": m["manager"]["team_name"],
            "captain_id": next((pk["id"] for pk in m["picks"] if pk["is_captain"]), None),
            "captain_name": next(
                (players_by_id.get(pk["id"], {}).get("name") for pk in m["picks"] if pk["is_captain"]),
                None,
            ),
        }
        for m in managers_picks
    ]

    overlaps = []
    for i in range(n):
        for j in range(i + 1, n):
            set_i = {pk["id"] for pk in managers_picks[i]["picks"]}
            set_j = {pk["id"] for pk in managers_picks[j]["picks"]}
            inter = len(set_i & set_j)
            union = len(set_i | set_j)
            overlaps.append({
                "a": managers_picks[i]["manager"]["name"],
                "b": managers_picks[j]["manager"]["name"],
                "shared_players": inter,
                "overlap_pct": round(inter / union * 100, 1) if union else 0.0,
            })
    overlaps.sort(key=lambda x: -x["overlap_pct"])

    return {
        "league_size": n,
        "players": league_players,
        "captains_by_manager": captains_by_manager,
        "squad_overlaps": overlaps,
    }
