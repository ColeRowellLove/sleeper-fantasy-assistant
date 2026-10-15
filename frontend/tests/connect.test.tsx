import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ConnectForm from "../components/ConnectForm";
import { expectNoA11yViolations } from "./a11y";

const userLeagues = (leagues: unknown[]) => ({ user_id: "u1", display_name: "Cole", leagues });
const league = { league_id: "123", name: "Family League", season: "2026", total_rosters: 10 };
const connected = {
  ...league,
  rules: {
    reception_scoring: "full",
    uses_faab: true,
    trade_deadline_week: 11,
    playoff_teams: 6,
  },
};

function mockFetch(...responses: Array<{ status?: number; body?: unknown } | "network-error">) {
  const fn = vi.fn();
  for (const r of responses) {
    if (r === "network-error") fn.mockRejectedValueOnce(new TypeError("fail"));
    else
      fn.mockResolvedValueOnce(
        new Response(JSON.stringify(r.body ?? {}), { status: r.status ?? 200 }),
      );
  }
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ConnectForm", () => {
  it("has no accessibility violations in any step", async () => {
    await expectNoA11yViolations(<ConnectForm />);
  });

  it("labels the username field and is operable by keyboard", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch({ body: userLeagues([league]) });
    render(<ConnectForm />);

    await user.tab();
    expect(screen.getByLabelText("Sleeper username")).toHaveFocus();
    await user.keyboard("cole{Enter}");

    expect(fetchMock).toHaveBeenCalledWith("/api/users/cole/leagues", undefined);
    expect(await screen.findByRole("button", { name: /Family League/ })).toBeInTheDocument();
  });

  it("walks through username, league pick and connect", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch({ body: userLeagues([league]) }, { body: connected });
    const { container } = render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "cole");
    await user.click(screen.getByRole("button", { name: "Find my leagues" }));
    await user.click(await screen.findByRole("button", { name: /Family League/ }));

    expect(await screen.findByText(/FAAB waivers/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open league dashboard" })).toHaveAttribute(
      "href",
      "/league/123",
    );
    expect(fetchMock).toHaveBeenLastCalledWith("/api/leagues/123/connect", { method: "POST" });

    const { axe } = await import("vitest-axe");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("remembers the Sleeper user id so the league page can find your team", async () => {
    const user = userEvent.setup();
    mockFetch({ body: userLeagues([league]) });
    render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "cole");
    await user.click(screen.getByRole("button", { name: "Find my leagues" }));
    await screen.findByRole("button", { name: /Family League/ });

    expect(document.cookie).toContain("sa_user=u1");
  });

  it("still works with the API's previous bare-array response (deploy skew)", async () => {
    const user = userEvent.setup();
    mockFetch({ body: [league] });
    render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "cole");
    await user.click(screen.getByRole("button", { name: "Find my leagues" }));

    expect(await screen.findByRole("button", { name: /Family League/ })).toBeInTheDocument();
  });

  it("announces validation errors via an alert and flags the field", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch();
    render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "no spaces allowed");
    await user.click(screen.getByRole("button", { name: "Find my leagues" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/Enter your Sleeper username/);
    expect(screen.getByLabelText("Sleeper username")).toBeInvalid();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows friendly errors for unknown users and network failures", async () => {
    const user = userEvent.setup();
    mockFetch({ status: 404 }, "network-error");
    render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "ghost");
    await user.click(screen.getByRole("button", { name: "Find my leagues" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("couldn't find that");

    await user.click(screen.getByRole("button", { name: "Find my leagues" }));
    expect(await screen.findByText(/Could not reach the server/)).toBeInTheDocument();
  });

  it("tells the user when no leagues exist", async () => {
    const user = userEvent.setup();
    mockFetch({ body: userLeagues([]) });
    render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "cole");
    await user.click(screen.getByRole("button", { name: "Find my leagues" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No leagues found");
  });
  it("moves focus to the new content after each step", async () => {
    const user = userEvent.setup();
    mockFetch({ body: userLeagues([league]) }, { body: connected });
    render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "cole");
    await user.click(screen.getByRole("button", { name: "Find my leagues" }));
    await screen.findByRole("button", { name: /Family League/ });
    expect(screen.getByText("Choose a league to connect:")).toHaveFocus();

    await user.click(screen.getByRole("button", { name: /Family League/ }));
    await screen.findByText(/FAAB waivers/);
    expect(screen.getByText(/Connected/)).toHaveFocus();
  });

  it("returns focus to the field and describes it with the error", async () => {
    const user = userEvent.setup();
    render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "bad name");
    await user.click(screen.getByRole("button", { name: "Find my leagues" }));

    const field = screen.getByLabelText("Sleeper username");
    expect(field).toHaveFocus();
    expect(field).toHaveAccessibleDescription(/Enter your Sleeper username/);
  });

  it("ignores repeat submits while a request is in flight", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(() => new Promise<Response>(() => {})); // never resolves
    vi.stubGlobal("fetch", fetchMock);
    render(<ConnectForm />);

    await user.type(screen.getByLabelText("Sleeper username"), "cole");
    const button = screen.getByRole("button", { name: "Find my leagues" });
    await user.click(button);
    await user.click(screen.getByRole("button", { name: "Looking…" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Looking…" })).toHaveAttribute("aria-disabled", "true");
  });
});
