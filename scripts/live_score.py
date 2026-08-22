"""Pure helpers for the live-gameweek view. No I/O here -
scripts/fetch_live.py does the fetching; this module only shapes the
raw FPL API responses into the small, frontend-friendly shape that
gets committed to data/live_fixtures.json and data/live_event.json
every few minutes on matchday."""

# Keeps only what the live squad table needs - drops the verbose
# per-fixture `explain` breakdown and rate stats (influence/creativity/
# threat/xG strings) that are already available elsewhere in
# players.json, so this file stays small enough to commit every few
# minutes without bloating the repo.
LIVE_STATS_KEEP = (
    "minutes", "total_points", "bonus", "bps",
    "goals_scored", "assists", "clean_sheets", "goals_conceded",
    "own_goals", "yellow_cards", "red_cards", "saves",
    "penalties_saved", "penalties_missed", "in_dreamteam",
)

FIXTURE_FIELDS_KEEP = (
    "id", "event", "kickoff_time", "started", "finished",
    "finished_provisional", "minutes", "team_h", "team_a",
    "team_h_score", "team_a_score",
)


def trim_live_elements(raw_live):
    """/event/{gw}/live/ is ~600 players x ~25 fields (~400KB+) - keyed
    by element id and trimmed to LIVE_STATS_KEEP, it's 5-8x smaller."""
    out = {}
    for el in raw_live.get("elements", []):
        stats = el.get("stats", {})
        out[str(el["id"])] = {k: stats.get(k) for k in LIVE_STATS_KEEP}
    return out


def trim_fixtures(raw_fixtures):
    return [{k: f.get(k) for k in FIXTURE_FIELDS_KEEP} for f in raw_fixtures]


def all_settled(fixtures):
    """True once every fixture in the gameweek is fully finished (bonus
    confirmed - `finished`, not just full-time's `finished_provisional`).
    Once true, nothing about the live view can change again until the
    next gameweek's deadline, so fetch_live.py can stop polling."""
    return bool(fixtures) and all(f.get("finished") for f in fixtures)


def any_in_progress(fixtures):
    return any(f.get("started") and not f.get("finished_provisional") for f in fixtures)
