import type { GamePlayer } from "./api";

export interface StatColumn {
  label: string;
  /** Reads the cell's text from a player's stat line (one decimal for projections); null when empty. */
  get: (stats: Record<string, number>, projected?: boolean) => string | null;
}

const fmt = (n: number, projected: boolean) => (projected ? n.toFixed(1) : String(Math.round(n)));

// A stat that is present is shown even when it is 0 (a shutout, no interceptions); only a stat the
// player has no line for is empty. The server sends the keys below (games_view.STAT_KEYS).
const num =
  (key: string) =>
  (stats: Record<string, number>, projected = false) =>
    key in stats ? fmt(stats[key], projected) : null;

const pair =
  (made: string, tried: string) =>
  (stats: Record<string, number>, projected = false) =>
    made in stats || tried in stats
      ? `${fmt(stats[made] ?? 0, projected)}/${fmt(stats[tried] ?? 0, projected)}`
      : null;

export type GroupKey = "passing" | "scrimmage" | "kicking" | "defense";

export interface StatGroup {
  key: GroupKey;
  title: string;
  positions: string[];
  columns: StatColumn[];
}

/** How a game's players are laid out: one table per kind of stat, like a box score. */
export const GROUPS: StatGroup[] = [
  {
    key: "passing",
    title: "Passing",
    positions: ["QB"],
    columns: [
      { label: "C/A", get: pair("pass_cmp", "pass_att") },
      { label: "Yds", get: num("pass_yd") },
      { label: "TD", get: num("pass_td") },
      { label: "INT", get: num("pass_int") },
      { label: "Rush yds", get: num("rush_yd") },
    ],
  },
  {
    key: "scrimmage",
    title: "Rushing and receiving",
    positions: ["RB", "WR", "TE"],
    columns: [
      { label: "Car", get: num("rush_att") },
      { label: "Rush yds", get: num("rush_yd") },
      { label: "Rush TD", get: num("rush_td") },
      { label: "Tgt", get: num("rec_tgt") },
      { label: "Rec", get: num("rec") },
      { label: "Rec yds", get: num("rec_yd") },
      { label: "Rec TD", get: num("rec_td") },
    ],
  },
  {
    key: "kicking",
    title: "Kicking",
    positions: ["K"],
    columns: [
      { label: "FG", get: pair("fgm", "fga") },
      { label: "XP", get: pair("xpm", "xpa") },
    ],
  },
  {
    key: "defense",
    title: "Defense",
    positions: ["DEF"],
    columns: [
      { label: "Sacks", get: num("sack") },
      { label: "INT", get: num("int") },
      { label: "Fum rec", get: num("fum_rec") },
      { label: "TD", get: num("def_td") },
      { label: "Pts allowed", get: num("pts_allow") },
    ],
  },
];

const RANK: Record<string, number> = { QB: 0, RB: 1, WR: 2, TE: 3, K: 4, DEF: 5 };

/** A team's players for one table, best first (most points, then name). */
export function playersFor(group: StatGroup, players: GamePlayer[], team: string): GamePlayer[] {
  return players
    .filter((p) => p.team === team && group.positions.includes(p.position))
    .sort(
      (a, b) =>
        (RANK[a.position] ?? 9) - (RANK[b.position] ?? 9) ||
        (b.points ?? -1) - (a.points ?? -1) ||
        a.name.localeCompare(b.name),
    );
}
