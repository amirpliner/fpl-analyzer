"""Python port of js/models/xpts.js - the shared expected-points model.

Kept as the single Python source of truth: both analysis.py (captain
recommendations) and backtest_xpts.py (accuracy checks) import from here
instead of each having their own copy. The JS version is separate (runs
in the browser, no build step) - keep the two formulas in sync when
tuning constants.
"""
import math

GOAL_PTS = {"GKP": 6, "DEF": 6, "MID": 5, "FWD": 4}
CS_PTS = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}
ASSIST_PTS = 3
CAMEO_MINUTES_ASSUMPTION = 20
AVAILABILITY_FALLBACK = {"a": 1.0, "d": 0.75, "i": 0.05, "s": 0.0, "u": 0.0, "n": 0.0}


def clamp01(x):
    return max(0.0, min(1.0, x))


def prob_play(player):
    if player.get("chance_next") is not None:
        return clamp01(player["chance_next"] / 100)
    return AVAILABILITY_FALLBACK.get(player.get("status"), 1.0)


def has_granular_strength(teams):
    return any((t.get("strength_attack_home") or 0) > 0 for t in teams)


def league_averages(teams):
    with_data = [t for t in teams if (t.get("strength_attack_home") or 0) > 0]
    if not with_data:
        return None
    avg = lambda key: sum(t[key] for t in with_data) / len(with_data)
    return {
        "avg_attack_home": avg("strength_attack_home"),
        "avg_attack_away": avg("strength_attack_away"),
        "avg_defence_home": avg("strength_defence_home"),
        "avg_defence_away": avg("strength_defence_away"),
    }


def opponent_factors(is_home, difficulty, opp_team, league_avg):
    venue_attack = 1.10 if is_home else 0.92
    venue_defence = 0.92 if is_home else 1.10

    if opp_team and league_avg:
        opp_defence = opp_team["strength_defence_away"] if is_home else opp_team["strength_defence_home"]
        opp_attack = opp_team["strength_attack_away"] if is_home else opp_team["strength_attack_home"]
        avg_defence = league_avg["avg_defence_away"] if is_home else league_avg["avg_defence_home"]
        avg_attack = league_avg["avg_attack_away"] if is_home else league_avg["avg_attack_home"]
        return (
            (avg_defence / (opp_defence or avg_defence)) * venue_attack,
            (opp_attack / (avg_attack or opp_attack)) * venue_defence,
        )

    fdr = difficulty or 3
    return (
        max(0.4, 1 + (3 - fdr) * 0.12),
        max(0.4, 1 + (fdr - 3) * 0.12),
    )


def expected_points(player, is_home, difficulty, opp_team, league_avg, ict_percentile):
    """player needs: pos, status, chance_next, starts_per_90, xg90, xa90,
    xgc90. Returns a dict with 'total' and a full 'breakdown', same shape
    as the JS version's return value (snake_case here vs camelCase there)."""
    pos = player["pos"]
    p_play = prob_play(player)
    p60 = clamp01(player.get("starts_per_90") or 0)
    p_cameo = max(0.0, min(1 - p60, 0.15))
    appearance = 2 * p60 + 1 * p_cameo
    exp_minute_fraction = (p60 * 90 + p_cameo * CAMEO_MINUTES_ASSUMPTION) / 90

    attack_factor, defence_factor_against_us = opponent_factors(is_home, difficulty, opp_team, league_avg)

    goals_pts = (player.get("xg90") or 0) * GOAL_PTS.get(pos, 0) * attack_factor * exp_minute_fraction
    assists_pts = (player.get("xa90") or 0) * ASSIST_PTS * attack_factor * exp_minute_fraction

    concede_lambda = (player.get("xgc90") or 1.3) * defence_factor_against_us * exp_minute_fraction
    cs_eligible = pos in ("GKP", "DEF", "MID")
    cs_pts = math.exp(-concede_lambda) * CS_PTS.get(pos, 0) if cs_eligible else 0
    concede_penalty = concede_lambda / 2 if pos in ("GKP", "DEF") else 0

    bonus_est = (ict_percentile or 0) * 1.2 * exp_minute_fraction

    bracket = appearance + goals_pts + assists_pts + cs_pts + bonus_est - concede_penalty
    total = p_play * bracket

    return {
        "total": round(total, 2),
        "breakdown": {
            "p_play": round(p_play, 2),
            "p60": round(p60, 2),
            "p_cameo": round(p_cameo, 2),
            "appearance": round(appearance, 2),
            "goals_pts": round(goals_pts, 2),
            "assists_pts": round(assists_pts, 2),
            "cs_pts": round(cs_pts, 2),
            "bonus_est": round(bonus_est, 2),
            "concede_penalty": round(concede_penalty, 2),
            "attack_factor": round(attack_factor, 2),
            "defence_factor_against_us": round(defence_factor_against_us, 2),
            "used_fdr_fallback": opp_team is None or league_avg is None,
        },
    }


def ict_percentiles_by_position(players):
    """Map(player_id -> 0..1 percentile of ICT-per-90 within their position)."""
    by_pos = {}
    for p in players:
        if not p.get("minutes"):
            continue
        ict90 = p["ict"] / (p["minutes"] / 90)
        by_pos.setdefault(p["pos"], []).append((p["id"], ict90))
    result = {}
    for group in by_pos.values():
        group.sort(key=lambda x: x[1])
        n = len(group)
        for i, (pid, _) in enumerate(group):
            result[pid] = i / (n - 1) if n > 1 else 0.5
    return result
