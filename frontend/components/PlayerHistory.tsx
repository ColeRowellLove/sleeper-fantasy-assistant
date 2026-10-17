import type { PlayerDetail } from "../lib/api";
import { historyRows } from "../lib/playerHistory";
import StatTable from "./StatTable";

/** His adds, drops and trades in this league, newest first. */
export default function PlayerHistory({ history }: { history: PlayerDetail["history"] }) {
  const rows = historyRows(history);
  if (rows.length === 0) return null;
  return (
    <section aria-labelledby="pd-transactions">
      <h3 id="pd-transactions">Transaction history</h3>
      <StatTable
        bare
        caption="His adds, drops and trades in this league, newest first"
        className="pd-table history"
      >
        <thead>
          <tr>
            <th scope="col">Move</th>
            <th scope="col">Details</th>
            <th scope="col" className="num-col">
              Date
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className={r.move === "Added" ? "move-added" : "move-dropped"}>
              <th scope="row">{r.move}</th>
              <td>{r.text}</td>
              <td className="num num-col">{r.date}</td>
            </tr>
          ))}
        </tbody>
      </StatTable>
    </section>
  );
}
