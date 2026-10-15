import Link from "next/link";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";

import LeagueDashboard from "../../../components/LeagueDashboard";
import MyTeamPicker from "../../../components/MyTeamPicker";
import WeeklyLineups from "../../../components/WeeklyLineups";
import type { Dashboard, Lineups } from "../../../lib/api";
import { USER_COOKIE, findMyRosterId, teamCookie } from "../../../lib/myTeam";

export const dynamic = "force-dynamic";
export const metadata = { title: "League", robots: { index: false } };

const API_URL = process.env.API_URL ?? "http://localhost:8000";

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
  searchParams: Promise<{ week?: string }>;
}) {
  const { leagueId } = await params;
  const { week } = await searchParams;
  if (!/^\d{1,25}$/.test(leagueId)) notFound();
  const weekNumber = Number(week);
  // ignore anything outside the weeks the API accepts instead of failing the whole page
  const weekQuery =
    Number.isInteger(weekNumber) && weekNumber >= 1 && weekNumber <= 18 ? `?week=${weekNumber}` : "";

  const [dashboard, lineups] = await Promise.all([
    getJson<Dashboard>(`/api/leagues/${leagueId}`),
    getJson<Lineups>(`/api/leagues/${leagueId}/lineups${weekQuery}`),
  ]);

  const jar = await cookies();
  const myRosterId = findMyRosterId(dashboard.standings, {
    team: jar.get(teamCookie(leagueId))?.value,
    userId: jar.get(USER_COOKIE)?.value,
  });

  return (
    <main id="main" className="container">
      <MyTeamPicker
        key={myRosterId ?? "none"} // remount when the server resolves a different team
        leagueId={leagueId}
        teams={dashboard.standings}
        myRosterId={myRosterId}
      />
      <LeagueDashboard data={dashboard} myRosterId={myRosterId} />
      <WeeklyLineups data={lineups} />
      <p>
        <Link href="/">Connect another league</Link>
      </p>
    </main>
  );
}
