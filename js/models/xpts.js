// xPts engine - the shared scoring model everything else (captain picks,
// transfer planner, chip planner) builds on. Pure functions: data in,
// numbers out, no DOM. See PLAN.md for the field-verification notes this
// formula is built on (string-typed API fields, team strength gaps, etc).
//
// xPts(player, fixture) =
//   P(play) x [ appearance + goals + assists + clean_sheet + bonus_est - concede_penalty ]
//
// IMPORTANT: scripts/backtest_xpts.py re-implements this same formula in
// Python (the backtest runs in the data pipeline, not the browser) - keep
// the two in sync when tuning constants.

export const GOAL_PTS = { GKP: 6, DEF: 6, MID: 5, FWD: 4 };
export const CS_PTS = { GKP: 4, DEF: 4, MID: 1, FWD: 0 };
export const ASSIST_PTS = 3;
export const CAMEO_MINUTES_ASSUMPTION = 20; // rough expected minutes for a non-starting appearance
export const AVAILABILITY_FALLBACK = { a: 1.0, d: 0.75, i: 0.05, s: 0.0, u: 0.0, n: 0.0 };

function clamp01(x) {
  return Math.max(0, Math.min(1, x));
}

function round2(x) {
  return Math.round(x * 100) / 100;
}

export function probPlay(player) {
  if (player.chance_next !== null && player.chance_next !== undefined) {
    return clamp01(player.chance_next / 100);
  }
  return AVAILABILITY_FALLBACK[player.status] ?? 1.0;
}

/** Whether teams.json has real strength_attack/defence values yet, or
 * they're still all 0 (unpopulated pre-season - confirmed live in
 * PLAN.md). Falls back to FDR-derived factors when they're not. */
export function hasGranularStrength(teams) {
  return teams.some(t => (t.strength_attack_home || 0) > 0);
}

export function leagueAverages(teams) {
  const withData = teams.filter(t => (t.strength_attack_home || 0) > 0);
  if (!withData.length) return null;
  const avg = key => withData.reduce((s, t) => s + t[key], 0) / withData.length;
  return {
    avgAttackHome: avg("strength_attack_home"),
    avgAttackAway: avg("strength_attack_away"),
    avgDefenceHome: avg("strength_defence_home"),
    avgDefenceAway: avg("strength_defence_away"),
  };
}

/**
 * fixture: { oppTeamId, isHome, difficulty (1-5, from our team's POV) }
 * Returns { attackFactor, defenceFactorAgainstUs, usedFallback } where
 * attackFactor scales our player's expected goals/assists, and
 * defenceFactorAgainstUs scales expected goals conceded by our team.
 */
export function opponentFactors(fixture, teamsById, leagueAvg) {
  const opp = teamsById.get(fixture.oppTeamId);
  const venueAttack = fixture.isHome ? 1.10 : 0.92;
  const venueDefence = fixture.isHome ? 0.92 : 1.10;

  if (opp && leagueAvg) {
    // Opponent's stance depends on where THEY are playing (away if we're home).
    const oppDefence = fixture.isHome ? opp.strength_defence_away : opp.strength_defence_home;
    const oppAttack = fixture.isHome ? opp.strength_attack_away : opp.strength_attack_home;
    const avgDefence = fixture.isHome ? leagueAvg.avgDefenceAway : leagueAvg.avgDefenceHome;
    const avgAttack = fixture.isHome ? leagueAvg.avgAttackAway : leagueAvg.avgAttackHome;
    return {
      attackFactor: (avgDefence / (oppDefence || avgDefence)) * venueAttack,
      defenceFactorAgainstUs: (oppAttack / (avgAttack || oppAttack)) * venueDefence,
      usedFallback: false,
    };
  }

  // Fallback: FDR already conflates attack+defence into one 1-5 rating.
  const fdr = fixture.difficulty ?? 3;
  return {
    attackFactor: Math.max(0.4, 1 + (3 - fdr) * 0.12),
    defenceFactorAgainstUs: Math.max(0.4, 1 + (fdr - 3) * 0.12),
    usedFallback: true,
  };
}

/** ICT-per-90 percentile within the same position, among players with
 * minutes > 0. Returns a Map(id -> 0..1). Used as a modest bonus-points
 * proxy since we can't compute real BPS without match-by-match data. */
export function ictPercentilesByPosition(players) {
  const byPos = new Map();
  for (const p of players) {
    if (!p.minutes) continue;
    const ict90 = p.ict / (p.minutes / 90);
    if (!byPos.has(p.pos)) byPos.set(p.pos, []);
    byPos.get(p.pos).push({ id: p.id, ict90 });
  }
  const percentiles = new Map();
  for (const list of byPos.values()) {
    list.sort((a, b) => a.ict90 - b.ict90);
    list.forEach((entry, i) => percentiles.set(entry.id, list.length > 1 ? i / (list.length - 1) : 0.5));
  }
  return percentiles;
}

/**
 * player: one row from players.json (or the enriched squad-player shape
 * used elsewhere - must have pos/status/chance_next/starts_per_90/
 * xg90/xa90/xgc90/ict/minutes/id).
 * fixture: { oppTeamId, isHome, difficulty }.
 * context: { teamsById, leagueAvg, ictPercentiles }.
 */
export function expectedPoints(player, fixture, context) {
  const pos = player.pos;
  const pPlay = probPlay(player);
  const p60 = clamp01(player.starts_per_90 ?? 0);
  const pCameo = Math.max(0, Math.min(1 - p60, 0.15));
  const appearance = 2 * p60 + 1 * pCameo;
  const expMinuteFraction = (p60 * 90 + pCameo * CAMEO_MINUTES_ASSUMPTION) / 90;

  const { attackFactor, defenceFactorAgainstUs, usedFallback } =
    opponentFactors(fixture, context.teamsById, context.leagueAvg);

  const goalsPts = (player.xg90 ?? 0) * (GOAL_PTS[pos] ?? 0) * attackFactor * expMinuteFraction;
  const assistsPts = (player.xa90 ?? 0) * ASSIST_PTS * attackFactor * expMinuteFraction;

  const concedeLambda = (player.xgc90 ?? 1.3) * defenceFactorAgainstUs * expMinuteFraction;
  const csEligible = pos === "GKP" || pos === "DEF" || pos === "MID";
  const csPts = csEligible ? Math.exp(-concedeLambda) * (CS_PTS[pos] ?? 0) : 0;
  const concedePenalty = (pos === "GKP" || pos === "DEF") ? concedeLambda / 2 : 0;

  const bonusEst = (context.ictPercentiles?.get(player.id) ?? 0) * 1.2 * expMinuteFraction;

  const bracket = appearance + goalsPts + assistsPts + csPts + bonusEst - concedePenalty;
  const total = pPlay * bracket;

  return {
    total: round2(total),
    breakdown: {
      pPlay: round2(pPlay),
      p60: round2(p60),
      pCameo: round2(pCameo),
      appearance: round2(appearance),
      goalsPts: round2(goalsPts),
      assistsPts: round2(assistsPts),
      csPts: round2(csPts),
      bonusEst: round2(bonusEst),
      concedePenalty: round2(concedePenalty),
      attackFactor: round2(attackFactor),
      defenceFactorAgainstUs: round2(defenceFactorAgainstUs),
      usedFdrFallback: usedFallback,
    },
  };
}

/** Sums expectedPoints across N upcoming fixtures for one team (naturally
 * handles DGW/BGW since `fixtures` already has the right number of rows
 * per event - 2 for a double gameweek, 0 for a blank one). */
export function expectedPointsMulti(player, fixtures, context) {
  const perFixture = fixtures.map(f => expectedPoints(player, f, context));
  return {
    total: round2(perFixture.reduce((s, r) => s + r.total, 0)),
    perFixture,
  };
}
