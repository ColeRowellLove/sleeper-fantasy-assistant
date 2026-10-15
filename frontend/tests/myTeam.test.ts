import { describe, expect, it } from "vitest";

import { findMyRosterId, teamCookie } from "../lib/myTeam";

const teams = [
  { roster_id: 1, owner_id: "u1" },
  { roster_id: 2, owner_id: null },
  { roster_id: 3, owner_id: "u3" },
];

describe("findMyRosterId", () => {
  it("matches the Sleeper user id the person connected with", () => {
    expect(findMyRosterId(teams, { userId: "u1" })).toBe(1);
    expect(findMyRosterId(teams, { userId: "u3" })).toBe(3);
  });

  it("prefers an explicit team pick for this league over the username", () => {
    expect(findMyRosterId(teams, { team: "2", userId: "u1" })).toBe(2);
  });

  it("ignores a stale or invalid team pick and falls back to the username", () => {
    expect(findMyRosterId(teams, { team: "99", userId: "u3" })).toBe(3);
    expect(findMyRosterId(teams, { team: "abc", userId: "u3" })).toBe(3);
  });

  it("is null when nothing identifies a team", () => {
    expect(findMyRosterId(teams, {})).toBeNull();
    expect(findMyRosterId(teams, { userId: "stranger" })).toBeNull();
    expect(findMyRosterId(teams, { team: null, userId: null })).toBeNull();
  });

  it("namespaces the team cookie by league", () => {
    expect(teamCookie("123")).toBe("sa_team_123");
  });
});
