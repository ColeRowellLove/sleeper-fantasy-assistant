import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Enforces docs/DESIGN.md: a stats table, a filter chip group and a player's face and name are
// built by one shared component each (StatTable, FilterChips, PlayerIdentity). A screen that
// needs something different changes the shared component, it does not make a copy.
//
// The lists below are the screens that have not moved over yet. They may only shrink: do not add
// to them. When a screen is migrated, delete its entry here.

const dir = join(__dirname, "..", "components");
const files = readdirSync(dir)
  .filter((f) => f.endsWith(".tsx"))
  .map((f) => ({ name: f, text: readFileSync(join(dir, f), "utf8") }));

function using(pattern: RegExp): string[] {
  return files
    .filter((f) => pattern.test(f.text))
    .map((f) => f.name)
    .sort();
}

describe("shared components are the only way to build these", () => {
  it("stats tables use StatTable (existing exceptions may only shrink)", () => {
    const found = using(/<table className=\{?[`"]players/);
    expect(found).toEqual(["StatTable.tsx"]);
    const scrolling = using(/className="players-scroll/);
    const allowed = [
      "PlayerDialog.tsx",
      "StatTable.tsx",
      "TeamDepthChart.tsx",
      "TeamStatsTable.tsx",
    ];
    expect(scrolling.filter((f) => !allowed.includes(f))).toEqual([]);
  });

  it("filter chips use FilterChips", () => {
    expect(using(/className="players-filter"/)).toEqual(["FilterChips.tsx"]);
    expect(using(/className="filter-chip"/)).toEqual(["FilterChips.tsx"]);
  });

  it("a player's face is shown through PlayerIdentity (existing exceptions may only shrink)", () => {
    const allowed = [
      "MatchupCard.tsx",
      "PlayerDialog.tsx",
      "PlayerIdentity.tsx",
      "RostersPanel.tsx",
      "StartSitTool.tsx",
    ];
    expect(using(/<PlayerAvatar/).filter((f) => !allowed.includes(f))).toEqual([]);
  });

  it("the shared components are used by the tabs they were built for", () => {
    for (const name of ["PlayersTable.tsx", "RankingsPanel.tsx", "GamePlayers.tsx"]) {
      const text = files.find((f) => f.name === name)?.text ?? "";
      expect(text, `${name} should use PlayerIdentity`).toContain("PlayerIdentity");
      expect(text, `${name} should use StatTable`).toContain("StatTable");
    }
    for (const name of ["PlayersTable.tsx", "RankingsPanel.tsx"]) {
      const text = files.find((f) => f.name === name)?.text ?? "";
      expect(text, `${name} should use FilterChips`).toContain("FilterChips");
    }
  });
});
