"""Pure transforms from raw FPL API data to the enriched static files the
frontend reads. No network calls and no disk I/O here - inputs in,
JSON-ready dicts out, so these are easy to unit test.
"""

POSITION_NAMES = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
PRICE_SNAPSHOT_RETENTION = 120


def _num(value, default=None):
    """FPL sends many numeric fields as strings (e.g. form: '4.2').
    Casts safely, since not every field is populated in preseason."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_teams(bootstrap):
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "short_name": t["short_name"],
            "strength_attack_home": t["strength_attack_home"],
            "strength_attack_away": t["strength_attack_away"],
            "strength_defence_home": t["strength_defence_home"],
            "strength_defence_away": t["strength_defence_away"],
            "strength_overall_home": t["strength_overall_home"],
            "strength_overall_away": t["strength_overall_away"],
        }
        for t in bootstrap["teams"]
    ]


def build_players(bootstrap):
    players = []
    for p in bootstrap["elements"]:
        players.append({
            "id": p["id"],
            "name": p["web_name"],
            "team": p["team"],
            "pos": POSITION_NAMES.get(p["element_type"], "?"),
            "price": round(p["now_cost"] / 10, 1),
            "form": _num(p["form"], 0.0),
            "points": p["total_points"],
            "ppg": _num(p["points_per_game"], 0.0),
            "owned": _num(p["selected_by_percent"], 0.0),
            "xg": _num(p["expected_goals"]),
            "xa": _num(p["expected_assists"]),
            "xgi90": p.get("expected_goal_involvements_per_90"),
            "xgc90": p.get("expected_goals_conceded_per_90"),
            "ict": _num(p["ict_index"]),
            "minutes": p["minutes"],
            "starts": p["starts"],
            "starts_per_90": p["starts_per_90"],
            # Per-gameweek current-season history doesn't exist until real
            # matches are played - filled in from player_history.json once
            # it does, never invented here.
            "last5_minutes": [],
            "rotation_risk": "unknown",
            "set_pieces": {
                "pens": p["penalties_order"],
                "fk": p["direct_freekicks_order"],
                "corners": p["corners_and_indirect_freekicks_order"],
            },
            "status": p["status"],
            "chance_next": p["chance_of_playing_next_round"],
            "news": p["news"] or None,
            "transfers_in_event": p["transfers_in_event"],
            "transfers_out_event": p["transfers_out_event"],
            "cost_change_event": p["cost_change_event"],
            # Needs 2+ price_history.json snapshots to compute a trend.
            "price_momentum": None,
        })
    return players


def compute_dgw_bgw(fixtures, teams):
    team_ids = [t["id"] for t in teams]
    events = sorted({f["event"] for f in fixtures if f["event"] is not None})
    counts = {ev: {tid: 0 for tid in team_ids} for ev in events}
    unscheduled = [f for f in fixtures if f["event"] is None]

    for f in fixtures:
        if f["event"] is None:
            continue
        counts[f["event"]][f["team_h"]] += 1
        counts[f["event"]][f["team_a"]] += 1

    dgw_teams_by_event = {
        ev: [tid for tid, c in per_team.items() if c >= 2]
        for ev, per_team in counts.items()
    }
    bgw_teams_by_event = {
        ev: [tid for tid, c in per_team.items() if c == 0]
        for ev, per_team in counts.items()
    }
    dgw_teams_by_event = {ev: t for ev, t in dgw_teams_by_event.items() if t}
    bgw_teams_by_event = {ev: t for ev, t in bgw_teams_by_event.items() if t}

    return {
        "team_fixture_counts": counts,
        "dgw_teams_by_event": dgw_teams_by_event,
        "bgw_teams_by_event": bgw_teams_by_event,
        "dgw_events": sorted(dgw_teams_by_event.keys()),
        "bgw_events": sorted(bgw_teams_by_event.keys()),
        "unscheduled_fixture_count": len(unscheduled),
    }


def append_price_snapshot(prior_history, bootstrap, generated_at, keep=PRICE_SNAPSHOT_RETENTION):
    snapshot = {
        "ts": generated_at,
        "players": {
            str(p["id"]): {
                "now_cost": p["now_cost"],
                "transfers_in_event": p["transfers_in_event"],
                "transfers_out_event": p["transfers_out_event"],
                "cost_change_event": p["cost_change_event"],
            }
            for p in bootstrap["elements"]
        },
    }
    history = (prior_history or []) + [snapshot]
    return history[-keep:]
