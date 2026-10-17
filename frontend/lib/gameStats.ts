import type { GamePlayer } from "./api";

type Stats = Record<string, number>;

export interface StatColumn {
  label: string;
  /** Reads the cell's text from a player's stat line (one decimal for projections); null when empty. */
  get: (stats: Stats, projected?: boolean) => string | null;
  /** The team total over every player in the table; absent where a sum means nothing. */
  total?: (lines: Stats[], projected?: boolean) => string | null;
}

const fmt = (n: number, projected: boolean) => (projected ? n.toFixed(1) : String(Math.round(n)));

// A stat that is present is shown even when it is 0 (a shutout, no interceptions); only a stat the
// player has no line for is empty. The server sends the keys below (games_view.STAT_KEYS).
const num =
  (key: string): StatColumn["get"] =>
  (stats, projected = false) =>
    key in stats ? fmt(stats[key], projected) : null;

const sum =
  (key: string): StatColumn["total"] =>
  (lines, projected = false) =>
    fmt(
      lines.reduce((total, s) => total + (s[key] ?? 0), 0),
      projected,
    );

const withTotal = (label: string, key: string): StatColumn => ({
  label,
  get: num(key),
  total: sum(key),
});

const pair =
  (made: string, tried: string): StatColumn["get"] =>
  (stats, projected = false) =>
    made in stats || tried in stats
      ? `${fmt(stats[made] ?? 0, projected)}/${fmt(stats[tried] ?? 0, projected)}`
      : null;

/** Yards per attempt, one decimal, "–" when there were no attempts. */
const average =
  (yards: string, tries: string): StatColumn["get"] =>
  (stats) =>
    (stats[tries] ?? 0) > 0 ? ((stats[yards] ?? 0) / stats[tries]).toFixed(1) : null;

const averageTotal =
  (yards: string, tries: string): StatColumn["total"] =>
  (lines) => {
    const att = lines.reduce((t, s) => t + (s[tries] ?? 0), 0);
    const yds = lines.reduce((t, s) => t + (s[yards] ?? 0), 0);
    return att > 0 ? (yds / att).toFixed(1) : null;
  };

export type GroupKey = "passing" | "rushing" | "receiving" | "kicking" | "defense";

export interface StatGroup {
  key: GroupKey;
  title: string;
  /** Who belongs in this table: by his stat line (a receiver who also ran appears in both). */
  includes: (p: GamePlayer) => boolean;
  columns: StatColumn[];
}

const positive = (p: GamePlayer, ...keys: string[]) => keys.some((k) => (p.stats?.[k] ?? 0) > 0);

/** How a game's players are laid out: one table per kind of stat, like theScore's box score. */
export const GROUPS: StatGroup[] = [
  {
    key: "passing",
    title: "Passing",
    includes: (p) => positive(p, "pass_att", "pass_yd"),
    columns: [
      {
        label: "C/ATT",
        get: pair("pass_cmp", "pass_att"),
      },
      withTotal("Yds", "pass_yd"),
      withTotal("TD", "pass_td"),
      withTotal("INT", "pass_int"),
    ],
  },
  {
    key: "rushing",
    title: "Rushing",
    includes: (p) => positive(p, "rush_att", "rush_yd"),
    columns: [
      withTotal("Rsh", "rush_att"),
      withTotal("Yds", "rush_yd"),
      {
        label: "Avg",
        get: average("rush_yd", "rush_att"),
        total: averageTotal("rush_yd", "rush_att"),
      },
      withTotal("TD", "rush_td"),
    ],
  },
  {
    key: "receiving",
    title: "Receiving",
    includes: (p) => positive(p, "rec", "rec_tgt", "rec_yd"),
    columns: [
      withTotal("Rec", "rec"),
      withTotal("Yds", "rec_yd"),
      withTotal("TD", "rec_td"),
      withTotal("Tgt", "rec_tgt"),
    ],
  },
  {
    key: "kicking",
    title: "Kicking",
    includes: (p) => positive(p, "fga", "xpa", "fgm", "xpm"),
    columns: [
      { label: "FG", get: pair("fgm", "fga") },
      { label: "XP", get: pair("xpm", "xpa") },
    ],
  },
  {
    key: "defense",
    title: "Defense",
    includes: (p) => p.position === "DEF",
    columns: [
      { label: "Sacks", get: num("sack") },
      { label: "INT", get: num("int") },
      { label: "Fum rec", get: num("fum_rec") },
      { label: "TD", get: num("def_td") },
      { label: "Pts allowed", get: num("pts_allow") },
    ],
  },
];

/** A team's players for one table, most fantasy points first (then name). */
export function playersFor(group: StatGroup, players: GamePlayer[], team: string): GamePlayer[] {
  return players
    .filter((p) => p.team === team && group.includes(p))
    .sort((a, b) => (b.points ?? -1) - (a.points ?? -1) || a.name.localeCompare(b.name));
}

/** The team-total cells for a table, in column order; empty where a total means nothing. */
export function totalCells(group: StatGroup, players: GamePlayer[]): (string | null)[] {
  const projected = players.length > 0 && players.every((p) => p.projected);
  const lines = players.map((p) => p.stats ?? {});
  return group.columns.map((c) => c.total?.(lines, projected) ?? null);
}
