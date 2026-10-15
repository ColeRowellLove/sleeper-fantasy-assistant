import Link from "next/link";

import { TABS, leaguePath, type TabKey } from "../lib/league";

/** Section navigation. Plain links (not ARIA tabs) so each tab is a real page that loads only its data. */
export default function LeagueTabs({ leagueId, active }: { leagueId: string; active: TabKey }) {
  return (
    <nav className="tabs" aria-label="League sections">
      <ul>
        {TABS.map((tab) => (
          <li key={tab.key}>
            <Link
              href={leaguePath(leagueId, `?tab=${tab.key}`)}
              aria-current={tab.key === active ? "page" : undefined}
            >
              {tab.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
