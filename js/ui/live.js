import { state } from "../state.js";
import { fetchJSON } from "../data.js";
import { naOr, teamCrestImg } from "../helpers.js";

// Only actually hits the network while the live tab is on-screen and
// visible, since matches only run a few hours a week - see
// setupLiveTab()/stopPolling() below.
const POLL_MS = 60_000;
let pollHandle = null;
let myEntryIdCache;

/** Mirrors myteam.js's manager selection (same localStorage/hash key)
 * so "my live score" always matches whoever is picked in "הקבוצה שלי" -
 * this is a shared site, not just for whoever runs the pipeline. */
async function resolveManagerId() {
  const cfg = state.config;
  const hashMatch = location.hash.match(/manager=(mine|\d+)/);
  let id = hashMatch?.[1] || localStorage.getItem("fplManagerId");
  const isKnown = id && (id === "mine"
    ? cfg?.has_mine_analysis
    : cfg?.managers?.some(m => String(m.id) === String(id)));
  if (!isKnown) id = cfg?.has_mine_analysis ? "mine" : (cfg?.managers?.[0]?.id ?? null);
  if (!id) return null;

  if (id === "mine") {
    if (myEntryIdCache === undefined) {
      const squad = await fetchJSON("data/my_squad.json");
      myEntryIdCache = squad?.entry_id ?? null;
    }
    return myEntryIdCache;
  }
  return Number(id);
}

function fixtureStatusLabel(f) {
  if (!f.started) {
    const d = new Date(f.kickoff_time);
    return d.toLocaleString("he-IL", { weekday: "short", hour: "2-digit", minute: "2-digit" });
  }
  if (f.finished) return "סופי";
  if (f.finished_provisional) return "הסתיים · בונוסים בבדיקה";
  return `${f.minutes ?? 0}׳`;
}

function renderFixturesBanner(fixtures) {
  if (!fixtures.length) {
    return `<p class="empty-state">אין עדיין נתוני משחקים למחזור הזה.</p>`;
  }
  const sorted = [...fixtures].sort((a, b) => new Date(a.kickoff_time) - new Date(b.kickoff_time));
  let html = `<div class="live-fixtures">`;
  for (const f of sorted) {
    const home = state.teamsById.get(f.team_h);
    const away = state.teamsById.get(f.team_a);
    const isLive = f.started && !f.finished_provisional;
    const score = f.started ? `${f.team_h_score ?? 0} - ${f.team_a_score ?? 0}` : "-";
    html += `<div class="live-fixture-card${isLive ? " is-live" : ""}">
      <div class="live-fixture-teams">
        <span class="team-cell">${teamCrestImg(home)}${home?.short_name || "?"}</span>
        <span class="live-fixture-score">${score}</span>
        <span class="team-cell">${away?.short_name || "?"}${teamCrestImg(away)}</span>
      </div>
      <div class="live-fixture-status">${isLive ? "🔴 " : ""}${fixtureStatusLabel(f)}</div>
    </div>`;
  }
  html += `</div>`;
  return html;
}

async function renderMyLive(gw) {
  const container = document.getElementById("liveMyTeam");
  const managerId = await resolveManagerId();
  if (!managerId) {
    container.innerHTML = `<p class="empty-state">בחר את עצמך בלשונית "הקבוצה שלי" כדי לראות כאן ניקוד לייב.</p>`;
    return;
  }

  const [picks, live] = await Promise.all([
    fetchJSON(`data/entry_${managerId}_picks_gw${gw}.json`),
    fetchJSON("data/live_event.json"),
  ]);
  if (!picks) {
    container.innerHTML = `<p class="empty-state">אין עדיין נתוני בחירות למנהל הזה במחזור הזה.</p>`;
    return;
  }

  const elements = (live && live.gameweek === gw) ? live.elements : {};
  const hasLiveData = Object.keys(elements).length > 0;
  const rows = picks.picks
    .map(pk => ({ pk, p: state.playersById.get(pk.element), stats: elements[String(pk.element)] }))
    .filter(r => r.p);

  // entry_history.points (the manager's own picks/ endpoint) lags well
  // behind the true live score during play - verified against real
  // gameweek data where it read 17 while the per-player live total
  // (and the league table's own event_total) already read 37. Summing
  // live per-player points ourselves is what actually tracks live -
  // entry_history.points is only used as a fallback before any live
  // data exists at all.
  const computedTotal = rows.reduce((s, r) => s + (r.stats?.total_points ?? 0) * r.pk.multiplier, 0);
  const total = hasLiveData ? computedTotal : (picks.entry_history?.points ?? 0);

  let html = `<div class="summary-card">
    <div class="summary-stat">
      <div class="value rating-score">${total}</div>
      <div class="label">ניקוד לייב</div>
      <div class="sub">${picks.active_chip ? `צ'יפ פעיל: ${picks.active_chip}` : ""}</div>
    </div>
    <div class="summary-stat">
      <div class="value">${naOr(picks.entry_history?.overall_rank, v => v.toLocaleString("he-IL"))}</div>
      <div class="label">דירוג כולל (זמני)</div>
    </div>
  </div>`;

  html += `<div class="table-wrap"><table><thead><tr>
    <th>שחקן</th><th>קבוצה</th><th>סטטוס</th><th>דקות</th><th>נק'</th>
  </tr></thead><tbody>`;
  for (const r of rows) {
    const team = state.teamsById.get(r.p.team);
    const minutes = r.stats?.minutes ?? 0;
    const points = (r.stats?.total_points ?? 0) * r.pk.multiplier;
    const tag = r.pk.is_captain ? " (C)" : r.pk.is_vice_captain ? " (V)" : "";
    const status = minutes > 0 ? (minutes >= 90 ? "שיחק" : "במגרש") : "טרם שיחק";
    html += `<tr${r.pk.multiplier === 0 ? ' class="bench-row"' : ""}>
      <td>${r.pk.position > 11 ? "🪑 " : ""}${r.p.web_name}${tag}</td>
      <td class="team-cell">${teamCrestImg(team)}${team?.short_name || "?"}</td>
      <td>${status}</td>
      <td>${minutes}׳</td>
      <td>${points}</td>
    </tr>`;
  }
  html += `</tbody></table></div>
    <p class="price-disclaimer">
      הניקוד מחושב לפי נקודות לייב לכל שחקן (כולל בונוסים ברגע שהם מאושרים) - אותו מקור שממנו גם טבלת
      הליגה החיה מתעדכנת. עדיין לא כולל החלפות ספסל אוטומטיות - אלו מתבצעות ומתעדכנות אצל FPL רק אחרי
      שכל משחקי המחזור מסתיימים.
    </p>`;
  container.innerHTML = html;
}

async function renderLiveLeagueTable() {
  const container = document.getElementById("liveLeagueTable");
  const cfg = state.config;
  if (!cfg?.league_id) {
    container.innerHTML = "";
    return;
  }
  const league = await fetchJSON(`data/league_${cfg.league_id}.json`);
  const rows = league?.standings?.results;
  if (!rows?.length) {
    container.innerHTML = `<p class="empty-state">אין עדיין דירוג ליגה למחזור הזה.</p>`;
    return;
  }
  const sorted = [...rows].sort((a, b) => b.event_total - a.event_total);
  let html = `<div class="table-wrap"><table><thead><tr>
    <th>#</th><th>מנהל</th><th>קבוצה</th><th>נק' מחזור (לייב)</th><th>סה"כ</th>
  </tr></thead><tbody>`;
  sorted.forEach((row, i) => {
    html += `<tr>
      <td>${i + 1}</td>
      <td>${row.player_name}</td>
      <td>${row.entry_name}</td>
      <td><strong>${row.event_total}</strong></td>
      <td>${row.total}</td>
    </tr>`;
  });
  html += `</tbody></table></div>`;
  container.innerHTML = html;
}

export async function renderLive() {
  const gw = state.meta?.gw_current;
  const banner = document.getElementById("liveFixturesBanner");
  const dots = [document.getElementById("tabLiveDot"), document.getElementById("liveStatusDot")];
  const statusText = document.getElementById("liveStatusText");

  if (!gw) {
    banner.innerHTML = `<p class="empty-state">עדיין אין מחזור פעיל - המעקב הלייב יתחיל ברגע שדדליין המחזור הראשון יעבור.</p>`;
    document.getElementById("liveMyTeam").innerHTML = "";
    document.getElementById("liveLeagueTable").innerHTML = "";
    dots.forEach(d => d?.classList.remove("is-live"));
    statusText.textContent = "";
    return;
  }

  const data = await fetchJSON("data/live_fixtures.json");
  const fixtures = (data?.gameweek === gw) ? data.fixtures : [];
  banner.innerHTML = renderFixturesBanner(fixtures);

  const anyLive = fixtures.some(f => f.started && !f.finished_provisional);
  dots.forEach(d => d?.classList.toggle("is-live", anyLive));
  statusText.textContent = anyLive
    ? "יש כרגע משחקים בעיצומם - מתעדכן אוטומטית"
    : fixtures.length
      ? "אין כרגע משחק בעיצומו"
      : "";

  await Promise.all([renderMyLive(gw), renderLiveLeagueTable()]);
}

function stopPolling() {
  if (pollHandle) {
    clearInterval(pollHandle);
    pollHandle = null;
  }
}

export function setupLiveTab() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      stopPolling();
      if (btn.dataset.tab !== "live") return;
      renderLive();
      pollHandle = setInterval(() => {
        if (document.visibilityState === "visible") renderLive();
      }, POLL_MS);
    });
  });
}
