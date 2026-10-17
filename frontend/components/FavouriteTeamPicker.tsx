"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { TEAM_CODES, TEAM_NAMES } from "../lib/depth";
import { NFL_TEAM_COOKIE, setCookie } from "../lib/myTeam";

/** Lets the viewer pick a favourite NFL team: its games come first and its depth chart opens by default. */
export default function FavouriteTeamPicker({ favourite }: { favourite: string | null }) {
  const router = useRouter();
  const [selected, setSelected] = useState(favourite ?? "");
  return (
    <div className="my-team">
      <label htmlFor="favourite-nfl-team" className="my-team-label">
        Favourite NFL team
      </label>
      <select
        id="favourite-nfl-team"
        value={selected}
        onChange={(e) => {
          setSelected(e.target.value);
          setCookie(NFL_TEAM_COOKIE, e.target.value);
          router.refresh();
        }}
      >
        <option value="">None</option>
        {[...TEAM_CODES]
          .sort((a, b) => TEAM_NAMES[a].localeCompare(TEAM_NAMES[b]))
          .map((code) => (
            <option key={code} value={code}>
              {TEAM_NAMES[code]}
            </option>
          ))}
      </select>
    </div>
  );
}
