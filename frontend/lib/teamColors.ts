/** The CSS variable (in `tokens.css`) holding each NFL team's main colour; no logos or assets. */
const CODES = new Set([
  "ARI",
  "ATL",
  "BAL",
  "BUF",
  "CAR",
  "CHI",
  "CIN",
  "CLE",
  "DAL",
  "DEN",
  "DET",
  "GB",
  "HOU",
  "IND",
  "JAX",
  "KC",
  "LV",
  "LAC",
  "LAR",
  "MIA",
  "MIN",
  "NE",
  "NO",
  "NYG",
  "NYJ",
  "PHI",
  "PIT",
  "SF",
  "SEA",
  "TB",
  "TEN",
  "WAS",
]);

const ALIASES: Record<string, string> = { JAC: "JAX", LA: "LAR", WSH: "WAS", OAK: "LV" };

/** The team's colour as a CSS `var(--team-xx)`, or null for a free agent or an unknown code. */
export function teamColor(team: string | null | undefined): string | null {
  if (!team) return null;
  const code = team.toUpperCase();
  const known = ALIASES[code] ?? code;
  return CODES.has(known) ? `var(--team-${known.toLowerCase()})` : null;
}
