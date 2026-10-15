export type Position = "QB" | "RB" | "WR" | "TE" | "K" | "DEF";

export const POSITIONS: Position[] = ["QB", "RB", "WR", "TE", "K", "DEF"];

const NAMES: Record<Position, string> = {
  QB: "Quarterback",
  RB: "Running back",
  WR: "Wide receiver",
  TE: "Tight end",
  K: "Kicker",
  DEF: "Defense",
};

export function positionName(position: Position): string {
  return NAMES[position];
}

/** CSS class that sets the --pos color variable for a position (neutral when unknown). */
export function positionClass(position: string | null | undefined): string {
  const key = (position ?? "").toLowerCase();
  return (POSITIONS as string[]).includes((position ?? "").toUpperCase()) ? `pos-${key}` : "pos-na";
}
