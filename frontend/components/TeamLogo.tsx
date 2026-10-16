"use client";

import { useState } from "react";

import { teamLogoUrl } from "../lib/images";

/**
 * An NFL team's logo from the same CDN as the rest of the app. Decorative (empty alt) because the
 * team's name is always written next to it, and it disappears if the image cannot load.
 */
export default function TeamLogo({ team, size = 40 }: { team: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- small CDN logo, as in PlayerAvatar
    <img
      src={teamLogoUrl(team)}
      alt=""
      width={size}
      height={size}
      decoding="async"
      className="team-logo"
      onError={() => setFailed(true)}
    />
  );
}
