import { TEAM_CODES, TEAM_NAMES } from "../lib/depth";

/**
 * Picks an NFL team with a plain form (it works without JavaScript): choosing a team and pressing
 * the button loads ?tab=teams&team=CODE.
 */
export default function TeamPicker({
  leagueId,
  selected,
}: {
  leagueId: string;
  selected: string | null;
}) {
  return (
    <form className="team-picker" method="get" action={`/league/${encodeURIComponent(leagueId)}`}>
      <input type="hidden" name="tab" value="teams" />
      <label>
        <span className="team-picker-label">NFL team</span>
        <select name="team" defaultValue={selected ?? ""}>
          <option value="" disabled>
            Choose a team
          </option>
          {TEAM_CODES.map((code) => (
            <option key={code} value={code}>
              {TEAM_NAMES[code]}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" className="btn btn-quiet">
        Show depth chart
      </button>
    </form>
  );
}
