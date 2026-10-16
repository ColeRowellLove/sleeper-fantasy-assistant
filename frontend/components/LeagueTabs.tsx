import Link from "next/link";

import { alertsTabLabel } from "../lib/alerts";
import { TABS, leaguePath, type TabKey } from "../lib/league";

/**
 * Section navigation. Plain links (not ARIA tabs) so each tab is a real page that loads only its
 * data. The everyday sections sit in the bar; the rest are under "More", which is a native
 * disclosure (keyboard and screen-reader friendly, no script) and closes itself on navigation
 * because each section is its own page.
 */
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
  const main = TABS.filter((t) => t.group === "main");
  const more = TABS.filter((t) => t.group === "more");
  const activeMore = more.find((t) => t.key === active);

  const link = (tab: (typeof TABS)[number]) => (
    <Link
      href={leaguePath(leagueId, `?tab=${tab.key}`)}
      aria-current={tab.key === active ? "page" : undefined}
    >
      {tab.key === "alerts" ? alertsTabLabel(unreadAlerts) : tab.label}
    </Link>
  );

  return (
    <nav className="tabs" aria-label="League sections">
      <ul>
        {main.map((tab) => (
          <li key={tab.key}>{link(tab)}</li>
        ))}
        <li className="tabs-more">
          <details>
            <summary className={activeMore ? "current" : undefined}>
              {activeMore ? `More: ${activeMore.label}` : "More"}
            </summary>
            <ul>
              {more.map((tab) => (
                <li key={tab.key}>{link(tab)}</li>
              ))}
            </ul>
          </details>
        </li>
      </ul>
    </nav>
  );
}
