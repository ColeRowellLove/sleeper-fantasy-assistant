import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import FavouriteMark, { FavouriteProvider } from "../components/FavouriteProvider";
import PanelTabs from "../components/PanelTabs";
import PlayerIdentity from "../components/PlayerIdentity";
import { expectNoA11yViolations } from "./a11y";

vi.mock("next/navigation", () => ({
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams(""),
}));

describe("FavouriteMark", () => {
  it("marks a player on the favourite team, in words as well as a star", () => {
    render(
      <FavouriteProvider favourite="WAS">
        <FavouriteMark team="WAS" />
      </FavouriteProvider>,
    );
    expect(screen.getByText(/your favourite NFL team/)).toBeInTheDocument();
    expect(screen.getByText(/Fav/)).toBeInTheDocument();
  });

  it("marks nobody on another team, without a favourite, or without a team", () => {
    const { container } = render(
      <>
        <FavouriteProvider favourite="WAS">
          <FavouriteMark team="SF" />
          <FavouriteMark team={null} />
        </FavouriteProvider>
        <FavouriteMark team="WAS" />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows on the shared player line wherever it is used", () => {
    render(
      <FavouriteProvider favourite="WAS">
        <PlayerIdentity player_id="1" name="Jayden Daniels" position="QB" team="WAS" />
        <PlayerIdentity player_id="2" name="Brock Purdy" position="QB" team="SF" />
      </FavouriteProvider>,
    );
    expect(screen.getAllByText(/your favourite NFL team/)).toHaveLength(1);
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <FavouriteProvider favourite="WAS">
        <PlayerIdentity player_id="1" name="Jayden Daniels" position="QB" team="WAS" />
      </FavouriteProvider>,
    );
  });
});

describe("PanelTabs initial tab", () => {
  const tabs = [
    { key: "a", label: "DEN", content: <p>away</p> },
    { key: "b", label: "KC", content: <p>home</p> },
  ];

  it("opens the tab named, and the first when it is unknown", () => {
    const { unmount } = render(<PanelTabs label="Team" tabs={tabs} initial="b" />);
    expect(screen.getByRole("tab", { name: "KC" })).toHaveAttribute("aria-selected", "true");
    unmount();
    render(<PanelTabs label="Team" tabs={tabs} initial="zzz" />);
    expect(screen.getByRole("tab", { name: "DEN" })).toHaveAttribute("aria-selected", "true");
  });
});
