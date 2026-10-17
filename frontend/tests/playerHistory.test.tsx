import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PlayerHistory from "../components/PlayerHistory";
import type { PlayerDetail } from "../lib/api";
import { historyDate, historyRows } from "../lib/playerHistory";
import { expectNoA11yViolations } from "./a11y";

type History = NonNullable<PlayerDetail["history"]>;

const history: History = [
  { kind: "added", source: "waivers", manager: "colehrl", date: "2026-10-10", week: 6 },
  { kind: "dropped", source: "waivers", manager: "colehrl", date: "2026-10-08", week: 6 },
  { kind: "added", source: "trade", manager: "Growell63", date: "2026-09-23", week: 3 },
  { kind: "dropped", source: "free_agency", manager: null, date: null, week: 1 },
  { kind: "added", source: "trade", manager: null, date: null, week: 1 },
  { kind: "dropped", source: "commissioner", manager: "cole", date: null, week: 1 },
];

describe("history rows", () => {
  it("words each move like Sleeper does, with who did it and when", () => {
    expect(historyRows(history).map((r) => [r.move, r.text, r.date])).toEqual([
      ["Added", "from Waivers by colehrl", "Oct 10, 2026"],
      ["Dropped", "to Waivers by colehrl", "Oct 8, 2026"],
      ["Added", "in a trade to Growell63", "Sep 23, 2026"],
      ["Dropped", "to Free agency", "–"],
      ["Added", "in a trade", "–"],
      ["Dropped", "by the commissioner from cole", "–"],
    ]);
    expect(historyRows(undefined)).toEqual([]);
  });

  it("writes a date in UTC, and a dash when there is none or it is not a date", () => {
    expect(historyDate("2026-01-01")).toBe("Jan 1, 2026");
    expect(historyDate(null)).toBe("–");
    expect(historyDate("nope")).toBe("–");
  });
});

describe("PlayerHistory", () => {
  it("lists the moves in a table, newest first", () => {
    render(<PlayerHistory history={history} />);
    const table = screen.getByRole("table", { name: /adds, drops and trades/i });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(7);
    expect(within(rows[1]).getByText("from Waivers by colehrl")).toBeInTheDocument();
  });

  it("renders nothing without moves, and has no accessibility violations", async () => {
    const { container } = render(<PlayerHistory history={[]} />);
    expect(container).toBeEmptyDOMElement();
    await expectNoA11yViolations(<PlayerHistory history={history} />);
  });
});
