#!/usr/bin/env python3
"""Backtests the xPts model against real finished gameweeks.

This is a Python port of js/models/xpts.js's formula - keep the two in
sync when tuning constants. It exists so the model's accuracy (MAE,
correlation vs actual points) can be measured, per PLAN.md's "כיול"
requirement: without this there's no way to know if the model is any
good.

KNOWN SIMPLIFICATION: this compares actual past points against a
prediction built from each player's CURRENT season-aggregate rates
(xG90, xA90, etc), not their rates as they stood before that gameweek
was played. That's some lookahead bias - acceptable for a first-pass
sanity check, but a true backtest would need a point-in-time stats
store, which is out of scope here. Flag if this becomes misleading.

Usage: python3 scripts/backtest_xpts.py
"""
import json
import math
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

GOAL_PTS = {"GKP": 6, "DEF": 6, "MID": 5, "FWD": 4}
CS_PTS = {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}
ASSIST_PTS = 3
CAMEO_MINUTES_ASSUMPTION = 20
AVAILABILITY_FALLBACK = {"a": 1.0, "d": 0.75, "i": 0.05, "s": 0.0, "u": 0.0, "n": 0.0}


def load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    return round(p_play * bracket, 2)


def ict_percentiles_by_position(players):
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


def main():
    players = load("players.json")
    teams = load("teams.json")
    player_history = load("player_history.json")
    fixtures = load("fixtures.json")

    if not all([players, teams, player_history, fixtures]):
        print("backtest: missing required data files, run fetch_data.py first")
        return

    finished_entries = sum(1 for hist in player_history.values() for h in hist if h.get("points") is not None)
    if finished_entries == 0:
        print("backtest: no finished gameweeks with recorded points yet - "
              "nothing to backtest against. This is expected pre-season; "
              "re-run once gameweek 1 finishes.")
        return

    players_by_id = {p["id"]: p for p in players}
    teams_by_id = {t["id"]: t for t in teams}
    league_avg = league_averages(teams)
    ict_pct = ict_percentiles_by_position(players)

    errors = []
    actuals, predictions = [], []

    for pid_str, history in player_history.items():
        pid = int(pid_str)
        player = players_by_id.get(pid)
        if not player:
            continue
        for h in history:
            if h.get("points") is None or h.get("gw") is None:
                continue
            is_home = h.get("was_home")
            fx = next((f for f in fixtures if f["event"] == h["gw"] and
                       (f["team_h"] == player["team"] or f["team_a"] == player["team"])), None)
            if not fx:
                continue
            difficulty = fx["team_h_difficulty"] if fx["team_h"] == player["team"] else fx["team_a_difficulty"]
            opp_id = fx["team_a"] if fx["team_h"] == player["team"] else fx["team_h"]
            opp_team = teams_by_id.get(opp_id)

            predicted = expected_points(player, is_home, difficulty, opp_team, league_avg, ict_pct.get(pid))
            actual = h["points"]
            errors.append(abs(predicted - actual))
            actuals.append(actual)
            predictions.append(predicted)

    if not errors:
        print("backtest: found finished gameweeks but couldn't match any to fixtures - check data consistency")
        return

    mae = sum(errors) / len(errors)
    n = len(actuals)
    mean_a = sum(actuals) / n
    mean_p = sum(predictions) / n
    cov = sum((a - mean_a) * (p - mean_p) for a, p in zip(actuals, predictions))
    std_a = math.sqrt(sum((a - mean_a) ** 2 for a in actuals))
    std_p = math.sqrt(sum((p - mean_p) ** 2 for p in predictions))
    correlation = cov / (std_a * std_p) if std_a and std_p else None

    print(f"backtest: {n} player-gameweek predictions")
    print(f"  MAE: {mae:.2f} points")
    print(f"  correlation: {correlation:.3f}" if correlation is not None else "  correlation: n/a (no variance)")
    print(f"  strength fields granular: {has_granular_strength(teams)}")


if __name__ == "__main__":
    main()
