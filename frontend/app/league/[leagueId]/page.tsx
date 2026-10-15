import Link from "next/link";
import { notFound } from "next/navigation";

import LeagueDashboard from "../../../components/LeagueDashboard";
import WeeklyLineups from "../../../components/WeeklyLineups";
import type { Dashboard, Lineups } from "../../../lib/api";

export const dynamic = "force-dynamic";
export const metadata = { title: "League dashboard", robots: { index: false } };

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

  return (
    <main>
      <LeagueDashboard data={dashboard} />
      <WeeklyLineups data={lineups} />
      <p>
        <Link href="/">Connect another league</Link>
      </p>
    </main>
  );
}
