import type { InjuryInfo } from "../lib/api";
import { injuryLabel } from "../lib/injury";

/** A player's injury designation (Out, Doubtful, Questionable, IR...) with the body part. */
export default function InjuryBadge({ injury }: { injury?: InjuryInfo | null }) {
  const label = injuryLabel(injury);
  if (!label) return null;
  return (
    <span className={`injury injury-${label.tone}`}>
      <span className="injury-state">{label.text}</span>
      {label.bodyPart && <span className="injury-part">{label.bodyPart}</span>}
    </span>
  );
}
