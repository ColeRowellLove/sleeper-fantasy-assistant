"use client";

import { useState } from "react";

import { avatarUrl, initials, teamLogoUrl } from "../lib/images";
import { positionClass } from "../lib/positions";

interface Props {
  player_id: string;
  name: string;
  position: string | null;
  team: string | null;
  /** Load immediately (images visible on first paint); others load lazily as they near the screen. */
  priority?: boolean;
}

/**
 * Decorative player image (the name is always next to it, so alt is empty): a headshot with a small
 * team logo, a team logo for defenses, and initials if an image fails to load.
 */
export default function PlayerAvatar({ player_id, name, position, team, priority = false }: Props) {
  const [faceFailed, setFaceFailed] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);
  const isDefense = position === "DEF";

  return (
    <span className={`avatar ${positionClass(position)}`} aria-hidden="true">
      {faceFailed ? (
        <span className="avatar-initials">{initials(name)}</span>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element -- small CDN images; skip the image optimizer's quota
        <img
          src={avatarUrl({ player_id, position, team })}
          alt=""
          width={40}
          height={40}
          loading={priority ? "eager" : "lazy"}
          decoding="async"
          className={isDefense ? "avatar-logo" : undefined}
          onError={() => setFaceFailed(true)}
        />
      )}
      {!isDefense && team && !logoFailed && (
        // eslint-disable-next-line @next/next/no-img-element -- see above
        <img
          src={teamLogoUrl(team)}
          alt=""
          width={16}
          height={16}
          loading={priority ? "eager" : "lazy"}
          decoding="async"
          className="avatar-team"
          onError={() => setLogoFailed(true)}
        />
      )}
    </span>
  );
}
