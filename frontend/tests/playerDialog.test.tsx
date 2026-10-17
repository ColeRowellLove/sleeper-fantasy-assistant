import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import PlayerDialog from "../components/PlayerDialog";
import PlayerLink from "../components/PlayerLink";
import type { PlayerDetail } from "../lib/api";
import {
  bioRows,
  describeStats,
  formatHeight,
  formatStat,
  rankText,
  statColumns,
  statTotals,
} from "../lib/playerDetail";
import { expectNoA11yViolations } from "./a11y";

const replace = vi.fn();
let search = "tab=players&week=6";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams(search),
}));

beforeAll(() => {
  // jsdom does not implement the modal dialog methods; this mirrors what they do to the element
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
});

beforeEach(() => {
  replace.mockClear();
  search = "tab=players&week=6";
});

const openTab = (name: string) => fireEvent.click(screen.getByRole("tab", { name }));

const detail: PlayerDetail = {
  player_id: "9493",
  name: "Puka Nacua",
  position: "WR",
  team: "LAR",
  injury: { status: "Questionable", body_part: "Knee" },
  game: { state: "upcoming", date: "2026-10-18", opponent: "SEA", home: true },
  bio: {
    age: 25,
    height: "74",
    weight: "216",
    college: "BYU",
    years_exp: 3,
    number: 12,
  },
  owner_roster_id: 1,
  owner_team: "Cole",
  owner_manager: "colerowell",
  league_id: "L1",
  team_stats: [
    {
      key: "rec_tgt",
      label: "Targets per game",
      side: "offense",
      value: 34.2,
      rank: 3,
      teams: 32,
      games: 5,
    },
  ],
  owned_pct: 99.9,
  started_pct: 25.9,
  adds: null,
  drops: 120,
  season: { points: 146.6, games: 5, average: 29.3, rank: 1 },
  projected: {
    week: 6,
    points: 22.5,
    stats: { rec: 6.6, rec_yd: 106.8, rec_td: 0.8, rec_tgt: 10 },
  },
  weeks: [
    {
      week: 1,
      team: "LAR",
      opponent: "SEA",
      home: true,
      points: 24.5,
      stats: { rec: 7, rec_yd: 90, rush_yd: 25 },
    },
    {
      week: 2,
      team: "LAR",
      opponent: "SF",
      home: false,
      points: 6,
      stats: { rec: 3, rec_yd: 30 },
    },
  ],
  past_seasons: [
    {
      season: "2025",
      games: 16,
      points: 200,
      rank: 2,
      teams: ["LAR", "SEA"],
      log: [
        {
          week: 1,
          team: "LAR",
          opponent: "HOU",
          home: true,
          points: 23.1,
          stats: { rec: 6, rec_yd: 85, rush_yd: 4 },
        },
        {
          week: 4,
          team: "SEA",
          opponent: "DEN",
          home: false,
          points: 10.4,
          stats: { rec: 4, rec_yd: 64 },
        },
      ],
    },
  ],
};

describe("player detail helpers", () => {
  it("formats height in feet and inches and leaves odd values as written", () => {
    expect(formatHeight("74")).toBe("6'2\"");
    expect(formatHeight(70)).toBe("5'10\"");
    expect(formatHeight("tall")).toBe("tall");
    expect(formatHeight(null)).toBeNull();
    expect(formatHeight("")).toBeNull();
  });

  it("lists only the bio facts Sleeper has, in plain words", () => {
    expect(bioRows(detail.bio)).toEqual([
      { label: "Age", value: "25" },
      { label: "Height", value: "6'2\"" },
      { label: "Weight", value: "216 lb" },
      { label: "College", value: "BYU" },
      { label: "Years in league", value: "3 years" },
      { label: "Jersey", value: "#12" },
    ]);
    expect(bioRows({ years_exp: 0 })).toEqual([{ label: "Years in league", value: "Rookie" }]);
    expect(bioRows({ depth_chart_position: "RWR", depth_chart_order: 1 })).toEqual([
      { label: "Depth chart", value: "RWR 1" },
    ]);
    expect(bioRows(null)).toEqual([]);
  });

  it("writes every counted stat in words, including a receiver's rushing yards", () => {
    expect(describeStats({ rush_yd: 25, rec_td: 1.5, rec_yd: 90, rec: 7 }, "WR")).toBe(
      "Catches 7, Rec yds 90, Rec TD 1.5, Rush yds 25",
    );
    expect(describeStats({})).toBe("No scoring stats");
  });

  it("puts each position's main stats first", () => {
    const line = {
      rec: 2,
      rec_yd: 20,
      rush_yd: 80,
      rush_att: 18,
      pass_yd: 250,
      pass_td: 2,
    };
    expect(describeStats(line, "QB")).toBe(
      "Pass yds 250, Pass TD 2, Carries 18, Rush yds 80, Catches 2, Rec yds 20",
    );
    expect(describeStats(line, "RB")).toBe(
      "Carries 18, Rush yds 80, Catches 2, Rec yds 20, Pass yds 250, Pass TD 2",
    );
    expect(describeStats({ fgm: 2, xpm: 3, fga: 3 }, "K")).toBe("FG att 3, FG made 2, XP made 3");
  });

  it("leaves out amounts too small to show, such as a 0.03 projected fumble", () => {
    expect(describeStats({ rec: 6.6, fum_lost: 0.03, rec_2pt: 0.04 }, "WR")).toBe("Catches 6.6");
  });

  it("writes rank as position plus number, and a dash when there is none", () => {
    expect(rankText("WR", 12)).toBe("WR12");
    expect(rankText("WR", null)).toBe("–");
    expect(rankText(null, 3)).toBe("–");
  });
});

describe("stat table helpers", () => {
  it("makes a column for every stat seen, main stats of the position first", () => {
    const lines: Record<string, number>[] = [
      { rush_yd: 156, rec: 5, rush_att: 29, rush_td: 2, fum_lost: 1 },
      { rec_yd: 61, rec: 6 },
    ];
    expect(statColumns(lines, "RB").map((c) => c.key)).toEqual([
      "rush_att",
      "rush_yd",
      "rush_td",
      "rec",
      "rec_yd",
      "fum_lost",
    ]);
    expect(statColumns(lines, "WR").map((c) => c.key)).toEqual([
      "rec",
      "rec_yd",
      "rush_att",
      "rush_yd",
      "rush_td",
      "fum_lost",
    ]);
  });

  it("gives no column to a stat that is zero or too small in every game", () => {
    const lines: Record<string, number>[] = [
      { rec: 4, fum_lost: 0, rec_2pt: 0.03 },
      { rec: 2, fum_lost: 0 },
    ];
    expect(statColumns(lines, "WR").map((c) => c.key)).toEqual(["rec"]);
  });

  it("formats cells and totals", () => {
    expect(formatStat(7)).toBe("7");
    expect(formatStat(6.64)).toBe("6.6");
    expect(formatStat(0)).toBe("–");
    expect(formatStat(0.02)).toBe("–");
    expect(formatStat(undefined)).toBe("–");
    expect(
      statTotals([
        { rec: 3, rush_yd: 10.5 },
        { rec: 4, rush_yd: 0.25 },
      ]),
    ).toEqual({
      rec: 7,
      rush_yd: 10.75,
    });
  });
});

describe("PlayerLink", () => {
  it("opens the pop-up on the same page, keeping the tab and week", () => {
    render(<PlayerLink playerId="9493">Puka Nacua</PlayerLink>);
    expect(screen.getByRole("link", { name: "Puka Nacua" })).toHaveAttribute(
      "href",
      "/league/1?tab=players&week=6&player=9493",
    );
  });

  it("replaces an earlier player rather than stacking", () => {
    search = "tab=lineups&player=111";
    render(<PlayerLink playerId="222">Next</PlayerLink>);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/league/1?tab=lineups&player=222");
  });
});

describe("PlayerDialog", () => {
  const renderDialog = (data: PlayerDetail = detail) =>
    render(<PlayerDialog detail={data} closeHref="/league/1?tab=players" />);

  it("is an open, labelled modal with the player's name", () => {
    renderDialog();
    const dialog = screen.getByRole("dialog", { name: "Puka Nacua" });
    expect(dialog).toHaveAttribute("open");
    expect(within(dialog).getByText(/^On/)).toHaveTextContent("On Cole (colerowell)");
  });

  it("shows the player's team rank chips with the per-game numbers", () => {
    renderDialog();
    openTab("Team");
    const dialog = screen.getByRole("dialog", { name: "Puka Nacua" });
    expect(within(dialog).getByRole("heading", { name: "LAR team rank" })).toBeInTheDocument();
    const chip = within(dialog).getByText("Targets per game").closest("li");
    expect(chip).toHaveTextContent("3rd");
    expect(chip).toHaveTextContent("34.2");
  });

  it("shows ESPN's ownership and start percentages, labelled as ESPN's", () => {
    renderDialog();
    const dialog = screen.getByRole("dialog", { name: "Puka Nacua" });
    expect(within(dialog).getByText("Owned").nextSibling).toHaveTextContent("99.9%");
    expect(within(dialog).getByText("Started").nextSibling).toHaveTextContent("25.9%");
  });

  it("shows a dash, never 0, when ESPN has no number for the player", () => {
    renderDialog({ ...detail, owned_pct: null, started_pct: undefined });
    const dialog = screen.getByRole("dialog", { name: "Puka Nacua" });
    expect(within(dialog).getByText("Owned").nextSibling).toHaveTextContent("–");
    expect(within(dialog).getByText("Started").nextSibling).toHaveTextContent("–");
  });

  it("links the owning team to its roster and says how long the player has been in the league", () => {
    renderDialog();
    const dialog = screen.getByRole("dialog", { name: "Puka Nacua" });
    expect(within(dialog).getByRole("link", { name: "Cole" })).toHaveAttribute(
      "href",
      "/league/L1?tab=rosters&roster=1",
    );
    expect(within(dialog).getByText("Exp").nextSibling).toHaveTextContent("3");
  });

  it("shows bio, season, projection, weekly log and past seasons", () => {
    renderDialog();
    expect(screen.getByRole("heading", { name: "Bio" })).toBeInTheDocument();
    expect(screen.getByText("BYU")).toBeInTheDocument();
    expect(screen.getByText("WR1")).toBeInTheDocument(); // position rank
    expect(screen.getByRole("heading", { name: "This week's game" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /projections by week/i })).toBeInTheDocument();
    expect(screen.getAllByText(/22\.5/).length).toBeGreaterThan(0); // the section and the table row
    expect(
      screen.getByText("Targets 10, Catches 6.6, Rec yds 106.8, Rec TD 0.8"),
    ).toBeInTheDocument();
    openTab("Game log");
    const weeks = screen.getByRole("table", {
      name: /every week of the season/i,
    });
    expect(within(weeks).getByText("SEA")).toBeInTheDocument(); // at home: the code alone
    expect(within(weeks).getByText("@SF")).toBeInTheDocument(); // away: "@" like Sleeper
    openTab("History");
    const past = screen.getByRole("table", { name: /under this league/i });
    expect(within(past).getByText("WR2")).toBeInTheDocument();
  });

  it("lays the weeks out as a stat table with one column per stat", () => {
    renderDialog();
    openTab("Game log");
    const table = screen.getByRole("table", {
      name: /every week of the season/i,
    });
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    // a receiver: targets and catches first, then yards, touchdowns, then the rushing yards he earned
    expect(headers).toEqual([
      "Wk",
      "Opp",
      "Pts",
      "Rank",
      "Targets",
      "Catches",
      "Rec yds",
      "Rec TD",
      "Rush yds",
    ]);
    const week1 = within(table).getByRole("row", { name: /^1 SEA/ });
    expect(
      within(week1)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["SEA", "24.5", "–", "–", "7", "90", "–", "25"]);
    const week2 = within(table).getByRole("row", { name: /^2 @SF/ });
    expect(
      within(week2)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["@SF", "6.0", "–", "–", "3", "30", "–", "–"]);
  });

  it("adds a season totals row that matches the season points, and a projection row", () => {
    renderDialog();
    openTab("Game log");
    const table = screen.getByRole("table", {
      name: /every week of the season/i,
    });
    const totals = within(table).getByRole("row", { name: /Season total/ });
    expect(
      within(totals)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["146.6", "1", "–", "10", "120", "–", "25"]);
    const projected = within(table).getByRole("row", {
      name: /Projected, week 6/,
    });
    expect(
      within(projected)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["22.5", "–", "10", "6.6", "106.8", "0.8", "–"]);
  });

  it("compares each finished week's points with its projection", () => {
    const withProjections: PlayerDetail = {
      ...detail,
      weeks: [
        { ...detail.weeks[0], projected: 14, final: true }, // 24.5 against 14.0
        { ...detail.weeks[1], projected: 9.5, final: false }, // still being played: no comparison
      ],
    };
    render(<PlayerDialog detail={withProjections} closeHref="/league/1?tab=players" />);
    openTab("Game log");
    const table = screen.getByRole("table", {
      name: /every week of the season/i,
    });
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers.slice(0, 6)).toEqual(["Wk", "Opp", "Pts", "Rank", "Proj", "+/-"]);
    const week1 = within(table).getByRole("row", { name: /^1 SEA/ });
    expect(
      within(week1)
        .getAllByRole("cell")
        .slice(1, 5)
        .map((c) => c.textContent),
    ).toEqual(["24.5", "–", "14.0", "+10.5"]);
    const week2 = within(table).getByRole("row", { name: /^2 @SF/ });
    expect(
      within(week2)
        .getAllByRole("cell")
        .slice(1, 5)
        .map((c) => c.textContent),
    ).toEqual([
      "6.0",
      "–",
      "9.5",
      "–", // not final yet
    ]);
    // the totals row has no projection total or difference unless every game is over
    const totals = within(table).getByRole("row", { name: /Season total/ });
    expect(
      within(totals)
        .getAllByRole("cell")
        .slice(0, 4)
        .map((c) => c.textContent),
    ).toEqual(["146.6", "1", "23.5", "–"]);
  });

  it("leaves the projection columns out when no week has a stored projection", () => {
    renderDialog();
    openTab("Game log");
    const table = screen.getByRole("table", {
      name: /every week of the season/i,
    });
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers).not.toContain("Proj");
    expect(headers).not.toContain("+/-");
  });

  it("copes with a player who has no bio, no projection and no games", () => {
    renderDialog({
      ...detail,
      bio: null,
      projected: null,
      weeks: [],
      past_seasons: [],
      owner_team: null,
      season: { points: 0, games: 0, average: null, rank: null },
    });
    expect(screen.queryByRole("heading", { name: "Bio" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Projected/ })).not.toBeInTheDocument();
    openTab("Game log");
    expect(screen.getByText("No games played yet this season.")).toBeInTheDocument();
    expect(screen.getByText("Available in this league")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Past seasons" })).not.toBeInTheDocument();
  });

  it("closes from the button, returning to the page without the player", async () => {
    renderDialog();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(replace).toHaveBeenCalledWith("/league/1?tab=players", {
      scroll: false,
    });
  });

  it("closes when the dialog itself is closed, for example with Escape", () => {
    renderDialog();
    screen.getByRole("dialog").dispatchEvent(new Event("close"));
    expect(replace).toHaveBeenCalledWith("/league/1?tab=players", {
      scroll: false,
    });
  });

  it("puts focus on the close button first", () => {
    renderDialog();
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <PlayerDialog detail={detail} closeHref="/league/1?tab=players" />,
    );
  });
});

describe("past seasons, game by game", () => {
  const open = async () => {
    const user = userEvent.setup();
    render(<PlayerDialog detail={detail} closeHref="/league/1?tab=players" />);
    openTab("History");
    const seasons = screen.getByRole("table", {
      name: /season totals under this league/i,
    });
    return { user, seasons };
  };

  it("lists every team he played for that season, in order, as links to the depth charts", async () => {
    const { seasons } = await open();
    const row = within(seasons).getByRole("row", { name: /2025/ });
    const links = within(row).getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual(["LAR", "SEA"]);
    expect(links[0]).toHaveAttribute("href", expect.stringContaining("depth=LAR"));
  });

  it("names the team for each week only when he played for more than one that season", () => {
    const traded: PlayerDetail = {
      ...detail,
      weeks: [detail.weeks[0], { ...detail.weeks[1], team: "SEA" }],
    };
    render(<PlayerDialog detail={traded} closeHref="/league/1?tab=players" />);
    openTab("Game log");
    const table = screen.getByRole("table", { name: /every week of the season/i });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent)
        .slice(0, 3),
    ).toEqual(["Wk", "Opp", "Team"]);
  });

  it("opens a season into a game-by-game table with the team and opponent for each game", async () => {
    const { user, seasons } = await open();
    const toggle = within(seasons).getByRole("button", { name: /2025/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("table", { name: /2025 game by game/i })).not.toBeInTheDocument();
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const games = screen.getByRole("table", { name: /2025 game by game/i });
    expect(
      within(games)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Week", "Team", "Opponent", "Points", "Catches", "Rec yds", "Rush yds"]);
    const traded = within(games).getByRole("row", { name: /^4 SEA at DEN/ }); // after the trade
    expect(
      within(traded)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["SEA", "at DEN", "10.4", "4", "64", "–"]);
    // the games add up to the season row
    const total = within(games).getByRole("row", { name: /Season total/ });
    expect(
      within(total)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["200.0", "10", "149", "4"]);
  });

  it("closes again and shows only one season at a time", async () => {
    const { user, seasons } = await open();
    const toggle = within(seasons).getByRole("button", { name: /2025/ });
    await user.click(toggle);
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("table", { name: /2025 game by game/i })).not.toBeInTheDocument();
  });

  it("has no toggle for a season with no stored games, and no accessibility violations", async () => {
    const bare = {
      ...detail,
      past_seasons: [{ season: "2024", games: 8, points: 90, rank: 12, teams: [] }],
    };
    const { container, unmount } = render(<PlayerDialog detail={bare} closeHref="/x" />);
    openTab("History");
    const seasons = within(container).getByRole("table", {
      name: /season totals under this league/i,
    });
    expect(within(seasons).queryByRole("button")).not.toBeInTheDocument();
    expect(within(seasons).getByText("–")).toBeInTheDocument(); // no teams known
    unmount();
    await expectNoA11yViolations(<PlayerDialog detail={detail} closeHref="/x" />);
  });
});
