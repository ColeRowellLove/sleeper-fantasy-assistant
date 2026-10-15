"use client";

import { useSyncExternalStore } from "react";

import { THEME_KEY } from "../lib/theme";

export type Theme = "light" | "dark";

const EVENT = "sa-theme-change";

function subscribe(onChange: () => void): () => void {
  const media = window.matchMedia("(prefers-color-scheme: light)");
  // a choice made in another open tab arrives as a storage event; mirror it onto this page
  const onStorage = (event: StorageEvent) => {
    if (event.key !== THEME_KEY) return;
    if (event.newValue === "light" || event.newValue === "dark") {
      document.documentElement.dataset.theme = event.newValue;
    }
    onChange();
  };
  media.addEventListener("change", onChange);
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    media.removeEventListener("change", onChange);
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onStorage);
  };
}

/**
 * An explicit choice (data-theme) wins. Otherwise this mirrors the CSS: dark is the default and the
 * page only turns light when the device asks for light, so "no preference" counts as dark.
 */
function currentTheme(): Theme {
  const chosen = document.documentElement.dataset.theme;
  if (chosen === "light" || chosen === "dark") return chosen;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* storage can be blocked (private mode); the choice then lasts for this visit only */
  }
  window.dispatchEvent(new Event(EVENT));
}

/** Switches between light and dark. Follows the device until the visitor chooses. */
export default function ThemeToggle() {
  // server and first client render assume dark (the default theme); the real value follows
  const theme = useSyncExternalStore(subscribe, currentTheme, () => "dark" as Theme);
  const next: Theme = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => applyTheme(next)}
    >
      {theme === "dark" ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" strokeLinecap="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z" strokeLinejoin="round" />
        </svg>
      )}
    </button>
  );
}
