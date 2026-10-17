import Link from "next/link";

import type { MovedPlayer, TeamMove, TransactionsData } from "../lib/api";
import { rosterPath } from "../lib/league";
import { transactionTitle } from "../lib/transactions";
import LocalTime from "./LocalTime";
import NoteList from "./NoteList";
import PlayerIdentity from "./PlayerIdentity";

function Moved({ player, kind }: { player: MovedPlayer; kind: "added" | "dropped" }) {
  return (
    <li className={`txn-player txn-${kind}`}>
      <PlayerIdentity
        player_id={player.player_id}
        name={player.name}
        position={player.position ?? null}
        team={player.team ?? null}
        meta={
          <span className="txn-sign">
            <span aria-hidden="true">{kind === "added" ? "+" : "−"}</span>{" "}
            {kind === "added" ? "Added" : "Dropped"}
          </span>
        }
      />
    </li>
  );
}

function Move({ move, leagueId, mine }: { move: TeamMove; leagueId: string; mine: boolean }) {
  return (
    <div className="txn-move">
      <p className="txn-team">
        <Link href={rosterPath(leagueId, move.roster_id)} className="member-link">
          {move.team}
        </Link>
        {mine && <span className="you">You</span>}
      </p>
      <ul className="txn-players">
        {move.added.map((p) => (
          <Moved key={`a-${p.player_id}`} player={p} kind="added" />
        ))}
        {move.dropped.map((p) => (
          <Moved key={`d-${p.player_id}`} player={p} kind="dropped" />
        ))}
      </ul>
    </div>
  );
}

/** The league's latest adds, drops, waiver claims and trades, like Sleeper's chat cards. */
export default function TransactionsPanel({
  data,
  leagueId,
  myRosterId,
}: {
  data: TransactionsData;
  leagueId: string;
  myRosterId: number | null;
}) {
  return (
    <section aria-labelledby="txn-heading" className="transactions">
      <h2 id="txn-heading">Transactions</h2>
      <NoteList
        items={[
          "Added players have a plus, dropped players a minus",
          "Newest first, in your time zone",
        ]}
      />
      {data.transactions.length === 0 ? (
        <p className="note">No adds, drops or trades have been synced for this league yet.</p>
      ) : (
        <ol className="txn-list">
          {data.transactions.map((item) => (
            <li key={item.transaction_id} className="card txn-card">
              <p className="txn-title">
                <strong>{transactionTitle(item)}</strong>
                {item.created_at && (
                  <span className="muted txn-time">
                    <LocalTime iso={item.created_at} />
                  </span>
                )}
              </p>
              <div className="txn-moves">
                {item.moves.map((move) => (
                  <Move
                    key={move.roster_id}
                    move={move}
                    leagueId={leagueId}
                    mine={move.roster_id === myRosterId}
                  />
                ))}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
