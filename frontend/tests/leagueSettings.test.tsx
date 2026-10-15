import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SettingsPanel from "../components/SettingsPanel";
import type { LeagueSettings } from "../lib/api";
import { parseTab } from "../lib/league";
import {
  rosterSummary,
  scoringLabel,
  scoringSummary,
  settingGroups,
} from "../lib/leagueSettings";
import { expectNoA11yViolations } from "./a11y";

const data: LeagueSettings = {
  league_id: "1",
  name: "Love League",
  season: "2026",
  total_rosters: 10,
  settings: {
    num_teams: 10,
    type: 0,
    waiver_type: 1,
    waiver_budget: 100,
    waiver_day_of_week: 2,
    trade_deadline: 11,
    pick_trading: 1,
    disable_trades: 0,
    playoff_teams: 6,
    playoff_week_start: 15,
    mystery_new_setting: 7,
  },
  scoring_settings: {
    rec: 1,
    pass_yd: 0.04,
    pass_td: 4,
    pass_int: -2,
    fgm_40_49: 3,
    pts_allow_14_20: 1,
    bonus_rec_te: 0,
    idp_sack: 0,
  },
  roster_positions: ["QB", "RB", "RB", "WR", "FLEX", "BN", "BN", "BN"],
};

describe("settingGroups", () => {
  const groups = settingGroups(data.settings);
  const value = (group: string, label: string) =>
    groups.find((g) => g.title === group)?.rows.find((r) => r.label === label)?.value;

  it("labels settings in plain language", () => {
    expect(value("League", "Teams")).toBe("10");
    expect(value("League", "League type")).toBe("Redraft");
    expect(value("Waivers and free agents", "Waiver system")).toBe("Reverse standings priority");
    expect(value("Waivers and free agents", "Waivers first run on")).toBe("Tuesday");
    expect(value("Trades", "Trade deadline")).toBe("Week 11");
    expect(value("Trades", "Draft pick trading")).toBe("On");
    expect(value("Trades", "Trades disabled")).toBe("Off");
    expect(value("Playoffs", "Playoffs start")).toBe("Week 15");
  });

  it("never hides a setting it has no label for", () => {
    expect(value("Other settings", "Mystery new setting")).toBe("7");
  });

  it("hides the FAAB settings unless the league bids with FAAB", () => {
    const labels = (waiver: number) =>
      settingGroups({ waiver_type: waiver, waiver_budget: 100, faab_suggestions: 1 }).flatMap((g) =>
        g.rows.map((r) => r.label),
      );
    expect(labels(1)).not.toContain("FAAB budget");
    expect(labels(1)).not.toContain("Other settings");
    expect(labels(2)).toContain("FAAB budget");
  });

  it("skips settings Sleeper did not send", () => {
    expect(groups.some((g) => g.title === "Draft")).toBe(false);
  });

  it("shows a value outside the known options as written", () => {
    const odd = settingGroups({ waiver_type: 9, waiver_day_of_week: 12 });
    expect(odd[0].rows.map((r) => r.value)).toEqual(["9", "12"]);
  });
});

describe("roster and scoring", () => {
  it("counts each lineup slot", () => {
    expect(rosterSummary(data.roster_positions)).toEqual([
      { label: "QB", value: "1" },
      { label: "RB", value: "2" },
      { label: "WR", value: "1" },
      { label: "FLEX", value: "1" },
      { label: "Bench", value: "3" },
    ]);
  });

  it("writes readable scoring labels, including ranges", () => {
    expect(scoringLabel("rec")).toBe("Reception");
    expect(scoringLabel("fgm_40_49")).toBe("Field goal made 40-49");
    expect(scoringLabel("pts_allow_14_20")).toBe("Points allowed 14-20");
    expect(scoringLabel("pass_td_50p")).toBe("Passing touchdown 50+");
    expect(scoringLabel("bonus_rec_yd_100")).toBe("Bonus receiving yards 100");
  });

  it("groups scoring by category and sets zero-point rules aside", () => {
    const { active, unused } = scoringSummary(data.scoring_settings);
    const rows = (title: string) => active.find((g) => g.title === title)?.rows;
    expect(rows("Receiving")).toEqual([{ label: "Reception", value: "+1" }]);
    expect(rows("Passing")).toContainEqual({ label: "Passing yard", value: "+0.04" });
    expect(rows("Passing")).toContainEqual({ label: "Interception thrown", value: "-2" });
    expect(rows("Kicking")).toEqual([{ label: "Field goal made 40-49", value: "+3" }]);
    expect(rows("Team defense")).toEqual([{ label: "Points allowed 14-20", value: "+1" }]);
    expect(unused.map((r) => r.label)).toEqual(["Bonus receiving TE", "IDP sack"]);
  });
});

describe("SettingsPanel", () => {
  it("shows groups with headings and label/value pairs", () => {
    render(<SettingsPanel data={data} />);
    const trades = screen.getByRole("region", { name: "Trades" });
    expect(within(trades).getByText("Trade deadline")).toBeInTheDocument();
    expect(within(trades).getByText("Week 11")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Scoring" })).toBeInTheDocument();
    expect(screen.getByText("Scored at zero in this league (2)")).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<SettingsPanel data={data} />);
  });
});

describe("settings tab", () => {
  it("is a known tab", () => {
    expect(parseTab("settings")).toBe("settings");
    expect(parseTab("nonsense")).toBe("standings");
  });
});
