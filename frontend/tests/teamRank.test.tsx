import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import PlayerDialog from "../components/PlayerDialog";
import TeamRankChips from "../components/TeamRankChips";
import type { PlayerDetail, TeamStat } from "../lib/api";
import { rankChips, teamRankTone } from "../lib/teamRank";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams(""),
}));

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close() {
    this.removeAttribute("open");
  };
});

const stat = (key: string, label: string, rank: number): TeamStat => ({
  key,
  label,
  side: "offense",
  value: 10,
  rank,
  teams: 32,
  games: 5,
});

describe("team rank", () => {
  it("colours the best third great, the worst third poor and the middle ok", () => {
    expect(teamRankTone(1, 32)).toBe("great");
    expect(teamRankTone(10, 32)).toBe("great");
    expect(teamRankTone(11, 32)).toBe("ok");
    expect(teamRankTone(21, 32)).toBe("ok");
    expect(teamRankTone(22, 32)).toBe("poor");
    expect(teamRankTone(5, 0)).toBe("ok");
  });

  it("makes a chip per stat with the rank in words for a screen reader", () => {
    expect(rankChips([stat("pass_yd", "Pass yds", 26)])).toEqual([
      {
        key: "pass_yd",
        label: "Pass yds",
        rank: "26th",
        value: "10",
        spoken: "Pass yds: 26th of 32 teams",
        tone: "poor",
      },
    ]);
    expect(rankChips(undefined)).toEqual([]);
  });

  it("renders nothing without stats and has no accessibility violations", async () => {
    const { container } = render(<TeamRankChips team="WAS" headingId="h" />);
    expect(container).toBeEmptyDOMElement();
    await expectNoA11yViolations(
      <TeamRankChips
        team="WAS"
        headingId="h"
        stats={[stat("a", "Offense", 17), stat("b", "Pass yds", 26)]}
      />,
    );
  });
});

describe("Team tab", () => {
  const detail = {
    player_id: "p1",
    name: "Jayden Daniels",
    position: "QB",
    team: "WAS",
    team_stats: [stat("pass_yd", "Pass yds", 26)],
    depth: {
      team: "WAS",
      groups: [
        {
          group: "offense",
          title: "Offense",
          slots: [
            {
              slot: "qb",
              label: "Quarterback",
              skill: true,
              players: [
                { name: "Jayden Daniels", player_id: "p1", depth: 1, label: "Starter" },
                { name: "Marcus Mariota", player_id: "p2", depth: 2, label: "2nd string" },
              ],
            },
          ],
        },
      ],
    },
    season: { points: 0, games: 0, average: null, rank: null },
    weeks: [],
    past_seasons: [],
  } as unknown as PlayerDetail;

  it("shows the rank chips and the depth chart with this player marked", () => {
    render(<PlayerDialog detail={detail} closeHref="/x" />);
    fireEvent.click(screen.getByRole("tab", { name: "Team" }));
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByRole("heading", { name: "WAS team rank" })).toBeInTheDocument();
    expect(within(panel).getByText("26th")).toBeInTheDocument();
    expect(within(panel).getByText("Marcus Mariota")).toBeInTheDocument();
    const mine = within(panel).getByText("Jayden Daniels").closest(".depth-player");
    expect(mine).toHaveClass("is-viewed");
  });
});
