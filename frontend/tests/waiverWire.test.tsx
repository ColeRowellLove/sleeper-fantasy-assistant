import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import WaiverWirePanel, { backingLabel, waiverDateLabel } from "../components/WaiverWirePanel";
import type { Dashboard, WaiverWireData, WireEntry } from "../lib/api";
import { parseTab } from "../lib/league";
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
  backing: 1,
  signals: [
    { source: "Sleeper trending adds", backs: true, detail: "added in 8,200 leagues" },
    { source: "NFL depth chart", backs: false, detail: "no starter out ahead of him" },
  ],
  ...over,
});

const data: WaiverWireData = {
  league_id: "1",
  roster_id: 1,
  waiver_date: "2026-10-20",
  waiver_day: "Tuesday",
  week: 7,
  entries: [entry(), entry({ player_id: "p2", name: "Free Back", backing: 1, owned: null })],
  note: null,
};

const panel = (d: WaiverWireData | null) => (
  <WaiverWirePanel data={d} rosters={rosters} leagueId="1" rosterId={1} myRosterId={1} />
);

describe("waiver wire", () => {
  it("is a tab, reachable by its key", () => {
    expect(parseTab("waiver")).toBe("waiver");
  });

  it("labels the date and the count in words", () => {
    expect(waiverDateLabel("2026-10-20")).toBe("Tue, Oct 20");
    expect(waiverDateLabel("nope")).toBe("nope");
    expect(backingLabel(entry())).toBe("Also backed by 1 of 2 other signals");
  });

  it("lists the adds best first with their numbers and every signal as text", () => {
    render(panel(data));
    expect(
      screen.getByText(/Best adds for the Tuesday \(Tue, Oct 20\) waivers/),
    ).toBeInTheDocument();
    const items = screen
      .getAllByRole("listitem")
      .filter((li) => li.classList.contains("wire-entry"));
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByRole("link", { name: "Tyler Horton" })).toBeInTheDocument();
    expect(
      within(items[0]).getByText(/Projected 11.4, \+4.2 over Second Receiver at WR/),
    ).toBeInTheDocument();
    expect(within(items[0]).getByText("Also backed by 1 of 2 other signals.")).toBeInTheDocument();
    expect(within(items[0]).getByText(/Owned in 42% of ESPN leagues/)).toBeInTheDocument();
    expect(within(items[0]).getByText(/Sleeper trending adds:/)).toBeInTheDocument();
    expect(within(items[1]).queryByText(/Owned in/)).not.toBeInTheDocument();
    expect(within(items[0]).getAllByText("Backs it")).toHaveLength(1);
    expect(within(items[0]).getByText("Does not back it")).toBeInTheDocument();
  });

  it("picks the team with a labelled GET form", () => {
    render(panel(data));
    const select = screen.getByRole("combobox", { name: /Team/ });
    expect(select).toHaveValue("1");
    expect(screen.getByRole("option", { name: "Cole (you)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show waiver wire" })).toBeInTheDocument();
  });

  it("reaches the team picker and its button with the keyboard", async () => {
    const user = userEvent.setup();
    render(panel(data));
    await user.tab();
    expect(screen.getByRole("combobox", { name: /Team/ })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Show waiver wire" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Tyler Horton" })).toHaveFocus();
  });

  it("explains an empty list and a failed load", () => {
    const { rerender } = render(
      panel({ ...data, entries: [], note: "Projections are not out yet." }),
    );
    expect(screen.getByText("Projections are not out yet.")).toBeInTheDocument();
    rerender(panel(null));
    expect(screen.getByText(/could not be loaded/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(panel(data));
    await expectNoA11yViolations(panel({ ...data, entries: [], note: "None." }));
  });
});
