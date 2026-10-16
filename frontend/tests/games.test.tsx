import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import GamesPanel from "../components/GamesPanel";
import type { GameCard, GamePlayer, Games } from "../lib/api";
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

describe("GamesPanel", () => {
  it("lists every game with the state, line and conditions in words", () => {
    render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    expect(screen.getByText("Played")).toBeInTheDocument();
    expect(screen.getByText("Final, KC 27 - DEN 20")).toBeInTheDocument();
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
    expect(first).toHaveTextContent("DEN at KC"); // the game with two of your players leads
  });

  it("lays out every stat like a box score, with your players highlighted and named", () => {
    render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    const table = screen.getByRole("table", { name: /KC rushing and receiving/ });
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(headers).toEqual([
      "Rushing and receiving",
      "Fantasy team",
      "Car",
      "Rush yds",
      "Rush TD",
      "Tgt",
      "Rec",
      "Rec yds",
      "Rec TD",
      "Pts",
    ]);
    const row = within(table).getByRole("row", { name: /My Back/ });
    expect(row).toHaveClass("mine");
    const cells = within(row)
      .getAllByRole("cell")
      .map((c) => c.textContent);
    expect(cells).toEqual(["You Cole", "18", "92", "1", "4", "3", "21", "–", "12.5"]);
    expect(within(row).getByText("You")).toBeInTheDocument();
  });

  it("marks other teams' players with that team's name and a lighter highlight", () => {
    render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    const table = screen.getByRole("table", { name: /DEN rushing and receiving/ });
    const other = within(table).getByRole("row", { name: /Rostered Elsewhere/ });
    expect(other).toHaveClass("owned-other");
    expect(other).not.toHaveClass("mine");
    expect(within(other).getByText("Dad Bods")).toBeInTheDocument();
  });

  it("shows each team in turn with its logo and faces, and free agents as available", () => {
    const { container } = render(<GamesPanel data={data} leagueId="1" myRosterId={1} />);
    const blocks = screen.getAllByRole("region", { name: /KC players|DEN players/ });
    expect(blocks.map((b) => b.getAttribute("aria-label"))).toEqual(["DEN players", "KC players"]);
    expect(container.querySelectorAll(".game-team-title .team-logo").length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".game-players .avatar").length).toBeGreaterThan(0);
    const free = screen.getByRole("table", { name: /SF rushing and receiving/ });
    expect(within(free).getByText("Available")).toBeInTheDocument();
    const mine = screen.getByRole("table", { name: /SEA rushing and receiving/ });
    expect(within(mine).getByRole("row", { name: /My Only/ })).toHaveTextContent("–");
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
    const table = screen.getByRole("table", { name: /KC rushing and receiving \(projected\)/ });
    expect(within(table).getByRole("columnheader", { name: "Proj pts" })).toBeInTheDocument();
    const row = within(table).getByRole("row", { name: /Projected Back/ });
    expect(within(row).getByText("14.2")).toBeInTheDocument();
    expect(within(row).getByText("proj")).toBeInTheDocument();
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
