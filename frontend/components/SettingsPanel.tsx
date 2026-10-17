import type { LeagueSettings } from "../lib/api";
import {
  rosterSummary,
  scoringSummary,
  settingGroups,
  type SettingGroup,
  type SettingRow,
} from "../lib/leagueSettings";

function Rows({ rows }: { rows: SettingRow[] }) {
  return (
    <dl className="setting-rows">
      {rows.map((row) => (
        <div key={row.label} className="setting-row">
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

const slug = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, "-");

function Group({ group, prefix }: { group: SettingGroup; prefix: string }) {
  const id = `${prefix}-${slug(group.title)}`;
  return (
    <section className="card setting-group" aria-labelledby={id}>
      <h3 id={id}>{group.title}</h3>
      <Rows rows={group.rows} />
    </section>
  );
}

/** Everything Sleeper tells us about how the league is set up, in plain language. */
export default function SettingsPanel({ data }: { data: LeagueSettings }) {
  const groups = settingGroups(data.settings);
  const lineup: SettingGroup = {
    title: "Starting lineup",
    rows: rosterSummary(data.roster_positions),
  };
  const scoring = scoringSummary(data.scoring_settings);

  return (
    <section aria-labelledby="settings-heading">
      <h2 id="settings-heading" className="visually-hidden">
        League settings
      </h2>
      <div className="settings-grid">
        <Group group={lineup} prefix="rules" />
        <section className="card setting-group setting-merged" aria-label="League rules">
          {groups.map((group) => (
            <div key={group.title} className="setting-sub">
              <h3 id={`rules-${slug(group.title)}`}>{group.title}</h3>
              <Rows rows={group.rows} />
            </div>
          ))}
        </section>
      </div>

      <h2 className="settings-scoring-heading">Scoring</h2>
      <div className="settings-grid">
        {scoring.active.map((group) => (
          <Group key={group.title} group={group} prefix="scoring" />
        ))}
      </div>
      {scoring.unused.length > 0 && (
        <details className="card setting-group unused">
          <summary>Scored at zero in this league ({scoring.unused.length})</summary>
          <Rows rows={scoring.unused} />
        </details>
      )}
    </section>
  );
}
