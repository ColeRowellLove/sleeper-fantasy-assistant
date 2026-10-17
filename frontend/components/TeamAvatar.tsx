"use client";

import { useState } from "react";

import { teamPictureUrl } from "../lib/images";
import { teamInitials } from "../lib/lineups";

const HUES = ["qb", "rb", "wr", "te", "k", "def"] as const;

/**
 * A round avatar for a fantasy team: its picture from Sleeper when it has one, otherwise its
 * initials on one of the position colours (chosen from the team id, so it never changes). The
 * initials also show if the picture fails to load. Decorative: the team's name is always next to it.
 */
export default function TeamAvatar({
  rosterId,
  name,
  picture,
}: {
  rosterId: number;
  name: string;
  picture?: string | null;
}) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const hue = HUES[Math.abs(rosterId) % HUES.length];
  const src = teamPictureUrl(picture);
  return (
    <span className={`team-avatar pos-${hue}`} aria-hidden="true">
      {src && failedSrc !== src ? (
        // eslint-disable-next-line @next/next/no-img-element -- small CDN image; skip the optimizer's quota
        <img
          src={src}
          alt=""
          width={42}
          height={42}
          loading="lazy"
          ref={(img) => {
            // an image that failed before the page woke up never fires onError
            if (img?.complete && img.naturalWidth === 0) setFailedSrc(src);
          }}
          onError={() => setFailedSrc(src)}
        />
      ) : (
        teamInitials(name)
      )}
    </span>
  );
}
