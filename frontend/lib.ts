export function leaguePath(leagueId: string): string {
  return `/league/${encodeURIComponent(leagueId)}`;
}
