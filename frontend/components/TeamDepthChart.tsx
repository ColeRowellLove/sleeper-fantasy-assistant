import type { DepthPlayer, DepthSlot, TeamDepth } from "../lib/api";
import { depthRows, groupSlots, TEAM_NAMES } from "../lib/depth";
import GameBadge from "./GameBadge";
import InjuryBadge from "./InjuryBadge";
import PlayerLink from "./PlayerLink";

function PlayerCell({ player, myRosterId }: { player: DepthPlayer; myRosterId: number | null }) {
  const mine = myRosterId !== null && player.owner_roster_id === myRosterId;
  return (
    <span className={`depth-player${player.next_up ? " next-up" : ""}`}>
      <span className="depth-name">
        {player.player_id ? (
          <PlayerLink playerId={player.player_id}>{player.name}</PlayerLink>
        ) : (
          player.name
        )}
      </span>
      <InjuryBadge injury={player.injury} />
      {player.next_up && <span className="depth-tag">Next up</span>}
      {player.owner_team ? (
        <span className="depth-owner">
          {mine ? "On your team" : `On ${player.owner_team}`}
        </span>
      ) : player.player_id ? (
        <span className="depth-available">Available</span>
      ) : null}
    </span>
  );
}

function SlotTable({ slots, myRosterId }: { slots: DepthSlot[]; myRosterId: number | null }) {
  const { columns, rows } = depthRows(slots);
  return (
    <div className="players-scroll">
      <table className="players depth-table">
        <thead>
          <tr>
            <th scope="col">Position</th>
            {columns.map((c) => (
              <th key={c.depth} scope="col">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ slot, cells }) => (
            <tr key={slot.slot}>
              <th scope="row">
                {slot.label}
                {slot.note && <span className="depth-note">{slot.note}</span>}
              </th>
              {cells.map((player, i) =>
                player ? (
                  <td key={columns[i].depth}>
                    <PlayerCell player={player} myRosterId={myRosterId} />
                  </td>
                ) : (
                  <td key={columns[i].depth} className="muted">
                    –
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One NFL team's depth chart: fantasy positions first, the full chart in sections that open. */
export default function TeamDepthChart({
  data,
  myRosterId,
}: {
  data: TeamDepth;
  myRosterId: number | null;
}) {
  const sections = groupSlots(data.groups);
  const name = TEAM_NAMES[data.team] ?? data.team;
  const updated = data.updated_at ? new Date(data.updated_at) : null;

  return (
    <section aria-labelledby="depth-heading" className="depth-chart">
      <h2 id="depth-heading">{name} depth chart</h2>
      <p className="depth-meta">
        <GameBadge game={data.game} />
        {data.source && (
          <span className="muted">
            Source: {data.source}
            {updated ? `, updated ${updated.toISOString().slice(0, 16).replace("T", " ")} UTC` : ""}
          </span>
        )}
      </p>

      {sections.skill.length === 0 && sections.more.length === 0 ? (
        <p className="note">No depth chart is available for this team yet.</p>
      ) : (
        <>
          {sections.skill.length > 0 && (
            <div className="card flush">
              <h3 className="depth-section-title">Fantasy positions</h3>
              <SlotTable slots={sections.skill} myRosterId={myRosterId} />
            </div>
          )}
          {sections.more.map((section) => (
            <details key={section.key} className="card flush depth-details">
              <summary>{section.title}</summary>
              <SlotTable slots={section.slots} myRosterId={myRosterId} />
            </details>
          ))}
        </>
      )}
      <p className="note">
        Depth order is 1 for the starter. A &quot;Next up&quot; tag shows who is first in line when a
        starter is out. Charts change with injuries and news, so check close to kickoff.
      </p>
    </section>
  );
}
