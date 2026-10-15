import type { StandingsRow } from "../lib/api";
import { formatRecord } from "../lib/league";

export default function StandingsTable({
  standings,
  playoffTeams,
  myRosterId,
}: {
  standings: StandingsRow[];
  playoffTeams: number | null;
  myRosterId: number | null;
}) {
  return (
    <section aria-labelledby="standings-heading">
      <h2 id="standings-heading" className="visually-hidden">
        Standings
      </h2>
      <div className="card flush">
        <table className="standings">
          <caption className="visually-hidden">League standings, best record first</caption>
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col">Team</th>
              <th scope="col">Record</th>
              <th scope="col" className="num-col">
                PF
              </th>
              <th scope="col" className="num-col">
                PA
              </th>
            </tr>
          </thead>
          <tbody>
            {standings.map((row) => {
              const mine = row.roster_id === myRosterId;
              const inPlayoffs = playoffTeams !== null && row.rank <= playoffTeams;
              const classes = [
                mine ? "mine" : "",
                inPlayoffs ? "playoff" : "",
                inPlayoffs && row.rank === playoffTeams ? "cutoff" : "",
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <tr
                  key={row.roster_id}
                  className={classes || undefined}
                  aria-current={mine ? "true" : undefined}
                >
                  <td className="rank num">
                    {row.rank}
                    {inPlayoffs && <span className="visually-hidden"> (playoff position)</span>}
                  </td>
                  <th scope="row">
                    {row.team}
                    {mine && <span className="you">You</span>}
                  </th>
                  <td className="num">{formatRecord(row.wins, row.losses, row.ties)}</td>
                  <td className="num num-col">{row.points_for.toFixed(2)}</td>
                  <td className="num num-col">{row.points_against.toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {playoffTeams !== null && (
        <p className="note">
          The top {playoffTeams} teams make the playoffs (marked with a bar and a line below
          {` #${playoffTeams}`}).
        </p>
      )}
    </section>
  );
}
