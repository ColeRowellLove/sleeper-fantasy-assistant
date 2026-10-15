import type { Dashboard } from "../lib/api";
import { ruleChips } from "../lib/league";
import MyTeamPicker from "./MyTeamPicker";

export default function LeagueHeader({
  data,
  myRosterId,
}: {
  data: Dashboard;
  myRosterId: number | null;
}) {
  return (
    <header className="league-head">
      <div>
        <h1>{data.name.trim()}</h1>
        <p className="league-meta">{data.season} season</p>
        <ul className="rule-chips" aria-label="League rules">
          {ruleChips(data.rules).map((chip) => (
            <li key={chip}>{chip}</li>
          ))}
        </ul>
      </div>
      <MyTeamPicker
        key={myRosterId ?? "none"} // remount when the server resolves a different team
        leagueId={data.league_id}
        teams={data.standings}
        myRosterId={myRosterId}
      />
    </header>
  );
}
