#!/usr/bin/env python3
"""Backtests the xPts model (scripts/xpts.py) against real finished
gameweeks, per PLAN.md's "כיול" requirement: without this there's no way
to know if the model is any good.

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

from xpts import expected_points, has_granular_strength, league_averages, ict_percentiles_by_position

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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

            predicted = expected_points(player, is_home, difficulty, opp_team, league_avg, ict_pct.get(pid))["total"]
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
