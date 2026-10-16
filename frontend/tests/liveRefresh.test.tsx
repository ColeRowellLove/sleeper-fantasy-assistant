import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LiveRefresh from "../components/LiveRefresh";
import type { GameInfo } from "../lib/api";
import { anyLive } from "../lib/game";
import { expectNoA11yViolations } from "./a11y";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh, replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/league/1",
  useSearchParams: () => new URLSearchParams(),
}));

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("LiveRefresh", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    refresh.mockClear();
    setHidden(false);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does nothing and shows nothing when no game is live", () => {
    const { container } = render(<LiveRefresh active={false} />);
    act(() => {
      vi.advanceTimersByTime(120_000);
    });
    expect(refresh).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it("refreshes the page data every interval while a game is live, and says so", () => {
    render(<LiveRefresh active seconds={15} />);
    expect(screen.getByText(/Live: updating every 15 seconds\./)).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(14_000);
    });
    expect(refresh).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1_000);
    });
    expect(refresh).toHaveBeenCalledTimes(1);
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    expect(refresh).toHaveBeenCalledTimes(3);
    expect(screen.getByText(/Last update/)).toBeInTheDocument();
  });

  it("can be paused and resumed", () => {
    render(<LiveRefresh active seconds={15} />);
    fireEvent.click(screen.getByRole("button", { name: "Pause live updates" }));
    expect(screen.getByText("Live updates paused.")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(refresh).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Resume live updates" }));
    act(() => {
      vi.advanceTimersByTime(15_000);
    });
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("waits while the tab is hidden and catches up when it is shown again", () => {
    render(<LiveRefresh active seconds={15} />);
    act(() => {
      setHidden(true);
      vi.advanceTimersByTime(60_000);
    });
    expect(refresh).not.toHaveBeenCalled();
    act(() => {
      setHidden(false);
    });
    expect(refresh).toHaveBeenCalledTimes(1); // straight away, not after another full wait
  });

  it("stops when the game ends", () => {
    const { rerender, container } = render(<LiveRefresh active seconds={15} />);
    rerender(<LiveRefresh active={false} seconds={15} />);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(refresh).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it("is a plain paragraph with a button, not a live region that would interrupt screen readers", async () => {
    vi.useRealTimers();
    const { container } = render(<LiveRefresh active />);
    expect(container.querySelector("[aria-live], [role='status'], [role='alert']")).toBeNull();
    await expectNoA11yViolations(<LiveRefresh active />);
  });
});

describe("anyLive", () => {
  const game = (state: GameInfo["state"]): GameInfo => ({
    state,
    date: "2026-10-18",
    opponent: "DEN",
    home: true,
  });

  it("is true when any list has a live game, ignoring gaps", () => {
    expect(anyLive([[game("final")], [undefined, null, game("live")]])).toBe(true);
  });

  it("is false for no games, finished games, upcoming games and byes", () => {
    expect(anyLive([])).toBe(false);
    expect(anyLive([[], [undefined, null]])).toBe(false);
    expect(anyLive([[game("final"), game("upcoming"), game("bye")]])).toBe(false);
  });
});
