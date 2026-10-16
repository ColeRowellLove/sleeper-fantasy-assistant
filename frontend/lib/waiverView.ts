import type { WaiverWireData, WireEntry } from "./api";

export type WireView = "top" | "QB" | "RB" | "WR" | "TE" | "FLEX" | "K" | "DEF";

export const VIEWS: { value: WireView; label: string }[] = [
  { value: "top", label: "Top adds" },
  { value: "QB", label: "QB" },
  { value: "RB", label: "RB" },
  { value: "WR", label: "WR" },
  { value: "TE", label: "TE" },
  { value: "FLEX", label: "Flex" },
  { value: "K", label: "K" },
  { value: "DEF", label: "DEF" },
];

const FLEX = ["RB", "WR", "TE"];

/** The entries of one view: the mixed best-of list, one position, or the flex positions together. */
export function entriesFor(data: WaiverWireData, view: WireView): WireEntry[] {
  if (view === "top") {
    const top = data.top ?? [];
    // the server's mixed list (in its own order); without it, the best few of everything
    const mixed = top
      .map((id) => data.entries.find((e) => e.player_id === id))
      .filter((e): e is WireEntry => e !== undefined);
    return mixed.length > 0 ? mixed : data.entries.slice(0, 10);
  }
  if (view === "FLEX") return data.entries.filter((e) => FLEX.includes(e.position ?? ""));
  return data.entries.filter((e) => e.position === view);
}

/** "For", "Against" or "Note": the word shown with a reason so colour is never the only cue. */
export function stanceWord(stance: "for" | "against" | "info"): string {
  return stance === "for" ? "For" : stance === "against" ? "Against" : "Note";
}
