"""Computes the "ניתוח הקבוצה שלי" analysis for one FPL squad.

Every recommendation carries a `reason` built from real fields - nothing
is invented. When a field FPL doesn't give us yet (e.g. in-season match
history before a ball has been kicked) is missing, we return null and let
the frontend show "אין נתון" instead of guessing.
"""

from build_static import POSITION_NAMES
from xpts import expected_points, league_averages, ict_percentiles_by_position

FDR_EASY = 2
FDR_HARD = 4
DIFFERENTIAL_OWNERSHIP = 10.0
DEAD_MINUTES_THRESHOLD = 45
MAX_PER_TEAM = 2


def player_price(p):
    return round(p["now_cost"] / 10, 1)


def team_fixture_run(team_id, fixtures, teams_by_id, from_event, count=5):
    upcoming = [
        f for f in fixtures
        if not f["finished"] and f["event"] is not None and f["event"] >= (from_event or 1)
        and (f["team_h"] == team_id or f["team_a"] == team_id)
    ]
    upcoming.sort(key=lambda f: f["event"])
    run = []
    for f in upcoming[:count]:
        is_home = f["team_h"] == team_id
        opp_id = f["team_a"] if is_home else f["team_h"]
        difficulty = f["team_h_difficulty"] if is_home else f["team_a_difficulty"]
        run.append({
            "event": f["event"],
            "opponent": teams_by_id.get(opp_id, {}).get("short_name", "?"),
            "opponent_id": opp_id,
            "is_home": is_home,
            "difficulty": difficulty,
        })
    return run


def has_easy_run(fixture_run):
    streak = 0
    for f in fixture_run:
        if f["difficulty"] <= FDR_EASY:
            streak += 1
            if streak >= 2:
                return True
        else:
            streak = 0
    return False


def minutes_trend(history):
    """history = this-season match-by-match list from element-summary,
    oldest first. Returns 'up' / 'down' / 'flat' / None (not enough data)."""
    if not history or len(history) < 2:
        return None
    recent = [h["minutes"] for h in history[-4:]]
    if len(recent) < 2:
        return None
    first_half = sum(recent[:len(recent) // 2]) / (len(recent) // 2)
    second_half = sum(recent[len(recent) // 2:]) / (len(recent) - len(recent) // 2)
    if second_half - first_half >= 10:
        return "up"
    if first_half - second_half >= 10:
        return "down"
    return "flat"


def avg_minutes_last(history, n=3):
    if not history:
        return None
    recent = history[-n:]
    if not recent:
        return None
    return round(sum(h["minutes"] for h in recent) / len(recent), 1)


def injury_flag(p):
    if p["status"] == "a" and (p["chance_of_playing_next_round"] is None or p["chance_of_playing_next_round"] == 100):
        return None
    return {
        "status": p["status"],
        "chance_of_playing_next_round": p["chance_of_playing_next_round"],
        "news": p["news"] or None,
    }


def analyze_player(pick, p, teams_by_id, fixtures, from_event, history):
    fixture_run = team_fixture_run(p["team"], fixtures, teams_by_id, from_event)
    avg_min_3 = avg_minutes_last(history, 3)
    return {
        "id": p["id"],
        "web_name": p["web_name"],
        "team": teams_by_id.get(p["team"], {}).get("short_name", "?"),
        "position": p["element_type"],
        "price": player_price(p),
        "is_captain": pick["is_captain"],
        "is_vice": pick["is_vice"],
        "on_bench": pick["on_bench"],
        "form": float(p["form"]) if p["form"] not in (None, "") else None,
        "total_points": p["total_points"],
        "ppm": round(p["total_points"] / player_price(p), 2) if player_price(p) else None,
        "ownership": float(p["selected_by_percent"]),
        "is_differential": float(p["selected_by_percent"]) < DIFFERENTIAL_OWNERSHIP,
        "xgi_per_90": p.get("expected_goal_involvements_per_90"),
        "xgc_per_90": p.get("expected_goals_conceded_per_90"),
        "fixture_run": fixture_run,
        "has_easy_run": has_easy_run(fixture_run),
        "avg_fdr_next5": round(sum(f["difficulty"] for f in fixture_run) / len(fixture_run), 2) if fixture_run else None,
        "minutes_trend": minutes_trend(history),
        "avg_minutes_last3": avg_min_3,
        "injury": injury_flag(p),
        "is_dead": (avg_min_3 is not None and avg_min_3 < DEAD_MINUTES_THRESHOLD) or p["status"] not in ("a", "d"),
    }


def team_exposure_warnings(players, teams_by_id):
    counts = {}
    for pl in players:
        counts[pl["team"]] = counts.get(pl["team"], 0) + 1
    warnings = []
    for team, count in counts.items():
        if count > MAX_PER_TEAM:
            hard_run = [pl for pl in players if pl["team"] == team and pl["avg_fdr_next5"] and pl["avg_fdr_next5"] >= FDR_HARD - 0.5]
            warnings.append({
                "type": "team_exposure",
                "team": team,
                "count": count,
                "reason": f"{count} שחקנים מ-{team} בסגל" + (
                    f" - וגם עם ריצת משחקים קשה ({round(hard_run[0]['avg_fdr_next5'],1)} FDR ממוצע)" if hard_run else ""
                ),
            })
    return warnings


def captain_recommendations(players, elements_by_id, teams_by_id, players_pool):
    """Top-5 captain picks ranked by the shared xPts model (scripts/xpts.py)
    against each player's next fixture. Every pick carries the full
    breakdown plus a confidence score (lower when we're on the FDR
    fallback instead of real team-strength data - see PLAN.md)."""
    starters = [pl for pl in players if not pl["on_bench"] and pl["fixture_run"]]
    league_avg = league_averages(list(teams_by_id.values()))
    ict_pct = ict_percentiles_by_position(players_pool)

    scored = []
    for pl in starters:
        raw = elements_by_id.get(pl["id"])
        if not raw:
            continue
        next_fx = pl["fixture_run"][0]
        opp_team = teams_by_id.get(next_fx["opponent_id"])
        xpts_input = {
            "pos": POSITION_NAMES.get(raw["element_type"], "?"),
            "status": raw["status"],
            "chance_next": raw["chance_of_playing_next_round"],
            "starts_per_90": raw["starts_per_90"],
            "xg90": raw.get("expected_goals_per_90"),
            "xa90": raw.get("expected_assists_per_90"),
            "xgc90": raw.get("expected_goals_conceded_per_90"),
        }
        result = expected_points(
            xpts_input, next_fx["is_home"], next_fx["difficulty"],
            opp_team, league_avg, ict_pct.get(pl["id"]),
        )
        scored.append((pl, result))

    scored.sort(key=lambda t: t[1]["total"], reverse=True)

    out = []
    for pl, result in scored[:5]:
        b = result["breakdown"]
        confidence = round(b["p_play"] * (0.85 if b["used_fdr_fallback"] else 1.0) * 100)
        reason_bits = [f"xPts משוער: {result['total']}"]
        attacking = round(b["goals_pts"] + b["assists_pts"], 2)
        if attacking:
            reason_bits.append(f"תרומה התקפית צפויה {attacking}")
        if b["cs_pts"]:
            reason_bits.append(f"סיכוי שער נקי {b['cs_pts']}")
        if b["used_fdr_fallback"]:
            reason_bits.append("מבוסס FDR - נתוני חוזק קבוצה עדיין לא זמינים העונה")
        out.append({
            "id": pl["id"],
            "web_name": pl["web_name"],
            "xpts": result["total"],
            "confidence": confidence,
            "breakdown": b,
            "reason": ", ".join(reason_bits),
        })
    return out


def transfer_suggestions(players, all_elements, bank, teams_by_id, fixtures, from_event):
    problems = [
        pl for pl in players
        if pl["is_dead"] or pl["injury"] is not None or
        (pl["avg_fdr_next5"] is not None and pl["avg_fdr_next5"] >= FDR_HARD) or
        (pl["form"] is not None and pl["form"] < 2)
    ]
    squad_ids = {pl["id"] for pl in players}
    suggestions = []
    for pl in problems[:3]:
        budget = pl["price"] + bank
        candidates = [
            e for e in all_elements
            if e["element_type"] == pl["position"]
            and e["id"] not in squad_ids
            and e["status"] == "a"
            and player_price(e) <= budget
        ]

        def cscore(e):
            form = float(e["form"]) if e["form"] not in (None, "") else 0
            run = team_fixture_run(e["team"], fixtures, teams_by_id, from_event, count=3)
            avg_fdr = sum(f["difficulty"] for f in run) / len(run) if run else 3
            return form * 2 - avg_fdr + (e["total_points"] / 50)

        candidates.sort(key=cscore, reverse=True)
        if not candidates:
            continue
        best = candidates[0]
        reasons = []
        if pl["injury"] is not None:
            reasons.append(f"בעיית זמינות ({pl['injury']['status']})")
        if pl["avg_fdr_next5"] is not None and pl["avg_fdr_next5"] >= FDR_HARD:
            reasons.append(f"ריצת משחקים קשה (FDR {pl['avg_fdr_next5']})")
        if pl["form"] is not None and pl["form"] < 2:
            reasons.append(f"פורם נמוך ({pl['form']})")
        if pl["is_dead"]:
            reasons.append("דקות משחק נמוכות")
        suggestions.append({
            "out": {"id": pl["id"], "web_name": pl["web_name"], "price": pl["price"]},
            "in": {"id": best["id"], "web_name": best["web_name"], "price": player_price(best)},
            "cost_delta": round(player_price(best) - pl["price"], 1),
            "reason": " · ".join(reasons) if reasons else "יש חלופה טובה יותר לפי הנתונים",
        })
    return suggestions


def squad_rating(players, warnings):
    ppms = [pl["ppm"] for pl in players if pl["ppm"] is not None]
    avg_ppm = sum(ppms) / len(ppms) if ppms else 0
    dead_count = sum(1 for pl in players if pl["is_dead"])
    injury_count = sum(1 for pl in players if pl["injury"] is not None)

    score = 5.5
    score += min(avg_ppm / 5, 2.5)
    score -= dead_count * 0.7
    score -= injury_count * 0.4
    score -= len(warnings) * 0.3
    score = max(1, min(10, round(score, 1)))

    bits = [f"PPM ממוצע {round(avg_ppm, 2)}"]
    if dead_count:
        bits.append(f"{dead_count} שחקנים עם בעיית זמינות/דקות")
    if injury_count:
        bits.append(f"{injury_count} סימני שאלה לפציעה")
    if warnings:
        bits.append(f"{len(warnings)} אזהרות חשיפה")

    return {"score": score, "reason": ", ".join(bits)}


def build_analysis(squad, bootstrap, fixtures, element_summaries, from_event, players_pool):
    elements_by_id = {e["id"]: e for e in bootstrap["elements"]}
    teams_by_id = {t["id"]: t for t in bootstrap["teams"]}

    players = []
    for pick in squad["picks"]:
        p = elements_by_id.get(pick["id"])
        if not p:
            continue
        history = element_summaries.get(pick["id"], {}).get("history", [])
        players.append(analyze_player(pick, p, teams_by_id, fixtures, from_event, history))

    warnings = team_exposure_warnings(players, teams_by_id)
    dead_players = []
    for pl in players:
        if not pl["is_dead"]:
            continue
        if pl["avg_minutes_last3"] is not None and pl["avg_minutes_last3"] < DEAD_MINUTES_THRESHOLD:
            reason = f"ממוצע {pl['avg_minutes_last3']} דקות ב-3 המשחקים האחרונים"
        elif pl["injury"] is not None:
            reason = pl["injury"]["news"] or f"סטטוס: {pl['injury']['status']}"
        else:
            reason = "לא זמין"
        dead_players.append({"id": pl["id"], "web_name": pl["web_name"], "reason": reason})

    return {
        "entry_id": squad.get("entry_id"),
        "gameweek": squad.get("gameweek"),
        "bank": squad.get("bank"),
        "free_transfers": squad.get("free_transfers"),
        "players": players,
        "warnings": warnings,
        "dead_players": dead_players,
        "captain_recommendations": captain_recommendations(players, elements_by_id, teams_by_id, players_pool),
        "transfer_suggestions": transfer_suggestions(
            players, bootstrap["elements"], squad.get("bank") or 0, teams_by_id, fixtures, from_event
        ),
        "rating": squad_rating(players, warnings),
    }
