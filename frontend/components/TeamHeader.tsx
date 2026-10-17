import type { Lineups, StandingsRow } from "../lib/api";
import { formatProjection, matchupFor } from "../lib/lineups";
import { teamStanding } from "../lib/teamStanding";
import TeamAvatar from "./TeamAvatar";

/**
 * The top of a team's page, like Sleeper's: its picture and name, then record, place and how it
 * ranks in points for and against, with this week's projection on the right.
 */
export default function TeamHeader({
  rosterId,
  name,
  headingId,
  standings,
  lineups,
}: {
  rosterId: number;
  name: string;
  headingId: string;
  standings?: StandingsRow[];
  lineups?: Lineups | null;
}) {
  const standing = teamStanding(standings, rosterId);
  const found = matchupFor(lineups, rosterId);
  const projected = formatProjection(found?.team.projected);
  return (
    <div className="team-header">
      <TeamAvatar rosterId={rosterId} name={name} picture={found?.team.avatar} />
      <div className="team-header-main">
        <h2 id={headingId} className="team-header-name">
          {name}
        </h2>
        {standing && (
          <ul className="team-header-line" aria-label="Standing">
            <li>
              {standing.record}
              {standing.streak && <span className="team-header-streak"> {standing.streak}</span>}
            </li>
            <li>{standing.place}</li>
            <li title="Points scored: 1st is the most">PF {standing.pointsFor}</li>
            <li title="Points allowed: 1st is the fewest">PA {standing.pointsAgainst}</li>
          </ul>
        )}
      </div>
      {projected && (
        <p className="team-header-proj">
          <strong className="num">{projected}</strong>
          <span className="muted">{found?.week ? `Week ${found.week} proj` : "proj"}</span>
        </p>
      )}
    </div>
  );
}
