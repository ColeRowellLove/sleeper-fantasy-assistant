import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import PlayerAvatar from "../components/PlayerAvatar";
import RostersPanel from "../components/RostersPanel";
import type { Dashboard } from "../lib/api";
import { expectNoA11yViolations } from "./a11y";

type Rosters = Dashboard["rosters"];

const rosters: Rosters = [
  {
    roster_id: 1,
    team: "Dad",
    owner_id: "u1",
    players: [
      { player_id: "1", name: "Dad Back", position: "RB", team: "DAL", status: "starter", slot: "RB" },
    ],
  },
  {
    roster_id: 2,
    team: "Cole",
    owner_id: "u2",
    players: [
      { player_id: "10", name: "Star QB", position: "QB", team: "HOU", status: "starter", slot: "QB" },
      { player_id: "11", name: "Flex Guy", position: "WR", team: "CAR", status: "starter", slot: "FLEX" },
      { player_id: "PIT", name: "PIT", position: "DEF", team: "PIT", status: "starter", slot: "DEF" },
      { player_id: "12", name: "Bench TE", position: "TE", team: "NYG", status: "bench", slot: null },
      { player_id: "13", name: "Hurt RB", position: "RB", team: "SEA", status: "ir", slot: null },
      { player_id: "14", name: "Stash WR", position: "WR", team: null, status: "taxi", slot: null },
    ],
  },
];

describe("RostersPanel", () => {
  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<RostersPanel rosters={rosters} myRosterId={2} />);
  });

  it("shows your team first and selected, labelled in the dropdown", () => {
    render(<RostersPanel rosters={rosters} myRosterId={2} />);
    const select = screen.getByLabelText("Team");
    expect(select).toHaveValue("2");
    const options = within(select)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(options).toEqual(["Cole (you)", "Dad"]);
    expect(screen.getByText("Star QB")).toBeInTheDocument();
    expect(screen.queryByText("Dad Back")).not.toBeInTheDocument();
  });

  it("falls back to the first team when none is yours", () => {
    render(<RostersPanel rosters={rosters} myRosterId={null} />);
    expect(screen.getByLabelText("Team")).toHaveValue("1");
    expect(screen.getByText("Dad Back")).toBeInTheDocument();
  });

  it("groups players into labelled Starters, Bench, IR and Taxi sections with counts", () => {
    render(<RostersPanel rosters={rosters} myRosterId={2} />);
    const titles = screen
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent?.replace(/\s+/g, " ").trim());
    expect(titles).toEqual(["Starters 3", "Bench 1", "Injured reserve 1", "Taxi squad 1"]);
    const starters = screen.getByRole("region", { name: /Starters/ });
    expect(within(starters).getAllByRole("listitem")).toHaveLength(3);
    expect(within(starters).getByText("FLEX")).toBeInTheDocument();
  });

  it("omits empty groups", () => {
    render(<RostersPanel rosters={rosters} myRosterId={1} />);
    expect(screen.queryByRole("heading", { level: 3, name: /Bench/ })).not.toBeInTheDocument();
  });

  it("switches the roster when another team is chosen", async () => {
    const user = userEvent.setup();
    render(<RostersPanel rosters={rosters} myRosterId={2} />);
    await user.selectOptions(screen.getByLabelText("Team"), "1");
    expect(screen.getByText("Dad Back")).toBeInTheDocument();
    expect(screen.queryByText("Star QB")).not.toBeInTheDocument();
  });

  it("gives each position its own color class on the chip", () => {
    render(<RostersPanel rosters={rosters} myRosterId={2} />);
    const chip = (text: string) =>
      screen.getAllByText(text).find((e) => e.className.includes("chip"));
    expect(chip("QB")?.className).toContain("pos-qb");
    expect(chip("WR")?.className).toContain("pos-wr");
    expect(chip("TE")?.className).toContain("pos-te");
    expect(chip("DEF")?.className).toContain("pos-def");
  });

  it("explains an empty league instead of rendering nothing", () => {
    render(<RostersPanel rosters={[]} myRosterId={null} />);
    expect(screen.getByText(/no rosters have been synced/i)).toBeInTheDocument();
  });
});

describe("PlayerAvatar", () => {
  it("is decorative and uses the team logo for a defense", () => {
    const { container } = render(
      <PlayerAvatar player_id="PIT" name="PIT" position="DEF" team="PIT" />,
    );
    const imgs = container.querySelectorAll("img");
    expect(imgs).toHaveLength(1); // no extra team badge on a logo
    expect(imgs[0]).toHaveAttribute("alt", "");
    expect(imgs[0].getAttribute("src")).toContain("team_logos/nfl/pit");
  });

  it("shows a headshot with a small team logo for players", () => {
    const { container } = render(
      <PlayerAvatar player_id="4034" name="Christian McCaffrey" position="RB" team="SF" />,
    );
    const srcs = [...container.querySelectorAll("img")].map((i) => i.getAttribute("src"));
    expect(srcs[0]).toContain("players/thumb/4034");
    expect(srcs[1]).toContain("team_logos/nfl/sf");
  });

  it("falls back to initials when the headshot fails to load", () => {
    const { container } = render(
      <PlayerAvatar player_id="4034" name="Christian McCaffrey" position="RB" team="SF" />,
    );
    fireEvent.error(container.querySelector("img") as HTMLImageElement);
    expect(screen.getByText("CM")).toBeInTheDocument();
  });

  it("is hidden from assistive technology because the name is always shown beside it", () => {
    const { container } = render(
      <PlayerAvatar player_id="1" name="A B" position="QB" team={null} />,
    );
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });
});
