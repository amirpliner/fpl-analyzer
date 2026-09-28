import { state } from "../state.js";
import { fetchJSON } from "../data.js";
import { teamCrestImg } from "../helpers.js";

function timeAgo(iso) {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diffMs / 3600000);
  if (hours < 1) return "לפני פחות משעה";
  if (hours < 24) return `לפני ${hours} שעות`;
  const days = Math.floor(hours / 24);
  return `לפני ${days} ימים`;
}

export async function renderNewsFeed() {
  const newsContainer = document.getElementById("newsFeed");
  const hotContainer = document.getElementById("hotPlayersFeed");
  const data = await fetchJSON("data/news_feed.json");
  if (!data) {
    newsContainer.innerHTML = "";
    hotContainer.innerHTML = "";
    return;
  }

  if (!data.news.length) {
    newsContainer.innerHTML = `<p class="empty-state">אין כרגע עדכוני פציעות/זמינות.</p>`;
  } else {
    // Capped well below what the pipeline collects (news_feed.py can
    // surface up to 20) - this section is open by default, and a long
    // wall of red-bordered warning boxes was the single biggest
    // contributor to the "too much clutter" feel. The rest is one
    // click away in the news_feed.json data itself if ever needed.
    let html = `<div class="warnings-list">`;
    for (const n of data.news.slice(0, 8)) {
      const team = state.teamsById.get(n.team);
      html += `<div class="warning-item severity-high">
        ${teamCrestImg(team)}<strong>${n.web_name}</strong> (${team?.short_name || "?"}): ${n.news}
        <span class="na">· ${timeAgo(n.news_added)}</span>
      </div>`;
    }
    html += `</div>`;
    newsContainer.innerHTML = html;
  }

  if (!data.hot_players.length) {
    hotContainer.innerHTML = `<p class="empty-state">אין כרגע מגמת העברות בולטת.</p>`;
  } else {
    let html = `<div class="table-wrap"><table><thead><tr>
      <th>שחקן</th><th>קבוצה</th><th>פורם</th><th>נבחר ע"י</th><th>נטו העברות</th>
    </tr></thead><tbody>`;
    for (const p of data.hot_players.slice(0, 6)) {
      const team = state.teamsById.get(p.team);
      html += `<tr>
        <td>${p.web_name}</td>
        <td class="team-cell">${teamCrestImg(team)}${team?.short_name || "?"}</td>
        <td>${p.form}</td>
        <td>${p.owned}%</td>
        <td>+${p.net_transfers.toLocaleString("he-IL")}</td>
      </tr>`;
    }
    html += `</tbody></table></div>`;
    hotContainer.innerHTML = html;
  }
}
