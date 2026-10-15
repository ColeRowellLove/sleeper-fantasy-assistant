import { describe, expect, it } from "vitest";

import { avatarUrl, headshotUrl, initials, teamLogoUrl } from "../lib/images";

describe("images", () => {
  it("builds headshot and team logo URLs on the Sleeper CDN", () => {
    expect(headshotUrl("4034")).toBe("https://sleepercdn.com/content/nfl/players/thumb/4034.jpg");
    expect(teamLogoUrl("PIT")).toBe("https://sleepercdn.com/images/team_logos/nfl/pit.png");
  });

  it("uses the team logo for defenses and a headshot for everyone else", () => {
    expect(avatarUrl({ player_id: "PIT", position: "DEF", team: "PIT" })).toContain(
      "team_logos/nfl/pit",
    );
    expect(avatarUrl({ player_id: "PIT", position: "DEF", team: null })).toContain(
      "team_logos/nfl/pit",
    );
    expect(avatarUrl({ player_id: "4034", position: "RB", team: "SF" })).toContain(
      "players/thumb/4034",
    );
  });

  it("escapes ids so a malformed id cannot change the URL path", () => {
    expect(headshotUrl("../x")).not.toContain("/../");
  });

  it("makes initials from names", () => {
    expect(initials("Christian McCaffrey")).toBe("CM");
    expect(initials("Cher")).toBe("CH");
    expect(initials("  ")).toBe("?");
    expect(initials("Jay Von Der Heyden")).toBe("JH");
  });
});
