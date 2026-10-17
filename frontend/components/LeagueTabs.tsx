import Link from "next/link";

import { SECTIONS, leaguePath, sectionOf, type TabKey } from "../lib/league";
import FilterChips from "./FilterChips";

/**
 * Navigation in two steps: a few sections, most important first, and under the open section its
 * pages as chips. Plain links (not ARIA tabs) so each page is a real URL that loads only its own
 * data; a section's link opens its first page.
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
  const open = sectionOf(active);
  const href = (tab: TabKey) => leaguePath(leagueId, `?tab=${tab}`);

  return (
    <>
      <nav className="tabs" aria-label="League sections">
        <ul>
          {SECTIONS.map((section) => (
            <li key={section.key}>
              <Link
                href={href(section.key === open.key ? active : section.pages[0].key)}
                aria-current={section.key === open.key ? "page" : undefined}
                // the count is short on screen and in words for a screen reader (it starts with
                // the visible text, as a name must)
                aria-label={
                  section.key === "alerts" && unreadAlerts > 0
                    ? `Alerts ${unreadAlerts} new`
                    : undefined
                }
              >
                {section.label}
                {section.key === "alerts" && unreadAlerts > 0 && (
                  <span className="tab-count">{unreadAlerts}</span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {open.pages.length > 1 && (
        <FilterChips
          label={`${open.label} pages`}
          options={open.pages.map((p) => ({ value: p.key, label: p.label }))}
          value={active}
          hrefFor={href}
        />
      )}
    </>
  );
}
