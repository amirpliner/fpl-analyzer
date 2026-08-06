import { state, FIXTURES_LOOKAHEAD } from "../state.js";
import { fdrClass, playerPrice, upcomingFixturesForTeam, fixtureRunScore } from "../helpers.js";

export function renderGwBadge() {
  const el = document.getElementById("gwBadge");
  if (!state.meta?.gameweek) { el.textContent = "אין נתוני מחזור"; return; }
  el.textContent = state.meta.is_upcoming
    ? `לקראת מחזור ${state.meta.gameweek}`
    : `מחזור ${state.meta.gameweek}`;
}

export function renderFdrTable() {
  const wrap = document.getElementById("fdrTable");
  const teams = [...state.teamsById.values()].sort((a, b) => a.name.localeCompare(b.name, "he"));
  let html = "<table><thead><tr><th>קבוצה</th>";
  for (let i = 0; i < FIXTURES_LOOKAHEAD; i++) html += `<th>+${i + 1}</th>`;
  html += "</tr></thead><tbody>";
  for (const t of teams) {
    const fx = upcomingFixturesForTeam(t.id);
    html += `<tr><td>${t.name}</td>`;
    for (let i = 0; i < FIXTURES_LOOKAHEAD; i++) {
      const f = fx[i];
      html += f
        ? `<td><span class="${fdrClass(f.diff)}">${f.opp}${f.isHome ? "" : "*"}</span></td>`
        : "<td>-</td>";
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;
}

export function renderTopPlayers() {
  const wrap = document.getElementById("topPlayers");
  const players = [...state.playersById.values()]
    .filter(p => p.element_type === state.activePos)
    .sort((a, b) => (parseFloat(b.form) - parseFloat(a.form)) || (b.total_points - a.total_points))
    .slice(0, 12);

  let html = "<table><thead><tr><th>שחקן</th><th>קבוצה</th><th>מחיר</th><th>פורם</th><th>נק'</th><th>נבחר ע\"י</th><th>ריצת משחקים</th></tr></thead><tbody>";
  for (const p of players) {
    const team = state.teamsById.get(p.team);
    const run = fixtureRunScore(p.team);
    const runClass = run <= 2.34 ? "fdr-1" : run <= 3 ? "fdr-2" : run <= 3.67 ? "fdr-3" : "fdr-4";
    html += `<tr>
      <td>${p.web_name}${p.chance_of_playing_next_round !== null && p.chance_of_playing_next_round < 100 ? " ⚠️" : ""}</td>
      <td>${team?.short_name || "?"}</td>
      <td>£${playerPrice(p)}</td>
      <td>${p.form}</td>
      <td>${p.total_points}</td>
      <td>${p.selected_by_percent}%</td>
      <td><span class="fdr-cell ${runClass}">${run.toFixed(1)}</span></td>
    </tr>`;
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;
}
