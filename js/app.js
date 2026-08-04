const POSITION_NAMES = { 1: "שוער", 2: "מגן", 3: "קשר", 4: "חלוץ" };
const FIXTURES_LOOKAHEAD = 5;

let state = {
  bootstrap: null,
  fixtures: null,
  meta: null,
  config: null,
  teamsById: new Map(),
  playersById: new Map(),
  activePos: 1,
};

async function fetchJSON(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

function fdrClass(diff) {
  return `fdr-cell fdr-${diff}`;
}

function playerPrice(p) {
  return (p.now_cost / 10).toFixed(1);
}

function upcomingFixturesForTeam(teamId, count = FIXTURES_LOOKAHEAD) {
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
      return { event: f.event, opp: opp?.short_name || "?", isHome, diff };
    });
}

function renderGwBadge() {
  const el = document.getElementById("gwBadge");
  if (!state.meta?.gameweek) { el.textContent = "אין נתוני מחזור"; return; }
  el.textContent = state.meta.is_upcoming
    ? `לקראת מחזור ${state.meta.gameweek}`
    : `מחזור ${state.meta.gameweek}`;
}

function renderFdrTable() {
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

function fixtureRunScore(teamId) {
  const fx = upcomingFixturesForTeam(teamId, 3);
  if (!fx.length) return 3;
  return fx.reduce((s, f) => s + f.diff, 0) / fx.length;
}

function renderTopPlayers() {
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

async function renderManagerTeam(teamId) {
  const container = document.getElementById("myTeamContent");
  const cfg = state.config;
  const entry = await fetchJSON(`data/entry_${teamId}.json`);
  const picks = await fetchJSON(`data/entry_${teamId}_picks_gw${cfg.picks_gw}.json`);
  if (!entry || !picks) {
    container.innerHTML = `<p class="empty-state">לא נמצאו נתונים למנהל הזה.</p>`;
    return;
  }

  let html = `<h2>${entry.name} (${entry.player_first_name} ${entry.player_last_name})</h2>`;
  html += `<div class="table-wrap"><table><thead><tr><th>שחקן</th><th>עמדה</th><th>קבוצה</th><th>מחיר</th><th>פורם</th><th>ריצת משחקים</th><th>המלצה</th></tr></thead><tbody>`;

  const squadPlayers = picks.picks.map(pk => state.playersById.get(pk.element)).filter(Boolean);

  for (const pk of picks.picks) {
    const p = state.playersById.get(pk.element);
    if (!p) continue;
    const team = state.teamsById.get(p.team);
    const run = fixtureRunScore(p.team);
    const runClass = run <= 2.34 ? "fdr-1" : run <= 3 ? "fdr-2" : run <= 3.67 ? "fdr-3" : "fdr-4";

    let recommendation = "";
    if (run >= 3.67 || parseFloat(p.form) < 2) {
      const alt = bestReplacement(p, squadPlayers);
      if (alt) recommendation = `<span class="suggest-out">שקול להחליף</span> ← <span class="suggest-in">${alt.web_name}</span>`;
    }

    html += `<tr>
      <td>${p.web_name}${p.chance_of_playing_next_round !== null && p.chance_of_playing_next_round < 100 ? " ⚠️" : ""}</td>
      <td>${POSITION_NAMES[p.element_type]}</td>
      <td>${team?.short_name || "?"}</td>
      <td>£${playerPrice(p)}</td>
      <td>${p.form}</td>
      <td><span class="fdr-cell ${runClass}">${run.toFixed(1)}</span></td>
      <td>${recommendation || "<span class=\"pill\">בסדר</span>"}</td>
    </tr>`;
  }
  html += "</tbody></table></div>";
  container.innerHTML = html;
}

function selectManager(id) {
  if (!id) {
    document.getElementById("myTeamContent").innerHTML =
      `<p class="empty-state">בחר את עצמך מהרשימה למעלה כדי לראות את הקבוצה שלך.</p>`;
    return;
  }
  localStorage.setItem("fplManagerId", id);
  location.hash = `manager=${id}`;
  if (id === "mine") {
    renderMineAnalysis();
  } else {
    renderManagerTeam(id);
  }
}

async function renderMyTeam() {
  const container = document.getElementById("myTeamContent");
  const picker = document.getElementById("managerPicker");
  const select = document.getElementById("managerSelect");
  const cfg = state.config;

  if (!cfg || (!cfg.managers?.length && !cfg.has_mine_analysis)) return;

  picker.style.display = "flex";
  const mineOption = cfg.has_mine_analysis ? '<option value="mine">⭐ אתה (ניתוח מלא)</option>' : "";
  select.innerHTML = '<option value="">-- בחר את עצמך --</option>' + mineOption +
    (cfg.managers || [])
      .sort((a, b) => a.name.localeCompare(b.name, "he"))
      .map(m => `<option value="${m.id}">${m.name} (${m.team_name})</option>`)
      .join("");

  select.addEventListener("change", () => selectManager(select.value));

  const hashMatch = location.hash.match(/manager=(mine|\d+)/);
  let savedId = hashMatch?.[1] || localStorage.getItem("fplManagerId");
  const isKnown = savedId === "mine"
    ? cfg.has_mine_analysis
    : savedId && cfg.managers?.some(m => String(m.id) === String(savedId));

  if (!isKnown && cfg.has_mine_analysis) savedId = "mine";

  if (isKnown || cfg.has_mine_analysis) {
    select.value = savedId;
    selectManager(savedId);
  } else {
    container.innerHTML = `<p class="empty-state">בחר את עצמך מהרשימה למעלה כדי לראות את הקבוצה שלך.</p>`;
  }
}

function fdrCellClass(avgFdr) {
  if (avgFdr == null) return "";
  return avgFdr <= 2.34 ? "fdr-1" : avgFdr <= 3 ? "fdr-2" : avgFdr <= 3.67 ? "fdr-3" : "fdr-4";
}

function naOr(value, fmt = v => v) {
  return value === null || value === undefined ? '<span class="na">אין נתון</span>' : fmt(value);
}

async function renderMineAnalysis() {
  const container = document.getElementById("myTeamContent");
  const a = await fetchJSON("data/analysis_mine.json");
  if (!a) {
    container.innerHTML = `<p class="empty-state">הניתוח עוד לא זמין.</p>`;
    return;
  }

  const topCaptain = a.captain_recommendations[0];
  let html = `<div class="summary-card">
    <div class="summary-stat">
      <div class="value rating-score">${a.rating.score}/10</div>
      <div class="label">דירוג סגל</div>
      <div class="sub">${a.rating.reason}</div>
    </div>
    <div class="summary-stat">
      <div class="value">${topCaptain ? topCaptain.web_name : "-"}</div>
      <div class="label">קפטן מומלץ</div>
      <div class="sub">${topCaptain ? topCaptain.reason : ""}</div>
    </div>
    <div class="summary-stat">
      <div class="value">${a.warnings.length + a.dead_players.length}</div>
      <div class="label">אזהרות</div>
      <div class="sub">${a.warnings.length} חשיפת קבוצה · ${a.dead_players.length} זמינות</div>
    </div>
    <div class="summary-stat">
      <div class="value">£${(a.bank ?? 0).toFixed(1)}</div>
      <div class="label">בבנק</div>
    </div>
  </div>`;

  if (a.warnings.length || a.dead_players.length) {
    html += `<h2>אזהרות</h2><div class="warnings-list">`;
    for (const w of a.warnings) {
      html += `<div class="warning-item">⚠️ ${w.reason}</div>`;
    }
    for (const d of a.dead_players) {
      html += `<div class="warning-item">🚑 <strong>${d.web_name}</strong>: ${d.reason}</div>`;
    }
    html += `</div>`;
  }

  html += `<h2>הסגל שלך</h2><div class="table-wrap"><table><thead><tr>
    <th>שחקן</th><th>מחיר</th><th>PPM</th><th>xGI/90</th><th>xGC/90</th>
    <th>FDR ממוצע (5)</th><th>בעלות</th>
  </tr></thead><tbody>`;
  for (const p of a.players) {
    const fdrClass = fdrCellClass(p.avg_fdr_next5);
    html += `<tr>
      <td>${p.on_bench ? "🪑 " : ""}${p.is_captain ? "©️ " : p.is_vice ? "Ⓥ " : ""}${p.web_name} (${p.team})
        ${p.injury ? `<span class="injury-tag">${p.injury.news || p.injury.status}</span>` : ""}
        ${p.is_differential ? `<span class="differential-tag">דיפרנציאל</span>` : ""}
      </td>
      <td>£${p.price.toFixed(1)}</td>
      <td>${naOr(p.ppm)}</td>
      <td>${naOr(p.xgi_per_90)}</td>
      <td>${naOr(p.xgc_per_90)}</td>
      <td>${p.avg_fdr_next5 != null ? `<span class="fdr-cell ${fdrClass}">${p.avg_fdr_next5}</span>` : naOr(null)}</td>
      <td>${p.ownership}%</td>
    </tr>`;
  }
  html += `</tbody></table></div>`;

  if (a.transfer_suggestions.length) {
    html += `<h2>הצעות העברה</h2><div class="transfer-cards">`;
    for (const t of a.transfer_suggestions) {
      html += `<div class="transfer-card">
        <div class="transfer-row">
          <span class="suggest-out">${t.out.web_name}</span>
          <span class="transfer-arrow">→</span>
          <span class="suggest-in">${t.in.web_name}</span>
        </div>
        <div class="transfer-cost">£${t.out.price.toFixed(1)} → £${t.in.price.toFixed(1)} (${t.cost_delta >= 0 ? "+" : ""}${t.cost_delta.toFixed(1)})</div>
        <div class="transfer-reason">${t.reason}</div>
      </div>`;
    }
    html += `</div>`;
  }

  container.innerHTML = html;
}

function bestReplacement(player, currentSquad) {
  const squadIds = new Set(currentSquad.map(p => p.id));
  const budget = player.now_cost + 5; // small wiggle room for a bank balance
  const candidates = [...state.playersById.values()]
    .filter(p => p.element_type === player.element_type &&
      !squadIds.has(p.id) &&
      p.now_cost <= budget &&
      p.status === "a")
    .map(p => ({ p, score: parseFloat(p.form) * 2 - fixtureRunScore(p.team) + p.total_points / 50 }))
    .sort((a, b) => b.score - a.score);
  return candidates[0]?.p || null;
}

async function renderLeague() {
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

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  document.querySelectorAll(".pos-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".pos-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.activePos = parseInt(btn.dataset.pos, 10);
      renderTopPlayers();
    });
  });
}

async function init() {
  setupTabs();

  const [bootstrap, fixtures, meta, config] = await Promise.all([
    fetchJSON("data/bootstrap.json"),
    fetchJSON("data/fixtures.json"),
    fetchJSON("data/meta.json"),
    fetchJSON("data/config.json"),
  ]);

  if (!bootstrap || !fixtures) {
    document.getElementById("gwBadge").textContent = "אין נתונים - הרץ את scripts/fetch_data.py";
    return;
  }

  state.bootstrap = bootstrap;
  state.fixtures = fixtures;
  state.meta = meta || {};
  state.config = config || {};
  state.teamsById = new Map(bootstrap.teams.map(t => [t.id, t]));
  state.playersById = new Map(bootstrap.elements.map(p => [p.id, p]));

  renderGwBadge();
  renderFdrTable();
  renderTopPlayers();
  renderMyTeam();
  renderLeague();

  const lastUpdated = new Date().toLocaleString("he-IL");
  document.getElementById("lastUpdated").textContent = lastUpdated;
}

init();
