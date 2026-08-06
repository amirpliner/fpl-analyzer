export const POSITION_NAMES = { 1: "שוער", 2: "מגן", 3: "קשר", 4: "חלוץ" };
export const FIXTURES_LOOKAHEAD = 5;

export const state = {
  bootstrap: null,
  fixtures: null,
  meta: null,
  config: null,
  teamsById: new Map(),
  playersById: new Map(),
  activePos: 1,
};
