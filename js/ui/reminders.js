// Deadline reminders. IMPORTANT LIMITATION (shown in the UI, not just here):
// there's no push server, so browser notifications only fire while this
// tab stays open in the browser the whole time until the deadline. The
// .ics download is the reliable fallback - it works through the user's
// own calendar app regardless of whether the site is open.

const REMINDER_OFFSETS_MS = [
  { label: "24 שעות", ms: 24 * 60 * 60 * 1000 },
  { label: "3 שעות", ms: 3 * 60 * 60 * 1000 },
  { label: "שעה", ms: 1 * 60 * 60 * 1000 },
];

let scheduledTimers = [];

function clearScheduled() {
  scheduledTimers.forEach(clearTimeout);
  scheduledTimers = [];
}

export function scheduleBrowserReminders(deadlineIso, gwLabel) {
  clearScheduled();
  const deadline = new Date(deadlineIso).getTime();
  const now = Date.now();
  let scheduledCount = 0;

  for (const { label, ms } of REMINDER_OFFSETS_MS) {
    const fireAt = deadline - ms;
    const delay = fireAt - now;
    if (delay <= 0) continue;
    const timerId = setTimeout(() => {
      if (Notification.permission === "granted") {
        new Notification(`דדליין FPL בעוד ${label}`, {
          body: `${gwLabel} ננעל בעוד ${label}. בדוק את הקבוצה שלך!`,
          icon: "⚽",
        });
      }
    }, delay);
    scheduledTimers.push(timerId);
    scheduledCount++;
  }
  return scheduledCount;
}

function icsEscape(text) {
  return text.replace(/\\/g, "\\\\").replace(/,/g, "\\,").replace(/;/g, "\\;");
}

function toIcsUtc(date) {
  return date.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
}

export function buildIcs(deadlineIso, gwLabel) {
  const deadline = new Date(deadlineIso);
  const end = new Date(deadline.getTime() + 15 * 60 * 1000);
  const now = new Date();
  const uid = `fpl-deadline-${deadline.getTime()}@fpl-analyzer`;

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//FPL Analyzer//he",
    "BEGIN:VEVENT",
    `UID:${uid}`,
    `DTSTAMP:${toIcsUtc(now)}`,
    `DTSTART:${toIcsUtc(deadline)}`,
    `DTEND:${toIcsUtc(end)}`,
    `SUMMARY:${icsEscape(`דדליין FPL - ${gwLabel}`)}`,
    `DESCRIPTION:${icsEscape(`דדליין להעברות ובחירת קבוצה ל${gwLabel} בפנטזי פרימייר ליג`)}`,
    "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:דדליין FPL בעוד יום", "TRIGGER:-P1D", "END:VALARM",
    "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:דדליין FPL בעוד 3 שעות", "TRIGGER:-PT3H", "END:VALARM",
    "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:דדליין FPL בעוד שעה", "TRIGGER:-PT1H", "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return lines.join("\r\n");
}

export function downloadIcs(deadlineIso, gwLabel) {
  const ics = buildIcs(deadlineIso, gwLabel);
  const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "fpl-deadline.ics";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function formatTimeLeft(deadlineIso) {
  const diff = new Date(deadlineIso).getTime() - Date.now();
  if (diff <= 0) return "הדדליין עבר";
  const days = Math.floor(diff / (24 * 60 * 60 * 1000));
  const hours = Math.floor((diff % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
  if (days > 0) return `${days} ימים ו-${hours} שעות`;
  return `${hours} שעות`;
}

export function renderReminderWidget(container, meta) {
  if (!meta?.deadline_time) {
    container.innerHTML = "";
    return;
  }
  const gwLabel = `מחזור ${meta.gw_next ?? meta.gameweek ?? ""}`;
  const supported = "Notification" in window;
  const permission = supported ? Notification.permission : "unsupported";

  container.innerHTML = `
    <div class="reminder-widget">
      <div class="reminder-info">
        <strong>דדליין ${gwLabel}:</strong> ${formatTimeLeft(meta.deadline_time)}
        <div class="reminder-caveat">
          התראות דפדפן עובדות רק כשהטאב הזה פתוח (אין שרת push) - לתזכורת אמינה, תוסיף ליומן.
        </div>
      </div>
      <div class="reminder-actions">
        <button id="btnBrowserNotif" class="reminder-btn">
          ${permission === "granted" ? "✓ התראות דפדפן פעילות" : "🔔 הפעל התראות דפדפן"}
        </button>
        <button id="btnIcsDownload" class="reminder-btn secondary">הוסף ליומן</button>
      </div>
    </div>
  `;

  const notifBtn = document.getElementById("btnBrowserNotif");
  const icsBtn = document.getElementById("btnIcsDownload");

  if (!supported) {
    notifBtn.disabled = true;
    notifBtn.textContent = "התראות דפדפן לא נתמכות";
  } else if (permission === "granted") {
    scheduleBrowserReminders(meta.deadline_time, gwLabel);
  }

  notifBtn.addEventListener("click", async () => {
    if (!supported) return;
    const result = await Notification.requestPermission();
    if (result === "granted") {
      const count = scheduleBrowserReminders(meta.deadline_time, gwLabel);
      notifBtn.textContent = "✓ התראות דפדפן פעילות";
      notifBtn.title = `${count} תזכורות מתוזמנות`;
    } else {
      notifBtn.textContent = "🔔 הרשאה נדחתה - נסה שוב";
    }
  });

  icsBtn.addEventListener("click", () => downloadIcs(meta.deadline_time, gwLabel));
}
