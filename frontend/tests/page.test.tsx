import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "../app/page";
import { expectNoA11yViolations } from "./a11y";

describe("Home page", () => {
  it("has a main landmark and a single top-level heading", () => {
    render(<Home />);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("has no automatically detectable accessibility violations", async () => {
    await expectNoA11yViolations(<Home />);
  });
});
