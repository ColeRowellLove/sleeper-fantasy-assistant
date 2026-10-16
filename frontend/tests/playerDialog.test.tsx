import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import PlayerDialog from "../components/PlayerDialog";
import PlayerLink from "../components/PlayerLink";
import type { PlayerDetail } from "../lib/api";
import { bioRows, describeStats, formatHeight, rankText } from "../lib/playerDetail";
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

const detail: PlayerDetail = {
  player_id: "9493",
  name: "Puka Nacua",
  position: "WR",
  team: "LAR",
  injury: { status: "Questionable", body_part: "Knee" },
  game: { state: "upcoming", date: "2026-10-18", opponent: "SEA", home: true },
  bio: { age: 25, height: "74", weight: "216", college: "BYU", years_exp: 3, number: 12 },
  owner_roster_id: 1,
  owner_team: "Cole",
  adds: null,
  drops: 120,
  season: { points: 146.6, games: 5, average: 29.3, rank: 1 },
  projected: { week: 6, points: 22.5, stats: { rec: 6.6, rec_yd: 106.8, rec_td: 0.8, rec_tgt: 10 } },
  weeks: [
    { week: 1, opponent: "SEA", home: true, points: 24.5, stats: { rec: 7, rec_yd: 90, rush_yd: 25 } },
    { week: 2, opponent: "SF", home: false, points: 6, stats: { rec: 3, rec_yd: 30 } },
  ],
  past_seasons: [{ season: "2025", games: 16, points: 200, rank: 2 }],
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
      { label: "Experience", value: "3 seasons" },
      { label: "Jersey", value: "#12" },
    ]);
    expect(bioRows({ years_exp: 0 })).toEqual([{ label: "Experience", value: "Rookie" }]);
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
    const line = { rec: 2, rec_yd: 20, rush_yd: 80, rush_att: 18, pass_yd: 250, pass_td: 2 };
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
    expect(within(dialog).getByText("On Cole")).toBeInTheDocument();
  });

  it("shows bio, season, projection, weekly log and past seasons", () => {
    renderDialog();
    expect(screen.getByRole("heading", { name: "Bio" })).toBeInTheDocument();
    expect(screen.getByText("BYU")).toBeInTheDocument();
    expect(screen.getByText("WR1")).toBeInTheDocument(); // position rank
    expect(screen.getByText("146.6")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Projected, week 6" })).toBeInTheDocument();
    expect(screen.getByText(/22\.5/)).toBeInTheDocument();
    expect(screen.getByText("Targets 10, Catches 6.6, Rec yds 106.8, Rec TD 0.8")).toBeInTheDocument();
    const weeks = screen.getByRole("table", { name: /points and stats by week/i });
    expect(within(weeks).getByText("vs SEA")).toBeInTheDocument();
    expect(within(weeks).getByText("at SF")).toBeInTheDocument();
    expect(within(weeks).getByText("Catches 7, Rec yds 90, Rush yds 25")).toBeInTheDocument();
    const past = screen.getByRole("table", { name: /season totals/i });
    expect(within(past).getByText("WR2")).toBeInTheDocument();
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
    expect(screen.getByText("No games played yet this season.")).toBeInTheDocument();
    expect(screen.getByText("Available in this league")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Past seasons" })).not.toBeInTheDocument();
  });

  it("closes from the button, returning to the page without the player", async () => {
    renderDialog();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(replace).toHaveBeenCalledWith("/league/1?tab=players", { scroll: false });
  });

  it("closes when the dialog itself is closed, for example with Escape", () => {
    renderDialog();
    screen.getByRole("dialog").dispatchEvent(new Event("close"));
    expect(replace).toHaveBeenCalledWith("/league/1?tab=players", { scroll: false });
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
