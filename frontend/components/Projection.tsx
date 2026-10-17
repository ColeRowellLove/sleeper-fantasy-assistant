import { formatProjection, projectionDelta, type WeekState } from "../lib/lineups";

/** "Projected 127.27 (+3.2)": the delta only once there is something to compare. */
export default function Projection({
  projected,
  compareWith,
  actual,
  state,
  label,
}: {
  projected: number | null | undefined;
  /** The projection frozen before kickoff: a finished week's score is compared with this one. */
  compareWith?: number | null;
  actual: number | null;
  state: WeekState;
  label: string;
}) {
  const text = formatProjection(projected);
  if (text === null) return null;
  const delta = projectionDelta(actual, compareWith ?? projected, state);
  return (
    <span className="proj">
      {label} {text}
      {delta && (
        <span className="proj-delta">
          {" "}
          ({delta}
          <span className="visually-hidden"> against projection</span>)
        </span>
      )}
    </span>
  );
}
