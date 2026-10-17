/** Each NFL team's main colour, used only to tint the player pop-up's header (no logos or assets). */
const TEAM_COLORS: Record<string, string> = {
  ARI: "#97233f",
  ATL: "#a71930",
  BAL: "#5a3fc0",
  BUF: "#00338d",
  CAR: "#0085ca",
  CHI: "#c83803",
  CIN: "#fb4f14",
  CLE: "#ff3c00",
  DAL: "#003594",
  DEN: "#fb4f14",
  DET: "#0076b6",
  GB: "#2f6b57",
  HOU: "#a71930",
  IND: "#1f5fa8",
  JAX: "#006778",
  KC: "#e31837",
  LV: "#a5acaf",
  LAC: "#0080c6",
  LAR: "#2a5db0",
  MIA: "#008e97",
  MIN: "#4f2683",
  NE: "#1c4a8a",
  NO: "#d3bc8d",
  NYG: "#2a4ab5",
  NYJ: "#125740",
  PHI: "#004c54",
  PIT: "#ffb612",
  SF: "#aa0000",
  SEA: "#69be28",
  TB: "#d50a0a",
  TEN: "#4b92db",
  WAS: "#773141",
};

const ALIASES: Record<string, string> = { JAC: "JAX", LA: "LAR", WSH: "WAS", OAK: "LV" };

/** The team's colour as a hex string, or null for a free agent or an unknown code. */
export function teamColor(team: string | null | undefined): string | null {
  if (!team) return null;
  const code = team.toUpperCase();
  return TEAM_COLORS[ALIASES[code] ?? code] ?? null;
}
