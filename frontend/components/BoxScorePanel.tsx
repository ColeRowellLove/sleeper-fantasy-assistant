"use client";

import Link from "next/link";

import type { BoxScoreData, BoxTable } from "../lib/api";
import { leaguePath } from "../lib/league";
import NoteList from "./NoteList";
import PanelTabs from "./PanelTabs";
import PlayerLink from "./PlayerLink";
import StatTable from "./StatTable";
import TeamLogo from "./TeamLogo";

function Section({ table, team, mine }: { table: BoxTable; team: string; mine: Set<string> }) {
  const id = `box-${team}-${table.key}`;
  return (
    <section aria-labelledby={id} className="box-section">
      <h3 id={id}>{table.title}</h3>
      <StatTable
        bare
        caption={`${team} ${table.title.toLowerCase()}`}
        className="box-table"
        scrollLabel={`${team} ${table.title.toLowerCase()} table, scrolls sideways`}
      >
        <thead>
          <tr>
            <th scope="col">Player</th>
            {table.columns.map((c) => (
              <th key={c} scope="col" className="num-col">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={`${i}-${row.name}`}>
              <th scope="row">
                {row.player_id ? (
                  <PlayerLink playerId={row.player_id}>{row.name}</PlayerLink>
                ) : (
                  row.name
                )}
                {row.position && <span className="muted"> {row.position}</span>}
                {row.player_id && mine.has(row.player_id) && <span className="you">You</span>}
              </th>
              {row.stats.map((value, i) => (
                <td key={i} className="num-col">
                  {value}
                </td>
              ))}
            </tr>
          ))}
          {table.totals && (
            <tr className="box-totals">
              <th scope="row">Team</th>
              {table.totals.map((value, i) => (
                <td key={i} className="num-col">
                  {value}
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </StatTable>
    </section>
  );
}

/**
 * ESPN's full box score for one game: a tab for each team, then every stat category (passing,
 * rushing, receiving, defense, kicking, returns) as a compact table. Your players are marked.
 */
export default function BoxScorePanel({
  data,
  leagueId,
  week,
  mine,
}: {
  data: BoxScoreData | null;
  leagueId: string;
  week: number;
  mine: string[];
}) {
  const back = (
    <Link href={leaguePath(leagueId, `?tab=games&week=${week}`)} className="back-link">
      ← All games
    </Link>
  );
  if (!data || data.teams.length === 0) {
    return (
      <section aria-labelledby="box-heading" className="box">
        {back}
        <h2 id="box-heading">Box score</h2>
        <p className="note" role="status">
          The full box score is not available right now. Try again in a moment.
        </p>
      </section>
    );
  }
  const mineSet = new Set(mine);
  return (
    <section aria-labelledby="box-heading" className="box">
      {back}
      <h2 id="box-heading" className="box-title">
        <TeamLogo team={data.away} size={24} /> {data.away} at{" "}
        <TeamLogo team={data.home} size={24} /> {data.home}
        <span className="muted"> · {data.final ? "Final" : "Box score so far"}</span>
      </h2>
      <NoteList
        items={[
          "Every player and stat category, from ESPN",
          "Your players are marked; players matched by name open their pop-up",
        ]}
      />
      <PanelTabs
        label="Teams"
        tabs={data.teams.map((t) => ({
          key: t.team,
          label: t.team,
          content: (
            <div className="box-team">
              {t.tables.map((table) => (
                <Section key={table.key} table={table} team={t.team} mine={mineSet} />
              ))}
            </div>
          ),
        }))}
      />
    </section>
  );
}
