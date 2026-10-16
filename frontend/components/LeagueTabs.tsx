import Link from "next/link";

import { alertsTabLabel } from "../lib/alerts";
import { TABS, leaguePath, type TabKey } from "../lib/league";

/** Section navigation. Plain links (not ARIA tabs) so each tab is a real page that loads only its data. */
export default function LeagueTabs({
  leagueId,
  active,
  unreadAlerts = 0,
}: {
  leagueId: string;
  active: TabKey;
  /** New alerts for the viewer's team; shown in words on the Alerts tab. */
  unreadAlerts?: number;
}) {
  return (
    <nav className="tabs" aria-label="League sections">
      <ul>
        {TABS.map((tab) => (
          <li key={tab.key}>
            <Link
              href={leaguePath(leagueId, `?tab=${tab.key}`)}
              aria-current={tab.key === active ? "page" : undefined}
            >
              {tab.key === "alerts" ? alertsTabLabel(unreadAlerts) : tab.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
