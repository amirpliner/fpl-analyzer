import { state, FIXTURES_LOOKAHEAD, POSITION_CODES } from "../state.js";
import { fetchJSON } from "../data.js";
import {
  fdrClass, upcomingFixturesForTeam, fixtureRunScore,
  naOr, rotationTag, minutesSparkline, setPieceBadges,
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
      <td>${team?.short_name || "?"}</td>
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
    .sort((a, b) => (b.form - a.form) || (b.points - a.points))
    .slice(0, 12);

  let html = `<table><thead><tr>
    <th>שחקן</th><th>קבוצה</th><th>מחיר</th><th>פורם</th><th>נק'</th><th>נבחר ע"י</th>
    <th>ריצת משחקים</th><th>xG</th><th>xA</th><th>ICT</th><th>כדורי-רגל</th><th>סטטוס דקות</th>
  </tr></thead><tbody>`;
  for (const p of players) {
    const team = state.teamsById.get(p.team);
    const run = fixtureRunScore(p.team);
    const runClass = run <= 2.34 ? "fdr-1" : run <= 3 ? "fdr-2" : run <= 3.67 ? "fdr-3" : "fdr-4";
    html += `<tr>
      <td>${p.name}${p.chance_next !== null && p.chance_next < 100 ? " ⚠️" : ""}</td>
      <td>${team?.short_name || "?"}</td>
      <td>£${p.price.toFixed(1)}</td>
      <td>${p.form}</td>
      <td>${p.points}</td>
      <td>${p.owned}%</td>
      <td><span class="fdr-cell ${runClass}">${run.toFixed(1)}</span></td>
      <td>${naOr(p.xg)}</td>
      <td>${naOr(p.xa)}</td>
      <td>${naOr(p.ict)}</td>
      <td>${setPieceBadges(p.set_pieces)}</td>
      <td>${rotationTag(p.rotation_risk)}${p.last5_minutes?.length ? minutesSparkline(p.last5_minutes) : ""}</td>
    </tr>`;
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;
}
