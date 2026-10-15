"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { setCookie, teamCookie } from "../lib/myTeam";

interface Team {
  roster_id: number;
  team: string;
}

/** Lets the user say which team is theirs; the choice is remembered per league. */
export default function MyTeamPicker({
  leagueId,
  teams,
  myRosterId,
}: {
  leagueId: string;
  teams: Team[];
  myRosterId: number | null;
}) {
  const router = useRouter();
  const id = `my-team-${leagueId}`;
  // follow the chosen value immediately; the server prop only catches up after the refresh
  const [selected, setSelected] = useState(myRosterId === null ? "" : String(myRosterId));

  return (
    <div className="my-team">
      <label htmlFor={id}>Your team</label>
      <select
        id={id}
        value={selected}
        onChange={(e) => {
          setSelected(e.target.value);
          setCookie(teamCookie(leagueId), e.target.value);
          router.refresh();
        }}
      >
        {selected === "" && <option value="">Choose your team</option>}
        {teams.map((t) => (
          <option key={t.roster_id} value={t.roster_id}>
            {t.team}
          </option>
        ))}
      </select>
    </div>
  );
}
