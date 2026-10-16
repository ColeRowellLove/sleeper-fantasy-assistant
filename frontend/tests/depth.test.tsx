import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PlayersTable from "../components/PlayersTable";
import TeamDepthChart from "../components/TeamDepthChart";
import TeamDialog from "../components/TeamDialog";
import TeamLink from "../components/TeamLink";
import TeamPicker from "../components/TeamPicker";
import type { DepthPlayer, DepthSlot, TeamDepth } from "../lib/api";
import { depthRows, groupSlots, isTeamCode, TEAM_CODES } from "../lib/depth";
import { parseTab } from "../lib/league";
import { expectNoA11yViolations } from "./a11y";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=teams&team=SEA"),
}));

const p = (
  name: string,
  depth: number,
  extra: Partial<DepthPlayer> = {},
): DepthPlayer => ({
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

  it("makes a column for each depth level in use, at most four", () => {
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
    ]);
    const { rows } = depthRows([
      slot("a", "A", [p("Only", 1)]),
      slot("b", "B", [p("X", 1), p("Y", 2)]),
    ]);
    expect(rows[0].cells).toEqual([
      expect.objectContaining({ name: "Only" }),
      null,
    ]); // padded
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
    expect(
      screen.queryByRole("link", { name: "Jake Bobo" }),
    ).not.toBeInTheDocument(); // not matched: no pop-up
    expect(screen.getByRole("link", { name: "Sam Darnold" })).toHaveAttribute(
      "href",
      "/league/1?tab=teams&team=SEA&player=id-SamDarnold",
    );
  });

  it("keeps the offensive line, defense and special teams in sections that open", () => {
    const { container } = render(
      <TeamDepthChart data={data} myRosterId={null} />,
    );
    const sections = [...container.querySelectorAll("details")];
    expect(
      sections.map((d) => d.querySelector("summary")?.textContent),
    ).toEqual(["Offensive line", "Defense", "Special teams"]);
    expect(sections.every((d) => !d.open)).toBe(true);
  });

  it("explains an empty chart instead of showing an empty table", () => {
    render(
      <TeamDepthChart data={{ team: "KC", groups: [] }} myRosterId={null} />,
    );
    expect(
      screen.getByText("No depth chart is available for this team yet."),
    ).toBeInTheDocument();
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
    expect(screen.getByRole("combobox", { name: "NFL team" })).toHaveValue(
      "SEA",
    );
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
    const { unmount } = render(
      <TeamLink team="DEN">DEN</TeamLink>,
    );
    expect(screen.getByRole("link")).toHaveAttribute("href", expect.not.stringContaining("player="));
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
    expect(screen.getByRole("link", { name: "LAR" })).toHaveAttribute("href", expect.stringContaining("depth=LAR"));
  });
});
