import { teamInitials } from "../lib/lineups";

const HUES = ["qb", "rb", "wr", "te", "k", "def"] as const;

/**
 * A round avatar for a fantasy team: its initials on one of the position colours (chosen from the
 * team id, so it never changes). Decorative: the team's name is always next to it.
 */
export default function TeamAvatar({ rosterId, name }: { rosterId: number; name: string }) {
  const hue = HUES[Math.abs(rosterId) % HUES.length];
  return (
    <span className={`team-avatar pos-${hue}`} aria-hidden="true">
      {teamInitials(name)}
    </span>
  );
}
