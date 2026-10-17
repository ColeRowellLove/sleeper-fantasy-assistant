import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import GamesPanel from "../components/GamesPanel";
import type { GameCard, GameInfo, GamePlayer, Games } from "../lib/api";
import { cardScores } from "../lib/game";
import { groupGames, teamNickname } from "../lib/games";
import { parseTab } from "../lib/league";
import { orderGames, yourPlayersText } from "../lib/games";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=games&week=6"),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const player = (id: string, name: string, over: Partial<GamePlayer> = {}): GamePlayer => ({
  player_id: id,
  name,
  position: "RB",
  team: "SF",
  stats: { rush_att: 10, rush_yd: 40 },
  ...over,
});

const card = (
  id: string,
  home: string,
  away: string,
  players: GamePlayer[],
  over = {},
): GameCard => ({
  game_id: id,
  week: 6,
  home,
  away,
  game: {
    state: "upcoming",
    date: "2026-10-18",
    opponent: away,
    home: true,
    team: home,
    conditions: { roof: "outdoors", temp: 53, wind: 3, spread: -3.5, total: 44.5 },
  },
  players,
  ...over,
});

const early = card("a", "SF", "DAL", [
  player("1", "Other Back", { owner_roster_id: 2, owner_team: "Dad Bods", points: 5 }),
  player("2", "Free Back", { points: 20, stat_line: "20 car, 100 yds" }),
]);
const mineGame = card(
  "b",
  "KC",
  "DEN",
  [
    player("3", "Rostered Elsewhere", {
      team: "DEN",
      owner_roster_id: 2,
      owner_team: "Dad Bods",
      points: 30,
    }),
    player("4", "My Back", {
      team: "KC",
      owner_roster_id: 1,
      owner_team: "Cole",
      points: 12.5,
      stat_line: "18 car, 92 yds, 1 TD",
      stats: { rush_att: 18, rush_yd: 92, rush_td: 1, rec_tgt: 4, rec: 3, rec_yd: 21 },
    }),
    player("5", "My Receiver", { team: "KC", owner_roster_id: 1, owner_team: "Cole", points: 3 }),
  ],
  {
    game: {
      state: "final",
      date: "2026-10-18",
      opponent: "DEN",
      home: true,
      team: "KC",
      team_score: 27,
      opponent_score: 20,
      period_text: "Final",
    },
  },
);
const lone = card("c", "SEA", "LAR", [
  player("6", "My Only", { team: "SEA", owner_roster_id: 1, owner_team: "Cole" }),
]);

const data: Games = {
  league_id: "1",
  week: 6,
  current_week: 6,
  weeks: [5, 6, 7],
  games: [early, mineGame, lone],
};

describe("game ordering", () => {
  it("puts games with your players first, most of your players first, then kickoff order", () => {
    expect(orderGames(data.games, 1).map((g) => g.card.game_id)).toEqual(["b", "c", "a"]);
    expect(orderGames(data.games, 1).map((g) => g.mine.length)).toEqual([2, 1, 0]);
  });

  it("keeps the kickoff order when no team is yours", () => {
    expect(orderGames(data.games, null).map((g) => g.card.game_id)).toEqual(["a", "b", "c"]);
    expect(orderGames(data.games, null).every((g) => g.mine.length === 0)).toBe(true);
  });

  it("leads each game with your players, then other rostered players, then the rest", () => {
    const first = orderGames(data.games, 1)[0].card.players.map((p) => p.name);
    expect(first).toEqual(["My Back", "My Receiver", "Rostered Elsewhere"]);
    const last = orderGames(data.games, 1)[2].card.players.map((p) => p.name);
    expect(last).toEqual(["Other Back", "Free Back"]);
  });

  it("says how many of your players are in a game", () => {
    expect(yourPlayersText(1)).toBe("1 of your player");
    expect(yourPlayersText(3)).toBe("3 of your players");
  });

  it("is a tab", () => {
    expect(parseTab("games")).toBe("games");
  });
});

const openTeam = (team: string) => fireEvent.click(screen.getByRole("tab", { name: team }));

describe("GamesPanel", () => {
  it("groups the games by day under a heading, your games first", () => {
    render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings[0]).toBe("Your games");
  });

  it("lists every game with the state, line and conditions in words", () => {
    render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    expect(screen.getAllByText("Played").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Final, KC 27 - DEN 20").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/53°F, wind 3 mph · SF -3.5, O\/U 44.5/).length).toBeGreaterThan(0);
  });

  it("marks games with your players, in words, and lists them first", () => {
    render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    const summaries = screen.getAllByText(/of your player/);
    expect(summaries.map((s) => s.textContent)).toEqual([
      "You 2 of your players",
      "You 1 of your player",
    ]);
    const first = document.querySelector("details summary .game-teams");
    expect(first).toHaveTextContent(/Broncos.*20.*Chiefs.*27/); // away over home, with scores
  });

  it("lays out one table per kind of stat, like theScore, with your players marked and totals", () => {
    render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    openTeam("KC");
    const rushing = screen.getByRole("table", { name: /KC rushing/ });
    expect(
      within(rushing)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Rushing", "Rsh", "Yds", "Avg", "TD", "Pts"]);
    const row = within(rushing).getByRole("row", { name: /My Back/ });
    expect(row).toHaveClass("mine");
    expect(
      within(row)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["18", "92", "5.1", "1", "12.5"]);
    expect(within(row).getByText("You")).toBeInTheDocument();
    // the same player also has a receiving line, so he is in that table too
    const receiving = screen.getByRole("table", { name: /KC receiving/ });
    expect(
      within(within(receiving).getByRole("row", { name: /My Back/ }))
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["3", "21", "–", "4", "12.5"]);
    // two KC runners: 18 + 10 carries, 92 + 40 yards
    const total = within(rushing).getByRole("row", { name: /Total/ });
    expect(within(total).getByText("28")).toBeInTheDocument();
    expect(within(total).getByText("132")).toBeInTheDocument();
  });

  it("adds a team total under a table with several players, averages included", () => {
    const two = card("t", "KC", "DEN", [
      player("8", "Back One", { team: "KC", stats: { rush_att: 14, rush_yd: 52, rush_td: 0 } }),
      player("9", "Back Two", { team: "KC", stats: { rush_att: 5, rush_yd: 20, rush_td: 1 } }),
    ]);
    render(<GamesPanel data={{ ...data, games: [two] }} leagueId="1" myRosterId={1} />);
    openTeam("KC");
    const total = within(screen.getByRole("table", { name: /KC rushing/ })).getByRole("row", {
      name: /Total/,
    });
    expect(
      within(total)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["19", "72", "3.8", "1", ""]); // 72 yards on 19 carries
  });

  it("marks other teams' players with that team's name and a lighter highlight", () => {
    render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    const table = screen.getByRole("table", { name: /DEN rushing/ });
    const other = within(table).getByRole("row", { name: /Rostered Elsewhere/ });
    expect(other).toHaveClass("owned-other");
    expect(other).not.toHaveClass("mine");
    expect(within(other).getByText("Dad Bods")).toBeInTheDocument();
  });

  it("shows one team at a time behind a tab each, free agents as FA in words", () => {
    const { container } = render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    const tabs = screen.getAllByRole("tab", { name: /KC|DEN|SF|SEA/ }).map((t) => t.textContent);
    expect(tabs).toEqual(expect.arrayContaining(["DEN", "KC"]));
    // away team first and open; the home team's tables are not rendered until its tab is opened
    expect(screen.getByRole("region", { name: "DEN players" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "KC players" })).not.toBeInTheDocument();
    openTeam("KC");
    expect(screen.getByRole("region", { name: "KC players" })).toBeInTheDocument();
    expect(container.querySelectorAll(".game-team-title .team-logo").length).toBeGreaterThan(0);
    openTeam("SF");
    const free = screen.getByRole("table", { name: /SF rushing/ });
    expect(within(free).getByText(/available in this league/)).toBeInTheDocument();
    openTeam("SEA");
    const mine = screen.getByRole("table", { name: /SEA rushing/ });
    expect(within(mine).getByRole("row", { name: /My Only/ })).toBeInTheDocument();
  });

  it("shows projections, labelled, before a player has played", () => {
    const upcoming = card("p", "KC", "DEN", [
      player("7", "Projected Back", {
        team: "KC",
        points: 14.2,
        projected: true,
        stats: { rush_att: 14.5, rush_yd: 61.7 },
      }),
    ]);
    render(<GamesPanel data={{ ...data, games: [upcoming] }} leagueId="1" myRosterId={1} />);
    openTeam("KC");
    const table = screen.getByRole("table", { name: /KC rushing \(projected\)/ });
    expect(within(table).getByRole("columnheader", { name: "Proj" })).toBeInTheDocument();
    const row = within(table).getByRole("row", { name: /Projected Back/ });
    expect(within(row).getByText("14.2")).toBeInTheDocument();
    // projections keep a decimal, so 14.5 carries does not read as 15 and 61.7 yards not as 62
    expect(within(row).getByText("14.5")).toBeInTheDocument();
    expect(within(row).getByText("61.7")).toBeInTheDocument();
  });

  it("explains an empty week and offers week chips back to the games tab", () => {
    const { rerender } = render(
      <GamesPanel data={{ ...data, games: [] }} leagueId="1" myRosterId={1} />,
    );
    expect(screen.getByText(/No games have been synced/)).toBeInTheDocument();
    rerender(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    expect(
      within(screen.getByRole("navigation", { name: "Week" })).getByRole("link", { name: /7/ }),
    ).toHaveAttribute("href", "/league/1?tab=games&week=7");
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
  });
});

describe("cardScores", () => {
  const card = (game: Partial<GameInfo>) => ({
    game: { state: "final", date: null, opponent: null, home: null, ...game } as GameInfo,
  });

  it("gives away then home once a game has started, and nothing before", () => {
    expect(cardScores(card({ team_score: 27, opponent_score: 20 }))).toEqual({
      away: 20,
      home: 27,
    });
    expect(cardScores(card({ state: "live", team_score: 3, opponent_score: 0 }))).toEqual({
      away: 0,
      home: 3,
    });
    expect(cardScores(card({ state: "upcoming", team_score: 0, opponent_score: 0 }))).toBeNull();
    expect(cardScores(card({ team_score: null, opponent_score: null }))).toBeNull();
  });
});

describe("groupGames", () => {
  const card = (id: string, date: string | null): GameCard =>
    ({
      game_id: id,
      week: 1,
      home: "KC",
      away: "DEN",
      game: { state: "upcoming", date, opponent: null, home: null } as GameInfo,
      players: [],
    }) as GameCard;
  const og = (id: string, date: string | null, mine = 0) => ({
    card: card(id, date),
    mine: Array.from({ length: mine }, () => ({}) as GamePlayer),
  });

  it("puts your games first, then one section per day in date order, undated last", () => {
    const sections = groupGames([
      og("a", "2026-10-19"),
      og("b", "2026-10-18"),
      og("c", null),
      og("d", "2026-10-18", 1),
      og("e", "2026-10-18"),
    ]);
    expect(sections.map((s) => s.title)).toEqual([
      "Your games",
      "Sunday, Oct 18",
      "Monday, Oct 19",
      "Date to be set",
    ]);
    expect(sections[1].games.map((g) => g.card.game_id)).toEqual(["b", "e"]);
  });

  it("writes a team's nickname, or its code when unknown", () => {
    expect(teamNickname("HOU")).toBe("Texans");
    expect(teamNickname("XXX")).toBe("XXX");
  });
});
