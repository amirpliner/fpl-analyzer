import { state, FIXTURES_LOOKAHEAD, POSITION_CODES } from "../state.js";
import { fetchJSON } from "../data.js";
import {
  fdrClass, upcomingFixturesForTeam, fixtureRunScore,
  naOr, rotationTag, minutesSparkline, setPieceBadges, teamCrestImg,
  setupDetailToggle,
} from "../helpers.js";

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
    html += `<tr><td class="team-cell">${teamCrestImg(t)}${t.name}</td>`;
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

export async function renderPriceAlerts() {
  const container = document.getElementById("priceAlerts");
  const data = await fetchJSON("data/price_alerts.json");
  if (!data) {
    container.innerHTML = "";
    return;
  }

  const disclaimer = `<div class="price-disclaimer">
    ⚠️ הערכה בלבד, לא נתון רשמי מ-FPL - מבוסס על נפח העברות יחסי למספר המנהלים הכולל.
    ${data.calibrated ? "הסף כוייל מנתונים היסטוריים אמיתיים." : "הסף עדיין זמני (עוד אין מספיק שינויי מחיר בפועל לכייל מולם)."}
  </div>`;

  if (!data.alerts.length) {
    container.innerHTML = `${disclaimer}<p class="empty-state">אין כרגע שחקנים עם מספיק תנועת העברות כדי להצדיק התראה.</p>`;
    return;
  }

  let html = disclaimer + `<div class="table-wrap"><table><thead><tr>
    <th>שחקן</th><th>קבוצה</th><th>כיוון</th><th>נטו העברות</th>
  </tr></thead><tbody>`;
  for (const a of data.alerts.slice(0, 15)) {
    const team = state.teamsById.get(a.team);
    const dirClass = a.direction === "rising" ? "rising" : "falling";
    const dirLabel = a.direction === "rising" ? "📈 צפוי לעלות" : "📉 צפוי לרדת";
    html += `<tr>
      <td>${a.name}</td>
      <td class="team-cell">${teamCrestImg(team)}${team?.short_name || "?"}</td>
      <td><span class="price-direction ${dirClass}">${dirLabel}</span></td>
      <td>${a.net_transfers_pct}%</td>
    </tr>`;
  }
  html += "</tbody></table></div>";
  container.innerHTML = html;
}

export function renderTopPlayers() {
  const wrap = document.getElementById("topPlayers");
  const posCode = POSITION_CODES[state.activePos];
  const players = [...state.enrichedById.values()]
    .filter(p => p.pos === posCode)
    // Third tiebreak covers GW1 right after a season reset, when form
    // and points are 0 for everyone - falls back to last season's rate
    // stats (see prior_season_fallback) instead of an arbitrary order.
    .sort((a, b) => (b.form - a.form) || (b.points - a.points) || ((b.xg90 + b.xa90) - (a.xg90 + a.xa90)))
    .slice(0, 12);

  let html = `<table><thead><tr>
    <th>שחקן</th><th>קבוצה</th><th>מחיר</th><th>פורם</th><th>נק'</th><th>ריצת משחקים</th><th></th>
  </tr></thead><tbody>`;
  for (const p of players) {
    const team = state.teamsById.get(p.team);
    const run = fixtureRunScore(p.team);
    const runClass = run <= 2.34 ? "fdr-1" : run <= 3 ? "fdr-2" : run <= 3.67 ? "fdr-3" : "fdr-4";
    const startsPct = p.starts_per_90 != null ? `${Math.round(p.starts_per_90 * 100)}%` : naOr(null);
    html += `<tr class="squad-row" data-player-id="${p.id}">
      <td>${p.name}${p.chance_next !== null && p.chance_next < 100 ? " ⚠️" : ""}</td>
      <td class="team-cell">${teamCrestImg(team)}${team?.short_name || "?"}</td>
      <td>£${p.price.toFixed(1)}</td>
      <td>${p.form}</td>
      <td>${p.points}</td>
      <td><span class="fdr-cell ${runClass}">${run.toFixed(1)}</span></td>
      <td><button type="button" class="detail-toggle" aria-expanded="false" title="עוד נתונים">▾</button></td>
    </tr>
    <tr class="detail-row" data-player-id="${p.id}" hidden>
      <td colspan="7">
        <div class="detail-grid">
          <div class="detail-stat"><span class="detail-label">נבחר ע"י</span><span class="detail-value">${p.owned}%</span></div>
          <div class="detail-stat"><span class="detail-label">xG</span><span class="detail-value">${naOr(p.xg)}</span></div>
          <div class="detail-stat"><span class="detail-label">xA</span><span class="detail-value">${naOr(p.xa)}</span></div>
          <div class="detail-stat"><span class="detail-label">ICT</span><span class="detail-value">${naOr(p.ict)}</span></div>
          <div class="detail-stat"><span class="detail-label">כדורי-רגל</span><span class="detail-value">${setPieceBadges(p.set_pieces)}</span></div>
          <div class="detail-stat" title="${p.chance_next != null ? `${p.chance_next}% סיכוי לשחק במחזור הבא` : ""}"><span class="detail-label">%התחלות</span><span class="detail-value">${startsPct}</span></div>
          <div class="detail-stat"><span class="detail-label">סטטוס דקות</span><span class="detail-value">${rotationTag(p.rotation_risk, p.prior_season_fallback)}${p.last5_minutes?.length ? minutesSparkline(p.last5_minutes) : ""}</span></div>
        </div>
      </td>
    </tr>`;
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;
  setupDetailToggle(wrap);
}
