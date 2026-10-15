import Link from "next/link";

import { weekState } from "../lib/lineups";

/** Week navigation as plain links (works without JavaScript). Later weeks are visibly upcoming. */
export default function WeekChips({
  leagueId,
  weeks,
  selected,
  currentWeek,
}: {
  leagueId: string;
  weeks: number[];
  selected: number | null;
  currentWeek: number | null | undefined;
}) {
  return (
    <nav className="week-chips" aria-label="Week">
      <ul>
        {weeks.map((w) => {
          const state = weekState(w, currentWeek);
          return (
            <li key={w}>
              <Link
                href={`/league/${encodeURIComponent(leagueId)}?tab=lineups&week=${w}`}
                className={`chip-week ${state}`}
                aria-current={w === selected ? "page" : undefined}
              >
                <span className="visually-hidden">Week </span>
                {w}
                {state === "current" && <span className="visually-hidden"> (this week)</span>}
                {state === "upcoming" && <span className="visually-hidden"> (upcoming)</span>}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
