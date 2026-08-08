"""Multi-gameweek transfer planner (Stage C10): beam search over transfer
decisions for the next HORIZON gameweeks, maximizing total expected
points (the Stage A4/A5 xPts engine, scripts/xpts.py) net of transfer
hit penalties (-4/transfer beyond free ones).

DOCUMENTED SIMPLIFICATIONS - real, not hidden:
1. Transfers are same-position swaps only. This keeps the 2/5/5/3 squad
   quota valid automatically with no extra bookkeeping, at the cost of
   not being able to suggest reshaping the squad across positions
   (e.g. going from 3 to 2 defenders to afford a better forward).
2. Selling price = current market price. FPL's real rule only refunds
   half of any price rise since purchase, but my_squad.json doesn't
   track original purchase price, so this can overstate the budget
   available for players that have risen in price.
3. A true joint search over which k players to transfer in one
   gameweek is combinatorially far larger than a beam width of 50 can
   cover (choosing k of 15 to sell x ~500 to buy). Instead, each
   squad's *candidate* transfers are generated greedily (best single
   swap per position slot, then the best pair via chaining two single
   swaps) - the beam search itself operates across the 3-gameweek
   horizon, choosing between these candidate actions week to week.
   This is what keeps the requested "beam search, not brute force"
   approach tractable, at the cost of not exploring every possible
   simultaneous k-transfer combination within a single week.
"""
import json
import os

from xpts import expected_points, league_averages, ict_percentiles_by_position

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

HORIZON = 3
BEAM_WIDTH = 50
HIT_COST = 4
MAX_FREE_TRANSFERS = 5
MAX_PER_TEAM = 3
CANDIDATES_PER_SLOT = 3  # top replacements considered per squad player


def team_fixtures_for_horizon(team_id, fixtures, from_event, horizon):
    """Returns a list of length `horizon`; each entry is the fixture
    context for that gameweek offset, or None on a blank gameweek."""
    by_event = {}
    for f in fixtures:
        if f["finished"] or f["event"] is None:
            continue
        if f["team_h"] == team_id or f["team_a"] == team_id:
            is_home = f["team_h"] == team_id
            opp_id = f["team_a"] if is_home else f["team_h"]
            difficulty = f["team_h_difficulty"] if is_home else f["team_a_difficulty"]
            by_event.setdefault(f["event"], []).append(
                {"opp_id": opp_id, "is_home": is_home, "difficulty": difficulty}
            )
    out = []
    for offset in range(horizon):
        ev = from_event + offset
        out.append(by_event.get(ev, []))
    return out


def precompute_player_xpts(players, teams_by_id, fixtures, from_event, league_avg, ict_pct, horizon=HORIZON):
    """player_id -> list of length `horizon`, each the summed xPts across
    that gameweek's fixtures (0 on a blank, summed on a double)."""
    result = {}
    for p in players:
        team_fx = team_fixtures_for_horizon(p["team"], fixtures, from_event, horizon)
        weekly = []
        for week_fixtures in team_fx:
            total = 0.0
            for fx in week_fixtures:
                opp_team = teams_by_id.get(fx["opp_id"])
                r = expected_points(p, fx["is_home"], fx["difficulty"], opp_team, league_avg, ict_pct.get(p["id"]))
                total += r["total"]
            weekly.append(round(total, 2))
        result[p["id"]] = weekly
    return result


VALID_FORMATIONS = [
    (d, m, f)
    for d in range(3, 6)
    for m in range(2, 6)
    for f in range(1, 4)
    if d + m + f == 10
]


def pick_best_xi(squad_ids, players_by_id, week_xpts, week_idx):
    """Returns (xi_score_with_captain, captain_id) for the best valid
    starting XI (1 GKP + a formation from VALID_FORMATIONS) by this
    week's xPts."""
    by_pos = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for pid in squad_ids:
        p = players_by_id.get(pid)
        if not p:
            continue
        score = week_xpts.get(pid, [0] * HORIZON)[week_idx]
        by_pos[p["pos"]].append((score, pid))
    for pos in by_pos:
        by_pos[pos].sort(reverse=True)

    if not by_pos["GKP"]:
        return 0.0, None
    gk_score, gk_id = by_pos["GKP"][0]

    best_total, best_captain = -1, None
    for d, m, f in VALID_FORMATIONS:
        if len(by_pos["DEF"]) < d or len(by_pos["MID"]) < m or len(by_pos["FWD"]) < f:
            continue
        chosen = by_pos["DEF"][:d] + by_pos["MID"][:m] + by_pos["FWD"][:f] + [(gk_score, gk_id)]
        base_total = sum(s for s, _ in chosen)
        cap_score, cap_id = max(chosen)
        total = base_total + cap_score  # captain doubles
        if total > best_total:
            best_total, best_captain = total, cap_id
    return round(best_total, 2), best_captain


def team_counts(squad_ids, players_by_id):
    counts = {}
    for pid in squad_ids:
        p = players_by_id.get(pid)
        if p:
            counts[p["team"]] = counts.get(p["team"], 0) + 1
    return counts


def best_replacements_for_player(out_id, squad_ids, players_by_id, week_xpts, budget, remaining_weeks):
    out_p = players_by_id.get(out_id)
    if not out_p:
        return []
    counts = team_counts(squad_ids, players_by_id)
    counts[out_p["team"]] = counts.get(out_p["team"], 1) - 1

    candidates = []
    for p in players_by_id.values():
        if p["pos"] != out_p["pos"] or p["id"] in squad_ids or p["status"] != "a":
            continue
        if p["price"] > out_p["price"] + budget:
            continue
        if counts.get(p["team"], 0) + 1 > MAX_PER_TEAM:
            continue
        gain = sum(
            week_xpts.get(p["id"], [0] * HORIZON)[w] - week_xpts.get(out_id, [0] * HORIZON)[w]
            for w in remaining_weeks
        )
        candidates.append((gain, p["id"], p["price"] - out_p["price"]))
    candidates.sort(reverse=True)
    return candidates[:CANDIDATES_PER_SLOT]


def generate_candidate_actions(squad_ids, players_by_id, week_xpts, bank, week_idx):
    remaining_weeks = list(range(week_idx, HORIZON))
    single_moves = []
    for out_id in squad_ids:
        for gain, in_id, cost_delta in best_replacements_for_player(
            out_id, squad_ids, players_by_id, week_xpts, bank, remaining_weeks
        ):
            if gain > 0:
                single_moves.append((gain, out_id, in_id, cost_delta))
    single_moves.sort(reverse=True)
    top_singles = single_moves[:5]

    actions = [[]]  # "hold" - zero transfers
    for gain, out_id, in_id, cost_delta in top_singles:
        actions.append([(out_id, in_id, cost_delta)])

    # Greedy double: chain the best single onto the second-best that
    # doesn't touch the same player and still fits the budget.
    if len(top_singles) >= 2:
        g1, o1, i1, c1 = top_singles[0]
        remaining_bank = bank - c1
        for g2, o2, i2, c2 in top_singles[1:]:
            if o2 != o1 and i2 != i1 and c2 <= remaining_bank:
                actions.append([(o1, i1, c1), (o2, i2, c2)])
                break

    return actions


def apply_action(squad_ids, action):
    new_squad = set(squad_ids)
    for out_id, in_id, _ in action:
        new_squad.discard(out_id)
        new_squad.add(in_id)
    return frozenset(new_squad)


def action_cost(action):
    return sum(c for _, _, c in action)


def action_label(action, players_by_id):
    return [
        {"out": players_by_id[o]["name"], "in": players_by_id[i]["name"], "cost_delta": round(c, 1)}
        for o, i, c in action
    ]


def run_beam_search(squad_ids, bank, free_transfers, players_by_id, week_xpts):
    # (squad, bank, free_transfers, cumulative_score, path)
    beam = [(frozenset(squad_ids), bank, free_transfers, 0.0, [])]

    for week in range(HORIZON):
        next_beam = []
        for squad, cur_bank, ft, cum_score, path in beam:
            actions = generate_candidate_actions(list(squad), players_by_id, week_xpts, cur_bank, week)
            for action in actions:
                cost = action_cost(action)
                if cost > cur_bank:
                    continue
                n_transfers = len(action)
                used = min(n_transfers, ft)
                hits = max(0, n_transfers - ft)
                new_ft = min(MAX_FREE_TRANSFERS, max(0, ft - used) + 1)

                new_squad = apply_action(squad, action)
                xi_score, captain_id = pick_best_xi(list(new_squad), players_by_id, week_xpts, week)
                week_score = xi_score - hits * HIT_COST
                new_bank = cur_bank - cost

                next_beam.append((
                    new_squad, new_bank, new_ft, cum_score + week_score,
                    path + [{"week": week + 1, "transfers": action_label(action, players_by_id),
                              "hits": hits, "xi_score": xi_score, "captain": players_by_id.get(captain_id, {}).get("name")}],
                ))
        next_beam.sort(key=lambda s: -s[3])
        beam = next_beam[:BEAM_WIDTH]

    return beam


def summarize_route(entry, baseline_score, players_by_id):
    squad, bank, ft, cum_score, path = entry
    total_transfers = sum(len(w["transfers"]) for w in path)
    return {
        "weekly_plan": path,
        "total_transfers": total_transfers,
        "total_hits": sum(w["hits"] for w in path),
        "final_bank": round(bank, 1),
        "total_xpts": round(cum_score, 2),
        "net_gain_vs_hold": round(cum_score - baseline_score, 2),
    }


def build_transfer_plan(my_squad, players, teams_by_id, fixtures, from_event):
    if not my_squad or not from_event:
        return None

    players_by_id = {p["id"]: p for p in players}
    league_avg = league_averages(list(teams_by_id.values()))
    ict_pct = ict_percentiles_by_position(players)
    week_xpts = precompute_player_xpts(players, teams_by_id, fixtures, from_event, league_avg, ict_pct)

    squad_ids = [pk["id"] for pk in my_squad["picks"]]
    bank = my_squad.get("bank") or 0
    free_transfers = min(MAX_FREE_TRANSFERS, max(1, my_squad.get("free_transfers") or 1))

    beam = run_beam_search(squad_ids, bank, free_transfers, players_by_id, week_xpts)

    # Baseline: always hold (the "roll transfer" scenario), forced
    # explicitly so it's always available to compare against even if
    # beam search pruned it out in favor of better-scoring routes.
    hold_entry = (frozenset(squad_ids), bank, free_transfers, 0.0, [])
    for week in range(HORIZON):
        squad, cur_bank, ft, cum_score, path = hold_entry
        xi_score, captain_id = pick_best_xi(list(squad), players_by_id, week_xpts, week)
        hold_entry = (squad, cur_bank, min(MAX_FREE_TRANSFERS, ft + 1), cum_score + xi_score,
                      path + [{"week": week + 1, "transfers": [], "hits": 0, "xi_score": xi_score,
                               "captain": players_by_id.get(captain_id, {}).get("name")}])
    baseline_score = hold_entry[3]

    seen_squads = {hold_entry[0]}
    routes = [summarize_route(hold_entry, baseline_score, players_by_id)]

    for entry in beam:
        if entry[0] in seen_squads:
            continue
        seen_squads.add(entry[0])
        routes.append(summarize_route(entry, baseline_score, players_by_id))
        if len(routes) >= 3:
            break

    routes.sort(key=lambda r: -r["total_xpts"])
    return {
        "horizon": HORIZON,
        "beam_width": BEAM_WIDTH,
        "from_gameweek": from_event,
        "baseline_xpts": round(baseline_score, 2),
        "routes": routes,
    }
