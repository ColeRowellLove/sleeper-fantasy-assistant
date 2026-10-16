import type { Dashboard, WaiverWireData, WireEntry } from "../lib/api";
import { leaguePath } from "../lib/league";
import PlayerLink from "./PlayerLink";

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

/** "Also backed by 1 of 2 other signals": the count in words, never only a color. */
export function backingLabel(entry: WireEntry): string {
  return `Also backed by ${entry.backing} of ${entry.signals.length} other signals`;
}

function Entry({ entry, rank }: { entry: WireEntry; rank: number }) {
  return (
    <li className="card wire-entry">
      <h3>
        <span className="wire-rank">{rank}.</span>{" "}
        <PlayerLink playerId={entry.player_id}>{entry.name}</PlayerLink>
        <span className="muted">
          {" "}
          ({entry.position ?? "?"}, {entry.team ?? "FA"})
        </span>
      </h3>
      <p className="wire-numbers">
        Projected {entry.projected.toFixed(1)}, +{entry.gain.toFixed(1)} {entry.over}.{" "}
        <strong>{backingLabel(entry)}.</strong>
        {entry.owned !== null && ` Owned in ${entry.owned.toFixed(0)}% of ESPN leagues.`}
      </p>
      <details className="wire-why">
        <summary>Why this pick</summary>
        <ul className="wire-signals">
          {entry.signals.map((s) => (
            <li key={s.source}>
              <span className="wire-signal-state">{s.backs ? "Backs it" : "Does not back it"}</span>{" "}
              {s.source}: {s.detail}
            </li>
          ))}
        </ul>
      </details>
    </li>
  );
}

/**
 * The waiver wire for one team: this cycle's most recommended adds, best first. Which team is a
 * plain GET form (works without JavaScript). The list is for the league's next waiver day and
 * rebuilds itself when the next cycle starts.
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
  return (
    <section aria-labelledby="wire-heading">
      <h2 id="wire-heading">Waiver wire</h2>
      {data ? (
        <p className="note">
          Best adds for the {data.waiver_day} ({waiverDateLabel(data.waiver_date)}) waivers
          {data.week !== null && `, scored for week ${data.week}`}. Only players available in this
          league, scored with its rules, and compared with the selected team&apos;s lineup. The list
          starts over each waiver cycle.
        </p>
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
        <ol className="wire-list">
          {data.entries.map((entry, i) => (
            <Entry key={entry.player_id} entry={entry} rank={i + 1} />
          ))}
        </ol>
      )}
      {data && data.entries.length === 0 && (
        <p className="note">{data.note ?? "No suggestions right now."}</p>
      )}
    </section>
  );
}
