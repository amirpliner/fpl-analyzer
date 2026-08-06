export const POSITION_NAMES = { 1: "שוער", 2: "מגן", 3: "קשר", 4: "חלוץ" };
export const POSITION_CODES = { 1: "GKP", 2: "DEF", 3: "MID", 4: "FWD" };
export const FIXTURES_LOOKAHEAD = 5;

export const ROTATION_LABELS = {
  nailed: "קבוע",
  rotation: "רוטציה",
  cameo: "מחליף",
  unknown: "אין נתון",
};

export const state = {
  bootstrap: null,
  fixtures: null,
  meta: null,
  config: null,
  teamsById: new Map(),
  playersById: new Map(),
  enrichedById: new Map(),
  activePos: 1,
};
