import { state, FIXTURES_LOOKAHEAD, ROTATION_LABELS } from "./state.js";

export function fdrClass(diff) {
  return `fdr-cell fdr-${diff}`;
}

/** Official Premier League team badge, hotlinked from the same CDN the
 * FPL site itself uses (resources.premierleague.com) - no data pipeline
 * change needed, bootstrap.json already has each team's `code`. */
export function teamByShortName(shortName) {
  return [...state.teamsById.values()].find(t => t.short_name === shortName);
}

export function teamCrestImg(team, size = 20) {
  if (!team?.code) return "";
  const url = `https://resources.premierleague.com/premierleague/badges/50/t${team.code}.png`;
  return `<img class="team-crest" src="${url}" width="${size}" height="${size}" alt="${team.short_name || ""}" loading="lazy">`;
}

export function fdrCellClass(avgFdr) {
  if (avgFdr == null) return "";
  return avgFdr <= 2.34 ? "fdr-1" : avgFdr <= 3 ? "fdr-2" : avgFdr <= 3.67 ? "fdr-3" : "fdr-4";
}

export function playerPrice(p) {
  return (p.now_cost / 10).toFixed(1);
}

export function naOr(value, fmt = v => v) {
  return value === null || value === undefined ? '<span class="na">אין נתון</span>' : fmt(value);
}

export function upcomingFixturesForTeam(teamId, count = FIXTURES_LOOKAHEAD) {
  const gw = state.meta?.gameweek || 1;
  return state.fixtures
    .filter(f => !f.finished && f.event !== null && f.event >= gw &&
      (f.team_h === teamId || f.team_a === teamId))
    .sort((a, b) => a.event - b.event)
    .slice(0, count)
    .map(f => {
      const isHome = f.team_h === teamId;
      const oppId = isHome ? f.team_a : f.team_h;
      const opp = state.teamsById.get(oppId);
      const diff = isHome ? f.team_h_difficulty : f.team_a_difficulty;
      return { event: f.event, opp: opp?.short_name || "?", oppId, isHome, diff };
    });
}

export function fixtureRunScore(teamId) {
  const fx = upcomingFixturesForTeam(teamId, 3);
  if (!fx.length) return 3;
  return fx.reduce((s, f) => s + f.diff, 0) / fx.length;
}

/** League-average team strength for the xPts model's opponent-adjustment
 * term - null when strength_attack/defence aren't populated yet (see
 * PLAN.md's FDR-fallback note), same convention as js/models/xpts.js. */
export function leagueAveragesFromTeams() {
  const teams = [...state.teamsById.values()];
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

/** Converts upcomingFixturesForTeam()'s shape into the {oppTeamId,
 * isHome, difficulty} shape js/models/xpts.js expects. */
export function fixturesToContext(fixtures) {
  return fixtures.map(f => ({ oppTeamId: f.oppId, isHome: f.isHome, difficulty: f.diff }));
}

/** Wires up the expand/collapse toggle for a table built from paired
 * `.squad-row`/`.detail-row[data-player-id]` rows (see myteam.js and
 * gameweek.js's renderTopPlayers) - one delegated listener per table
 * instead of one per row. */
export function setupDetailToggle(wrap) {
  const tbody = wrap.querySelector(".squad-row")?.closest("tbody");
  if (!tbody) return;
  tbody.addEventListener("click", (e) => {
    const btn = e.target.closest(".detail-toggle");
    if (!btn) return;
    const row = btn.closest("tr");
    const detailRow = tbody.querySelector(`.detail-row[data-player-id="${row.dataset.playerId}"]`);
    const expanded = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", String(!expanded));
    btn.textContent = expanded ? "▾" : "▴";
    detailRow.hidden = expanded;
  });
}

export function rotationTag(risk, priorSeasonFallback) {
  const r = risk || "unknown";
  const title = priorSeasonFallback ? ` title="לפי עונת ${priorSeasonFallback} - עוד לא שיחק העונה"` : "";
  return `<span class="rotation-tag ${r}"${title}>${ROTATION_LABELS[r] || r}</span>`;
}

export function minutesSparkline(minutesList) {
  if (!minutesList || !minutesList.length) return naOr(null);
  const bars = minutesList.map(m => {
    const height = Math.max(2, Math.round((m / 90) * 22));
    return `<span class="bar" style="height:${height}px" title="${m}'"></span>`;
  }).join("");
  return `<span class="sparkline">${bars}</span>`;
}

export function setPieceBadges(setPieces) {
  if (!setPieces) return naOr(null);
  const items = [
    ["P", setPieces.pens],
    ["FK", setPieces.fk],
    ["C", setPieces.corners],
  ].filter(([, order]) => order !== null && order !== undefined);
  if (!items.length) return naOr(null);
  return items
    .map(([label, order]) => `<span class="setpiece-badge${order === 1 ? " primary" : ""}">${label}${order}</span>`)
    .join("");
}
