"""Chip engine (Stage C11): recommends which chip to play, and when,
over the next CHIP_HORIZON gameweeks - built on DGW/BGW detection
(dgw_bgw.json, Stage A1) and the shared xPts engine (scripts/xpts.py).

Bench Boost / Triple Captain / Free Hit are evaluated per future
gameweek for YOUR specific squad. Wildcard is a standalone "squad
decay" signal rather than a single-gameweek recommendation, since a
wildcard is about the whole squad's long-term health, not one week's
fixtures.

Thresholds below (BENCH_BOOST_THRESHOLD etc.) are documented defaults,
not calibrated against real results - there's no ground truth for
"was this chip worth it" to learn from yet.
"""
from transfer_planner import precompute_player_xpts, VALID_FORMATIONS
from xpts import league_averages, ict_percentiles_by_position

CHIP_HORIZON = 8
BENCH_BOOST_THRESHOLD = 12.0
FREE_HIT_BLANK_THRESHOLD = 3
WILDCARD_DECAY_THRESHOLD = 4
WEAK_XPTS_THRESHOLD = 2.0


def best_xi_and_bench(squad_ids, players_by_id, week_xpts, week_idx, horizon):
    by_pos = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for pid in squad_ids:
        p = players_by_id.get(pid)
        if not p:
            continue
        score = week_xpts.get(pid, [0] * horizon)[week_idx]
        by_pos[p["pos"]].append((score, pid))
    for pos in by_pos:
        by_pos[pos].sort(reverse=True)

    if not by_pos["GKP"]:
        return [], list(squad_ids)
    gk_id = by_pos["GKP"][0][1]

    best_total, best_combo = -1, []
    for d, m, f in VALID_FORMATIONS:
        if len(by_pos["DEF"]) < d or len(by_pos["MID"]) < m or len(by_pos["FWD"]) < f:
            continue
        chosen = by_pos["DEF"][:d] + by_pos["MID"][:m] + by_pos["FWD"][:f]
        total = sum(s for s, _ in chosen)
        if total > best_total:
            best_total, best_combo = total, chosen

    xi_ids = [gk_id] + [pid for _, pid in best_combo]
    bench_ids = [pid for pid in squad_ids if pid not in xi_ids]
    return xi_ids, bench_ids


def squad_team_ids(pids, players_by_id):
    return {players_by_id[pid]["team"] for pid in pids if pid in players_by_id}


def recommend_bench_boost(squad_ids, players_by_id, week_xpts, dgw_bgw, from_event, horizon):
    out = []
    for offset in range(horizon):
        event = from_event + offset
        _, bench_ids = best_xi_and_bench(squad_ids, players_by_id, week_xpts, offset, horizon)
        bench_score = sum(week_xpts.get(pid, [0] * horizon)[offset] for pid in bench_ids)
        dgw_teams = set(dgw_bgw.get("dgw_teams_by_event", {}).get(str(event), []))
        is_dgw = bool(squad_team_ids(bench_ids, players_by_id) & dgw_teams)
        if bench_score >= BENCH_BOOST_THRESHOLD:
            out.append({
                "event": event,
                "score": round(bench_score, 2),
                "is_dgw": is_dgw,
                "reason": f"הספסל צפוי לתרום {round(bench_score, 2)} נק' (סף: {BENCH_BOOST_THRESHOLD})"
                          + (" - וגם יש לך שחקן ספסל במחזור כפול" if is_dgw else ""),
            })
    out.sort(key=lambda r: (-r["is_dgw"], -r["score"]))
    return out[:3]


def recommend_triple_captain(squad_ids, players_by_id, week_xpts, dgw_bgw, from_event, horizon):
    out = []
    for offset in range(horizon):
        event = from_event + offset
        xi_ids, _ = best_xi_and_bench(squad_ids, players_by_id, week_xpts, offset, horizon)
        if not xi_ids:
            continue
        best_id = max(xi_ids, key=lambda pid: week_xpts.get(pid, [0] * horizon)[offset])
        best_score = week_xpts.get(best_id, [0] * horizon)[offset]
        dgw_teams = set(dgw_bgw.get("dgw_teams_by_event", {}).get(str(event), []))
        is_dgw = players_by_id[best_id]["team"] in dgw_teams
        out.append({
            "event": event,
            "player": players_by_id[best_id]["name"],
            "score": round(best_score, 2),
            "is_dgw": is_dgw,
            "reason": f"{players_by_id[best_id]['name']} צפוי {round(best_score, 2)} xPts"
                      + (" במחזור כפול" if is_dgw else ""),
        })
    out.sort(key=lambda r: -r["score"])
    return out[:3]


def recommend_free_hit(squad_ids, players_by_id, fixtures, from_event, horizon):
    has_fixture = set()  # (team_id, event)
    for f in fixtures:
        if f["finished"] or f["event"] is None:
            continue
        has_fixture.add((f["team_h"], f["event"]))
        has_fixture.add((f["team_a"], f["event"]))

    out = []
    for offset in range(horizon):
        event = from_event + offset
        blanks = sum(
            1 for pid in squad_ids
            if pid in players_by_id and (players_by_id[pid]["team"], event) not in has_fixture
        )
        if blanks >= FREE_HIT_BLANK_THRESHOLD:
            out.append({
                "event": event,
                "blank_players": blanks,
                "reason": f"{blanks} משחקנים בסגל שלך ללא משחק במחזור {event}",
            })
    out.sort(key=lambda r: -r["blank_players"])
    return out[:2]


def recommend_wildcard(squad_ids, players_by_id, week_xpts, horizon):
    weak_form_count = 0
    injury_count = 0
    for pid in squad_ids:
        p = players_by_id.get(pid)
        if not p:
            continue
        if p.get("status") not in ("a", "d"):
            injury_count += 1
        avg_xpts = sum(week_xpts.get(pid, [0] * horizon)) / horizon if horizon else 0
        if avg_xpts < WEAK_XPTS_THRESHOLD:
            weak_form_count += 1

    decay_score = round(weak_form_count + injury_count * 1.5, 1)
    recommend = decay_score >= WILDCARD_DECAY_THRESHOLD
    return {
        "decay_score": decay_score,
        "weak_players": weak_form_count,
        "injury_players": injury_count,
        "recommend": recommend,
        "reason": (
            f"{weak_form_count} שחקנים עם xPts ממוצע חלש, {injury_count} עם בעיית זמינות. "
            + ("כדאי לשקול Wildcard בקרוב." if recommend
               else "הסגל עדיין בריא יחסית - אין צורך דחוף ב-Wildcard.")
        ),
    }


def build_chip_plan(my_squad, players, teams_by_id, fixtures, dgw_bgw, from_event, chips_used):
    if not my_squad or not from_event:
        return None

    players_by_id = {p["id"]: p for p in players}
    league_avg = league_averages(list(teams_by_id.values()))
    ict_pct = ict_percentiles_by_position(players)
    squad_ids = [pk["id"] for pk in my_squad["picks"]]

    week_xpts = precompute_player_xpts(
        players, teams_by_id, fixtures, from_event, league_avg, ict_pct, horizon=CHIP_HORIZON
    )

    used_names = {c["name"] for c in chips_used}

    return {
        "horizon": CHIP_HORIZON,
        "from_gameweek": from_event,
        "chips_used": chips_used,
        "note": "יש שני Wildcard בעונה (WC1/WC2) עם דדליין נפרד לכל אחד - בדוק בעצמך את התאריך המדויק באתר FPL.",
        "bench_boost": {
            "available": "bboost" not in used_names,
            "recommendations": recommend_bench_boost(squad_ids, players_by_id, week_xpts, dgw_bgw, from_event, CHIP_HORIZON),
        },
        "triple_captain": {
            "available": "3xc" not in used_names,
            "recommendations": recommend_triple_captain(squad_ids, players_by_id, week_xpts, dgw_bgw, from_event, CHIP_HORIZON),
        },
        "free_hit": {
            "available": "freehit" not in used_names,
            "recommendations": recommend_free_hit(squad_ids, players_by_id, fixtures, from_event, CHIP_HORIZON),
        },
        "wildcard": {
            "available": sum(1 for c in chips_used if c["name"] == "wildcard") < 2,
            **recommend_wildcard(squad_ids, players_by_id, week_xpts, CHIP_HORIZON),
        },
    }
