import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import PlayersTable from "../components/PlayersTable";
import type { PlayerListing, PlayersData } from "../lib/api";
import { parseTab } from "../lib/league";
import {
  DEFAULT_FILTERS,
  describeSort,
  filterPlayers,
  nextSort,
  sortPlayers,
} from "../lib/playersFilter";
import { expectNoA11yViolations } from "./a11y";

const player = (
  id: string,
  name: string,
  position: string,
  extra: Partial<PlayerListing> = {},
) => ({
  player_id: id,
  name,
  position,
  team: "SF",
  owner_roster_id: null,
  owner_team: null,
  adds: null,
  drops: null,
  total_points: 0,
  rank: null,
  projected: null,
  ...extra,
});

const players: PlayerListing[] = [
  player("1", "Puka Nacua", "WR", {
    owner_roster_id: 1,
    owner_team: "Cole",
    total_points: 90,
    rank: 1,
    projected: 20,
  }),
  player("2", "Free Receiver", "WR", {
    adds: 900,
    total_points: 60,
    rank: 2,
    projected: 12.5,
  }),
  player("3", "Patrick Mahomes", "QB", {
    owner_roster_id: 2,
    owner_team: "Dad Bods",
    total_points: 120,
    rank: 1,
  }),
  player("4", "José Ramírez", "RB", {
    adds: 50,
    drops: 700,
    total_points: 30,
    rank: 1,
    projected: 8,
  }),
  player("5", "D'Andre Swift", "RB", {
    owner_roster_id: 1,
    owner_team: "Cole",
    total_points: 80,
    rank: 2,
  }),
  player("6", "Nobody Kicker", "K", { total_points: 0 }),
];

const names = (list: PlayerListing[]) => list.map((p) => p.name);
const data: PlayersData = { league_id: "1", week: 6, players };

describe("filterPlayers", () => {
  it("filters by position, with FLEX meaning RB, WR and TE", () => {
    expect(
      names(filterPlayers(players, { ...DEFAULT_FILTERS, position: "QB" })),
    ).toEqual(["Patrick Mahomes"]);
    expect(
      filterPlayers(players, { ...DEFAULT_FILTERS, position: "FLEX" }),
    ).toHaveLength(4);
    expect(filterPlayers(players, DEFAULT_FILTERS)).toHaveLength(6);
  });

  it("filters by availability in this league", () => {
    expect(
      names(
        filterPlayers(players, {
          ...DEFAULT_FILTERS,
          availability: "available",
        }),
      ),
    ).toEqual(["Free Receiver", "José Ramírez", "Nobody Kicker"]);
    expect(
      filterPlayers(players, { ...DEFAULT_FILTERS, availability: "rostered" }),
    ).toHaveLength(3);
  });

  it("searches names and teams ignoring case, accents and punctuation", () => {
    const find = (search: string) =>
      names(filterPlayers(players, { ...DEFAULT_FILTERS, search }));
    expect(find("jose ramirez")).toEqual(["José Ramírez"]);
    expect(find("dandre")).toEqual(["D'Andre Swift"]);
    expect(find("  PUKA ")).toEqual(["Puka Nacua"]);
    expect(find("sf")).toHaveLength(6); // team abbreviations match too
    expect(find("zzz")).toEqual([]);
  });

  it("combines the filters", () => {
    const got = filterPlayers(players, {
      position: "WR",
      availability: "available",
      search: "",
    });
    expect(names(got)).toEqual(["Free Receiver"]);
  });
});

describe("sortPlayers", () => {
  const sorted = (
    key: Parameters<typeof nextSort>[1],
    direction: "asc" | "desc",
  ) => names(sortPlayers(players, { key, direction }));

  it("sorts by adds and drops, with players off Sleeper's list always last", () => {
    expect(sorted("adds", "desc")).toEqual([
      "Free Receiver",
      "José Ramírez",
      "Puka Nacua",
      "Patrick Mahomes",
      "D'Andre Swift",
      "Nobody Kicker",
    ]);
    expect(sorted("adds", "asc").slice(0, 2)).toEqual([
      "José Ramírez",
      "Free Receiver",
    ]);
    expect(sorted("adds", "asc").slice(2)).toEqual([
      "Puka Nacua",
      "Patrick Mahomes",
      "D'Andre Swift",
      "Nobody Kicker",
    ]);
    expect(sorted("drops", "desc")[0]).toBe("José Ramírez");
  });

  it("sorts by projected points with players without a projection last", () => {
    expect(sorted("projected", "desc").slice(0, 3)).toEqual([
      "Puka Nacua",
      "Free Receiver",
      "José Ramírez",
    ]);
    expect(sorted("projected", "asc").slice(0, 3)).toEqual([
      "José Ramírez",
      "Free Receiver",
      "Puka Nacua",
    ]);
  });

  it("sorts by total points and by positional rank", () => {
    expect(sorted("total", "desc")[0]).toBe("Patrick Mahomes");
    expect(sorted("total", "asc")[0]).toBe("Nobody Kicker");
    expect(sorted("rank", "asc").slice(0, 3)).toEqual([
      "Puka Nacua",
      "Patrick Mahomes",
      "José Ramírez",
    ]); // rank 1s first, ties keep the season-points order
    expect(sorted("rank", "asc").at(-1)).toBe("Nobody Kicker"); // no rank yet: last
    expect(sorted("rank", "desc").at(-1)).toBe("Nobody Kicker"); // and last the other way too
  });

  it("sorts by status and by name", () => {
    expect(sorted("status", "asc").slice(0, 3)).toEqual([
      "Free Receiver",
      "José Ramírez",
      "Nobody Kicker",
    ]);
    expect(sorted("name", "asc")[0]).toBe("D'Andre Swift");
    expect(sorted("name", "desc")[0]).toBe("Puka Nacua");
  });

  it("does not change the list it was given", () => {
    const before = names(players);
    sortPlayers(players, { key: "name", direction: "asc" });
    expect(names(players)).toEqual(before);
  });
});

describe("sort direction and description", () => {
  it("starts each column in its natural order, then flips", () => {
    const base = { key: "total", direction: "desc" } as const;
    expect(nextSort(base, "name")).toEqual({ key: "name", direction: "asc" });
    expect(nextSort(base, "rank")).toEqual({ key: "rank", direction: "asc" });
    expect(nextSort(base, "adds")).toEqual({ key: "adds", direction: "desc" });
    expect(nextSort(base, "total")).toEqual({ key: "total", direction: "asc" });
  });

  it("describes the sort in words", () => {
    expect(describeSort({ key: "rank", direction: "asc" })).toBe(
      "Sorted by Position rank, best first",
    );
    expect(describeSort({ key: "status", direction: "asc" })).toBe(
      "Sorted by Status, available first",
    );
    expect(describeSort({ key: "adds", direction: "desc" })).toBe(
      "Sorted by Adds, high to low",
    );
    expect(describeSort({ key: "name", direction: "desc" })).toBe(
      "Sorted by Player, Z to A",
    );
  });
});

describe("PlayersTable", () => {
  const rowNames = () =>
    screen
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("rowheader")[0].textContent ?? "");

  it("starts with every player, best season first", () => {
    render(<PlayersTable data={data} myRosterId={null} />);
    expect(rowNames()[0]).toContain("Patrick Mahomes");
    expect(rowNames()).toHaveLength(6);
  });

  it("shows availability, rank as position plus number, and dashes for missing numbers", () => {
    render(<PlayersTable data={data} myRosterId={1} />);
    const row = screen.getByRole("row", { name: /Free Receiver/ });
    expect(within(row).getByText("Available")).toBeInTheDocument();
    expect(within(row).getByText("WR2")).toBeInTheDocument();
    expect(within(row).getByText("900")).toBeInTheDocument();
    const owned = screen.getByRole("row", { name: /Puka Nacua/ });
    expect(within(owned).getByText("Cole")).toBeInTheDocument();
    expect(within(owned).getByText("You")).toBeInTheDocument(); // my team is marked in text
    const kicker = screen.getByRole("row", { name: /Nobody Kicker/ });
    expect(within(kicker).getAllByText("–").length).toBeGreaterThanOrEqual(4);
  });

  it("filters with the position and availability buttons and says which are on", async () => {
    const user = userEvent.setup();
    render(<PlayersTable data={data} myRosterId={null} />);
    await user.click(screen.getByRole("button", { name: "WR" }));
    await user.click(screen.getByRole("button", { name: "Available" }));
    expect(rowNames()).toHaveLength(1);
    expect(screen.getByRole("button", { name: "WR" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "QB" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Showing 1 of 1 players",
    );
  });

  it("searches as you type and explains an empty result", async () => {
    const user = userEvent.setup();
    render(<PlayersTable data={data} myRosterId={null} />);
    await user.type(
      screen.getByRole("searchbox", { name: /search players/i }),
      "ramirez",
    );
    expect(rowNames()).toHaveLength(1);
    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "nobody-here");
    expect(
      screen.getByText("No players match these filters."),
    ).toBeInTheDocument();
  });

  it("sorts from the column buttons and announces it", async () => {
    const user = userEvent.setup();
    render(<PlayersTable data={data} myRosterId={null} />);
    await user.click(screen.getByRole("button", { name: /^Adds/ }));
    expect(rowNames()[0]).toContain("Free Receiver");
    expect(screen.getByRole("columnheader", { name: /Adds/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Sorted by Adds, high to low",
    );
    await user.click(screen.getByRole("button", { name: /^Adds/ }));
    expect(rowNames()[0]).toContain("José Ramírez");
  });

  it("pages a long list and returns to the top when a filter changes", async () => {
    const user = userEvent.setup();
    const many = Array.from({ length: 120 }, (_, i) =>
      player(`p${i}`, `Player ${String(i).padStart(3, "0")}`, "WR", {
        total_points: 200 - i,
      }),
    );
    render(
      <PlayersTable data={{ ...data, players: many }} myRosterId={null} />,
    );
    expect(rowNames()).toHaveLength(50);
    await user.click(screen.getByRole("button", { name: "Show more players" }));
    expect(rowNames()).toHaveLength(100);
    await user.click(screen.getByRole("button", { name: "Show more players" }));
    expect(rowNames()).toHaveLength(120);
    expect(
      screen.queryByRole("button", { name: "Show more players" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "WR" }));
    expect(rowNames()).toHaveLength(50); // a new filter starts from the top again
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(<PlayersTable data={data} myRosterId={1} />);
  });
});

describe("players tab", () => {
  it("is a known tab", () => {
    expect(parseTab("players")).toBe("players");
  });
});

describe("ESPN ownership columns", () => {
  const withOwnership: PlayerListing[] = [
    player("1", "Rarely Started", "RB", {
      owned_pct: 80.25,
      started_pct: 12.3,
    }),
    player("2", "Always Started", "QB", {
      owned_pct: 99.9,
      started_pct: 99.04,
    }),
    player("3", "No ESPN Match", "WR"),
    player("4", "Barely Owned", "WR", { owned_pct: 0.4, started_pct: 0 }),
  ];

  it("sorts by owned and started with players ESPN has no number for always last", () => {
    const sorted = (key: "owned" | "started", direction: "asc" | "desc") =>
      names(sortPlayers(withOwnership, { key, direction }));
    expect(sorted("owned", "desc")).toEqual([
      "Always Started",
      "Rarely Started",
      "Barely Owned",
      "No ESPN Match",
    ]);
    expect(sorted("owned", "asc")).toEqual([
      "Barely Owned",
      "Rarely Started",
      "Always Started",
      "No ESPN Match",
    ]);
    expect(sorted("started", "desc")[0]).toBe("Always Started");
    expect(sorted("started", "asc").at(-1)).toBe("No ESPN Match");
    expect(sorted("started", "asc")[0]).toBe("Barely Owned"); // a real 0 percent is data, not missing
  });

  it("starts both columns high to low and describes them as ESPN's numbers", () => {
    const base = { key: "total", direction: "desc" } as const;
    expect(nextSort(base, "owned")).toEqual({
      key: "owned",
      direction: "desc",
    });
    expect(nextSort(base, "started")).toEqual({
      key: "started",
      direction: "desc",
    });
    expect(describeSort({ key: "owned", direction: "desc" })).toBe(
      "Sorted by Owned % (ESPN), high to low",
    );
  });

  it("shows percentages, a dash when ESPN has none, and says the numbers are ESPN's", async () => {
    const user = userEvent.setup();
    render(
      <PlayersTable
        data={{ ...data, players: withOwnership }}
        myRosterId={null}
      />,
    );
    const rarely = screen.getByRole("row", { name: /Rarely Started/ });
    expect(within(rarely).getByText("80.3%")).toBeInTheDocument();
    expect(within(rarely).getByText("12.3%")).toBeInTheDocument();
    const missing = screen.getByRole("row", { name: /No ESPN Match/ });
    expect(within(missing).queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.getByText(/ESPN-wide/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Start %/ }));
    expect(
      screen.getByRole("columnheader", { name: /Start %/ }),
    ).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Sorted by Start % (ESPN), high to low",
    );
    expect(screen.getAllByRole("row").slice(1)[0].textContent).toContain(
      "Always Started",
    );
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <PlayersTable
        data={{ ...data, players: withOwnership }}
        myRosterId={null}
      />,
    );
  });
});
