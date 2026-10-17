import { describe, expect, it } from "vitest";

import { splitName } from "../lib/playerName";
import { teamColor } from "../lib/teamColors";

describe("splitName", () => {
  it("makes the last word the large part", () => {
    expect(splitName("Jayden Daniels")).toEqual({ first: "Jayden", last: "Daniels" });
    expect(splitName("Amon-Ra St. Brown")).toEqual({ first: "Amon-Ra", last: "St. Brown" });
  });

  it("keeps a particle with the surname", () => {
    expect(splitName("Justin Van Jefferson")).toEqual({ first: "Justin", last: "Van Jefferson" });
  });

  it("keeps a suffix with the last name", () => {
    expect(splitName("Odell Beckham Jr.")).toEqual({ first: "Odell", last: "Beckham Jr." });
    expect(splitName("Marvin Harrison III")).toEqual({ first: "Marvin", last: "Harrison III" });
  });

  it("copes with one word, extra spaces and nothing", () => {
    expect(splitName("Cher")).toEqual({ first: "", last: "Cher" });
    expect(splitName("  Puka   Nacua ")).toEqual({ first: "Puka", last: "Nacua" });
    expect(splitName("")).toEqual({ first: "", last: "" });
    expect(splitName("Jr.")).toEqual({ first: "", last: "Jr." });
  });
});

describe("teamColor", () => {
  it("gives the team's colour for any case, and nothing for a free agent or unknown code", () => {
    expect(teamColor("WAS")).toBe("#773141");
    expect(teamColor("was")).toBe("#773141");
    expect(teamColor("JAC")).toBe(teamColor("JAX"));
    expect(teamColor(null)).toBeNull();
    expect(teamColor("XXX")).toBeNull();
  });
});
