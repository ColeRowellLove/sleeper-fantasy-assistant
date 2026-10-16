import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ThemeToggle from "../components/ThemeToggle";
import { THEME_INIT, THEME_KEY } from "../lib/theme";
import { expectNoA11yViolations } from "./a11y";

/** "light" and "dark" device settings, or "none" (no preference, which the CSS treats as dark). */
function mockDevice(setting: "light" | "dark" | "none") {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("light")
        ? setting === "light"
        : query.includes("dark")
          ? setting === "dark"
          : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

beforeEach(() => {
  delete document.documentElement.dataset.theme;
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks(); // undo the blocked-storage spies so tests cannot leak into each other
});

describe("ThemeToggle", () => {
  it("has no accessibility violations and an icon-only button with a clear name", async () => {
    mockDevice("dark");
    await expectNoA11yViolations(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();
  });

  it("treats a device with no preference as dark, matching the CSS default", () => {
    mockDevice("none");
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();
  });

  it("follows the device until the visitor chooses", () => {
    mockDevice("light");
    render(<ThemeToggle />);
    // the device prefers light, so the button offers dark and nothing is forced on the page
    expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("switches the page theme, remembers the choice and updates its own label", async () => {
    mockDevice("dark");
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(screen.getByRole("button", { name: "Switch to light theme" }));

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Switch to dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
  });

  it("an explicit choice beats the device setting", () => {
    mockDevice("dark");
    document.documentElement.dataset.theme = "light";
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();
  });

  it("follows a choice made in another tab", () => {
    mockDevice("dark");
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY, newValue: "light" }));
    });

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeInTheDocument();
  });

  it("ignores storage events for other keys", () => {
    mockDevice("dark");
    render(<ThemeToggle />);
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: "other", newValue: "light" }));
    });
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("still switches when storage is blocked", async () => {
    mockDevice("dark");
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Switch to light theme" }));
    });

    expect(document.documentElement.dataset.theme).toBe("light");
  });
});

describe("pre-paint theme script", () => {
  const run = () => new Function(THEME_INIT)();

  it("uses the real storage key (an undefined key once shipped here by mistake)", () => {
    expect(THEME_KEY).toBe("sa_theme");
    expect(THEME_INIT).toContain('"sa_theme"');
    expect(THEME_INIT).not.toContain("undefined");
  });

  it("applies a saved light or dark choice before the app loads", () => {
    localStorage.setItem(THEME_KEY, "light");
    run();
    expect(document.documentElement.dataset.theme).toBe("light");

    localStorage.setItem(THEME_KEY, "dark");
    run();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("ignores missing or unexpected values and never throws", () => {
    run();
    expect(document.documentElement.dataset.theme).toBeUndefined();

    localStorage.setItem(THEME_KEY, "<script>alert(1)</script>");
    run();
    expect(document.documentElement.dataset.theme).toBeUndefined();

    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(run).not.toThrow();
  });
});
