"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Opens a player's pop-up by adding ?player=ID to the page you are on, keeping the tab and week.
 * It is a real link, so the pop-up can be shared, bookmarked and opened without JavaScript.
 */
export default function PlayerLink({
  playerId,
  children,
  className,
}: {
  playerId: string;
  children: ReactNode;
  className?: string;
}) {
  const pathname = usePathname() ?? "";
  const current = useSearchParams();
  const params = new URLSearchParams(current?.toString() ?? "");
  params.set("player", playerId);
  return (
    <Link href={`${pathname}?${params.toString()}`} className={className ?? "player-link"} scroll={false}>
      {children}
    </Link>
  );
}
