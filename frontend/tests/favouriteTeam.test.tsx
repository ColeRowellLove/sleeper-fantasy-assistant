import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FavouriteTeamPicker from "../components/FavouriteTeamPicker";
import GamesPanel from "../components/GamesPanel";
import type { GameCard, Games } from "../lib/api";
import { groupGames, orderGames } from "../lib/games";
import { NFL_TEAM_COOKIE } from "../lib/myTeam";
import { expectNoA11yViolations } from "./a11y";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=games"),
}));

beforeEach(() => {
  refresh.mockClear();
  document.cookie = `${NFL_TEAM_COOKIE}=; max-age=0; path=/`;
});

const card = (id: string, home: string, away: string, date: string): GameCard =>
  ({
    game_id: id,
    week: 7,
    home,
    away,
    game: { state: "upcoming", date, opponent: away, home: true },
    players: [],
  }) as GameCard;

const games: Games = {
  league_id: "1",
  week: 7,
  current_week: 7,
  weeks: [7],
  games: [
    card("a", "KC", "DEN", "2026-10-18"),
    card("b", "WAS", "SF", "2026-10-19"),
    card("c", "DAL", "SEA", "2026-10-18"),
  ],
};

describe("favourite NFL team", () => {
  it("lists its game first, in a section named in words", () => {
    const sections = groupGames(orderGames(games.games, null), "WAS");
    expect(sections.map((s) => s.title)).toEqual(["Your NFL team: Commanders", "Sunday, Oct 18"]);
    expect(sections[0].games.map((g) => g.card.game_id)).toEqual(["b"]);
    expect(sections[1].games).toHaveLength(2); // the favourite game is not repeated
  });

  it("changes nothing without a favourite, or when it has no game this week", () => {
    expect(groupGames(orderGames(games.games, null), null)[0].title).toBe("Sunday, Oct 18");
    expect(groupGames(orderGames(games.games, null), "NYJ").map((s) => s.title)).toEqual([
      "Sunday, Oct 18",
      "Monday, Oct 19",
    ]);
  });

  it("shows on the Games page", () => {
    render(<GamesPanel data={games} leagueId="1" myRosterId={null} favourite="WAS" />);
    expect(screen.getByRole("heading", { name: "Your NFL team: Commanders" })).toBeInTheDocument();
  });
});

describe("FavouriteTeamPicker", () => {
  it("remembers the choice in a cookie and refreshes the page", async () => {
    const user = userEvent.setup();
    render(<FavouriteTeamPicker favourite={null} />);
    const select = screen.getByRole("combobox", { name: "Favourite NFL team" });
    expect(select).toHaveValue("");
    await user.selectOptions(select, "WAS");
    expect(document.cookie).toContain(`${NFL_TEAM_COOKIE}=WAS`);
    expect(refresh).toHaveBeenCalledTimes(1);
    await user.selectOptions(select, "");
    expect(select).toHaveValue("");
  });

  it("starts on the saved team and has no accessibility violations", async () => {
    render(<FavouriteTeamPicker favourite="SF" />);
    expect(screen.getByRole("combobox", { name: "Favourite NFL team" })).toHaveValue("SF");
    await expectNoA11yViolations(<FavouriteTeamPicker favourite="SF" />);
  });
});
