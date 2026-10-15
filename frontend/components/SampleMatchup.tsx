import { positionClass } from "../lib/positions";

const ROWS = [
  { pos: "QB", name: "Starting QB", pts: "27.3" },
  { pos: "RB", name: "Lead back", pts: "15.8" },
  { pos: "WR", name: "Top receiver", pts: "18.7" },
  { pos: "TE", name: "Starting TE", pts: "9.4" },
];

/** Decorative preview of the weekly matchup view, with made-up placeholder players. */
export default function SampleMatchup() {
  return (
    <section className="card sample" aria-hidden="true">
      <h2>Sample matchup</h2>
      <p className="sample-score num">
        <span>104.2</span>
        <span>98.1</span>
      </p>
      {ROWS.map((r) => (
        <div key={r.pos} className={`sample-row ${positionClass(r.pos)}`}>
          <span className="chip">{r.pos}</span>
          <strong>{r.name}</strong>
          <span className="num">{r.pts}</span>
        </div>
      ))}
    </section>
  );
}
