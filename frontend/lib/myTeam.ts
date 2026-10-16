/** Remembering which team is "mine". Both cookies hold public data (a Sleeper user id, a roster id). */

export const USER_COOKIE = "sa_user";

export function teamCookie(leagueId: string): string {
  return `sa_team_${leagueId}`;
}

export interface TeamRef {
  roster_id: number;
  owner_id: string | null;
}

/**
 * The user's roster id: an explicit pick for this league wins, otherwise the team owned by the
 * Sleeper user id they connected with. Null when neither identifies a team in this league.
 */
export function findMyRosterId(
  teams: TeamRef[],
  picks: { team?: string | null; userId?: string | null },
): number | null {
  if (picks.team) {
    const id = Number(picks.team);
    if (Number.isInteger(id) && teams.some((t) => t.roster_id === id)) return id;
  }
  if (picks.userId) {
    const match = teams.find((t) => t.owner_id === picks.userId);
    if (match) return match.roster_id;
  }
  return null;
}

/** Browser only: store a cookie for a year. */
export function setCookie(name: string, value: string): void {
  const secure = location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=31536000; samesite=lax${secure}`;
}

/** The cookie holding the alert types the viewer has switched off in a league (comma separated). */
export function alertsOffCookie(leagueId: string): string {
  return `sa_alerts_off_${leagueId}`;
}

/** The cookie holding when the viewer last cleared their alerts in a league (an ISO time). */
export function alertsSeenCookie(leagueId: string): string {
  return `sa_alerts_seen_${leagueId}`;
}
