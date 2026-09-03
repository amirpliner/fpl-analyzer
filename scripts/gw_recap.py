"""Builds data/gw_recap.json - the retrospective half of the site's
original idea (build_analysis in analysis.py is the forward-looking
half): after a gameweek finishes, how did it actually go, and what
should that change about the squad going forward.

Only ever looks at the most recently FINISHED gameweek (bootstrap
events[].finished, i.e. bonus points confirmed) - never the in-progress
one, since live scores still move.
"""

from analysis import team_fixture_run, has_easy_run

HAUL_THRESHOLD = 8
BUST_THRESHOLD = 1


def last_finished_gw(bootstrap):
    finished = [ev["id"] for ev in bootstrap["events"] if ev["finished"]]
    return max(finished) if finished else None


def _player_gw_points(player_history, pid, gw):
    for h in player_history.get(str(pid), []):
        if h["gw"] == gw:
            return h["points"], h["minutes"]
    return None, None


def build_gw_recap(recap_gw, entry_history, picks_gw_data, player_history,
                    elements_by_id, teams_by_id, fixtures, from_event):
    if not picks_gw_data:
        return None
    current = entry_history.get("current", [])
    row = next((r for r in current if r["event"] == recap_gw), None)
    if not row:
        return None

    idx = current.index(row)
    prev_row = current[idx - 1] if idx > 0 else None
    rank_change = (prev_row["overall_rank"] - row["overall_rank"]) if prev_row else None

    player_rows = []
    for pk in picks_gw_data.get("picks", []):
        p = elements_by_id.get(pk["element"])
        if not p:
            continue
        base_points, minutes = _player_gw_points(player_history, pk["element"], recap_gw)
        player_rows.append({
            "id": p["id"],
            "web_name": p["web_name"],
            "team": teams_by_id.get(p["team"], {}).get("short_name", "?"),
            "on_bench": pk["position"] > 11,
            "is_captain": pk["is_captain"],
            "multiplier": pk["multiplier"],
            "base_points": base_points,
            "points": base_points * pk["multiplier"] if base_points is not None else None,
            "minutes": minutes,
            "chance_next": p.get("chance_of_playing_next_round"),
        })

    starters = [r for r in player_rows if not r["on_bench"] and r["base_points"] is not None]
    captain_row = next((r for r in player_rows if r["is_captain"]), None)
    best_starter = max(starters, key=lambda r: r["base_points"]) if starters else None

    captain_verdict = None
    if captain_row and best_starter and captain_row["base_points"] is not None:
        captain_verdict = "optimal" if captain_row["id"] == best_starter["id"] else "suboptimal"

    hauls = sorted(
        (r for r in player_rows if r["base_points"] is not None and r["base_points"] >= HAUL_THRESHOLD),
        key=lambda r: -r["base_points"],
    )[:4]
    busts = [
        r for r in player_rows
        if not r["on_bench"] and r["base_points"] is not None and r["base_points"] <= BUST_THRESHOLD
    ]

    keep, change = [], []
    for r in player_rows:
        p = elements_by_id.get(r["id"])
        if not p or r["base_points"] is None:
            continue
        run = team_fixture_run(p["team"], fixtures, teams_by_id, from_event)
        easy = has_easy_run(run) if run else None
        low_chance = (r["chance_next"] or 100) < 75

        if r["base_points"] >= HAUL_THRESHOLD and not low_chance:
            reason = f"הביא {r['base_points']} נק' במחזור {recap_gw}"
            if easy:
                reason += " וגם הריצה הקרובה נוחה"
            keep.append({"web_name": r["web_name"], "reason": reason})
        elif (r["base_points"] <= BUST_THRESHOLD or low_chance) and (easy is False or low_chance):
            bits = []
            if r["minutes"] == 0:
                bits.append("לא שיחק")
            elif r["base_points"] <= BUST_THRESHOLD:
                bits.append(f"רק {r['base_points']} נק' במחזור {recap_gw}")
            if low_chance:
                bits.append(f"{r['chance_next']}% סיכוי לשחק במחזור הבא")
            if easy is False:
                bits.append("ריצת משחקים קשה")
            change.append({"web_name": r["web_name"], "reason": " · ".join(bits)})

    return {
        "gw": recap_gw,
        "points": row["points"],
        "points_on_bench": row["points_on_bench"],
        "overall_rank": row["overall_rank"],
        "rank_change": rank_change,
        "event_transfers": row["event_transfers"],
        "event_transfers_cost": row["event_transfers_cost"],
        "active_chip": picks_gw_data.get("active_chip"),
        "captain": captain_row,
        "best_possible_captain": best_starter if (captain_row and best_starter and captain_row["id"] != best_starter["id"]) else None,
        "captain_verdict": captain_verdict,
        "hauls": hauls,
        "busts": busts,
        "keep": keep,
        "change": change,
    }
