import type { Dashboard } from "../lib/api";
import { ruleChips } from "../lib/league";
import FavouriteTeamPicker from "./FavouriteTeamPicker";
import MyTeamPicker from "./MyTeamPicker";

export default function LeagueHeader({
  data,
  myRosterId,
  favourite = null,
}: {
  data: Dashboard;
  myRosterId: number | null;
  /** The viewer's favourite NFL team code, if they chose one. */
  favourite?: string | null;
}) {
  return (
    <header className="league-head">
      <div>
        <h1 title={data.name.trim()}>{data.name.trim()}</h1>
        <p className="league-meta">{data.season} season</p>
        <ul className="rule-chips" aria-label="League rules" tabIndex={0}>
          {ruleChips(data.rules).map((chip) => (
            <li key={chip}>{chip}</li>
          ))}
        </ul>
      </div>
      <div className="head-pickers">
        <MyTeamPicker
          key={myRosterId ?? "none"} // remount when the server resolves a different team
          leagueId={data.league_id}
          teams={data.standings}
          myRosterId={myRosterId}
        />
        <FavouriteTeamPicker key={favourite ?? "none"} favourite={favourite} />
      </div>
    </header>
  );
}
