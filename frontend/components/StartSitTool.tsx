import type { BestLineup, Dashboard, StartSitCandidate, StartSitComparison } from "../lib/api";
import { leaguePath } from "../lib/league";
import GameBadge from "./GameBadge";
import PlayerAvatar from "./PlayerAvatar";
import InjuryBadge from "./InjuryBadge";
import PlayerIdentity from "./PlayerIdentity";
import PlayerLink from "./PlayerLink";
import PositionChip from "./PositionChip";
import StatTable from "./StatTable";

const number = (n: number | null | undefined) =>
  n === null || n === undefined ? "–" : n.toFixed(1);

function PlayerCell({ c }: { c: StartSitCandidate }) {
  return (
    <PlayerIdentity
      player_id={c.player_id}
      name={c.name}
      position={c.position}
      team={c.team}
      injury={c.injury}
    />
  );
}

/**
 * Start/Sit: the best lineup the roster allows and a side-by-side comparison for one spot. Both
 * are plain GET forms, so they work without JavaScript and every result has its own link.
 */
export default function StartSitTool({
  leagueId,
  rosters,
  rosterId,
  picks,
  week,
  best,
  comparison,
}: {
  leagueId: string;
  rosters: Dashboard["rosters"];
  rosterId: number;
  picks: string[];
  week: number | null;
  best: BestLineup | null;
  comparison: StartSitComparison | null;
}) {
  const roster = rosters.find((r) => r.roster_id === rosterId) ?? rosters[0];
  const action = leaguePath(leagueId);
  const weekField = week ? <input type="hidden" name="week" value={week} /> : null;
  const choices = (roster?.players ?? []).filter((p) => p.status !== "ir" && p.status !== "taxi");
  // the server's candidates carry projection, matchup and game; the plain roster is the fallback
  const base: StartSitCandidate[] =
    best?.roster && best.roster.length > 0
      ? best.roster
      : choices.map((p) => ({
          player_id: p.player_id,
          name: p.name,
          position: p.position ?? null,
          team: p.team ?? null,
          sources: 0,
        }));
  // a player picked in the link (or compared above) always keeps his checkbox
  const known = new Set(base.map((p) => p.player_id));
  const pickable = [
    ...base,
    ...(comparison?.candidates ?? []).filter((c) => !known.has(c.player_id)),
  ];

  return (
    <section aria-labelledby="startsit-heading">
      <h2 id="startsit-heading">Start/Sit</h2>
      <p className="note">
        Compare players for a lineup spot or see the best lineup for the week. Projections use this
        league&apos;s scoring.
      </p>

      <form method="get" action={action} className="players-controls">
        <input type="hidden" name="tab" value="startsit" />
        {weekField}
        <label>
          Team{" "}
          <select name="roster" defaultValue={String(roster?.roster_id ?? "")}>
            {rosters.map((r) => (
              <option key={r.roster_id} value={r.roster_id}>
                {r.team}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn">
          Show team
        </button>
      </form>

      {best && (
        <section aria-labelledby="best-heading" className="card flush">
          <h3 id="best-heading" className="depth-section-title">
            Best lineup{best.week ? `, week ${best.week}` : ""}
          </h3>
          <p className="note">
            Projected {best.projected.toFixed(1)} against {best.current_projected.toFixed(1)} for
            the current lineup.
          </p>
          <StatTable bare caption="Best projected lineup by slot" className="pd-table">
            <thead>
              <tr>
                <th scope="col">Slot</th>
                <th scope="col">Player</th>
                <th scope="col" className="hide-narrow">
                  Opponent
                </th>
                <th scope="col" className="num">
                  Proj
                </th>
              </tr>
            </thead>
            <tbody>
              {best.lineup.map((spot, i) => (
                <tr key={`${spot.slot}-${i}`}>
                  <th scope="row">{spot.slot}</th>
                  {spot.player ? (
                    <>
                      <td>
                        <PlayerCell c={spot.player} />
                      </td>
                      <td className="hide-narrow">
                        <GameBadge
                          game={spot.player.game}
                          matchup={spot.player.matchup}
                          position={spot.player.position}
                        />
                      </td>
                      <td className="num">{number(spot.player.projected)}</td>
                    </>
                  ) : (
                    <td colSpan={3} className="muted">
                      No one on this roster can fill this slot.
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </StatTable>
          {best.changes.length > 0 && (
            <>
              <h4 className="depth-section-title">Swaps to make</h4>
              <ul className="startsit-changes">
                {best.changes.map((c) => (
                  <li key={`${c.start.player_id}-${c.sit.player_id}`}>
                    Start <PlayerLink playerId={c.start.player_id}>{c.start.name}</PlayerLink> (
                    {number(c.start.projected)}) over{" "}
                    <PlayerLink playerId={c.sit.player_id}>{c.sit.name}</PlayerLink> (
                    {number(c.sit.projected)}): +{c.gain.toFixed(1)} projected points
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      <form method="get" action={action} className="card startsit-compare">
        <input type="hidden" name="tab" value="startsit" />
        <input type="hidden" name="roster" value={roster?.roster_id} />
        {weekField}
        <fieldset>
          <legend>Players to compare (pick two to six)</legend>
          <ul className="pick-rows">
            {pickable.map((p) => (
              <li key={p.player_id}>
                <div className="pick-row">
                  <input
                    id={`pick-${p.player_id}`}
                    type="checkbox"
                    name="pick"
                    value={p.player_id}
                    defaultChecked={picks.includes(p.player_id)}
                    aria-describedby={`pick-info-${p.player_id}`}
                  />
                  <PlayerAvatar
                    player_id={p.player_id}
                    name={p.name}
                    position={p.position}
                    team={p.team}
                  />
                  <span className="pick-main">
                    <label htmlFor={`pick-${p.player_id}`} className="player-name pick-label">
                      {p.name}
                    </label>
                    <span className="player-meta" id={`pick-info-${p.player_id}`}>
                      <PositionChip position={p.position} />
                      <span className="muted">{p.team ?? "FA"}</span>
                      <InjuryBadge injury={p.injury} />
                      {p.game !== undefined && (
                        <GameBadge game={p.game} matchup={p.matchup} position={p.position} />
                      )}
                    </span>
                    {p.out && p.out !== "no projection this week" && (
                      <span className="pick-out">Can&apos;t start: {p.out}</span>
                    )}
                  </span>
                  <span className="pick-proj num">
                    {p.projected === undefined
                      ? ""
                      : p.projected === null
                        ? "No projection yet"
                        : `Proj ${p.projected.toFixed(1)}`}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </fieldset>
        <button type="submit" className="btn">
          Compare
        </button>
      </form>

      {picks.length > 0 && picks.length < 2 && (
        <p className="note" role="status">
          Pick at least two players to compare.
        </p>
      )}

      {comparison && (
        <section aria-labelledby="compare-heading" className="card flush">
          <h3 id="compare-heading" className="depth-section-title">
            Recommendation
          </h3>
          <p className="startsit-why" role="status">
            {comparison.why}
          </p>
          <StatTable bare caption="Players compared, best first" className="pd-table">
            <thead>
              <tr>
                <th scope="col">Player</th>
                <th scope="col">Opponent</th>
                <th scope="col" className="num">
                  Proj
                </th>
                <th scope="col" className="num">
                  Last 3 avg
                </th>
                <th scope="col" className="num">
                  Consensus rank
                </th>
                <th scope="col">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {comparison.candidates.map((c) => (
                <tr key={c.player_id}>
                  <th scope="row" className="player-cell">
                    <PlayerCell c={c} />
                  </th>
                  <td>
                    {c.game ? (
                      <GameBadge
                        game={c.game}
                        matchup={c.matchup}
                        position={c.position}
                        conditions="compact"
                      />
                    ) : (
                      <span className="muted">No game found</span>
                    )}
                  </td>
                  <td className="num">{number(c.projected)}</td>
                  <td className="num">{number(c.form)}</td>
                  <td className="num">{c.rank ?? "–"}</td>
                  <td>
                    {c.player_id === comparison.start ? (
                      <span className="verdict verdict-start">
                        {comparison.close_call ? "Start (close call)" : "Start"}
                      </span>
                    ) : c.out ? (
                      <span className="verdict verdict-out">Can&apos;t start: {c.out}</span>
                    ) : (
                      <span className="verdict">Sit</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </StatTable>
        </section>
      )}
    </section>
  );
}
