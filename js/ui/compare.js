import { state } from "../state.js";
import { naOr, fdrClass, upcomingFixturesForTeam, leagueAveragesFromTeams, fixturesToContext, teamCrestImg } from "../helpers.js";
import { expectedPointsMulti, ictPercentilesByPosition } from "../models/xpts.js";

const MAX_PLAYERS = 4;
const STORAGE_KEY = "fplCompareIds";

let selectedIds = [];
let nameToId = new Map();

function loadSaved() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(saved) ? saved.filter(id => state.enrichedById.has(id)) : [];
  } catch {
    return [];
  }
}

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedIds));
}

function populateDatalist() {
  const datalist = document.getElementById("comparePlayerList");
  nameToId = new Map();
  const players = [...state.enrichedById.values()].sort((a, b) => b.points - a.points);
  let html = "";
  for (const p of players) {
    const team = state.teamsById.get(p.team);
    const label = `${p.name} (${team?.short_name || "?"}) - £${p.price.toFixed(1)}`;
    nameToId.set(label, p.id);
    html += `<option value="${label}"></option>`;
  }
  datalist.innerHTML = html;
}

function addPlayer(id) {
  if (selectedIds.includes(id) || selectedIds.length >= MAX_PLAYERS) return;
  selectedIds.push(id);
  save();
  renderAll();
}

function removePlayer(id) {
  selectedIds = selectedIds.filter(x => x !== id);
  save();
  renderAll();
}

function renderChips() {
  const container = document.getElementById("compareChips");
  if (!selectedIds.length) {
    container.innerHTML = `<p class="empty-state">הקלד שם שחקן למעלה כדי להתחיל להשוות (עד 4 שחקנים).</p>`;
    return;
  }
  container.innerHTML = selectedIds.map(id => {
    const p = state.enrichedById.get(id);
    const team = state.teamsById.get(p.team);
    return `<span class="compare-chip">${teamCrestImg(team, 16)}${p.name} <button data-remove="${id}" aria-label="הסר">✕</button></span>`;
  }).join("");

  container.querySelectorAll("[data-remove]").forEach(btn => {
    btn.addEventListener("click", () => removePlayer(parseInt(btn.dataset.remove, 10)));
  });
}

function winnerClass(values, value, higherIsBetter = true) {
  const comparable = values.filter(v => v !== null && v !== undefined && !isNaN(v));
  if (comparable.length < 2) return "";
  const best = higherIsBetter ? Math.max(...comparable) : Math.min(...comparable);
  return value === best ? " winner" : "";
}

function renderComparisonTable() {
  const container = document.getElementById("compareContent");
  if (selectedIds.length < 2) {
    container.innerHTML = selectedIds.length === 1
      ? `<p class="empty-state">תוסיף עוד שחקן אחד לפחות כדי להשוות.</p>`
      : "";
    return;
  }

  const players = selectedIds.map(id => state.enrichedById.get(id));
  const leagueAvg = leagueAveragesFromTeams();
  const teamsById = state.teamsById;
  const ictPct = ictPercentilesByPosition([...state.enrichedById.values()]);

  const xptsData = players.map(p => {
    const fixtures = upcomingFixturesForTeam(p.team, 3);
    const contexts = fixturesToContext(fixtures);
    const result = contexts.length
      ? expectedPointsMulti(p, contexts, { teamsById, leagueAvg, ictPercentiles: ictPct })
      : { total: null, perFixture: [] };
    return { fixtures, ...result };
  });

  const rows = [
    { label: "מחיר", get: p => p.price, fmt: v => `£${v.toFixed(1)}`, higherIsBetter: false },
    { label: "פורם", get: p => p.form, fmt: v => v },
    { label: "נקודות עונה שעברה", get: p => p.points, fmt: v => v },
    { label: "PPM", get: p => (p.points / p.price), fmt: v => v.toFixed(2) },
    { label: "xG (עונה)", get: p => p.xg, fmt: v => v },
    { label: "xA (עונה)", get: p => p.xa, fmt: v => v },
    { label: "ICT", get: p => p.ict, fmt: v => v },
    { label: "בעלות", get: p => p.owned, fmt: v => `${v}%`, higherIsBetter: null },
  ];

  let html = `<div class="table-wrap"><table><thead><tr><th></th>`;
  for (const p of players) html += `<th class="team-cell">${teamCrestImg(teamsById.get(p.team))}${p.name}</th>`;
  html += `</tr></thead><tbody>`;

  for (const row of rows) {
    const values = players.map(row.get);
    html += `<tr><td>${row.label}</td>`;
    values.forEach(v => {
      const cls = row.higherIsBetter === null ? "" : winnerClass(values, v, row.higherIsBetter);
      html += `<td class="${cls}">${v == null ? naOr(null) : row.fmt(v)}</td>`;
    });
    html += `</tr>`;
  }

  const xptsNextValues = xptsData.map(x => x.perFixture[0]?.total ?? null);
  html += `<tr><td>xPts - המשחק הבא</td>`;
  xptsNextValues.forEach(v => {
    html += `<td class="${winnerClass(xptsNextValues, v)}">${naOr(v)}</td>`;
  });
  html += `</tr>`;

  const xpts3Values = xptsData.map(x => x.total);
  html += `<tr><td>xPts - 3 מחזורים</td>`;
  xpts3Values.forEach(v => {
    html += `<td class="${winnerClass(xpts3Values, v)}">${naOr(v)}</td>`;
  });
  html += `</tr>`;

  html += `</tbody></table></div>`;

  html += `<h2>לוח משחקים מקביל</h2><div class="table-wrap"><table><thead><tr><th></th><th>+1</th><th>+2</th><th>+3</th></tr></thead><tbody>`;
  players.forEach((p, i) => {
    html += `<tr><td class="team-cell">${teamCrestImg(state.teamsById.get(p.team))}${p.name}</td>`;
    for (let j = 0; j < 3; j++) {
      const f = xptsData[i].fixtures[j];
      html += f
        ? `<td><span class="${fdrClass(f.diff)}">${f.opp}${f.isHome ? "" : "*"}</span></td>`
        : `<td>-</td>`;
    }
    html += `</tr>`;
  });
  html += `</tbody></table></div>`;

  container.innerHTML = html;
}

function renderAll() {
  renderChips();
  renderComparisonTable();
}

export function setupCompareTab() {
  populateDatalist();
  selectedIds = loadSaved();

  const input = document.getElementById("comparePlayerInput");
  input.addEventListener("change", () => {
    const id = nameToId.get(input.value);
    if (id !== undefined) {
      addPlayer(id);
      input.value = "";
    }
  });

  renderAll();
}
