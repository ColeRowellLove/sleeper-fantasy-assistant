import type { ReactNode } from "react";

/**
 * Explanatory text as a few short bullets, the same on every screen (never a paragraph wall).
 * Each item is one short sentence.
 */
export default function NoteList({
  items,
  label,
}: {
  items: readonly ReactNode[];
  label?: string;
}) {
  return (
    <ul className="note-list" aria-label={label}>
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}
