import type { ReactNode } from "react";

/**
 * The shared frame for a table of stats: a card that scrolls sideways on a narrow screen (names
 * stay readable), a hidden caption for screen readers and an optional empty message. Every
 * stats table uses it, so spacing, scrolling and captions are the same on each tab.
 */
export default function StatTable({
  caption,
  className = "",
  empty,
  bare = false,
  children,
}: {
  caption: string;
  /** Extra classes on the table (the shared "players" class is always there). */
  className?: string;
  /** Shown under the table; pass it only when there are no rows. */
  empty?: ReactNode;
  /** Without the card around it, for a table nested in another card. */
  bare?: boolean;
  children: ReactNode;
}) {
  const table = (
    <div className="players-scroll">
      <table className={`players ${className}`.trim()}>
        <caption className="visually-hidden">{caption}</caption>
        {children}
      </table>
    </div>
  );
  if (bare) return table;
  return (
    <div className="card flush">
      {table}
      {empty && <p className="note players-empty">{empty}</p>}
    </div>
  );
}
