import type { LineupPlayer, Lineups, TeamLineup } from "../lib/api";

function pts(value: number | null): string {
  return value === null ? "–" : value.toFixed(2);
}

function LineupTable({ team }: { team: TeamLineup }) {
  const rows: LineupPlayer[] = [...team.starters, ...team.bench];
  return (
    <table>
      <caption>
        {team.team}: {team.points.toFixed(2)} points
      </caption>
      <thead>
        <tr>
          <th scope="col">Slot</th>
          <th scope="col">Player</th>
          <th scope="col">Pos</th>
          <th scope="col">NFL</th>
          <th scope="col">Pts</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p, i) => (
          <tr key={`${p.slot}-${p.player_id ?? "empty"}-${i}`}>
            <td>{p.slot === "BN" ? "Bench" : p.slot}</td>
            <th scope="row">{p.name}</th>
            <td>{p.position ?? "–"}</td>
            <td>{p.team ?? "–"}</td>
            <td>{pts(p.points)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function WeeklyLineups({ data }: { data: Lineups }) {
  return (
    <section aria-labelledby="lineups-heading">
      <h2 id="lineups-heading">Weekly lineups</h2>

      {data.weeks.length > 0 && (
        // A plain GET form works without JavaScript and is keyboard/screen-reader friendly.
        <form method="get">
          <label htmlFor="week">Week</label>
          <select id="week" name="week" defaultValue={data.week ?? undefined}>
            {data.weeks.map((w) => (
              <option key={w} value={w}>
                Week {w}
              </option>
            ))}
          </select>
          <button type="submit">Show week</button>
        </form>
      )}

      {data.matchups.length === 0 && <p>No matchups have been synced yet.</p>}

      {data.matchups.map((m, i) => (
        <article key={m.matchup_id ?? `solo-${i}`} aria-label={m.teams.map((t) => t.team).join(" vs ")}>
          <h3>
            {m.teams.map((t) => t.team).join(" vs ")}
            {m.teams.length > 1 && (
              <span className="muted"> ({m.teams.map((t) => t.points.toFixed(2)).join(" – ")})</span>
            )}
          </h3>
          <div className="matchup">
            {m.teams.map((team) => (
              <LineupTable key={team.roster_id} team={team} />
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}
