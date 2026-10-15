import type { Lineups } from "../lib/api";
import MatchupCard from "./MatchupCard";

type Matchup = Lineups["matchups"][number];

const p = (slot: string, name: string, position: string, team: string, points: number) => ({
  slot,
  player_id: null as string | null,
  name,
  position,
  team,
  points,
});

// Made-up placeholder players and teams: a decorative preview of the real matchup view.
const SAMPLE: Matchup = {
  matchup_id: 1,
  teams: [
    {
      roster_id: 1,
      team: "Your team",
      owner_id: null,
      points: 104.2,
      starters: [p("QB", "Starting QB", "QB", "HOU", 27.3), p("RB", "Lead back", "RB", "SF", 15.8)],
      bench: [p("BN", "Bench receiver", "WR", "MIN", 3.2)],
    },
    {
      roster_id: 2,
      team: "Rival",
      owner_id: null,
      points: 98.1,
      starters: [p("QB", "Their QB", "QB", "CHI", 21.4), p("RB", "Their back", "RB", "DAL", 19.9)],
      bench: [p("BN", "Bench tight end", "TE", "NYG", 8.1)],
    },
  ],
};

/** Decorative preview (hidden from assistive technology) built from the real matchup card. */
export default function SampleMatchup() {
  return (
    <div className="sample" aria-hidden="true">
      <p className="note">Sample matchup</p>
      <MatchupCard matchup={SAMPLE} state="played" week={0} myRosterId={1} mine />
    </div>
  );
}
