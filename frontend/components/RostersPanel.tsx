"use client";

import { useState } from "react";

import type { Dashboard, Lineups, RosterPlayer, RosterStatus } from "../lib/api";
import { notPlayedYet, ownershipText, slotShort } from "../lib/lineups";
import { positionClass } from "../lib/positions";
import GameLine from "./GameLine";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PlayerLink from "./PlayerLink";
import PlayerStatLine from "./PlayerStatLine";
import TeamLink from "./TeamLink";
import RosterMatchup from "./RosterMatchup";
import TeamHeader from "./TeamHeader";

type Roster = Dashboard["rosters"][number];

const GROUPS: { status: RosterStatus; title: string; note: string }[] = [
  { status: "starter", title: "Starters", note: "In the lineup" },
  { status: "bench", title: "Bench", note: "Not in the lineup" },
  { status: "ir", title: "Injured reserve", note: "Out of the lineup, off the active roster" },
  { status: "taxi", title: "Taxi squad", note: "Stashed, not eligible to start" },
];

const BENCH_SLOT: Record<RosterStatus, string | null> = {
  starter: null,
  bench: "BN",
  ir: "IR",
  taxi: "TAXI",
};

/** Rosters tab: pick a team, see its players grouped by role. Your team is listed and shown first. */
export default function RostersPanel({
  rosters,
  myRosterId,
  initialRosterId = null,
  lineups = null,
  standings,
  leagueId,
}: {
  rosters: Roster[];
  myRosterId: number | null;
  /** The team to start on (from a link); your own team when absent or unknown. */
  initialRosterId?: number | null;
  /** This week's lineups: the selected team's matchup and win chance come from here. */
  lineups?: Lineups | null;
  /** The standings, for the team header's record, place and points ranks. */
  standings?: Dashboard["standings"];
  leagueId: string;
}) {
  const ordered = [
    ...rosters.filter((r) => r.roster_id === myRosterId),
    ...rosters.filter((r) => r.roster_id !== myRosterId),
  ];
  const linked = ordered.find((r) => r.roster_id === initialRosterId);
  const [selectedId, setSelectedId] = useState(linked?.roster_id ?? ordered[0]?.roster_id ?? null);
  const selected = ordered.find((r) => r.roster_id === selectedId) ?? ordered[0];

  if (!selected) return <p className="note">No rosters have been synced yet.</p>;

  return (
    <section aria-labelledby="team-heading" className="rosters">
      <div className="picker-row">
        <label htmlFor="roster-team">Team</label>
        <select
          id="roster-team"
          value={selected.roster_id}
          onChange={(e) => setSelectedId(Number(e.target.value))}
        >
          {ordered.map((r) => (
            <option key={r.roster_id} value={r.roster_id}>
              {r.team}
              {r.roster_id === myRosterId ? " (you)" : ""}
            </option>
          ))}
        </select>
      </div>

      <TeamHeader
        rosterId={selected.roster_id}
        name={selected.team}
        headingId="team-heading"
        standings={standings}
        lineups={lineups}
      />

      <RosterMatchup lineups={lineups} rosterId={selected.roster_id} leagueId={leagueId} />

      <p role="status" className="visually-hidden">
        Showing {selected.team}: {selected.players.filter((p) => p.status === "starter").length}{" "}
        starters, {selected.players.length} players in total.
      </p>

      <div>
        {GROUPS.map(({ status, title, note }) => {
          const players = selected.players.filter((p) => p.status === status);
          if (players.length === 0) return null;
          return (
            <section
              key={status}
              className={`roster-group role-${status}`}
              aria-labelledby={`g-${status}`}
            >
              <header>
                <h3 id={`g-${status}`}>
                  {title} <span className="count">{players.length}</span>
                </h3>
                <p>{note}</p>
              </header>
              <ul>
                {players.map((p) => (
                  <PlayerItem key={p.player_id} player={p} />
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </section>
  );
}

function PlayerItem({ player }: { player: RosterPlayer }) {
  const slot = player.status === "starter" ? player.slot : BENCH_SLOT[player.status];
  const own = ownershipText(player);
  return (
    <li className="player">
      {slot && (
        <span className={`slot-chip ${positionClass(slot)}`}>
          <span className="visually-hidden">Slot {slot}</span>
          <span aria-hidden="true">{slotShort(slot)}</span>
        </span>
      )}
      <PlayerAvatar
        player_id={player.player_id}
        name={player.name}
        position={player.position}
        team={player.team}
      />
      <span className="player-main">
        <span className="player-name">
          <PlayerLink playerId={player.player_id}>{player.name}</PlayerLink>
          <span className="player-posteam">
            {player.position ?? "–"} ·{" "}
            {player.team ? <TeamLink team={player.team}>{player.team}</TeamLink> : "No team"}
          </span>
          <InjuryBadge injury={player.injury} />
        </span>
        {own && <span className="player-own">{own}</span>}
        <GameLine game={player.game} matchup={player.matchup} position={player.position} />
        <PlayerStatLine line={player.stat_line} projected={player.stat_line_projected} />
      </span>
      {/* three fixed-width columns on every row, so the numbers and slot line up; a row with
          no value keeps its (empty) column */}
      <span className="player-nums">
        {player.points !== null && player.points !== undefined ? (
          <span className="player-proj player-pts num">
            <span className="visually-hidden">Points this week </span>
            {player.points.toFixed(1)}
            <span className="player-proj-label" aria-hidden="true">
              pts
            </span>
          </span>
        ) : notPlayedYet("current", player.game) ? (
          <span className="player-proj player-pts num">
            <span className="visually-hidden">Not played yet</span>
            <span aria-hidden="true">–</span>
            <span className="player-proj-label" aria-hidden="true">
              pts
            </span>
          </span>
        ) : (
          <span className="player-proj player-pts" aria-hidden="true" />
        )}
        {player.projected !== null && player.projected !== undefined ? (
          <span className="player-proj num">
            <span className="visually-hidden">Projected </span>
            {player.projected.toFixed(1)}
            <span className="player-proj-label" aria-hidden="true">
              proj
            </span>
          </span>
        ) : (
          <span className="player-proj" aria-hidden="true" />
        )}
      </span>
    </li>
  );
}
