import type { DepthPlayer, DepthSlot, TeamDepth } from "../lib/api";
import { depthRows, groupSlots, recordText, SLIDE_FROM, TEAM_NAMES } from "../lib/depth";
import { unitOnField, type Unit } from "../lib/game";
import GameBadge from "./GameBadge";
import LocalTime from "./LocalTime";
import InjuryBadge from "./InjuryBadge";
import TeamLogo from "./TeamLogo";
import TeamStatsTable from "./TeamStatsTable";
import PlayerLink from "./PlayerLink";
import NoteList from "./NoteList";

function PlayerCell({
  player,
  myRosterId,
  highlightId,
}: {
  player: DepthPlayer;
  myRosterId: number | null;
  highlightId?: string | null;
}) {
  const mine = myRosterId !== null && player.owner_roster_id === myRosterId;
  return (
    <span
      className={`depth-player${player.next_up ? " next-up" : ""}${
        highlightId && player.player_id === highlightId ? " is-viewed" : ""
      }`}
    >
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
        <span className="depth-owner">{mine ? "On your team" : `On ${player.owner_team}`}</span>
      ) : player.player_id ? (
        <span className="depth-available">Available</span>
      ) : null}
    </span>
  );
}

function SlotTable({
  slots,
  myRosterId,
  highlightId,
  title,
}: {
  slots: DepthSlot[];
  myRosterId: number | null;
  highlightId?: string | null;
  title: string;
}) {
  const { columns, rows } = depthRows(slots);
  const slides = columns.length > SLIDE_FROM;
  return (
    <>
      {slides && (
        <p className="depth-slide-hint">Slide sideways to see all {columns.length} depth levels.</p>
      )}
      {/* a focusable, labelled scroll region so keyboard users can slide it with the arrow keys */}
      <div
        className="players-scroll depth-scroll"
        role="group"
        aria-label={`${title} depth, ${columns.length} levels${slides ? ", scrolls sideways" : ""}`}
        tabIndex={0}
      >
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
                      <PlayerCell
                        player={player}
                        myRosterId={myRosterId}
                        highlightId={highlightId}
                      />
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
    </>
  );
}

/** One NFL team's depth chart: fantasy positions first, the full chart in sections that open. */
export default function TeamDepthChart({
  data,
  myRosterId,
  highlightId = null,
  compact = false,
  headingId = "depth-heading",
  landmark = true,
}: {
  data: TeamDepth;
  myRosterId: number | null;
  /** A player to mark in the chart, such as the one whose pop-up it is shown in. */
  highlightId?: string | null;
  /** Just the chart: no title, game line, team stats or notes (for a place that has its own). */
  compact?: boolean;
  /** Differs when the chart is shown in a pop-up over a page that already has one. */
  headingId?: string;
  /** A page section is a landmark; inside a dialog it is just content (and would clash with the page's). */
  landmark?: boolean;
}) {
  const Wrapper = landmark ? "section" : "div";
  const sections = groupSlots(data.groups);
  const name = TEAM_NAMES[data.team] ?? data.team;
  // while the game is live, the unit on the field is marked in words on its sections
  const onField = unitOnField(data.game, data.team);
  const marker = (unit: Unit | null) =>
    unit !== null && unit === onField ? <span className="unit-on">On the field now</span> : null;
  // fantasy positions are the offense's; the other sections are named by the chart's own keys
  const SECTION_UNITS: Record<string, Unit> = { "offense-line": "offense", defense: "defense" };

  return (
    <Wrapper {...(landmark ? { "aria-labelledby": headingId } : {})} className="depth-chart">
      {compact ? (
        <h3 id={headingId}>Depth chart</h3>
      ) : (
        <>
          <div className="depth-title">
            <TeamLogo team={data.team} />
            <h2 id={headingId}>{name} depth chart</h2>
            {data.record && (
              <span className="depth-record">
                <span aria-hidden="true">{recordText(data.record).short}</span>
                <span className="visually-hidden">{recordText(data.record).spoken}</span>
              </span>
            )}
          </div>
          <p className="depth-meta">
            <GameBadge game={data.game} conditions="full" />
            {data.source && (
              <span className="muted">
                Source: {data.source}
                {data.updated_at && (
                  <>
                    , updated <LocalTime iso={data.updated_at} />
                  </>
                )}
              </span>
            )}
          </p>
        </>
      )}

      {sections.skill.length === 0 && sections.more.length === 0 ? (
        <p className="note">No depth chart is available for this team yet.</p>
      ) : (
        <>
          {sections.skill.length > 0 && (
            <div className="card flush">
              <h3 className="depth-section-title">
                Fantasy positions
                {marker("offense")}
              </h3>
              <SlotTable
                slots={sections.skill}
                myRosterId={myRosterId}
                highlightId={highlightId}
                title="Fantasy positions"
              />
            </div>
          )}
          {sections.more.map((section) => (
            <details key={section.key} className="card flush depth-details">
              <summary>
                {section.title}
                {marker(SECTION_UNITS[section.key] ?? null)}
              </summary>
              <SlotTable
                slots={section.slots}
                myRosterId={myRosterId}
                highlightId={highlightId}
                title={section.title}
              />
            </details>
          ))}
        </>
      )}
      {!compact && data.stats && data.stats.length > 0 && (
        <TeamStatsTable
          stats={data.stats}
          team={data.team}
          headingId={`${headingId}-stats`}
          title="Team stats"
        />
      )}
      <NoteList
        items={[
          "Depth order is 1 for the starter",
          'A "Next up" tag shows who is first in line when a starter is out',
          "Charts change with injuries and news, so check close to kickoff",
        ]}
      />
    </Wrapper>
  );
}
