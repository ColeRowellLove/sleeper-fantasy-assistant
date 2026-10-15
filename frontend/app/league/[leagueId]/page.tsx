import Link from "next/link";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";

import LeagueHeader from "../../../components/LeagueHeader";
import LeagueTabs from "../../../components/LeagueTabs";
import RostersPanel from "../../../components/RostersPanel";
import StandingsTable from "../../../components/StandingsTable";
import WeeklyLineups from "../../../components/WeeklyLineups";
import type { Dashboard, Lineups } from "../../../lib/api";
import { resolveApiUrl } from "../../../lib/apiUrl";
import { parseTab } from "../../../lib/league";
import { USER_COOKIE, findMyRosterId, teamCookie } from "../../../lib/myTeam";

export const dynamic = "force-dynamic";
export const metadata = { title: "League", robots: { index: false } };

const API_URL = resolveApiUrl();

async function getJson<T>(path: string): Promise<T> {
  // data only changes when a sync runs, so a short shared cache keeps repeat views instant
  const res = await fetch(`${API_URL}${path}`, { next: { revalidate: 30 } });
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error("Could not load the league. Please try again.");
  return (await res.json()) as T;
}

export default async function LeaguePage({
  params,
  searchParams,
}: {
  params: Promise<{ leagueId: string }>;
  searchParams: Promise<{ tab?: string; week?: string }>;
}) {
  const { leagueId } = await params;
  const { tab: tabParam, week } = await searchParams;
  if (!/^\d{1,25}$/.test(leagueId)) notFound();
  const tab = parseTab(tabParam);
  const weekNumber = Number(week);
  // ignore anything outside the weeks the API accepts instead of failing the whole page
  const weekQuery =
    Number.isInteger(weekNumber) && weekNumber >= 1 && weekNumber <= 18 ? `?week=${weekNumber}` : "";

  // the header needs the dashboard on every tab; lineups are only fetched for their own tab
  const [dashboard, lineups] = await Promise.all([
    getJson<Dashboard>(`/api/leagues/${leagueId}`),
    tab === "lineups"
      ? getJson<Lineups>(`/api/leagues/${leagueId}/lineups${weekQuery}`)
      : Promise.resolve(null),
  ]);

  const jar = await cookies();
  const myRosterId = findMyRosterId(dashboard.standings, {
    team: jar.get(teamCookie(leagueId))?.value,
    userId: jar.get(USER_COOKIE)?.value,
  });

  return (
    <main id="main" className="container">
      <LeagueHeader data={dashboard} myRosterId={myRosterId} />
      <LeagueTabs leagueId={leagueId} active={tab} />
      {tab === "standings" && (
        <StandingsTable
          standings={dashboard.standings}
          playoffTeams={dashboard.rules.playoff_teams}
          myRosterId={myRosterId}
        />
      )}
      {tab === "rosters" && (
        <RostersPanel
          key={myRosterId ?? "none"} // reset the selection when the user changes their team
          rosters={dashboard.rosters}
          myRosterId={myRosterId}
          week={dashboard.week ?? null}
        />
      )}
      {tab === "lineups" && lineups && <WeeklyLineups data={lineups} />}
      <p className="back">
        <Link href="/">Connect another league</Link>
      </p>
    </main>
  );
}
