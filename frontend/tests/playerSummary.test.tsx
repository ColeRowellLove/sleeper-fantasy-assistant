import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PlayerSummary from "../components/PlayerSummary";
import type { PlayerDetail } from "../lib/api";
import { count, percent } from "../lib/format";
import { projectionCards, summaryStats } from "../lib/playerSummary";
import { expectNoA11yViolations } from "./a11y";

const detail: PlayerDetail = {
  player_id: "1",
  name: "Test Player",
  position: "QB",
  team: "WAS",
  game: { state: "upcoming", date: "2026-10-19", opponent: "SF", home: false },
  adds: 1204,
  drops: null,
  owned_pct: 88,
  started_pct: 53.04,
  season: { points: 100, games: 4, average: 21.55, rank: 24 },
  projected: { week: 3, points: 16.9, stats: { pass_yd: 250 } },
  schedule: [
    { week: 1, opponent: "NYG", home: true },
    { week: 2, bye: true },
    { week: 3, opponent: "SF", home: false },
  ],
  weeks: [
    {
      week: 1,
      team: "WAS",
      opponent: "NYG",
      home: true,
      points: 32.26,
      stats: {},
      projected: 16.44,
      final: true,
    },
  ],
  past_seasons: [],
} as unknown as PlayerDetail;

describe("summary helpers", () => {
  it("writes percentages and counts, with a dash for a missing number", () => {
    expect(percent(88)).toBe("88.0%");
    expect(percent(null)).toBe("–");
    expect(count(1204)).toBe("1,204");
    expect(count(undefined)).toBe("–");
  });

  it("gives rank, points per game, owned and started", () => {
    expect(summaryStats(detail).map((s) => [s.label, s.value])).toEqual([
      ["Rank", "QB24"],
      ["Pts/game", "21.6"],
      ["Points", "100.0"],
      ["Games", "4"],
      ["Owned", "88.0%"],
      ["Started", "53.0%"],
    ]);
  });

  it("makes a card per week: the result, the coming week's live projection, and the bye", () => {
    expect(projectionCards(detail)).toEqual([
      { week: 1, opponent: "NYG", difficulty: null, bye: false, projected: 16.44, final: 32.26 },
      { week: 2, opponent: null, difficulty: null, bye: true, projected: null, final: null },
      { week: 3, opponent: "@SF", difficulty: null, bye: false, projected: 16.9, final: null },
    ]);
  });
});

describe("PlayerSummary", () => {
  it("shows the stats, this week's projection, the strip and the activity", () => {
    render(<PlayerSummary detail={detail} />);
    expect(screen.getByText("Rank").nextSibling).toHaveTextContent("QB24");
    expect(screen.getByText("Points").nextSibling).toHaveTextContent("100.0");
    expect(screen.getByText(/ESPN.s numbers/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "This week's game" })).toBeInTheDocument();
    expect(screen.getByText("Week 3")).toBeInTheDocument();
    const strip = screen.getByRole("region", { name: /projections by week/i });
    expect(within(strip).getByText("BYE")).toBeInTheDocument();
    expect(within(strip).getByText("32.3")).toBeInTheDocument();
    expect(screen.getByText("1,204")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<PlayerSummary detail={detail} />);
  });
});
