"use client";

import { useState } from "react";

import type { Dashboard, RosterPlayer, RosterStatus } from "../lib/api";
import GameBadge from "./GameBadge";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PositionChip from "./PositionChip";

type Roster = Dashboard["rosters"][number];

const GROUPS: { status: RosterStatus; title: string; note: string }[] = [
  { status: "starter", title: "Starters", note: "In the lineup" },
  { status: "bench", title: "Bench", note: "Not in the lineup" },
  { status: "ir", title: "Injured reserve", note: "Out of the lineup, off the active roster" },
  { status: "taxi", title: "Taxi squad", note: "Stashed, not eligible to start" },
];

/** Rosters tab: pick a team, see its players grouped by role. Your team is listed and shown first. */
export default function RostersPanel({
  rosters,
  myRosterId,
  week = null,
}: {
  rosters: Roster[];
  myRosterId: number | null;
  week?: number | null;
}) {
  const ordered = [
    ...rosters.filter((r) => r.roster_id === myRosterId),
    ...rosters.filter((r) => r.roster_id !== myRosterId),
  ];
  const [selectedId, setSelectedId] = useState(ordered[0]?.roster_id ?? null);
  const selected = ordered.find((r) => r.roster_id === selectedId) ?? ordered[0];

  if (!selected) return <p className="note">No rosters have been synced yet.</p>;

  return (
    <section aria-labelledby="rosters-heading" className="rosters">
      <h2 id="rosters-heading" className="visually-hidden">
        Rosters
      </h2>
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

      {week !== null && (
        <p className="note">
          Game status is for NFL week {week}: upcoming, live, played, or bye.
        </p>
      )}

      <p role="status" className="visually-hidden">
        Showing {selected.team}: {selected.players.filter((p) => p.status === "starter").length}{" "}
        starters, {selected.players.length} players in total.
      </p>

      <div>
        {GROUPS.map(({ status, title, note }) => {
          const players = selected.players.filter((p) => p.status === status);
          if (players.length === 0) return null;
          return (
            <section key={status} className={`roster-group role-${status}`} aria-labelledby={`g-${status}`}>
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
  return (
    <li className="player">
      <PlayerAvatar
        player_id={player.player_id}
        name={player.name}
        position={player.position}
        team={player.team}
      />
      <span className="player-main">
        <span className="player-name">{player.name}</span>
        <span className="player-sub">{player.team ?? "No team"}</span>
        <span className="player-tags">
          <InjuryBadge injury={player.injury} />
          <GameBadge game={player.game} />
        </span>
      </span>
      {player.status === "starter" && player.slot && (
        <span className="slot" title="Lineup slot">
          <span className="visually-hidden">Slot </span>
          {player.slot}
        </span>
      )}
      <PositionChip position={player.position} />
    </li>
  );
}
