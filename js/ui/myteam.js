import { state, POSITION_NAMES } from "../state.js";
import { fetchJSON } from "../data.js";
import { fdrCellClass, naOr, playerPrice, fixtureRunScore, teamCrestImg, teamByShortName } from "../helpers.js";

export async function renderManagerTeam(teamId) {
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
      <td class="team-cell">${teamCrestImg(team)}${team?.short_name || "?"}</td>
      <td>£${playerPrice(p)}</td>
      <td>${p.form}</td>
      <td><span class="fdr-cell ${runClass}">${run.toFixed(1)}</span></td>
      <td>${recommendation || "<span class=\"pill\">בסדר</span>"}</td>
    </tr>`;
  }
  html += "</tbody></table></div>";
  container.innerHTML = html;
}

export function bestReplacement(player, currentSquad) {
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

export function selectManager(id) {
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

export async function renderMyTeam() {
  const container = document.getElementById("myTeamContent");
  const picker = document.getElementById("managerPicker");
  const select = document.getElementById("managerSelect");
  const cfg = state.config;

  if (!cfg || (!cfg.managers?.length && !cfg.has_mine_analysis)) return;

  picker.style.display = "flex";
  const mineOption = cfg.has_mine_analysis ? '<option value="mine">אתה (ניתוח מלא)</option>' : "";
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

export async function renderMineAnalysis() {
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
      <div class="label">קפטן מומלץ${topCaptain ? ` (${topCaptain.xpts} xPts)` : ""}</div>
      <div class="sub">${topCaptain ? `${topCaptain.confidence}% ביטחון` : ""}</div>
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

  if (a.captain_recommendations.length) {
    html += `<h2>קפטן מומלץ</h2><div class="captain-cards">`;
    a.captain_recommendations.forEach((c, i) => {
      html += `<div class="captain-card${i === 0 ? " top" : ""}">
        <div class="captain-rank">#${i + 1}</div>
        <div class="captain-name">${c.web_name}</div>
        <div class="captain-xpts">${c.xpts} <span class="captain-xpts-label">xPts</span></div>
        <div class="captain-confidence">${c.confidence}% ביטחון</div>
        <div class="captain-reason">${c.reason}</div>
      </div>`;
    });
    html += `</div>`;
  }

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
    <th>%התחלות</th><th>FDR ממוצע (5)</th><th>בעלות</th>
  </tr></thead><tbody>`;
  for (const p of a.players) {
    const fdrClass = fdrCellClass(p.avg_fdr_next5);
    const startsPct = p.starts_per_90 != null ? `${Math.round(p.starts_per_90 * 100)}%` : naOr(null);
    html += `<tr>
      <td>${teamCrestImg(teamByShortName(p.team), 18)}${p.on_bench ? "🪑 " : ""}${p.is_captain ? "©️ " : p.is_vice ? "Ⓥ " : ""}${p.web_name} (${p.team})
        ${p.injury ? `<span class="injury-tag">${p.injury.news || p.injury.status}</span>` : ""}
        ${p.is_differential ? `<span class="differential-tag">דיפרנציאל</span>` : ""}
      </td>
      <td>£${p.price.toFixed(1)}</td>
      <td>${naOr(p.ppm)}</td>
      <td>${naOr(p.xgi_per_90)}</td>
      <td>${naOr(p.xgc_per_90)}</td>
      <td title="${p.chance_next != null ? `${p.chance_next}% סיכוי לשחק במחזור הבא` : ""}">${startsPct}</td>
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

  const plan = await fetchJSON("data/transfer_plan.json");
  if (plan) {
    html += `<h2>תוכנית העברות ל-${plan.horizon} מחזורים</h2>
      <p class="price-disclaimer">
        מבוסס על xPts חזוי בלבד, לא מבטיח כלום. עלות מכירה מחושבת לפי מחיר שוק נוכחי (לא כלל "חצי רווח" של FPL).
        עסקאות מוצעות רק בין שחקנים באותה עמדה. מסלול "ללא העברות" תמיד מוצג כבסיס להשוואה.
      </p>
      <div class="plan-routes">`;
    plan.routes.forEach((route, i) => {
      const isBaseline = route.total_transfers === 0;
      html += `<div class="plan-route${i === 0 ? " top" : ""}">
        <div class="plan-route-header">
          <span class="plan-route-title">${isBaseline ? "בלי העברות (roll)" : `מסלול ${i + 1}`}</span>
          <span class="plan-route-gain">${route.net_gain_vs_hold >= 0 ? "+" : ""}${route.net_gain_vs_hold} xPts מול roll</span>
        </div>
        <div class="plan-route-meta">${route.total_transfers} העברות · ${route.total_hits ? `${route.total_hits * 4}- נק' קנס` : "בלי קנס"} · בנק סופי £${route.final_bank}</div>
        <div class="plan-weeks">`;
      for (const w of route.weekly_plan) {
        html += `<div class="plan-week">
          <div class="plan-week-label">מחזור ${w.week}</div>
          ${w.transfers.length
            ? w.transfers.map(t => `<div class="plan-transfer"><span class="suggest-out">${t.out}</span> → <span class="suggest-in">${t.in}</span></div>`).join("")
            : `<div class="plan-transfer na">ללא העברה</div>`}
          <div class="plan-week-captain">קפטן: ${w.captain || naOr(null)}</div>
        </div>`;
      }
      html += `</div></div>`;
    });
    html += `</div>`;
  }

  const chipPlan = await fetchJSON("data/chip_plan.json");
  if (chipPlan) {
    html += renderChipPlan(chipPlan);
  }

  container.innerHTML = html;
}

function chipUsedNote(name, chipsUsed) {
  const used = chipsUsed.find(c => c.name === name);
  return used ? `<span class="chip-used-tag">כבר נוצל במחזור ${used.event}</span>` : "";
}

function renderChipPlan(plan) {
  let html = `<h2>מנוע צ'יפים (${plan.horizon} מחזורים קדימה)</h2>
    <p class="price-disclaimer">${plan.note} הסף להמלצה בכל צ'יפ הוא ברירת מחדל סבירה, לא מכויל מול תוצאות אמיתיות.</p>
    <div class="chip-cards">`;

  html += `<div class="chip-card">
    <div class="chip-card-title">Bench Boost ${chipUsedNote("bboost", plan.chips_used)}</div>`;
  if (plan.bench_boost.recommendations.length) {
    for (const r of plan.bench_boost.recommendations) {
      html += `<div class="chip-rec">מחזור ${r.event}${r.is_dgw ? " (כפול)" : ""}: ${r.reason}</div>`;
    }
  } else {
    html += `<div class="chip-rec na">אין מחזור עם ספסל מספיק חזק בטווח הזה</div>`;
  }
  html += `</div>`;

  html += `<div class="chip-card">
    <div class="chip-card-title">Triple Captain ${chipUsedNote("3xc", plan.chips_used)}</div>`;
  if (plan.triple_captain.recommendations.length) {
    for (const r of plan.triple_captain.recommendations) {
      html += `<div class="chip-rec">מחזור ${r.event}: ${r.reason}</div>`;
    }
  } else {
    html += `<div class="chip-rec na">אין מועמד בולט בטווח הזה</div>`;
  }
  html += `</div>`;

  html += `<div class="chip-card">
    <div class="chip-card-title">Free Hit ${chipUsedNote("freehit", plan.chips_used)}</div>`;
  if (plan.free_hit.recommendations.length) {
    for (const r of plan.free_hit.recommendations) {
      html += `<div class="chip-rec">מחזור ${r.event}: ${r.reason}</div>`;
    }
  } else {
    html += `<div class="chip-rec na">אין מחזור עם ריבוי שחקנים ללא משחק בטווח הזה</div>`;
  }
  html += `</div>`;

  html += `<div class="chip-card${plan.wildcard.recommend ? " urgent" : ""}">
    <div class="chip-card-title">Wildcard ${chipUsedNote("wildcard", plan.chips_used)}</div>
    <div class="chip-rec">${plan.wildcard.reason}</div>
  </div>`;

  html += `</div>`;
  return html;
}
