import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import FilterChips from "../components/FilterChips";
import NoteList from "../components/NoteList";
import PlayerIdentity from "../components/PlayerIdentity";
import StatTable from "../components/StatTable";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=players"),
  useRouter: () => ({ refresh: vi.fn(), replace: vi.fn(), push: vi.fn() }),
}));

describe("PlayerIdentity", () => {
  const ui = (
    <PlayerIdentity
      player_id="4034"
      name="Kyren Williams"
      position="RB"
      team="LAR"
      injury={{ status: "Questionable", body_part: "Ribs" }}
      meta={<span>On your team</span>}
    >
      <span className="player-meta">vs ARI</span>
    </PlayerIdentity>
  );

  it("shows the face, a name link, position, team link, injury, meta and extra lines", () => {
    const { container } = render(ui);
    expect(container.querySelector(".avatar")).not.toBeNull();
    expect(screen.getByRole("link", { name: "Kyren Williams" })).toBeInTheDocument();
    expect(screen.getByText("RB")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "LAR" })).toBeInTheDocument();
    expect(screen.getByText("Questionable")).toBeInTheDocument();
    expect(screen.getByText("On your team")).toBeInTheDocument();
    expect(screen.getByText("vs ARI")).toBeInTheDocument();
  });

  it("says FA for a player with no team, and can leave the team out", () => {
    const { rerender } = render(
      <PlayerIdentity player_id="1" name="Free Agent" position="WR" team={null} />,
    );
    expect(screen.getByText("FA")).toBeInTheDocument();
    rerender(
      <PlayerIdentity player_id="1" name="Free Agent" position="WR" team="SF" showTeam={false} />,
    );
    expect(screen.queryByText("SF")).not.toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(ui);
  });
});

describe("FilterChips", () => {
  const options = [
    { value: "all", label: "All" },
    { value: "mine", label: "Mine" },
  ] as const;

  it("is a named group of toggle buttons that reports the choice", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FilterChips label="Show" options={options} value="all" onChange={onChange} />);
    const group = screen.getByRole("group", { name: "Show" });
    expect(within(group).getByRole("button", { name: "All" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(group).getByRole("button", { name: "Mine" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await user.click(within(group).getByRole("button", { name: "Mine" }));
    expect(onChange).toHaveBeenCalledWith("mine");
  });

  it("is reachable and pressable with the keyboard, and has no accessibility violations", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FilterChips label="Show" options={options} value="all" onChange={onChange} />);
    await user.tab();
    await user.tab();
    expect(screen.getByRole("button", { name: "Mine" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith("mine");
    await expectNoA11yViolations(
      <FilterChips label="Show" options={options} value="all" onChange={onChange} />,
    );
  });
});

describe("StatTable", () => {
  const body = (
    <tbody>
      <tr>
        <th scope="row">A</th>
        <td>1</td>
      </tr>
    </tbody>
  );

  it("frames a table in a scrolling card with a caption for screen readers", () => {
    const { container } = render(
      <StatTable caption="Things" className="mine-table">
        {body}
      </StatTable>,
    );
    expect(screen.getByRole("table", { name: "Things" })).toHaveClass("players", "mine-table");
    expect(container.querySelector(".card.flush .players-scroll")).not.toBeNull();
  });

  it("shows an empty message under the card, and can be used without the card", () => {
    const { container, rerender } = render(
      <StatTable caption="Things" empty="Nothing here.">
        {body}
      </StatTable>,
    );
    expect(screen.getByText("Nothing here.")).toBeInTheDocument();
    rerender(
      <StatTable caption="Things" bare>
        {body}
      </StatTable>,
    );
    expect(container.querySelector(".card")).toBeNull();
    rerender(
      <StatTable caption="Things" bare empty="No rows.">
        {body}
      </StatTable>,
    );
    expect(screen.getByText("No rows.")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<StatTable caption="Things">{body}</StatTable>);
  });
});

describe("NoteList", () => {
  it("renders short bullets as a list", async () => {
    const ui = (
      <NoteList items={["Shows the best adds", "Resets each cycle"]} label="About this page" />
    );
    render(ui);
    const list = screen.getByRole("list", { name: "About this page" });
    expect(
      within(list)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["Shows the best adds", "Resets each cycle"]);
    await expectNoA11yViolations(ui);
  });
});
