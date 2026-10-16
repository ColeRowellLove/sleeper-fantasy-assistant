import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import InjuryBadge from "../components/InjuryBadge";
import MatchupCard from "../components/MatchupCard";
import RostersPanel from "../components/RostersPanel";
import type { Dashboard, InjuryInfo, TeamLineup } from "../lib/api";
import { injuryLabel } from "../lib/injury";
import { expectNoA11yViolations } from "./a11y";

const injury = (status: string, body_part: string | null = null): InjuryInfo => ({
  status,
  body_part,
});

describe("injuryLabel", () => {
  it("maps Sleeper designations to plain words and a severity", () => {
    expect(injuryLabel(injury("Out"))).toEqual({ tone: "out", text: "Out", bodyPart: null });
    expect(injuryLabel(injury("IR"))?.tone).toBe("out");
    expect(injuryLabel(injury("PUP"))?.tone).toBe("out");
    expect(injuryLabel(injury("Sus"))?.text).toBe("Suspended");
    expect(injuryLabel(injury("DNR"))?.text).toBe("Did not report");
    expect(injuryLabel(injury("Doubtful"))?.tone).toBe("doubtful");
    expect(injuryLabel(injury("Questionable", "Hamstring"))).toEqual({
      tone: "questionable",
      text: "Questionable",
      bodyPart: "Hamstring",
    });
  });

  it("shows an unrecognised designation as written, with a neutral tone", () => {
    expect(injuryLabel(injury("Day-to-day"))).toEqual({
      tone: "other",
      text: "Day-to-day",
      bodyPart: null,
    });
  });

  it("leaves out an undisclosed body part and returns nothing when healthy", () => {
    expect(injuryLabel(injury("Out", "Undisclosed"))?.bodyPart).toBeNull();
    expect(injuryLabel(null)).toBeNull();
    expect(injuryLabel(undefined)).toBeNull();
    expect(injuryLabel(injury(""))).toBeNull();
  });
});

describe("InjuryBadge", () => {
  it("has no accessibility violations for each severity", async () => {
    await expectNoA11yViolations(
      <div>
        <InjuryBadge injury={injury("Out")} />
        <InjuryBadge injury={injury("Doubtful", "Knee")} />
        <InjuryBadge injury={injury("Questionable", "Ankle")} />
      </div>,
    );
  });

  it("puts the designation and body part in visible text", () => {
    render(<InjuryBadge injury={injury("Questionable", "Hamstring")} />);
    expect(screen.getByText("Questionable")).toBeInTheDocument();
    expect(screen.getByText("Hamstring")).toBeInTheDocument();
  });

  it("renders nothing for a healthy player", () => {
    const { container } = render(<InjuryBadge injury={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("injury status on rosters and lineups", () => {
  const rosters: Dashboard["rosters"] = [
    {
      roster_id: 1,
      team: "Cole",
      owner_id: "u1",
      players: [
        {
          player_id: "1",
          name: "Hurt Back",
          position: "RB",
          team: "SF",
          status: "starter",
          slot: "RB",
          injury: injury("Questionable", "Hamstring"),
        },
        {
          player_id: "2",
          name: "Healthy QB",
          position: "QB",
          team: "HOU",
          status: "bench",
          slot: null,
        },
      ],
    },
  ];

  it("shows the designation next to the player on the roster", () => {
    render(<RostersPanel rosters={rosters} myRosterId={1} />);
    expect(screen.getByText("Questionable")).toBeInTheDocument();
    expect(screen.getByText("Hamstring")).toBeInTheDocument();
    expect(screen.getAllByText(/Questionable/)).toHaveLength(1); // the healthy player has none
  });

  const lineup = (id: number, name: string, withInjury: boolean): TeamLineup => ({
    roster_id: id,
    team: name,
    owner_id: null,
    points: 0,
    starters: [
      {
        slot: "RB",
        player_id: `p${id}`,
        name: `${name} RB`,
        position: "RB",
        team: "SF",
        points: 0,
        injury: withInjury ? injury("Out", "Knee") : null,
      },
    ],
    bench: [],
  });

  it("shows the designation in the head-to-head lineup", async () => {
    const matchup = { matchup_id: 1, teams: [lineup(1, "Cole", true), lineup(2, "Dad", false)] };
    render(<MatchupCard matchup={matchup} state="current" week={6} myRosterId={1} />);
    expect(screen.getByText("Out")).toBeInTheDocument();
    expect(screen.getAllByText("Out")).toHaveLength(1);
    await expectNoA11yViolations(
      <MatchupCard matchup={matchup} state="current" week={6} myRosterId={1} />,
    );
  });

  it("does not show today's injury designation against a week that was already played", () => {
    const matchup = { matchup_id: 1, teams: [lineup(1, "Cole", true), lineup(2, "Dad", false)] };
    render(<MatchupCard matchup={matchup} state="played" week={3} myRosterId={1} />);
    expect(screen.queryByText("Out")).not.toBeInTheDocument();
  });

  it("does show it for an upcoming week", () => {
    const matchup = { matchup_id: 1, teams: [lineup(1, "Cole", true), lineup(2, "Dad", false)] };
    render(<MatchupCard matchup={matchup} state="upcoming" week={7} myRosterId={1} />);
    expect(screen.getByText("Out")).toBeInTheDocument();
  });
});
