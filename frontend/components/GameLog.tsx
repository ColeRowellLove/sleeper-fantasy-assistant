import type { PlayerDetail } from "../lib/api";
import { gameLogRows, opponentText, rankTone } from "../lib/gameLog";
import { formatStat } from "../lib/playerDetail";
import { projectionDelta } from "../lib/lineups";
import StatTable from "./StatTable";
import TeamLink from "./TeamLink";

type Column = { key: string; label: string };

/**
 * His whole season, one row per week, like Sleeper's game log: the opponent coloured by how hard
 * the matchup is, the week's points and his rank at the position tinted by that rank (the number
 * is always shown), then the stat columns. Weeks still to come are dashes, a bye is a grey row,
 * and the week and opponent stay in view while the table scrolls sideways.
 */
export default function GameLog({
  detail,
  columns,
  totals,
}: {
  detail: PlayerDetail;
  columns: Column[];
  totals: Record<string, number>;
}) {
  const rows = gameLogRows(detail);
  const showProjections = detail.weeks.some(
    (w) => w.projected !== null && w.projected !== undefined,
  );
  const allProjected =
    detail.weeks.length > 0 &&
    detail.weeks.every((w) => w.projected !== null && w.projected !== undefined);
  const projectedTotal = detail.weeks.reduce((sum, w) => sum + (w.projected ?? 0), 0);
  // a player traded mid-season shows which team each week was for
  const multiTeam = new Set(detail.weeks.map((w) => w.team).filter(Boolean)).size > 1;
  const span = 2 + (multiTeam ? 1 : 0) + 2 + (showProjections ? 2 : 0) + columns.length;
  const dash = <span className="gl-dash">–</span>;

  if (rows.length === 0) return <p className="note">No games played yet this season.</p>;
  return (
    <StatTable
      bare
      caption="Every week of the season: opponent, points, rank at his position, and stats"
      className="pd-table pd-stats-table gamelog"
      scrollLabel="Game log, scrolls sideways"
    >
      <thead>
        <tr>
          <th scope="col" className="gl-sticky gl-week">
            Wk
          </th>
          <th scope="col" className="gl-sticky gl-opp">
            Opp
          </th>
          {multiTeam && <th scope="col">Team</th>}
          <th scope="col" className="num-col">
            Pts
          </th>
          <th scope="col" className="num-col">
            Rank
          </th>
          {showProjections && (
            <>
              <th scope="col" className="num-col">
                Proj
              </th>
              <th scope="col" className="num-col">
                +/-
              </th>
            </>
          )}
          {columns.map((c) => (
            <th key={c.key} scope="col" className="num-col">
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          if (row.kind === "bye") {
            return (
              <tr key={row.week} className="gl-bye">
                <th scope="row" className="gl-sticky gl-week">
                  {row.week}
                </th>
                <td colSpan={span - 1} className="gl-bye-cell">
                  BYE
                </td>
              </tr>
            );
          }
          const opponent = opponentText(row);
          const tone = rankTone(row.rank);
          return (
            <tr key={row.week} className={row.kind === "upcoming" ? "gl-upcoming" : undefined}>
              <th scope="row" className="gl-sticky gl-week">
                {row.week}
              </th>
              <td className="gl-sticky gl-opp">
                {opponent ? (
                  <span
                    className={`gl-opponent${row.difficulty ? ` diff-${row.difficulty}` : ""}`}
                    title={row.difficulty ? `${row.difficulty} matchup` : undefined}
                  >
                    <TeamLink team={row.opponent ?? ""}>{opponent}</TeamLink>
                    {row.difficulty && (
                      <span className="visually-hidden"> ({row.difficulty} matchup)</span>
                    )}
                  </span>
                ) : (
                  dash
                )}
              </td>
              {multiTeam && (
                <td>{row.team ? <TeamLink team={row.team}>{row.team}</TeamLink> : dash}</td>
              )}
              <td className="num num-col">{row.points === null ? dash : row.points.toFixed(1)}</td>
              <td className={`num num-col${tone ? ` tone-${tone}` : ""}`}>
                {row.rank === null ? dash : row.rank}
              </td>
              {showProjections && (
                <>
                  <td className="num num-col">
                    {row.projected === null ? dash : row.projected.toFixed(1)}
                  </td>
                  <td className="num num-col">
                    {row.points === null
                      ? dash
                      : (projectionDelta(
                          row.points,
                          row.projected,
                          row.final ? "played" : "current",
                        ) ?? dash)}
                  </td>
                </>
              )}
              {columns.map((c) => (
                <td key={c.key} className="num num-col">
                  {row.kind === "played" ? formatStat(row.stats[c.key]) : dash}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row" colSpan={multiTeam ? 3 : 2} className="gl-sticky">
            Season total
          </th>
          <td className="num num-col">{detail.season.points.toFixed(1)}</td>
          <td className="num num-col">{detail.season.rank ?? dash}</td>
          {showProjections && (
            <>
              <td className="num num-col">{allProjected ? projectedTotal.toFixed(1) : dash}</td>
              <td className="num num-col">
                {allProjected && detail.weeks.every((w) => w.final)
                  ? (projectionDelta(detail.season.points, projectedTotal, "played") ?? dash)
                  : dash}
              </td>
            </>
          )}
          {columns.map((c) => (
            <td key={c.key} className="num num-col">
              {formatStat(totals[c.key])}
            </td>
          ))}
        </tr>
        {detail.projected && (
          <tr className="pd-projected-row">
            <th scope="row" colSpan={multiTeam ? 3 : 2} className="gl-sticky">
              Projected, week {detail.projected.week}
            </th>
            <td className="num num-col">{detail.projected.points.toFixed(1)}</td>
            <td className="num num-col">{dash}</td>
            {showProjections && (
              <>
                <td className="num num-col">{dash}</td>
                <td className="num num-col">{dash}</td>
              </>
            )}
            {columns.map((c) => (
              <td key={c.key} className="num num-col">
                {formatStat(detail.projected?.stats[c.key])}
              </td>
            ))}
          </tr>
        )}
      </tfoot>
    </StatTable>
  );
}
