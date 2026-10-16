"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";

function Inner({
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
  params.delete("depth"); // only one pop-up is open at a time
  params.set("player", playerId);
  return (
    <Link href={`${pathname}?${params.toString()}`} className={className ?? "player-link"} scroll={false}>
      {children}
    </Link>
  );
}

/**
 * Opens a player's pop-up by adding ?player=ID to the page you are on, keeping the tab and week.
 * It is a real link, so the pop-up can be shared, bookmarked and opened without JavaScript.
 *
 * Reading the current query needs a Suspense boundary so a page that is prerendered at build time
 * (the home page's sample matchup) still builds: it shows the plain text until the browser takes over.
 */
export default function PlayerLink(props: {
  playerId: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Suspense fallback={props.children}>
      <Inner {...props} />
    </Suspense>
  );
}
