import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import PanelTabs from "../components/PanelTabs";
import { bioDetails, bioStrip } from "../lib/playerDetail";
import { expectNoA11yViolations } from "./a11y";

const tabs = [
  { key: "a", label: "Summary", content: <p>First panel</p> },
  { key: "b", label: "Game log", content: <p>Second panel</p> },
  { key: "c", label: "History", content: <p>Third panel</p> },
];

describe("PanelTabs", () => {
  it("opens the first tab and shows only its panel", () => {
    render(<PanelTabs label="Sections" tabs={tabs} />);
    expect(screen.getByRole("tablist", { name: "Sections" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Summary" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("First panel");
    expect(screen.queryByText("Second panel")).not.toBeInTheDocument();
  });

  it("switches on click", async () => {
    render(<PanelTabs label="Sections" tabs={tabs} />);
    await userEvent.click(screen.getByRole("tab", { name: "History" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Third panel");
  });

  it("moves with the arrow keys, wrapping, and Home and End", async () => {
    const user = userEvent.setup();
    render(<PanelTabs label="Sections" tabs={tabs} />);
    screen.getByRole("tab", { name: "Summary" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Game log" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Second panel");
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "History" })).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Summary" })).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "History" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Summary" })).toHaveFocus();
  });

  it("keeps only the open tab in the tab order", () => {
    render(<PanelTabs label="Sections" tabs={tabs} />);
    expect(screen.getByRole("tab", { name: "Summary" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "Game log" })).toHaveAttribute("tabindex", "-1");
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<PanelTabs label="Sections" tabs={tabs} />);
  });
});

describe("header strip", () => {
  const bio = { age: 25.8, height: "76", weight: "210", years_exp: 2, college: "LSU", number: 5 };

  it("gives age, height, weight and experience for the header", () => {
    expect(bioStrip(bio)).toEqual([
      { label: "Age", value: "25.8" },
      { label: "Height", value: "6'4\"" },
      { label: "Weight", value: "210 lbs" },
      { label: "Exp", value: "2" },
    ]);
    expect(bioStrip(null)).toEqual([]);
  });

  it("keeps the rest of the bio for the summary", () => {
    expect(bioDetails(bio).map((r) => r.label)).toEqual(["College", "Jersey"]);
  });
});
