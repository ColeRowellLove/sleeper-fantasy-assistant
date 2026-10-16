import type { ReactNode } from "react";

import type { InjuryInfo } from "../lib/api";
import InjuryBadge from "./InjuryBadge";
import PlayerAvatar from "./PlayerAvatar";
import PlayerLink from "./PlayerLink";
import PositionChip from "./PositionChip";
import TeamLink from "./TeamLink";

/**
 * The one way a player is shown: face, name (a link to his page), position chip, NFL team, injury.
 * Lists, tables, pickers and cards all use it so a player looks the same everywhere. Anything
 * specific to a screen goes in ``meta`` (more chips on the same line) or ``children`` (extra lines
 * below, such as the opponent or why he is ranked).
 */
export default function PlayerIdentity({
  player_id,
  name,
  position,
  team,
  injury,
  showTeam = true,
  meta,
  children,
}: {
  player_id: string;
  name: string;
  position: string | null | undefined;
  team: string | null | undefined;
  injury?: InjuryInfo | null;
  /** Leave the team out where it is already obvious (a team's own box score). */
  showTeam?: boolean;
  meta?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <span className="player-line">
      <PlayerAvatar
        player_id={player_id}
        name={name}
        position={position ?? null}
        team={team ?? null}
      />
      <span className="player-text">
        <span className="player-name">
          <PlayerLink playerId={player_id}>{name}</PlayerLink>
        </span>
        <span className="player-meta">
          <PositionChip position={position ?? null} />
          {showTeam && (
            <span className="muted">{team ? <TeamLink team={team}>{team}</TeamLink> : "FA"}</span>
          )}
          <InjuryBadge injury={injury} />
          {meta}
        </span>
        {children}
      </span>
    </span>
  );
}
