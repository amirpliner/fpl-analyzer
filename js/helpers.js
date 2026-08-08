import { state, FIXTURES_LOOKAHEAD, ROTATION_LABELS } from "./state.js";

export function fdrClass(diff) {
  return `fdr-cell fdr-${diff}`;
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

export function rotationTag(risk) {
  const r = risk || "unknown";
  return `<span class="rotation-tag ${r}">${ROTATION_LABELS[r] || r}</span>`;
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
