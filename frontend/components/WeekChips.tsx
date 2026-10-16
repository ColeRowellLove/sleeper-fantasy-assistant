import Link from "next/link";

import { leaguePath } from "../lib/league";
import { weekState } from "../lib/lineups";

/** Week navigation as plain links (works without JavaScript). Later weeks are visibly upcoming. */
export default function WeekChips({
  leagueId,
  weeks,
  selected,
  currentWeek,
  tab = "lineups",
  extraQuery = "",
}: {
  leagueId: string;
  weeks: number[];
  selected: number | null;
  currentWeek: number | null | undefined;
  /** The league tab the chips link to. */
  tab?: string;
  /** Extra query to keep on every link, such as "&pos=WR". */
  extraQuery?: string;
}) {
  return (
    <nav className="week-chips" aria-label="Week">
      <ul>
        {weeks.map((w) => {
          const state = weekState(w, currentWeek);
          return (
            <li key={w}>
              <Link
                href={leaguePath(leagueId, `?tab=${tab}&week=${w}${extraQuery}`)}
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
