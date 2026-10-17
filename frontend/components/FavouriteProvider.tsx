"use client";

import { createContext, useContext, type ReactNode } from "react";

const FavouriteContext = createContext<string | null>(null);

/** Tells every list on the page which NFL team the viewer follows, so its players can be marked. */
export function FavouriteProvider({
  favourite,
  children,
}: {
  favourite: string | null;
  children: ReactNode;
}) {
  return <FavouriteContext.Provider value={favourite}>{children}</FavouriteContext.Provider>;
}

/** The viewer's favourite NFL team code, or null. */
export function useFavourite(): string | null {
  return useContext(FavouriteContext);
}

/**
 * A star by a player on the favourite team, with the words for a screen reader (and a visible
 * "Fav" so colour and shape are never the only cue).
 */
export default function FavouriteMark({ team }: { team: string | null | undefined }) {
  const favourite = useFavourite();
  if (!favourite || !team || team !== favourite) return null;
  return (
    <span className="fav-mark" title="Your favourite NFL team">
      <span aria-hidden="true">★</span> Fav
      <span className="visually-hidden"> (your favourite NFL team)</span>
    </span>
  );
}
