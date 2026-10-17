import { stanceWord } from "../lib/waiverView";

export interface Reason {
  label: string;
  /** For and against get a word and a colour; without one the chip is neutral. */
  stance?: "for" | "against" | "info";
}

/**
 * The short reasons behind a recommendation as chips, the same on the waiver wire and in the
 * rankings. A stance is always said in a word as well as shown in colour.
 */
export default function ReasonChips({
  reasons,
  label,
}: {
  reasons: Reason[];
  /** What the list is, for a screen reader. */
  label: string;
}) {
  if (reasons.length === 0) return null;
  return (
    <ul className="wire-reasons" aria-label={label}>
      {reasons.map((r) => (
        <li
          key={r.label}
          className={`reason${r.stance && r.stance !== "info" ? ` reason-${r.stance}` : ""}`}
        >
          {r.stance && r.stance !== "info" && (
            <>
              <span className="reason-word">{stanceWord(r.stance)}</span>{" "}
            </>
          )}
          {r.label}
        </li>
      ))}
    </ul>
  );
}
