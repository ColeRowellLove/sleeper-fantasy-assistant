import type { Dashboard, RosterPlayer } from "../lib/api";

export function roleLabel(p: RosterPlayer): string {
  if (p.status === "starter") return p.slot ? `Starter (${p.slot})` : "Starter";
  if (p.status === "ir") return "IR";
  if (p.status === "taxi") return "Taxi";
  return "Bench";
}

export default function LeagueDashboard({
  data,
  myRosterId = null,
}: {
  data: Dashboard;
  myRosterId?: number | null;
}) {
  const { rules } = data;
  return (
    <>
      <h1>{data.name}</h1>
      <p>{data.season} season</p>

      <section aria-labelledby="rules-heading">
        <h2 id="rules-heading">League rules</h2>
        <dl>
          <dt>Reception scoring</dt>
          <dd>{rules.reception_scoring}</dd>
          <dt>Waivers</dt>
          <dd>{rules.uses_faab ? "FAAB" : "Priority"}</dd>
          <dt>Trade deadline</dt>
          <dd>{rules.trade_deadline_week ? `Week ${rules.trade_deadline_week}` : "None"}</dd>
          <dt>Playoff teams</dt>
          <dd>{rules.playoff_teams ?? "Not set"}</dd>
        </dl>
      </section>

      <section aria-labelledby="standings-heading">
        <h2 id="standings-heading">Standings</h2>
        <table>
          <caption className="visually-hidden">League standings, best record first</caption>
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col">Team</th>
              <th scope="col">W-L-T</th>
              <th scope="col">PF</th>
              <th scope="col">PA</th>
            </tr>
          </thead>
          <tbody>
            {data.standings.map((row) => (
              <tr
                key={row.roster_id}
                className={row.roster_id === myRosterId ? "mine" : undefined}
                aria-current={row.roster_id === myRosterId ? "true" : undefined}
              >
                <td>{row.rank}</td>
                <th scope="row">
                  {row.team}
                  {row.roster_id === myRosterId && <span className="you">You</span>}
                </th>
                <td>
                  {row.wins}-{row.losses}-{row.ties}
                </td>
                <td>{row.points_for.toFixed(2)}</td>
                <td>{row.points_against.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="rosters-heading">
        <h2 id="rosters-heading">Rosters</h2>
        {data.rosters.map((roster) => (
          <details key={roster.roster_id}>
            <summary>
              {roster.team} ({roster.players.length} players)
            </summary>
            <table>
              <caption className="visually-hidden">
                {roster.team} roster: starters, then bench, IR and taxi
              </caption>
              <thead>
                <tr>
                  <th scope="col">Role</th>
                  <th scope="col">Player</th>
                  <th scope="col">Pos</th>
                  <th scope="col">Team</th>
                </tr>
              </thead>
              <tbody>
                {roster.players.map((p) => (
                  <tr key={p.player_id}>
                    <td>{roleLabel(p)}</td>
                    <th scope="row">{p.name}</th>
                    <td>{p.position ?? "–"}</td>
                    <td>{p.team ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        ))}
      </section>
    </>
  );
}
