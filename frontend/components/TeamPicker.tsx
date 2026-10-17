import AutoSubmitForm from "./AutoSubmitForm";
import { TEAM_CODES, TEAM_NAMES } from "../lib/depth";

/**
 * Picks an NFL team with a plain form (it works without JavaScript): choosing a team loads ?tab=teams&team=CODE.
 */
export default function TeamPicker({
  leagueId,
  selected,
}: {
  leagueId: string;
  selected: string | null;
}) {
  return (
    <AutoSubmitForm
      className="team-picker"
      action={`/league/${encodeURIComponent(leagueId)}`}
      submitLabel="Show depth chart"
    >
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
    </AutoSubmitForm>
  );
}
