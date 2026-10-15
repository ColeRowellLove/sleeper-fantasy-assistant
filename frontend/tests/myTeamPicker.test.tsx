import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import MyTeamPicker from "../components/MyTeamPicker";
import { expectNoA11yViolations } from "./a11y";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const teams = [
  { roster_id: 1, team: "Cole" },
  { roster_id: 2, team: "Dad" },
];

describe("MyTeamPicker", () => {
  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<MyTeamPicker leagueId="9" teams={teams} myRosterId={1} />);
  });

  it("shows the current team and prompts when none is chosen", () => {
    const first = render(<MyTeamPicker leagueId="9" teams={teams} myRosterId={2} />);
    expect(screen.getByLabelText("Your team")).toHaveValue("2");
    first.unmount();
    render(<MyTeamPicker leagueId="9" teams={teams} myRosterId={null} />);
    expect(screen.getByRole("option", { name: "Choose your team" })).toBeInTheDocument();
  });

  it("remembers the pick in a per-league cookie and refreshes the page", async () => {
    const user = userEvent.setup();
    render(<MyTeamPicker leagueId="9" teams={teams} myRosterId={1} />);
    await user.selectOptions(screen.getByLabelText("Your team"), "2");
    expect(document.cookie).toContain("sa_team_9=2");
    expect(refresh).toHaveBeenCalled();
    // the dropdown keeps showing the new choice while the server refresh is still in flight
    expect(screen.getByLabelText("Your team")).toHaveValue("2");
  });
});
