"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";

function Inner({
  team,
  children,
  className,
}: {
  team: string;
  children: ReactNode;
  className?: string;
}) {
  const pathname = usePathname() ?? "";
  const current = useSearchParams();
  const params = new URLSearchParams(current?.toString() ?? "");
  params.delete("player");
  params.set("depth", team);
  return (
    <Link href={`${pathname}?${params.toString()}`} className={className ?? "player-link"} scroll={false}>
      {children}
    </Link>
  );
}

/**
 * Opens an NFL team's depth chart as a pop-up by adding ?depth=CODE to the page you are on, keeping
 * the tab and week. Opening a team closes a player pop-up (only one pop-up is open at a time).
 *
 * The Suspense boundary lets pages that are prerendered at build time (the home page's sample
 * matchup) build: they show the plain team code until the browser takes over.
 */
export default function TeamLink(props: { team: string; children: ReactNode; className?: string }) {
  return (
    <Suspense fallback={props.children}>
      <Inner {...props} />
    </Suspense>
  );
}
