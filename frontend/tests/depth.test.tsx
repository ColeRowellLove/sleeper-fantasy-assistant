import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PlayersTable from "../components/PlayersTable";
import TeamDepthChart from "../components/TeamDepthChart";
import TeamDialog from "../components/TeamDialog";
import TeamLink from "../components/TeamLink";
import TeamLogo from "../components/TeamLogo";
import TeamPicker from "../components/TeamPicker";
import type { DepthPlayer, DepthSlot, GameInfo, TeamDepth, TeamStat } from "../lib/api";
import {
  depthLabel,
  depthRows,
  groupSlots,
  isTeamCode,
  recordText,
  TEAM_CODES,
} from "../lib/depth";
import { parseTab } from "../lib/league";
import { expectNoA11yViolations } from "./a11y";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=teams&team=SEA"),
}));

const p = (name: string, depth: number, extra: Partial<DepthPlayer> = {}): DepthPlayer => ({
  name,
  depth,
  label: depth === 1 ? "Starter" : `${depth}th string`,
  player_id: `id-${name.replace(/\s+/g, "")}`,
  ...extra,
});

const slot = (
  key: string,
  label: string,
  players: DepthPlayer[],
  extra: Partial<DepthSlot> = {},
) => ({
  slot: key,
  label,
  players,
  ...extra,
});

const data: TeamDepth = {
  team: "SEA",
  source: "ESPN",
  updated_at: "2026-10-16T01:45:00Z",
  game: { state: "upcoming", date: "2026-10-18", opponent: "DEN", home: true },
  groups: [
    {
      group: "offense",
      title: "Offense",
      slots: [
        slot("qb", "Quarterback", [p("Sam Darnold", 1), p("Drew Lock", 2)], {
          skill: true,
        }),
        slot(
          "wr1",
          "Wide receiver 1",
          [
            p("Jaxon Smith-Njigba", 1, {
              injury: { status: "Out", body_part: "Hamstring" },
            }),
            p("Tory Horton", 2, {
              next_up: true,
              owner_team: "Cole",
              owner_roster_id: 1,
            }),
            p("Jake Bobo", 3, { player_id: null }),
          ],
          {
            skill: true,
            note: "Jaxon Smith-Njigba is out: next up is Tory Horton",
          },
        ),
        slot("lt", "Left tackle", [p("Charles Cross", 1)]),
      ],
    },
    {
      group: "defense",
      title: "Defense",
      slots: [slot("lde", "Left defensive end", [p("Leonard Williams", 1)])],
    },
    {
      group: "special",
      title: "Special teams",
      slots: [slot("pk", "Kicker", [p("Jason Myers", 1)])],
    },
  ],
};

describe("depth helpers", () => {
  it("knows the 32 team codes", () => {
    expect(TEAM_CODES).toHaveLength(32);
    expect(isTeamCode("SEA")).toBe(true);
    expect(isTeamCode("XYZ")).toBe(false);
    expect(isTeamCode(undefined)).toBe(false);
  });

  it("labels any depth level", () => {
    expect([1, 2, 3, 4, 11, 12, 21, 22, 23].map(depthLabel)).toEqual([
      "Starter",
      "2nd string",
      "3rd string",
      "4th string",
      "11th string",
      "12th string",
      "21st string",
      "22nd string",
      "23rd string",
    ]);
  });

  it("makes a column for each depth level in use, however deep", () => {
    const wide = [
      slot(
        "a",
        "A",
        [1, 2, 3, 4, 5, 6].map((d) => p(`P${d}`, d)),
      ),
    ];
    expect(depthRows(wide).columns.map((c) => c.label)).toEqual([
      "Starter",
      "2nd string",
      "3rd string",
      "4th string",
      "5th string",
      "6th string",
    ]);
    const { rows } = depthRows([
      slot("a", "A", [p("Only", 1)]),
      slot("b", "B", [p("X", 1), p("Y", 2)]),
    ]);
    expect(rows[0].cells).toEqual([expect.objectContaining({ name: "Only" }), null]); // padded
  });

  it("puts the fantasy slots up front and the rest into their own sections", () => {
    const sections = groupSlots(data.groups);
    expect(sections.skill.map((s) => s.slot)).toEqual(["qb", "wr1"]);
    expect(sections.more.map((m) => m.title)).toEqual([
      "Offensive line",
      "Defense",
      "Special teams",
    ]);
    expect(groupSlots([])).toEqual({ skill: [], more: [] });
  });
});

describe("TeamDepthChart", () => {
  it("shows the chart with the team name, game, source and who is next up", () => {
    render(<TeamDepthChart data={data} myRosterId={null} />);
    expect(
      screen.getByRole("heading", { name: "Seattle Seahawks depth chart" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Source: ESPN/)).toBeInTheDocument();
    const fantasy = screen.getAllByRole("table")[0];
    const wr = within(fantasy).getByRole("row", { name: /Wide receiver 1/ });
    expect(
      within(wr).getByText("Jaxon Smith-Njigba is out: next up is Tory Horton"),
    ).toBeInTheDocument();
    expect(within(wr).getByText("Out")).toBeInTheDocument(); // the injury badge
    expect(within(wr).getByText("Next up")).toBeInTheDocument(); // a tag in words, not only color
  });

  it("marks players on your team, available players and players without a Sleeper match", () => {
    render(<TeamDepthChart data={data} myRosterId={1} />);
    expect(screen.getByText("On your team")).toBeInTheDocument();
    expect(screen.getAllByText("Available").length).toBeGreaterThan(0);
    expect(screen.getByText("Jake Bobo")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Jake Bobo" })).not.toBeInTheDocument(); // not matched: no pop-up
    expect(screen.getByRole("link", { name: "Sam Darnold" })).toHaveAttribute(
      "href",
      "/league/1?tab=teams&team=SEA&player=id-SamDarnold",
    );
  });

  it("shows one unit at a time: offense with its line folded away, then defense, then special teams", async () => {
    const user = userEvent.setup();
    const { container } = render(<TeamDepthChart data={data} myRosterId={null} />);
    const group = screen.getByRole("group", { name: "Unit" });
    expect(
      within(group)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["Offense", "Defense", "Special teams"]);
    expect(screen.getByText("Fantasy positions")).toBeInTheDocument();
    const folds = [...container.querySelectorAll("details")];
    expect(folds.map((d) => d.querySelector("summary")?.textContent)).toEqual(["Offensive line"]);
    expect(folds.every((d) => !d.open)).toBe(true);
    await user.click(within(group).getByRole("button", { name: "Defense" }));
    expect(screen.getByRole("heading", { name: "Defense" })).toBeInTheDocument();
    expect(screen.queryByText("Fantasy positions")).not.toBeInTheDocument();
    await user.click(within(group).getByRole("button", { name: "Special teams" }));
    expect(screen.getByRole("heading", { name: "Special teams" })).toBeInTheDocument();
  });

  it("shows only the stats of the chosen unit, and says so when it has none", async () => {
    const user = userEvent.setup();
    const stat = (key: string, label: string, side: string) =>
      ({ key, label, side, value: 10, rank: 3, teams: 32, games: 5 }) as TeamStat;
    render(
      <TeamDepthChart
        data={{
          ...data,
          stats: [
            stat("yards", "Total yards per game", "offense"),
            stat("sack", "Sacks per game", "defense"),
          ],
        }}
        myRosterId={null}
      />,
    );
    expect(screen.getByText("Total yards per game")).toBeInTheDocument();
    expect(screen.queryByText("Sacks per game")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Defense" }));
    expect(screen.getByText("Sacks per game")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Special teams" }));
    expect(screen.getByText("No special teams stats yet.")).toBeInTheDocument();
  });

  it("explains an empty chart instead of showing an empty table", () => {
    render(<TeamDepthChart data={{ team: "KC", groups: [] }} myRosterId={null} />);
    expect(screen.getByText("No depth chart is available for this team yet.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<TeamDepthChart data={data} myRosterId={1} />);
  });
});

describe("TeamPicker", () => {
  it("is a plain form that loads the teams tab for the chosen team", () => {
    const { container } = render(<TeamPicker leagueId="123" selected="SEA" />);
    const form = container.querySelector("form");
    expect(form).toHaveAttribute("method", "get");
    expect(form).toHaveAttribute("action", "/league/123");
    expect(container.querySelector("input[name=tab]")).toHaveValue("teams");
    expect(screen.getByRole("combobox", { name: "NFL team" })).toHaveValue("SEA");
    expect(screen.getAllByRole("option")).toHaveLength(33); // the prompt plus 32 teams
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<TeamPicker leagueId="123" selected={null} />);
  });
});

describe("teams tab", () => {
  it("is a known tab", () => {
    expect(parseTab("teams")).toBe("teams");
  });
});

describe("team pop-up", () => {
  const beforeEachDialog = () => {
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function close() {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    };
  };

  it("a team code is a link that opens that team's depth chart, keeping the page you are on", () => {
    render(<TeamLink team="LAR">LAR</TeamLink>);
    expect(screen.getByRole("link", { name: "LAR" })).toHaveAttribute(
      "href",
      "/league/1?tab=teams&team=SEA&depth=LAR",
    );
  });

  it("opening a team replaces an open player pop-up, and opening a player replaces a team", () => {
    // the mocked page already has a player open; a team link drops it
    const { unmount } = render(<TeamLink team="DEN">DEN</TeamLink>);
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      expect.not.stringContaining("player="),
    );
    unmount();
  });

  it("is an open, labelled modal with the team's chart and a Close button that comes first", () => {
    beforeEachDialog();
    render(<TeamDialog data={data} closeHref="/league/1?tab=players" myRosterId={1} />);
    const dialog = screen.getByRole("dialog", { name: "Seattle Seahawks depth chart" });
    expect(dialog).toHaveAttribute("open");
    expect(within(dialog).getByText("Quarterback")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
  });

  it("closes back to the page without the team, from the button or Escape", async () => {
    beforeEachDialog();
    const user = userEvent.setup();
    render(<TeamDialog data={data} closeHref="/league/1?tab=players" myRosterId={null} />);
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(replace).toHaveBeenCalledWith("/league/1?tab=players", { scroll: false });
    replace.mockClear();
    screen.getByRole("dialog", { hidden: true }).dispatchEvent(new Event("close")); // Escape
    expect(replace).toHaveBeenCalledWith("/league/1?tab=players", { scroll: false });
  });

  it("has no accessibility violations, even over a page that already has a depth chart", async () => {
    beforeEachDialog();
    await expectNoA11yViolations(
      <div>
        <TeamDepthChart data={data} myRosterId={null} />
        <TeamDialog data={data} closeHref="/league/1?tab=teams" myRosterId={null} />
      </div>,
    );
  });
});

describe("team codes in rows open the pop-up", () => {
  it("shows the team as a link in the Players tab and on rosters", () => {
    render(
      <PlayersTable
        data={{
          league_id: "1",
          week: 6,
          players: [
            {
              player_id: "1",
              name: "Puka Nacua",
              position: "WR",
              team: "LAR",
              owner_roster_id: null,
              owner_team: null,
              adds: null,
              drops: null,
              total_points: 10,
              rank: 1,
              projected: null,
            },
          ],
        }}
        myRosterId={null}
      />,
    );
    expect(screen.getByRole("link", { name: "LAR" })).toHaveAttribute(
      "href",
      expect.stringContaining("depth=LAR"),
    );
  });
});

describe("deep charts slide sideways", () => {
  const deep: TeamDepth = {
    ...data,
    groups: [
      {
        group: "offense",
        title: "Offense",
        slots: [
          slot(
            "rb",
            "Running back",
            [1, 2, 3, 4, 5].map((d) => p(`Back ${d}`, d)),
            {
              skill: true,
            },
          ),
        ],
      },
    ],
  };

  it("shows every level in a focusable, labelled scroll area with a hint", async () => {
    render(<TeamDepthChart data={deep} myRosterId={null} />);
    const area = screen.getByRole("group", {
      name: "Fantasy positions depth, 5 levels, scrolls sideways",
    });
    expect(area).toHaveAttribute("tabindex", "0");
    expect(within(area).getByRole("columnheader", { name: "5th string" })).toBeInTheDocument();
    expect(within(area).getByText("Back 5")).toBeInTheDocument();
    expect(screen.getByText("Slide sideways to see all 5 depth levels.")).toBeInTheDocument();
    await expectNoA11yViolations(<TeamDepthChart data={deep} myRosterId={null} />);
  });

  it("does not suggest sliding for a short chart", () => {
    render(<TeamDepthChart data={data} myRosterId={null} />);
    expect(screen.queryByText(/Slide sideways/)).not.toBeInTheDocument();
  });
});

describe("team stats with league ranks", () => {
  const stats: TeamStat[] = [
    {
      key: "rush_yd",
      label: "Rush yards per game",
      side: "offense",
      value: 142.5,
      rank: 2,
      teams: 32,
      games: 5,
    },
    {
      key: "pts_allow",
      label: "Points allowed per game",
      side: "defense",
      value: 17.2,
      rank: 1,
      teams: 32,
      games: 5,
    },
  ];

  it("shows a few stats as rank chips with the per-game number", async () => {
    render(<TeamDepthChart data={{ ...data, stats }} myRosterId={null} />);
    const chip = screen.getByText("Rush yards per game").closest("li") as HTMLElement;
    expect(chip).toHaveTextContent("2nd");
    expect(chip).toHaveTextContent("142.5");
    expect(screen.queryByText(/team stats$/)).not.toBeInTheDocument(); // nothing more to open
    await expectNoA11yViolations(<TeamDepthChart data={{ ...data, stats }} myRosterId={null} />);
  });

  it("keeps the first ten as chips and the full table under a disclosure", () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      ...stats[0],
      key: `s${i}`,
      label: `Stat ${i}`,
      rank: i + 1,
    }));
    render(<TeamDepthChart data={{ ...data, stats: many }} myRosterId={null} />);
    expect(document.querySelectorAll(".rank-chip")).toHaveLength(10);
    const more = screen.getByText("All 12 team stats").closest("details") as HTMLElement;
    expect(more).not.toHaveAttribute("open");
    const table = within(more).getByRole("table", { name: /per-game stats and league rank/ });
    expect(within(table).getAllByRole("row")).toHaveLength(13); // header and twelve stats
  });

  it("shows no stats section without data", () => {
    render(<TeamDepthChart data={data} myRosterId={null} />);
    expect(screen.queryByRole("heading", { name: "Team stats" })).not.toBeInTheDocument();
  });
});

describe("team logo and record", () => {
  it("writes the record, with ties only when there are some", () => {
    expect(recordText({ wins: 3, losses: 2, ties: 0 })).toEqual({
      short: "3-2",
      spoken: "Record: 3 wins and 2 losses",
    });
    expect(recordText({ wins: 1, losses: 1, ties: 1 })).toEqual({
      short: "1-1-1",
      spoken: "Record: 1 win, 1 loss and 1 tie",
    });
    expect(recordText({ wins: 0, losses: 1, ties: 2 }).spoken).toBe(
      "Record: 0 wins, 1 loss and 2 ties",
    );
  });

  it("shows the logo (decorative) and the record beside the title", async () => {
    const { container } = render(
      <TeamDepthChart
        data={{ ...data, record: { wins: 3, losses: 2, ties: 0 } }}
        myRosterId={null}
      />,
    );
    const heading = screen.getByRole("heading", { name: "Seattle Seahawks depth chart" });
    const title = heading.closest(".depth-title") as HTMLElement;
    const logo = title.querySelector("img");
    expect(logo).toHaveAttribute("alt", "");
    expect(logo?.getAttribute("src")).toContain("/team_logos/nfl/sea.png");
    expect(within(title).getByText("3-2")).toBeInTheDocument();
    expect(title).toHaveTextContent("Record: 3 wins and 2 losses"); // for screen readers
    expect(container.querySelectorAll(".depth-record")).toHaveLength(1);
    await expectNoA11yViolations(
      <TeamDepthChart
        data={{ ...data, record: { wins: 3, losses: 2, ties: 0 } }}
        myRosterId={null}
      />,
    );
  });

  it("shows another team's logo even after one logo failed to load", () => {
    const { rerender } = render(<TeamLogo team="SEA" />);
    fireEvent.error(document.querySelector("img") as HTMLImageElement);
    expect(document.querySelector("img")).toBeNull();
    rerender(<TeamLogo team="DEN" />);
    expect(document.querySelector("img")?.getAttribute("src")).toContain("/den.png");
  });

  it("leaves the record out when it is not known, and drops a logo that will not load", () => {
    render(<TeamDepthChart data={data} myRosterId={null} />);
    expect(document.querySelector(".depth-record")).toBeNull();
    const logo = document.querySelector(".depth-title img") as HTMLImageElement;
    fireEvent.error(logo);
    expect(document.querySelector(".depth-title img")).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Seattle Seahawks depth chart" }),
    ).toBeInTheDocument();
  });
});

describe("the unit on the field", () => {
  const liveGame = (team: string): GameInfo => ({
    state: "live",
    date: "2026-10-18",
    opponent: "DEN",
    home: true,
    team,
    situation: { possession: "SEA", down_distance: "1st & 10", ball_on: "SEA 35", red_zone: false },
  });

  it("marks the offense sections when the team has the ball", async () => {
    render(<TeamDepthChart data={{ ...data, game: liveGame("SEA") }} myRosterId={null} />);
    expect(screen.getAllByText("On the field now")).toHaveLength(2); // fantasy positions and the line
    expect(screen.getByText("SEA have the ball · 1st & 10 · at SEA 35")).toBeInTheDocument();
    await expectNoA11yViolations(
      <TeamDepthChart data={{ ...data, game: liveGame("SEA") }} myRosterId={null} />,
    );
  });

  it("marks the defense when the other team has the ball", async () => {
    const user = userEvent.setup();
    render(
      <TeamDepthChart
        data={{ ...data, game: { ...liveGame("SEA"), situation: { possession: "DEN" } } }}
        myRosterId={null}
      />,
    );
    expect(screen.queryByText("On the field now")).not.toBeInTheDocument(); // the offense is shown
    await user.click(screen.getByRole("button", { name: "Defense" }));
    expect(screen.getAllByText("On the field now")).toHaveLength(1);
  });

  it("marks nothing when the game is not live or ESPN has no situation", () => {
    render(<TeamDepthChart data={data} myRosterId={null} />);
    expect(screen.queryByText("On the field now")).not.toBeInTheDocument();
  });
});
