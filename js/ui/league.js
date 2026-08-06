import { state } from "../state.js";
import { fetchJSON } from "../data.js";

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
