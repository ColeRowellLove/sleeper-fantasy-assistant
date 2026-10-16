import ConnectForm from "../components/ConnectForm";
import SampleMatchup from "../components/SampleMatchup";
import { POSITIONS, positionClass, positionName } from "../lib/positions";

export default function Home() {
  return (
    <main id="main" className="container">
      <div className="hero">
        <div>
          <h1>Every lineup in your league, side by side.</h1>
          <p className="lede">
            Connect a Sleeper league by username to see standings, rosters and weekly matchups in
            one place.
          </p>
          <ul className="legend" aria-label="Position colors">
            {POSITIONS.map((p) => (
              <li key={p} className={positionClass(p)}>
                <span className="chip" title={positionName(p)}>
                  {p}
                </span>
              </li>
            ))}
          </ul>
          <p className="legend-note">
            Every position has its own color, so lineups read at a glance.
          </p>
        </div>
        <ConnectForm />
      </div>
      <SampleMatchup />
    </main>
  );
}
