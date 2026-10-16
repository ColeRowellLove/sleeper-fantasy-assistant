import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import RankingsPanel from "../components/RankingsPanel";
import type { RankedPlayer, Rankings } from "../lib/api";
import { parseTab } from "../lib/league";
import {
  agreementText,
  parseRankPosition,
  parseSources,
  rankedFor,
  sourcesQuery,
} from "../lib/rankings";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=rankings&week=6"),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const player = (
  over: Partial<RankedPlayer> & Pick<RankedPlayer, "player_id" | "name">,
): RankedPlayer => ({
  position: "RB",
  team: "SF",
  signal_ranks: { projection: 1, form: 1 },
  rank: 1,
  flex_rank: 1,
  score: 1,
  spread: 0,
  sources: 2,
  why: "projected 15.0 (1st RB)",
  ...over,
});

const data: Rankings = {
  league_id: "1",
  week: 6,
  current_week: 6,
  weeks: [5, 6, 7],
  signals: { projection: "Sleeper projection", form: "Last three games", start: "ESPN start %" },
  players: [
    player({
      player_id: "1",
      name: "Mine Back",
      owner_roster_id: 1,
      owner_team: "Cole",
      projected: 15,
      form: 12.5,
      started_pct: 90,
      matchup: { opponent: "JAX", rank: 3, teams: 32, points: 24, games: 5 },
      game: { state: "upcoming", date: "2026-10-18", opponent: "JAX", home: true },
    }),
    player({ player_id: "2", name: "Free Back", rank: 2, flex_rank: 3, spread: 2, sources: 3 }),
    player({
      player_id: "3",
      name: "Wide One",
      position: "WR",
      rank: 1,
      flex_rank: 2,
      signal_ranks: { projection: 2 },
      sources: 1,
    }),
    player({ player_id: "4", name: "Quarter Back", position: "QB", flex_rank: null }),
  ],
};

describe("rankings helpers", () => {
  it("defaults to a valid position", () => {
    expect(parseRankPosition("WR")).toBe("WR");
    expect(parseRankPosition("nope")).toBe("RB");
    expect(parseRankPosition(undefined)).toBe("RB");
  });

  it("filters by position, pooling RB, WR and TE for FLEX, best first", () => {
    expect(rankedFor(data.players, "RB", "all", 1).map((p) => p.name)).toEqual([
      "Mine Back",
      "Free Back",
    ]);
    expect(rankedFor(data.players, "FLEX", "all", 1).map((p) => p.name)).toEqual([
      "Mine Back",
      "Wide One",
      "Free Back",
    ]);
  });

  it("keeps available players or the viewer's own", () => {
    expect(rankedFor(data.players, "RB", "available", 1).map((p) => p.name)).toEqual(["Free Back"]);
    expect(rankedFor(data.players, "RB", "mine", 1).map((p) => p.name)).toEqual(["Mine Back"]);
    expect(rankedFor(data.players, "RB", "mine", null)).toEqual([]);
  });

  it("says how much the sources agree", () => {
    expect(agreementText({ sources: 1, spread: 0 })).toBe("1 source");
    expect(agreementText({ sources: 3, spread: 0 })).toBe("3 sources agree");
    expect(agreementText({ sources: 3, spread: 1 })).toBe("3 sources, 1 place apart");
    expect(agreementText({ sources: 3, spread: 4 })).toBe("3 sources, 4 places apart");
  });

  it("is a tab", () => {
    expect(parseTab("rankings")).toBe("rankings");
  });
});

describe("RankingsPanel", () => {
  it("lists the position's players with the numbers behind each rank", () => {
    render(<RankingsPanel data={data} leagueId="1" myRosterId={1} />);
    const table = screen.getByRole("table", { name: /RB rankings for week 6/ });
    const row = within(table).getByRole("row", { name: /Mine Back/ });
    expect(within(row).getByText("15.0")).toBeInTheDocument();
    expect(within(row).getByText("12.5")).toBeInTheDocument();
    expect(within(row).getByText("90%")).toBeInTheDocument();
    expect(within(row).getByText("(3rd)")).toBeInTheDocument(); // the opponent's rank vs RBs
    expect(within(row).getByText("On your team")).toBeInTheDocument();
    expect(within(row).getByText("2 sources agree")).toBeInTheDocument();
    expect(within(table).getByText("3 sources, 2 places apart")).toBeInTheDocument();
    expect(within(table).getByText("Available")).toBeInTheDocument();
    expect(within(table).queryByText("Wide One")).not.toBeInTheDocument();
  });

  it("switches position and availability", async () => {
    const user = userEvent.setup();
    render(<RankingsPanel data={data} leagueId="1" myRosterId={1} />);
    await user.click(screen.getByRole("button", { name: "WR" }));
    expect(screen.getByRole("button", { name: "WR" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Wide One")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "RB" }));
    await user.click(screen.getByRole("button", { name: "Available" }));
    expect(screen.queryByText("Mine Back")).not.toBeInTheDocument();
    expect(screen.getByText("Free Back")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "My team" }));
    await user.click(screen.getByRole("button", { name: "QB" }));
    expect(screen.getByText("No players match these filters.")).toBeInTheDocument();
  });

  it("says projections have not loaded when there are no players at all", () => {
    render(<RankingsPanel data={{ ...data, players: [] }} leagueId="1" myRosterId={1} />);
    expect(screen.getByText(/projections have not loaded for this week yet/i)).toBeInTheDocument();
    expect(screen.queryByText("No players match these filters.")).not.toBeInTheDocument();
  });

  it("links the week chips back to the rankings tab", () => {
    render(<RankingsPanel data={data} leagueId="1" myRosterId={null} />);
    const nav = screen.getByRole("navigation", { name: "Week" });
    expect(within(nav).getByRole("link", { name: /7/ })).toHaveAttribute(
      "href",
      "/league/1?tab=rankings&week=7&pos=RB",
    );
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<RankingsPanel data={data} leagueId="1" myRosterId={1} />);
  });
});

describe("choosing which sources the ranks use", () => {
  const withSources: Rankings = {
    ...data,
    signals: {
      projection: "Sleeper projection",
      form: "Last three games",
      start: "ESPN start %",
      vegas: "Vegas implied points",
    },
    selected: ["projection", "vegas"],
    unavailable: { fantasypros: "FantasyPros (not connected: needs a license)" },
  };

  it("offers every available source as a checkbox with the chosen ones ticked", () => {
    render(<RankingsPanel data={withSources} leagueId="1" myRosterId={1} />);
    const group = screen.getByRole("group", { name: "Ranked by" });
    expect(within(group).getByRole("checkbox", { name: "Sleeper projection" })).toBeChecked();
    expect(within(group).getByRole("checkbox", { name: "Vegas implied points" })).toBeChecked();
    expect(within(group).getByRole("checkbox", { name: "Last three games" })).not.toBeChecked();
    expect(within(group).getByRole("checkbox", { name: "ESPN start %" })).not.toBeChecked();
  });

  it("is a plain GET form that keeps the tab, week and position", async () => {
    const user = userEvent.setup();
    render(<RankingsPanel data={withSources} leagueId="1" myRosterId={1} />);
    await user.click(screen.getByRole("button", { name: "WR" }));
    const button = screen.getByRole("button", { name: "Update rankings" });
    const form = button.closest("form") as HTMLFormElement;
    expect(form).toHaveAttribute("method", "get");
    expect(form).toHaveAttribute("action", "/league/1");
    const fields = Object.fromEntries(
      [...form.querySelectorAll<HTMLInputElement>('input[type="hidden"]')].map((i) => [
        i.name,
        i.value,
      ]),
    );
    expect(fields).toEqual({ tab: "rankings", week: "6", pos: "WR" });
  });

  it("says which sources are not connected instead of faking them", () => {
    render(<RankingsPanel data={withSources} leagueId="1" myRosterId={1} />);
    expect(screen.getByText(/Not included yet: FantasyPros/)).toBeInTheDocument();
  });

  it("shows source checkboxes as small controls beside their labels", () => {
    render(<RankingsPanel data={withSources} leagueId="1" myRosterId={1} />);
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.length).toBeGreaterThan(0);
    for (const box of boxes) expect(box.closest("label")).not.toBeNull();
  });

  it("says which sources the ranks come from, and keeps them on the week links", () => {
    render(<RankingsPanel data={withSources} leagueId="1" myRosterId={1} />);
    expect(
      screen.getByText(/ranked by Sleeper projection, Vegas implied points/),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("navigation", { name: "Week" })).getByRole("link", { name: /7/ }),
    ).toHaveAttribute("href", "/league/1?tab=rankings&week=7&sources=projection,vegas&pos=RB");
  });

  it("omits the sources query when every source is chosen", () => {
    const all = { ...withSources, selected: Object.keys(withSources.signals) };
    render(<RankingsPanel data={all} leagueId="1" myRosterId={1} />);
    expect(
      within(screen.getByRole("navigation", { name: "Week" })).getByRole("link", { name: /7/ }),
    ).toHaveAttribute("href", "/league/1?tab=rankings&week=7&pos=RB");
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<RankingsPanel data={withSources} leagueId="1" myRosterId={1} />);
  });
});

describe("source helpers", () => {
  it("leaves the query empty for all or none and lists the chosen ones in order", () => {
    const all = ["projection", "form", "vegas"];
    expect(sourcesQuery(all, all)).toBe("");
    expect(sourcesQuery([], all)).toBe("");
    expect(sourcesQuery(["vegas", "projection"], all)).toBe("projection,vegas");
  });

  it("keeps only well-formed names from the URL", () => {
    expect(parseSources("projection,vegas")).toEqual(["projection", "vegas"]);
    expect(parseSources(["form", "vegas"])).toEqual(["form", "vegas"]);
    expect(parseSources("bad;drop,Form,vegas")).toEqual(["vegas"]);
    expect(parseSources(undefined)).toEqual([]);
  });
});
