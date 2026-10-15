import { positionClass } from "../lib/positions";

/** A position pill in the position's color. The letters carry the meaning; color is reinforcement. */
export default function PositionChip({ position }: { position: string | null }) {
  if (!position) return <span className="muted">–</span>;
  return <span className={`chip ${positionClass(position)}`}>{position}</span>;
}
