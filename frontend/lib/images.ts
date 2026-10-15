// Sleeper serves player headshots and team logos from its public CDN (unofficial but stable).
const CDN = "https://sleepercdn.com";

export function headshotUrl(playerId: string): string {
  return `${CDN}/content/nfl/players/thumb/${encodeURIComponent(playerId)}.jpg`;
}

export function teamLogoUrl(team: string): string {
  return `${CDN}/images/team_logos/nfl/${encodeURIComponent(team.toLowerCase())}.png`;
}

/**
 * The image for a player row. Defenses have no face: their player id is the team code, so they
 * show the team logo. Everyone else shows a headshot.
 */
export function avatarUrl(player: {
  player_id: string;
  position: string | null;
  team: string | null;
}): string {
  if (player.position === "DEF") return teamLogoUrl(player.team ?? player.player_id);
  return headshotUrl(player.player_id);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
