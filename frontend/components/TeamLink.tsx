"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/** Opens an NFL team's depth chart on the Teams tab of the league you are looking at. */
export default function TeamLink({ team, children }: { team: string; children: ReactNode }) {
  const pathname = usePathname() ?? "";
  return (
    <Link href={`${pathname}?tab=teams&team=${encodeURIComponent(team)}`} className="player-link">
      {children}
    </Link>
  );
}
