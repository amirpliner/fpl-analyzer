# FPL מנתח — תוכנית שדרוג

## 1. מיפוי הקוד הקיים

### Frontend — `js/app.js` (388 שורות, קובץ יחיד כרגע)
| פונקציה | תפקיד |
|---|---|
| `fetchJSON` | fetch עם cache:no-store, מחזיר null בשגיאה |
| `fdrClass`, `fdrCellClass` | ממפים דירוג קושי (1-5) למחלקת CSS |
| `playerPrice` | now_cost/10 |
| `upcomingFixturesForTeam` | המשחקים הבאים של קבוצה מתוך fixtures.json |
| `fixtureRunScore` | ממוצע FDR ל-3 המחזורים הקרובים |
| `renderFdrTable`, `renderTopPlayers` | לשונית "ניתוח מחזור" |
| `renderManagerTeam`, `selectManager`, `renderMyTeam` | תפריט הבחירה + טבלת סגל בסיסית לכל מנהל בליגה |
| `renderMineAnalysis`, `naOr` | הצגת `analysis_mine.json` (כרטיס סיכום, טבלה, אזהרות, הצעות העברה) |
| `bestReplacement` | היוריסטיקה הישנה (form+FDR+points) שמזינה את `renderManagerTeam` הבסיסי |
| `renderLeague`, `setupTabs`, `init` | ליגת החברים + ניתוב לשוניות + bootstrap |

**נקודת הרחבה:** כרגע הכל גלובלי בקובץ אחד עם `state` משותף. הפיצול ל-ES Modules שביקשת אפשרי ללא שינוי התנהגות — `<script type="module" src="js/app.js">` ב-`index.html` יאפשר `import`/`export` בין קבצים, ו-GitHub Pages מגיש קבצי `.js` עם ה-MIME type הנכון אז זה יעבוד ללא build step. **וידאתי את זה — אין חסם.**

### Data pipeline — Python
- `scripts/fetch_data.py` (165 שורות): `get_json`, `save`, `current_event` (קובע gw נוכחי/הבא), `fetch_entry_picks` (per-manager), `resolve_my_squad` (API עם fallback ל-`my_squad.json`), `fetch_element_summaries`, `main`.
- `scripts/analysis.py` (279 שורות): כל הפונקציות הטהורות (`team_fixture_run`, `has_easy_run`, `minutes_trend`, `avg_minutes_last`, `injury_flag`, `analyze_player`, `team_exposure_warnings`, `captain_recommendations`, `transfer_suggestions`, `squad_rating`, `build_analysis`) — **כבר כתוב בסגנון שביקשת**: קלט=נתונים, פלט=ציונים, בלי side effects.
- `.github/workflows/update-data.yml`: cron יומי (5:00 UTC), מריץ עם `--league-id 367147`, מבצע commit+push אם יש שינוי.

### קבצי `/data` קיימים (סכימה בפועל)
```
bootstrap.json, fixtures.json          # גולמי מה-API, ללא עיבוד
league_367147.json                     # standings/new_entries גולמי
entry_<id>.json, entry_<id>_picks_gw<n>.json   # לכל אחד מ-17 חברי הליגה (רק לאחר דדליין)
config.json      = {managers:[{id,name,team_name}], league_id, picks_gw, has_mine_analysis}
meta.json         = {gameweek, is_upcoming}
my_squad.json / my_squad.example.json  # קלט ידני, {entry_id, gameweek, bank, free_transfers, picks:[{id,is_captain,is_vice,on_bench}]}
analysis_mine.json                     # פלט build_analysis() — הסכימה היחידה ה"מעובדת" שקיימת היום
```
**שים לב:** `players.json` הנפרד, `player_history.json`, `price_history.json`, `teams.json` שהמפרט מבקש — **אף אחד מהם לא קיים עדיין**. `analysis_mine.json` היום מכיל רק את הסגל שלי, לא את כל 700 השחקנים.

---

## 2. אימות שדות API אמיתי (לא מזיכרון) — נמשך עכשיו, פריסיזון

✅ **כל השדות שהמפרט מזכיר קיימים בפועל**: `expected_goals`, `expected_assists`, `expected_goal_involvements_per_90`, `expected_goals_conceded_per_90`, `ict_index`, `starts_per_90`, `chance_of_playing_next_round`, `status`, `news`, `penalties_order`, `direct_freekicks_order`, `corners_and_indirect_freekicks_order`, `transfers_in_event`, `transfers_out_event`, `cost_change_event`.

### ⚠️ שלושה ממצאים שמשפיעים ישירות על התכנון:

**א. שדות מספריים רבים הם מחרוזות, לא float** — `form`, `selected_by_percent`, `ict_index`, `creativity`, `influence`, `threat`, `expected_goals`, `expected_assists`, `expected_goal_involvements`, `points_per_game`, `value_form`, `value_season` כולם `'0.07'` ולא `0.07`. **חייב `float()` בכל מקום** — קוד קיים כבר עושה את זה בחלק מהמקומות, אבל מודולי xPts/planner/price חייבים להיות עקביים ב-100%.

**ב. `strength_attack_home/away` ו-`strength_defence_home/away` הם `0` לכל הקבוצות כרגע** (פריסיזון — FPL עוד לא אכלס אותם). `strength_overall_home/away` כן מאוכלסים (למשל ARS: 4/5). **זה שובר את נוסחת ה-xPts כפי שהוגדרה** (`opp_strength_factor` מנורמל לממוצע ליגה — חלוקה באפס/0 בכל מקום). **החלטה נדרשת:** מנוע ה-xPts חייב fallback דינמי — כשה-strength fields הם 0, להשתמש ב-FDR הגס (`team_h_difficulty`/`team_a_difficulty`, 1-5) כתחליף למקדם היריב, ולעבור אוטומטית לנוסחה העדינה ברגע ש-FPL יאכלסו את השדות (קורה בד"כ אחרי כמה מחזורים). **זה לא משהו שאפשר לדעת מראש מתי יקרה — המודול צריך לבדוק את זה בכל ריצה.**

**ג. `history` (פר-מחזור, העונה הנוכחית) ריק לגמרי כרגע. `history_past` הוא צבירה **של עונה שלמה** (רשומה אחת ל-2025/26, לא פר-מחזור).** המשמעות: **אין שום דרך** לחשב `last5_minutes`, `minutes_trend`, ספארקליין דקות, `rotation_risk`, או `price momentum` פר-מחזור לפני שמשחקים אמיתיים יתקיימו — לא משנה איזה fallback נבחר. זה בדיוק התנהגות "אין נתון" שכבר קיימת ב-`analysis.py` (`minutes_trend` מחזיר `None`) — נשמור על העיקרון הזה בכל מודול חדש, כולל ב-UI ("אין נתון עדיין" ולא ערך מומצא).

**מסקנה מעשית:** אפשר ומומלץ לבנות את כל מנוע ה-xPts, ה-planner, ומנוע הצ'יפים **עכשיו**, אבל:
- ה-**backtest** (סעיף "כיול") לא יניב שום דבר עד שמחזור 1 יסתיים (21.8+) ויהיו נתוני `finished:true` אמיתיים להשוואה.
- **פיצ'ר 4 (התראות מחיר)** דורש היסטוריה שנצברת מריצה לריצה — יתחיל ריק ויבנה את עצמו יום אחרי יום מרגע הפריסה; לא יהיה שימושי בשבועות הראשונים.
- **פיצ'ר 7 (EO בליגה)** דורש picks של 17 החברים — כרגע ריק (אחרי הדדליין ב-21.8 יתמלא לבד, כמו ש-`config.json` כבר עושה היום ל-`renderManagerTeam`).

---

## 3. תוכנית שלבים (עדיפויות שלך, A→B→C, commit נפרד לכל שלב)

| # | שלב | תלוי ב-נתונים אמיתיים? | תוצר |
|---|---|---|---|
| A1 | הרחבת pipeline: `teams.json`, `players.json` (כל 700, מוגבל ~500KB), `player_history.json` (סגל שלי+ליגה+top200, עם sleep/retry/cache), `fixtures.json`+DGW/BGW, `price_history.json` (מתחיל ריק) | לא | קבצי JSON חדשים |
| A2 | פיצוץ `app.js` ל-ES Modules (`data.js` + `models/` + `ui/`) — ריפקטור בלבד, בלי שינוי פיצ'רים | לא | מבנה קבצים חדש |
| A3 | פיצ'ר 1: ניתוח שחקן מעמיק ב-UI (xG/xA/ICT/ספארקליין/rotation tag/כדורי-רגל) | חלקית — ספארקליין יראה "אין נתון" עד שיהיו משחקים | UI מורחב |
| A4 | מנוע xPts (`models/xpts.js`) + fallback ל-FDR כשstrength=0 + `scripts/backtest_xpts.py` | המנוע לא, ה-backtest כן (לא ירוץ משמעותית לפני 21.8+) | מודול + סקריפט |
| A5 | פיצ'ר 6: קפטן מומלץ משודרג עם xPts + פירוק ציון | לא | UI |
| A6 | פיצ'ר 8: תזכורות דדליין (Notification API + קובץ .ics) | לא | UI |
| B7 | פיצ'ר 5: השוואת שחקנים side-by-side | לא | UI |
| B8 | פיצ'ר 4: התראות שינוי מחיר + Action כל שעה | כן — יתחיל חלש, ישתפר עם הזמן | pipeline+UI |
| B9 | פיצ'ר 7: תובנות מיני-ליגה (EO, טמפלייט, דיפרנציאלים אמיתיים) | כן — picks אחרי 21.8 | pipeline+UI |
| C10 | פיצ'ר 2: planner רב-מחזורי (beam search) | לא לבנייה, כן לתוצאות משמעותיות | מודול+UI |
| C11 | פיצ'ר 3: מנוע צ'יפים (DGW/BGW+status) | לא לבנייה | מודול+UI |

**הצעה:** מתחילים ב-A1 (יסודות הנתונים) כי הכל אחר תלוי בזה, עוצרים אחרי כל שלב לאישור בדיוק כמו שביקשת.

---

## 4. שאלות פתוחות לפני שמתחילים בפועל

1. **אישור על ה-fallback ל-FDR** כש-strength fields הם 0 (סעיף 2ב) — זו סטייה קלה מהנוסחה המדויקת שכתבת, נדרשת כדי שהמנוע לא יתן תוצאות שגויות/NaN כרגע.
2. **`element-summary` ל-~200+ שחקנים כל ריצה** (top 200 + סגלים) עם `sleep(0.4)` = כ-80-90 שניות ריצה נוספת ל-Action היומי. זה בסדר (Actions לrepo ציבורי חינם ללא הגבלה), רק מוודא שאתה מודע לזמן הריצה שיעלה.
3. **קנה המידה של כל זה** — זו תוכנית של 11 שלבים משמעותיים (חלקם כמו ה-planner הם בפועל אלגוריתם beam search לא טריוויאלי). מציע לעבוד שלב-שלב בדיוק כמו שכתבת, ולעצור לבדוק שהכיוון עדיין נכון כל כמה שלבים — לא רק טכנית אלא גם "זה עוד שימושי לך".

מאשר להתחיל ב-A1?
