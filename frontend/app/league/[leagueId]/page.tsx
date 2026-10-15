import Link from "next/link";
import { notFound } from "next/navigation";

import LeagueDashboard from "../../../components/LeagueDashboard";
import type { Dashboard } from "../../../lib/api";

export const dynamic = "force-dynamic";
export const metadata = { title: "League dashboard", robots: { index: false } };

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export default async function LeaguePage({ params }: { params: Promise<{ leagueId: string }> }) {
  const { leagueId } = await params;
  if (!/^\d{1,25}$/.test(leagueId)) notFound();

  const res = await fetch(`${API_URL}/api/leagues/${leagueId}`, { cache: "no-store" });
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error("Could not load the league. Please try again.");

  return (
    <main>
      <LeagueDashboard data={(await res.json()) as Dashboard} />
      <p>
        <Link href="/">Connect another league</Link>
      </p>
    </main>
  );
}
