import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import WaiverWirePanel, { reasonCounts, waiverDateLabel } from "../components/WaiverWirePanel";
import type { Dashboard, WaiverWireData, WireEntry } from "../lib/api";
import { parseTab } from "../lib/league";
import { entriesFor, stanceWord } from "../lib/waiverView";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=waiver"),
  useRouter: () => ({ refresh: vi.fn(), replace: vi.fn(), push: vi.fn() }),
}));

const rosters: Dashboard["rosters"] = [
  { roster_id: 1, team: "Cole", owner_id: "u1", players: [] },
  { roster_id: 2, team: "Dad Bods", owner_id: "u2", players: [] },
];

const entry = (over: Partial<WireEntry> = {}): WireEntry => ({
  player_id: "p1",
  name: "Tyler Horton",
  position: "WR",
  team: "SEA",
  projected: 11.4,
  gain: 4.2,
  slot: "WR",
  over: "over Second Receiver at WR",
  reason: "projected 11.4",
  owned: 41.5,
  for_count: 2,
  against_count: 1,
  reasons: [
    { stance: "for", label: "Adds points", detail: "projected 11.4, +4.2 over Second Receiver" },
    { stance: "for", label: "Trending adds", detail: "added in 8,200 leagues today" },
    { stance: "against", label: "Tough matchup", detail: "JAX defense ranks 30th of 32" },
    { stance: "info", label: "Ownership", detail: "owned in 42% of ESPN leagues" },
  ],
  ...over,
});

const data: WaiverWireData = {
  league_id: "1",
  roster_id: 1,
  waiver_date: "2026-10-20",
  waiver_day: "Tuesday",
  week: 7,
  entries: [
    entry(),
    entry({ player_id: "p2", name: "Free Back", position: "RB", for_count: 1, against_count: 0 }),
    entry({ player_id: "d1", name: "CLE defense", position: "DEF", team: "CLE" }),
  ],
  top: ["p1", "d1"],
  note: null,
};

const panel = (d: WaiverWireData | null) => (
  <WaiverWirePanel data={d} rosters={rosters} leagueId="1" rosterId={1} myRosterId={1} />
);

describe("waiver wire", () => {
  it("is a tab, reachable by its key", () => {
    expect(parseTab("waiver")).toBe("waiver");
  });

  it("labels the date and the counts in words", () => {
    expect(waiverDateLabel("2026-10-20")).toBe("Tue, Oct 20");
    expect(waiverDateLabel("nope")).toBe("nope");
    expect(reasonCounts(entry())).toBe("2 for, 1 against");
    expect(stanceWord("for")).toBe("For");
    expect(stanceWord("against")).toBe("Against");
    expect(stanceWord("info")).toBe("Note");
  });

  it("starts with the mixed top adds in the server's order", () => {
    render(panel(data));
    const items = screen
      .getAllByRole("listitem")
      .filter((li) => li.classList.contains("wire-entry"));
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByRole("link", { name: "Tyler Horton" })).toBeInTheDocument();
    expect(within(items[1]).getByRole("link", { name: "CLE defense" })).toBeInTheDocument();
  });

  it("switches between position views", async () => {
    const user = userEvent.setup();
    render(panel(data));
    const group = screen.getByRole("group", { name: "Position" });
    expect(within(group).getByRole("button", { name: "Top adds" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(within(group).getByRole("button", { name: "RB" }));
    expect(screen.getByRole("link", { name: "Free Back" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Tyler Horton" })).not.toBeInTheDocument();
    await user.click(within(group).getByRole("button", { name: "Flex" }));
    expect(screen.getByRole("link", { name: "Free Back" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tyler Horton" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "CLE defense" })).not.toBeInTheDocument();
    await user.click(within(group).getByRole("button", { name: "QB" }));
    expect(
      screen.getByText(/Nobody available would improve this team at that position/),
    ).toBeInTheDocument();
  });

  it("builds the views from the data, with a fallback when the server sends no top list", () => {
    expect(entriesFor(data, "top").map((e) => e.player_id)).toEqual(["p1", "d1"]);
    expect(entriesFor({ ...data, top: undefined }, "top")).toHaveLength(3);
    expect(entriesFor(data, "FLEX").map((e) => e.player_id)).toEqual(["p1", "p2"]);
    expect(entriesFor(data, "DEF").map((e) => e.name)).toEqual(["CLE defense"]);
  });

  it("marks each reason For or Against in words, and keeps plain facts out of the chips", () => {
    render(panel(data));
    const first = screen
      .getAllByRole("listitem")
      .filter((li) => li.classList.contains("wire-entry"))[0];
    const chips = within(first).getByRole("list", { name: /2 for, 1 against/ });
    const text = within(chips)
      .getAllByRole("listitem")
      .map((li) => li.textContent);
    expect(text).toEqual(["For Adds points", "For Trending adds", "Against Tough matchup"]);
    expect(within(chips).getAllByRole("listitem")[2]).toHaveClass("reason-against");
    expect(within(chips).getAllByRole("listitem")[0]).toHaveClass("reason-for");
    // the sentences, including the plain ownership note, are under Details
    expect(within(first).getByText(/owned in 42% of ESPN leagues/)).toBeInTheDocument();
    expect(within(first).getByText("Details")).toBeInTheDocument();
  });

  it("shows the projection and the gain beside each name", () => {
    render(panel(data));
    const first = screen
      .getAllByRole("listitem")
      .filter((li) => li.classList.contains("wire-entry"))[0];
    expect(within(first).getByText("11.4")).toBeInTheDocument();
    expect(within(first).getByText("+4.2")).toBeInTheDocument();
  });

  it("picks the team with a labelled GET form", () => {
    render(panel(data));
    expect(screen.getByRole("combobox", { name: /Team/ })).toHaveValue("1");
    expect(screen.getByRole("option", { name: "Cole (you)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show waiver wire" })).toBeInTheDocument();
  });

  it("reaches the team picker, its button and the position chips with the keyboard", async () => {
    const user = userEvent.setup();
    render(panel(data));
    await user.tab();
    expect(screen.getByRole("combobox", { name: /Team/ })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Show waiver wire" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Top adds" })).toHaveFocus();
  });

  it("explains an empty list and a failed load", () => {
    const { rerender } = render(
      panel({ ...data, entries: [], top: [], note: "Projections are not out yet." }),
    );
    expect(screen.getByText("Projections are not out yet.")).toBeInTheDocument();
    rerender(panel(null));
    expect(screen.getByText(/could not be loaded/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(panel(data));
    await expectNoA11yViolations(panel({ ...data, entries: [], top: [], note: "None." }));
  });
});
