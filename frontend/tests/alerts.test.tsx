import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AlertsPanel from "../components/AlertsPanel";
import LeagueTabs from "../components/LeagueTabs";
import type { AlertsData, Dashboard } from "../lib/api";
import {
  alertAdvice,
  alertTime,
  alertsTabLabel,
  newestAlertTime,
  parseSeen,
  unreadAlerts,
  waiverTargets,
} from "../lib/alerts";
import { parseTab } from "../lib/league";
import { expectNoA11yViolations } from "./a11y";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams("tab=alerts"),
}));

const rosters: Dashboard["rosters"] = [
  { roster_id: 1, team: "Cole", owner_id: "u1", players: [] },
  { roster_id: 2, team: "Dad Bods", owner_id: "u2", players: [] },
];

const data: AlertsData = {
  league_id: "1",
  roster_id: 1,
  alerts: [
    {
      id: 2,
      kind: "injury_out",
      title: "J. Smith was ruled out",
      why: "He starts at RB for you in week 7 (projected 14.2).",
      player_id: "4034",
      created_at: "2026-10-17T16:05:00Z",
    },
    {
      id: 1,
      kind: "waiver_targets",
      title: "Waiver targets for Tuesday",
      why: "T. Horton: projected 11.4, +4.2 over your WR3.",
      created_at: "2026-10-16T12:00:00Z",
    },
  ],
};

beforeEach(() => {
  refresh.mockClear();
  document.cookie = "sa_alerts_seen_1=; max-age=0; path=/";
});

describe("alert helpers", () => {
  it("counts the alerts newer than the viewer's last clear, or all without one", () => {
    expect(unreadAlerts(data.alerts, null)).toHaveLength(2);
    expect(unreadAlerts(data.alerts, "not a date")).toHaveLength(2);
    expect(unreadAlerts(data.alerts, "2026-10-16T12:00:00Z").map((a) => a.id)).toEqual([2]);
    expect(unreadAlerts(data.alerts, "2026-10-17T16:05:00Z")).toEqual([]);
  });

  it("reads the viewer's cookie safely, ignoring anything malformed", () => {
    expect(parseSeen("2026-10-17T16:05:00.000Z")).toBe("2026-10-17T16:05:00.000Z");
    expect(parseSeen("2026-10-17T16%3A05%3A00.000Z")).toBe("2026-10-17T16:05:00.000Z");
    expect(parseSeen("%E0%A4%A")).toBeNull(); // would throw in decodeURIComponent
    expect(parseSeen("garbage")).toBeNull();
    expect(parseSeen("")).toBeNull();
    expect(parseSeen(undefined)).toBeNull();
  });

  it("remembers the newest alert's own time", () => {
    expect(newestAlertTime(data.alerts)).toBe("2026-10-17T16:05:00.000Z");
    expect(newestAlertTime([])).toBeNull();
  });

  it("puts the new count in words on the tab", () => {
    expect(alertsTabLabel(0)).toBe("Alerts");
    expect(alertsTabLabel(3)).toBe("Alerts (3 new)");
  });

  it("writes times in UTC so the server and the browser agree", () => {
    expect(alertTime("2026-10-17T16:05:00Z")).toBe("Sat, Oct 17, 4:05 PM UTC");
    expect(alertTime("nonsense")).toBe("");
  });

  it("is a tab", () => {
    expect(parseTab("alerts")).toBe("alerts");
  });
});

describe("LeagueTabs", () => {
  it("shows how many alerts are new on the Alerts tab, in words", () => {
    render(<LeagueTabs leagueId="1" active="standings" unreadAlerts={2} />);
    expect(screen.getByRole("link", { name: "Alerts (2 new)" })).toHaveAttribute(
      "href",
      "/league/1?tab=alerts",
    );
  });

  it("shows just Alerts when there is nothing new", () => {
    render(<LeagueTabs leagueId="1" active="standings" />);
    expect(screen.getByRole("link", { name: "Alerts" })).toBeInTheDocument();
  });
});

describe("AlertsPanel", () => {
  it("lists a team's alerts newest first with title, why, time and a player link", () => {
    render(<AlertsPanel data={data} rosters={rosters} leagueId="1" myRosterId={1} seen={null} />);
    const titles = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(titles).toEqual(["NewJ. Smith was ruled out", "NewWaiver targets for Tuesday"]);
    expect(
      screen.getByText("He starts at RB for you in week 7 (projected 14.2)."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Sat, Oct 17, 4:05 PM UTC/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View player" })).toHaveAttribute(
      "href",
      expect.stringContaining("player=4034"),
    );
  });

  it("marks only the alerts after the viewer's last clear as new, in words", () => {
    render(
      <AlertsPanel
        data={data}
        rosters={rosters}
        leagueId="1"
        myRosterId={1}
        seen="2026-10-16T12:00:00Z"
      />,
    );
    expect(screen.getAllByText("New")).toHaveLength(1);
    expect(screen.getByText("1 new alert.", { exact: false })).toBeInTheDocument();
  });

  it("remembers the clear in the viewer's own cookie and refreshes", () => {
    render(<AlertsPanel data={data} rosters={rosters} leagueId="1" myRosterId={1} seen={null} />);
    fireEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    expect(decodeURIComponent(document.cookie)).toContain(
      "sa_alerts_seen_1=2026-10-17T16:05:00.000Z",
    );
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("offers no clear button once everything is read, nor for another team's alerts", () => {
    const { rerender } = render(
      <AlertsPanel
        data={data}
        rosters={rosters}
        leagueId="1"
        myRosterId={1}
        seen="2026-10-17T16:05:00Z"
      />,
    );
    expect(screen.queryByRole("button", { name: "Mark all as read" })).not.toBeInTheDocument();
    rerender(
      <AlertsPanel
        data={{ ...data, roster_id: 2 }}
        rosters={rosters}
        leagueId="1"
        myRosterId={1}
        seen={null}
      />,
    );
    expect(screen.queryByRole("button", { name: "Mark all as read" })).not.toBeInTheDocument();
    expect(screen.queryByText("New")).not.toBeInTheDocument(); // read state is only for your own team
  });

  it("picks the team with a plain GET form", () => {
    render(<AlertsPanel data={data} rosters={rosters} leagueId="1" myRosterId={1} seen={null} />);
    const form = screen
      .getByRole("button", { name: "Show alerts" })
      .closest("form") as HTMLFormElement;
    expect(form).toHaveAttribute("method", "get");
    expect(form).toHaveAttribute("action", "/league/1");
    expect((form.querySelector('input[name="tab"]') as HTMLInputElement).value).toBe("alerts");
    expect(screen.getByRole("combobox", { name: /Team/ })).toHaveValue("1");
  });

  it("explains an empty feed", () => {
    render(
      <AlertsPanel
        data={{ ...data, alerts: [] }}
        rosters={rosters}
        leagueId="1"
        myRosterId={1}
        seen={null}
      />,
    );
    expect(screen.getByText(/No alerts yet for your team/)).toBeInTheDocument();
  });

  it("says what alerts are sent: open when there are none, folded away when there are some", () => {
    const empty = { ...data, alerts: [] };
    const { rerender } = render(
      <AlertsPanel data={empty} rosters={rosters} leagueId="1" myRosterId={1} seen={null} />,
    );
    const summary = screen.getByText("What alerts are sent");
    const details = summary.closest("details") as HTMLElement;
    expect(details).toHaveAttribute("open");
    const items = within(details).getAllByRole("listitem");
    expect(items.map((li) => li.querySelector("strong")?.textContent)).toEqual([
      "A player on your team is ruled out.",
      "Waiver targets.",
      "AI suggestion.",
      "Text messages.",
    ]);
    expect(within(details).getByText(/Not on yet/)).toBeInTheDocument();
    expect(within(details).getByText(/9 am Eastern the day before/)).toBeInTheDocument();
    rerender(<AlertsPanel data={data} rosters={rosters} leagueId="1" myRosterId={1} seen={null} />);
    expect(screen.getByText("What alerts are sent").closest("details")).not.toHaveAttribute("open");
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(
      <AlertsPanel data={data} rosters={rosters} leagueId="1" myRosterId={1} seen={null} />,
    );
  });
});

describe("waiver target alerts", () => {
  const waiver: AlertsData["alerts"][number] = {
    id: 9,
    kind: "waiver_targets",
    title: "Top waiver targets for Tuesday, Oct 20",
    why: "1. T. Horton (WR, SEA): projected 11.4, +4.2 over Smith at WR. 2. Free Back (RB, SF): projected 9.0, +9.0 at an open RB spot.",
    created_at: "2026-10-19T14:00:00Z",
    data: {
      targets: [
        {
          player_id: "11",
          name: "T. Horton",
          position: "WR",
          team: "SEA",
          projected: 11.4,
          gain: 4.2,
          detail:
            "(WR, SEA): projected 11.4, +4.2 over Smith at WR. Added in 8,200 leagues in the last day.",
          line: "T. Horton (WR, SEA): projected 11.4, +4.2 over Smith at WR. Added in 8,200 leagues in the last day.",
        },
        {
          player_id: "12",
          name: "Free Back",
          position: "RB",
          team: "SF",
          projected: 9,
          gain: 9,
          line: "Free Back (RB, SF): projected 9.0, +9.0 at an open RB spot.",
        },
      ],
    },
  };
  const panel = (seen: string | null) => (
    <AlertsPanel
      data={{ league_id: "1", roster_id: 1, alerts: [waiver] }}
      rosters={rosters}
      leagueId="1"
      myRosterId={1}
      seen={seen}
    />
  );

  it("reads the pickups from the alert, ignoring anything malformed", () => {
    expect(waiverTargets(waiver).map((t) => t.player_id)).toEqual(["11", "12"]);
    expect(waiverTargets({ ...waiver, kind: "injury_out" })).toEqual([]);
    expect(waiverTargets({ ...waiver, data: undefined })).toEqual([]);
    expect(waiverTargets({ ...waiver, data: { targets: "nope" } })).toEqual([]);
    expect(waiverTargets({ ...waiver, data: { targets: [null, { player_id: 1 }, 5] } })).toEqual(
      [],
    );
  });

  it("lists each pickup as a numbered, linked line with its numbers", () => {
    render(panel("2026-10-20T00:00:00Z"));
    const items = screen.getAllByRole("listitem").filter((li) => li.closest("ol"));
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent(
      "T. Horton (WR, SEA): projected 11.4, +4.2 over Smith at WR. Added in 8,200 leagues",
    );
    expect(screen.getByRole("link", { name: "T. Horton" })).toHaveAttribute(
      "href",
      expect.stringContaining("player=11"),
    );
    expect(items[1]).toHaveTextContent(
      "Free Back (RB, SF): projected 9.0, +9.0 at an open RB spot.",
    );
  });

  it("falls back to the one-line text for an alert with no structured targets", () => {
    render(
      <AlertsPanel
        data={{ league_id: "1", roster_id: 1, alerts: [{ ...waiver, data: {} }] }}
        rosters={rosters}
        leagueId="1"
        myRosterId={1}
        seen={null}
      />,
    );
    expect(screen.getByText(/1\. T\. Horton/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    await expectNoA11yViolations(panel(null));
  });
});

describe("keyboard", () => {
  it("reaches the player links in an alert with the Tab key", async () => {
    const user = userEvent.setup();
    render(
      <AlertsPanel
        data={{
          league_id: "1",
          roster_id: 2,
          alerts: [
            {
              id: 5,
              kind: "waiver_targets",
              title: "Top waiver targets for Tuesday, Oct 20",
              why: "1. T. Horton (WR, SEA): projected 11.4, +4.2 over Smith at WR.",
              created_at: "2026-10-19T14:00:00Z",
              data: {
                targets: [
                  {
                    player_id: "11",
                    name: "T. Horton",
                    projected: 11.4,
                    gain: 4.2,
                    detail: "(WR, SEA): projected 11.4, +4.2 over Smith at WR.",
                    line: "T. Horton (WR, SEA): projected 11.4, +4.2 over Smith at WR.",
                  },
                ],
              },
            },
          ],
        }}
        rosters={rosters}
        leagueId="1"
        myRosterId={1}
        seen={null}
      />,
    );
    await user.tab(); // the folded "What alerts are sent" disclosure
    await user.tab(); // the team picker
    await user.tab(); // its button
    await user.tab(); // the first alert's player link
    expect(screen.getByRole("link", { name: "T. Horton" })).toHaveFocus();
  });
});

describe("model advice", () => {
  const advice = {
    source: "model",
    summary: "Start the backup.",
    picks: [
      {
        player_id: "9",
        name: "Bench Back",
        position: "RB",
        team: "SF",
        action: "bench",
        reason: "He is projected 8.0.",
      },
      {
        player_id: "7",
        name: "Free Back",
        position: "RB",
        team: "SF",
        action: "pickup",
        drop_name: "Slow Back",
        reason: "He is projected 11.0.",
      },
    ],
  };
  const withAdvice: AlertsData = {
    ...data,
    alerts: [{ ...data.alerts[0], data: { advice } }],
  };

  it("reads well-formed advice and ignores anything else", () => {
    expect(alertAdvice(withAdvice.alerts[0])?.picks).toHaveLength(2);
    expect(alertAdvice(data.alerts[0])).toBeNull();
    expect(alertAdvice({ ...data.alerts[0], data: { advice: "text" } })).toBeNull();
    expect(
      alertAdvice({ ...data.alerts[0], data: { advice: { summary: "x", picks: [{ nope: 1 }] } } }),
    ).toBeNull();
  });

  it("shows the advice, labelled as AI, above the numbers", async () => {
    const panel = (
      <AlertsPanel data={withAdvice} rosters={rosters} leagueId="1" myRosterId={1} seen={null} />
    );
    render(panel);
    expect(screen.getByText("Suggested by an AI assistant")).toBeInTheDocument();
    expect(screen.getByText("Start the backup.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bench Back" })).toBeInTheDocument();
    expect(screen.getByText(/start from your bench: He is projected 8.0/)).toBeInTheDocument();
    expect(
      screen.getByText(/pick up, dropping Slow Back: He is projected 11.0/),
    ).toBeInTheDocument();
    expect(screen.getByText(/He starts at RB for you/)).toBeInTheDocument();
    await expectNoA11yViolations(panel);
  });
});
