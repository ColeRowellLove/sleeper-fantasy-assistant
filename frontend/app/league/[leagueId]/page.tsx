import Link from "next/link";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";

import LeagueHeader from "../../../components/LeagueHeader";
import LeagueTabs from "../../../components/LeagueTabs";
import RostersPanel from "../../../components/RostersPanel";
import SettingsPanel from "../../../components/SettingsPanel";
import PlayerDialog from "../../../components/PlayerDialog";
import TeamDepthChart from "../../../components/TeamDepthChart";
import TeamDialog from "../../../components/TeamDialog";
import TeamPicker from "../../../components/TeamPicker";
import PlayersTable from "../../../components/PlayersTable";
import StandingsTable from "../../../components/StandingsTable";
import StartSitTool from "../../../components/StartSitTool";
import GamesPanel from "../../../components/GamesPanel";
import RankingsPanel from "../../../components/RankingsPanel";
import AccuracyTable from "../../../components/AccuracyTable";
import WeeklyLineups from "../../../components/WeeklyLineups";
import type {
  Dashboard,
  Games,
  LeagueSettings,
  BestLineup,
  LineupAccuracy,
  StartSitComparison,
  Rankings,
  Lineups,
  PlayerDetail,
  PlayersData,
  TeamDepth,
} from "../../../lib/api";
import { resolveApiUrl } from "../../../lib/apiUrl";
import { isTeamCode } from "../../../lib/depth";
import { leaguePath, parseTab } from "../../../lib/league";
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
  searchParams: Promise<{
    roster?: string;
    tab?: string;
    week?: string;
    player?: string;
    team?: string;
    depth?: string;
    pick?: string | string[];
  }>;
}) {
  const { leagueId } = await params;
  const { tab: tabParam, week, player, team, depth: depthParam, roster, pick } = await searchParams;
  if (!/^\d{1,25}$/.test(leagueId)) notFound();
  const tab = parseTab(tabParam);
  const weekNumber = Number(week);
  // ignore anything outside the weeks the API accepts instead of failing the whole page
  const weekQuery =
    Number.isInteger(weekNumber) && weekNumber >= 1 && weekNumber <= 18
      ? `?week=${weekNumber}`
      : "";

  // the header needs the dashboard on every tab; lineups are only fetched for their own tab
  const [
    dashboard,
    lineups,
    games,
    rankings,
    accuracy,
    leagueSettings,
    players,
    playerDetail,
    depth,
    depthDialog,
  ] = await Promise.all([
    getJson<Dashboard>(`/api/leagues/${leagueId}`),
    tab === "lineups"
      ? getJson<Lineups>(`/api/leagues/${leagueId}/lineups${weekQuery}`)
      : Promise.resolve(null),
    tab === "games"
      ? getJson<Games>(`/api/leagues/${leagueId}/games${weekQuery}`)
      : Promise.resolve(null),
    tab === "rankings"
      ? getJson<Rankings>(`/api/leagues/${leagueId}/rankings${weekQuery}`)
      : Promise.resolve(null),
    tab === "accuracy"
      ? getJson<LineupAccuracy>(`/api/leagues/${leagueId}/accuracy`)
      : Promise.resolve(null),
    tab === "settings"
      ? getJson<LeagueSettings>(`/api/leagues/${leagueId}/settings`)
      : Promise.resolve(null),
    tab === "players"
      ? getJson<PlayersData>(`/api/leagues/${leagueId}/players`)
      : Promise.resolve(null),
    // an unknown or malformed ?player= simply opens nothing
    player && /^[A-Za-z0-9]{1,12}$/.test(player)
      ? getJson<PlayerDetail>(`/api/leagues/${leagueId}/players/${player}`).catch(() => null)
      : Promise.resolve(null),
    tab === "teams" && isTeamCode(team)
      ? getJson<TeamDepth>(`/api/leagues/${leagueId}/teams/${team}`)
      : Promise.resolve(null),
    // a team opened as a pop-up from any team code; an unknown code opens nothing
    isTeamCode(depthParam)
      ? getJson<TeamDepth>(`/api/leagues/${leagueId}/teams/${depthParam}`).catch(() => null)
      : Promise.resolve(null),
  ]);

  // closing the pop-up returns to this same page without ?player
  const closeParams = new URLSearchParams();
  if (tabParam) closeParams.set("tab", tabParam);
  if (weekQuery) closeParams.set("week", String(weekNumber));
  if (tabParam === "teams" && isTeamCode(team)) closeParams.set("team", team);
  const closeQuery = closeParams.toString();
  const closeHref = `${leaguePath(leagueId)}${closeQuery ? `?${closeQuery}` : ""}`;

  const jar = await cookies();
  const myRosterId = findMyRosterId(dashboard.standings, {
    team: jar.get(teamCookie(leagueId))?.value,
    userId: jar.get(USER_COOKIE)?.value,
  });

  // a link from a team name to that team's roster; anything that is not one of this league's teams is ignored
  const linkedRosterId = dashboard.rosters.some((r) => String(r.roster_id) === roster)
    ? Number(roster)
    : null;

  // Start/Sit works on one team's roster: the linked team, else yours, else the first. It needs
  // the dashboard (to know the teams), so it is fetched after it.
  let startSit: {
    rosterId: number;
    picks: string[];
    best: BestLineup | null;
    comparison: StartSitComparison | null;
  } | null = null;
  if (tab === "startsit") {
    const rosterId = linkedRosterId ?? myRosterId ?? dashboard.rosters[0]?.roster_id ?? 0;
    const weekPart = weekQuery ? `&week=${weekNumber}` : "";
    const picks = [...new Set([pick ?? []].flat())]
      .filter((id) => /^[A-Za-z0-9]{1,12}$/.test(id))
      .slice(0, 6);
    const [best, comparison] = await Promise.all([
      rosterId
        ? getJson<BestLineup>(
            `/api/leagues/${leagueId}/start-sit/lineup?roster=${rosterId}${weekPart}`,
          ).catch(() => null)
        : Promise.resolve(null),
      picks.length >= 2
        ? getJson<StartSitComparison>(
            `/api/leagues/${leagueId}/start-sit?${picks.map((id) => `player=${id}`).join("&")}${weekPart}`,
          ).catch(() => null)
        : Promise.resolve(null),
    ]);
    startSit = { rosterId, picks, best, comparison };
  }

  return (
    <main id="main" className="container">
      <LeagueHeader data={dashboard} myRosterId={myRosterId} />
      <LeagueTabs leagueId={leagueId} active={tab} />
      {tab === "standings" && (
        <StandingsTable
          leagueId={leagueId}
          standings={dashboard.standings}
          playoffTeams={dashboard.rules.playoff_teams}
          myRosterId={myRosterId}
        />
      )}
      {tab === "rosters" && (
        <RostersPanel
          key={`${myRosterId ?? "none"}-${linkedRosterId ?? "none"}`} // reset the selection when the team or the link changes
          initialRosterId={linkedRosterId}
          rosters={dashboard.rosters}
          myRosterId={myRosterId}
          week={dashboard.week ?? null}
        />
      )}
      {tab === "lineups" && lineups && (
        <WeeklyLineups data={lineups} leagueId={leagueId} myRosterId={myRosterId} />
      )}
      {tab === "games" && games && (
        <GamesPanel data={games} leagueId={leagueId} myRosterId={myRosterId} />
      )}
      {tab === "rankings" && rankings && (
        <RankingsPanel data={rankings} leagueId={leagueId} myRosterId={myRosterId} />
      )}
      {tab === "startsit" && startSit && (
        <StartSitTool
          leagueId={leagueId}
          rosters={dashboard.rosters}
          rosterId={startSit.rosterId}
          picks={startSit.picks}
          week={weekQuery ? weekNumber : null}
          best={startSit.best}
          comparison={startSit.comparison}
        />
      )}
      {tab === "accuracy" && accuracy && (
        <AccuracyTable data={accuracy} leagueId={leagueId} myRosterId={myRosterId} />
      )}
      {tab === "players" && players && (
        <PlayersTable data={players} myRosterId={myRosterId} leagueId={leagueId} />
      )}
      {tab === "teams" && (
        <>
          <TeamPicker leagueId={leagueId} selected={isTeamCode(team) ? team : null} />
          {depth ? (
            <TeamDepthChart data={depth} myRosterId={myRosterId} />
          ) : (
            <p className="note">Pick a team to see its depth chart.</p>
          )}
        </>
      )}
      {tab === "settings" && leagueSettings && <SettingsPanel data={leagueSettings} />}
      {depthDialog && (
        <TeamDialog
          key={depthDialog.team}
          data={depthDialog}
          closeHref={closeHref}
          myRosterId={myRosterId}
        />
      )}
      {!depthDialog && playerDetail && (
        <PlayerDialog key={playerDetail.player_id} detail={playerDetail} closeHref={closeHref} />
      )}
      <p className="back">
        <Link href="/">Connect another league</Link>
      </p>
    </main>
  );
}
