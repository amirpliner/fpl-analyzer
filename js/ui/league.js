import { state } from "../state.js";
import { fetchJSON } from "../data.js";
import { naOr, upcomingFixturesForTeam, leagueAveragesFromTeams, fixturesToContext } from "../helpers.js";
import { expectedPointsMulti } from "../models/xpts.js";

export async function renderLeague() {
  const container = document.getElementById("leagueContent");
  const cfg = state.config;
  if (!cfg || !cfg.league_id) return;
  const league = await fetchJSON(`data/league_${cfg.league_id}.json`);
  if (!league) return;

  let html = `<h2>${league.league.name}</h2>`;

  if (league.standings.results.length) {
    html += `<div class="table-wrap"><table><thead><tr><th>#</th><th>מנהל</th><th>קבוצה</th><th>נק' מחזור</th><th>סה"כ</th></tr></thead><tbody>`;
    for (const row of league.standings.results) {
      html += `<tr>
        <td>${row.rank}</td>
        <td>${row.player_name}</td>
        <td>${row.entry_name}</td>
        <td>${row.event_total}</td>
        <td>${row.total}</td>
      </tr>`;
    }
    html += "</tbody></table></div>";
  } else if (league.new_entries?.results?.length) {
    html += `<p class="empty-state">העונה עוד לא התחילה, אז אין דירוג עדיין - הנה המנהלים שהצטרפו לליגה:</p>`;
    html += `<div class="table-wrap"><table><thead><tr><th>מנהל</th><th>קבוצה</th></tr></thead><tbody>`;
    for (const row of league.new_entries.results) {
      html += `<tr><td>${row.player_first_name} ${row.player_last_name}</td><td>${row.entry_name}</td></tr>`;
    }
    html += "</tbody></table></div>";
  }
  container.innerHTML = html;
}

function playerNextXpts(playerId) {
  const p = state.enrichedById.get(playerId);
  if (!p) return null;
  const fixtures = upcomingFixturesForTeam(p.team, 1);
  if (!fixtures.length) return null;
  const result = expectedPointsMulti(p, fixturesToContext(fixtures), {
    teamsById: state.teamsById,
    leagueAvg: leagueAveragesFromTeams(),
    ictPercentiles: null,
  });
  return result.total;
}

export async function renderLeagueInsights() {
  const container = document.getElementById("leagueInsights");
  const cfg = state.config;
  if (!cfg?.league_id) return;
  const insights = await fetchJSON("data/league_insights.json");

  if (!insights) {
    container.innerHTML = `<h2>תובנות ליגה</h2><p class="empty-state">
      עדיין אין תובנות ליגה - הן דורשות את הבחירות האמיתיות של כל החברים, שנפתחות רק אחרי הדדליין של המחזור.
    </p>`;
    return;
  }

  const template = insights.players.filter(p => p.is_template).slice(0, 8);
  const differentials = insights.players
    .filter(p => p.is_league_differential)
    .map(p => ({ ...p, xpts: playerNextXpts(p.id) }))
    .filter(p => p.xpts !== null)
    .sort((a, b) => b.xpts - a.xpts)
    .slice(0, 5);

  let html = `<h2>שחקני טמפלייט בליגה (${insights.league_size} מנהלים)</h2>
    <div class="table-wrap"><table><thead><tr>
      <th>שחקן</th><th>בעלות בליגה</th><th>EO</th><th>בעלות גלובלית</th>
    </tr></thead><tbody>`;
  for (const p of template) {
    html += `<tr>
      <td>${p.name}</td>
      <td>${p.league_ownership_pct}%</td>
      <td>${p.eo_pct}%</td>
      <td>${naOr(p.global_ownership_pct, v => `${v}%`)}</td>
    </tr>`;
  }
  html += `</tbody></table></div>`;

  if (differentials.length) {
    html += `<h2>דיפרנציאלים אמיתיים בליגה</h2>
      <p class="price-disclaimer">בעלות נמוכה בליגה שלך (מתחת ל-20%) אבל xPts גבוה למשחק הבא - סיכוי להתרחק מהחברים.</p>
      <div class="table-wrap"><table><thead><tr>
        <th>שחקן</th><th>בעלות בליגה</th><th>xPts הבא</th>
      </tr></thead><tbody>`;
    for (const p of differentials) {
      html += `<tr><td>${p.name}</td><td>${p.league_ownership_pct}%</td><td>${p.xpts}</td></tr>`;
    }
    html += `</tbody></table></div>`;
  }

  html += `<h2>קפטנים של החברים</h2><div class="table-wrap"><table><thead><tr>
    <th>מנהל</th><th>קבוצה</th><th>קפטן</th>
  </tr></thead><tbody>`;
  for (const c of insights.captains_by_manager) {
    html += `<tr><td>${c.manager}</td><td>${c.team_name}</td><td>${c.captain_name || naOr(null)}</td></tr>`;
  }
  html += `</tbody></table></div>`;

  if (insights.squad_overlaps.length) {
    const top = insights.squad_overlaps[0];
    html += `<h2>חפיפת סגלים</h2><p>הכי דומים בליגה: <strong>${top.a}</strong> ו-<strong>${top.b}</strong> - ${top.shared_players} שחקנים משותפים (${top.overlap_pct}%)</p>`;
  }

  container.innerHTML = html;
}
