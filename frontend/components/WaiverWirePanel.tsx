"use client";

import { useState } from "react";

import type { Dashboard, WaiverWireData, WireEntry } from "../lib/api";
import { leaguePath } from "../lib/league";
import { VIEWS, entriesFor, stanceWord, type WireView } from "../lib/waiverView";
import FilterChips from "./FilterChips";
import PlayerIdentity from "./PlayerIdentity";
import NoteList from "./NoteList";
import ReasonChips from "./ReasonChips";

/** "Tue, Oct 20" from an ISO date, the same on the server and in the browser. */
export function waiverDateLabel(iso: string): string {
  const date = new Date(`${iso}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** "2 for, 1 against": the count in words. */
export function reasonCounts(entry: WireEntry): string {
  return `${entry.for_count} for, ${entry.against_count} against`;
}

function Entry({ entry, rank }: { entry: WireEntry; rank: number }) {
  return (
    <li className="card wire-entry">
      <div className="wire-title">
        <span className="wire-rank">{rank}</span>
        <PlayerIdentity
          player_id={entry.player_id}
          name={entry.name}
          position={entry.position}
          team={entry.team}
        />
        <span className="wire-numbers">
          <strong>{entry.projected.toFixed(1)}</strong> proj
          <span className="wire-gain">+{entry.gain.toFixed(1)}</span>
        </span>
      </div>
      <ReasonChips
        label={`Reasons for and against: ${reasonCounts(entry)}`}
        reasons={entry.reasons.filter((r) => r.stance !== "info")}
      />
      <details className="wire-why">
        <summary>Details</summary>
        <ul className="wire-signals">
          {entry.reasons.map((r) => (
            <li key={r.label}>
              <span className={`reason-word reason-${r.stance}`}>{stanceWord(r.stance)}</span>{" "}
              <strong>{r.label}:</strong> {r.detail}
            </li>
          ))}
        </ul>
      </details>
    </li>
  );
}

/**
 * The waiver wire for one team: this cycle's most recommended adds, best first, by position view
 * (Top adds, QB, RB, WR, TE, Flex, K, DEF). Each pick shows its reasons for and against as chips
 * marked in words as well as colour, with the full sentences under "Details". Which team is a
 * plain GET form (works without JavaScript).
 */
export default function WaiverWirePanel({
  data,
  rosters,
  leagueId,
  rosterId,
  myRosterId,
}: {
  data: WaiverWireData | null;
  rosters: Dashboard["rosters"];
  leagueId: string;
  rosterId: number | null;
  myRosterId: number | null;
}) {
  const [view, setView] = useState<WireView>("top");
  const entries = data ? entriesFor(data, view) : [];
  return (
    <section aria-labelledby="wire-heading">
      <h2 id="wire-heading">Waiver wire</h2>
      {data ? (
        <NoteList
          items={[
            <>
              Best adds for the {data.waiver_day} ({waiverDateLabel(data.waiver_date)}) waivers
              {data.week !== null && `, scored for week ${data.week}`}
            </>,
            "Only players available in this league, scored with its rules",
            "Compared with the selected team's lineup",
            "The list starts over each waiver cycle",
          ]}
        />
      ) : (
        <p className="note">The waiver wire could not be loaded. Try again in a moment.</p>
      )}

      <form method="get" action={leaguePath(leagueId)} className="inline-form">
        <input type="hidden" name="tab" value="waiver" />
        <label>
          Team{" "}
          <select name="roster" defaultValue={rosterId === null ? "" : String(rosterId)}>
            {rosters.map((r) => (
              <option key={r.roster_id} value={r.roster_id}>
                {r.team}
                {r.roster_id === myRosterId ? " (you)" : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn">
          Show waiver wire
        </button>
      </form>

      {data && data.entries.length > 0 && (
        <FilterChips label="Position" options={VIEWS} value={view} onChange={setView} />
      )}

      {entries.length > 0 && (
        <ol className="wire-list">
          {entries.map((entry, i) => (
            <Entry key={entry.player_id} entry={entry} rank={i + 1} />
          ))}
        </ol>
      )}
      {data && data.entries.length > 0 && entries.length === 0 && (
        <p className="note">Nobody available would improve this team at that position.</p>
      )}
      {data && data.entries.length === 0 && (
        <p className="note">{data.note ?? "No suggestions right now."}</p>
      )}
    </section>
  );
}
