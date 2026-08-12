import { state } from "./state.js";
import { fetchJSON } from "./data.js";
import { renderGwBadge, renderFdrTable, renderTopPlayers, renderPriceAlerts } from "./ui/gameweek.js";
import { renderMyTeam } from "./ui/myteam.js";
import { renderLeague, renderLeagueInsights } from "./ui/league.js";
import { renderReminderWidget } from "./ui/reminders.js";
import { setupCompareTab } from "./ui/compare.js";

function hideLoadingOverlay() {
  const overlay = document.getElementById("loadingOverlay");
  if (!overlay) return;
  overlay.classList.add("hidden");
  overlay.addEventListener("transitionend", () => overlay.remove(), { once: true });
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

  const [bootstrap, fixtures, meta, config, players] = await Promise.all([
    fetchJSON("data/bootstrap.json"),
    fetchJSON("data/fixtures.json"),
    fetchJSON("data/meta.json"),
    fetchJSON("data/config.json"),
    fetchJSON("data/players.json"),
  ]);

  if (!bootstrap || !fixtures) {
    document.getElementById("gwBadge").textContent = "אין נתונים - הרץ את scripts/fetch_data.py";
    hideLoadingOverlay();
    return;
  }

  state.bootstrap = bootstrap;
  state.fixtures = fixtures;
  state.meta = meta || {};
  state.config = config || {};
  state.teamsById = new Map(bootstrap.teams.map(t => [t.id, t]));
  state.playersById = new Map(bootstrap.elements.map(p => [p.id, p]));
  state.enrichedById = new Map((players || []).map(p => [p.id, p]));

  renderGwBadge();
  renderFdrTable();
  renderTopPlayers();
  renderPriceAlerts();
  renderMyTeam();
  renderLeague();
  renderLeagueInsights();
  renderReminderWidget(document.getElementById("reminderWidget"), state.meta);
  setupCompareTab();

  const lastUpdated = new Date().toLocaleString("he-IL");
  document.getElementById("lastUpdated").textContent = lastUpdated;

  hideLoadingOverlay();
}

init();
