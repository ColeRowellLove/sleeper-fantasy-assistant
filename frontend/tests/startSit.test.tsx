import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import StartSitTool from "../components/StartSitTool";
import type { BestLineup, Dashboard, StartSitCandidate, StartSitComparison } from "../lib/api";
import { parseTab } from "../lib/league";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=startsit"),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const cand = (over: Partial<StartSitCandidate> & Pick<StartSitCandidate, "player_id" | "name">) =>
  ({ position: "RB", team: "SF", sources: 2, ...over }) as StartSitCandidate;

const rosters: Dashboard["rosters"] = [
  {
    roster_id: 1,
    team: "Cole",
    owner_id: "u1",
    players: [
      {
        player_id: "1",
        name: "Star Back",
        position: "RB",
        team: "SF",
        status: "starter",
        slot: "RB",
      },
      {
        player_id: "2",
        name: "Bench Back",
        position: "RB",
        team: "SF",
        status: "bench",
        slot: null,
      },
      { player_id: "3", name: "Parked", position: "RB", team: "SF", status: "ir", slot: null },
    ],
  },
  { roster_id: 2, team: "Dad Bods", owner_id: "u2", players: [] },
];

const best: BestLineup = {
  league_id: "1",
  roster_id: 1,
  week: 6,
  lineup: [
    { slot: "RB", player: cand({ player_id: "2", name: "Bench Back", projected: 15 }) },
    { slot: "WR", player: null },
  ],
  projected: 15,
  current_projected: 9,
  changes: [
    {
      start: cand({ player_id: "2", name: "Bench Back", projected: 15 }),
      sit: cand({ player_id: "1", name: "Star Back", projected: 9 }),
      gain: 6,
    },
  ],
  why: "start Bench Back (projected 15.0) for Star Back (projected 9.0): +6.0",
};

const comparison: StartSitComparison = {
  league_id: "1",
  week: 6,
  start: "2",
  close_call: true,
  why: "Start Bench Back: projected 15.0. Over Star Back by +1.0 projected points. This is a close call.",
  candidates: [
    cand({ player_id: "2", name: "Bench Back", projected: 15, form: 12, rank: 3 }),
    cand({ player_id: "1", name: "Star Back", projected: 14, form: 10, rank: 4 }),
    cand({ player_id: "9", name: "Hurt Back", out: "listed Out" }),
  ],
};

const props = {
  leagueId: "1",
  rosters,
  rosterId: 1,
  picks: [],
  week: 6,
  best: null,
  comparison: null,
};

describe("Start/Sit tool", () => {
  it("is a tab", () => {
    expect(parseTab("startsit")).toBe("startsit");
  });

  it("offers the team's active players to compare, as a plain form that works without JavaScript", () => {
    render(<StartSitTool {...props} picks={["2"]} />);
    const group = screen.getByRole("group", { name: /Players to compare/ });
    expect(within(group).getByRole("checkbox", { name: /Star Back/ })).not.toBeChecked();
    expect(within(group).getByRole("checkbox", { name: /Bench Back/ })).toBeChecked();
    expect(within(group).queryByRole("checkbox", { name: /Parked/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Compare" }).closest("form")).toHaveAttribute(
      "method",
      "get",
    );
    expect(screen.getByRole("status")).toHaveTextContent("Pick at least two players");
  });

  it("shows each player as a row with his face, matchup, injury and projection", async () => {
    const withRoster: BestLineup = {
      ...best,
      roster: [
        cand({ player_id: "1", name: "Star Back", projected: 9.04 }),
        cand({ player_id: "2", name: "Bench Back", projected: null }),
      ],
    };
    const ui = <StartSitTool {...props} picks={["1"]} best={withRoster} />;
    const { container } = render(ui);
    const group = screen.getByRole("group", { name: /Players to compare/ });
    const rows = within(group).getAllByRole("checkbox");
    expect(rows).toHaveLength(2);
    expect(within(group).getByText("Proj 9.0")).toBeInTheDocument();
    expect(within(group).getByText("No projection yet")).toBeInTheDocument();
    expect(container.querySelectorAll(".pick-row .avatar")).toHaveLength(2);
    expect(rows[0]).toBeChecked();
    expect(within(group).queryByText(/Can't start/)).not.toBeInTheDocument();
    await expectNoA11yViolations(ui);
  });

  it("says why a player cannot be started, but not when he only lacks a projection", async () => {
    const withOut: BestLineup = {
      ...best,
      roster: [
        cand({ player_id: "9", name: "Hurt Back", projected: 12.3, out: "listed Out" }),
        cand({ player_id: "8", name: "No Data", projected: null, out: "no projection this week" }),
      ],
    };
    const ui = <StartSitTool {...props} best={withOut} />;
    render(ui);
    expect(screen.getByText(/Can't start: listed Out/)).toBeInTheDocument();
    expect(screen.getByText("No projection yet")).toBeInTheDocument();
    expect(screen.queryByText(/Can't start: no projection/)).not.toBeInTheDocument();
    await expectNoA11yViolations(ui);
  });

  it("shows the best lineup with the swaps and why", () => {
    render(<StartSitTool {...props} best={best} />);
    const table = screen.getByRole("table", { name: /Best projected lineup/ });
    expect(within(table).getByText("Bench Back")).toBeInTheDocument();
    expect(
      within(table).getByText("No one on this roster can fill this slot."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Projected 15.0 against 9.0 for the current lineup/),
    ).toBeInTheDocument();
    expect(screen.getByText(/\+6.0 projected points/)).toBeInTheDocument();
  });

  it("shows the recommendation, the reason and a verdict for each player", () => {
    render(<StartSitTool {...props} picks={["1", "2", "9"]} comparison={comparison} />);
    expect(screen.getByText(/This is a close call/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: /Players compared/ });
    expect(
      within(within(table).getByRole("row", { name: /Bench Back/ })).getByText(
        "Start (close call)",
      ),
    ).toBeInTheDocument();
    expect(
      within(within(table).getByRole("row", { name: /^Star Back/ })).getByText("Sit"),
    ).toBeInTheDocument();
    expect(within(table).getByText("Can't start: listed Out")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <StartSitTool {...props} picks={["1", "2"]} best={best} comparison={comparison} />,
    );
  });
});

describe("recommendation table", () => {
  it("shows the verdict as a short chip and says when no game was found", () => {
    const comparison2: StartSitComparison = {
      ...comparison,
      candidates: [cand({ player_id: "2", name: "Bench Back", projected: 15, game: null })],
    };
    const { container } = render(
      <StartSitTool {...props} picks={["2", "1"]} comparison={comparison2} />,
    );
    expect(container.querySelector(".verdict-start")).toHaveTextContent("Start (close call)");
    expect(screen.getByText("No game found")).toBeInTheDocument();
    expect(screen.getByText("Start (close call)")).toBeInTheDocument();
  });

  it("has no accessibility violations with start, sit and can't-start verdicts", async () => {
    await expectNoA11yViolations(
      <StartSitTool {...props} picks={["1", "2", "9"]} comparison={comparison} />,
    );
  });
});
