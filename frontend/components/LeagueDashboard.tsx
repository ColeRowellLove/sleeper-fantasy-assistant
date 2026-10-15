import type { Dashboard, RosterPlayer } from "../lib/api";

export function roleLabel(p: RosterPlayer): string {
  if (p.status === "starter") return p.slot ? `Starter (${p.slot})` : "Starter";
  if (p.status === "ir") return "IR";
  if (p.status === "taxi") return "Taxi";
  return "Bench";
}

/** Rosters tab. Rebuilt in the next redesign step (player faces, positions, team picker). */
export default function LeagueDashboard({ data }: { data: Dashboard }) {
  return (
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
  );
}
