"use client";

import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export interface PanelTab {
  key: string;
  label: string;
  content: ReactNode;
}

/**
 * Tabs that swap a panel in place (the player pop-up's Summary, Game log, Team, History), with an
 * underline under the open one. Arrow keys, Home and End move between tabs; only the open panel is
 * rendered, so a closed tab costs nothing.
 */
export default function PanelTabs({ label, tabs }: { label: string; tabs: PanelTab[] }) {
  const [active, setActive] = useState(tabs[0]?.key ?? "");
  const id = useId();
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({});

  const move = (event: KeyboardEvent, index: number) => {
    const last = tabs.length - 1;
    const next =
      event.key === "ArrowRight"
        ? (index + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (next === null) return;
    event.preventDefault();
    setActive(tabs[next].key);
    buttons.current[tabs[next].key]?.focus();
  };

  const open = tabs.find((t) => t.key === active) ?? tabs[0];
  return (
    <div className="panel-tabs">
      <div role="tablist" aria-label={label} className="panel-tablist">
        {tabs.map((tab, index) => (
          <button
            key={tab.key}
            ref={(el) => {
              buttons.current[tab.key] = el;
            }}
            type="button"
            role="tab"
            id={`${id}-tab-${tab.key}`}
            aria-selected={tab.key === open.key}
            aria-controls={tab.key === open.key ? `${id}-panel-${tab.key}` : undefined}
            tabIndex={tab.key === open.key ? 0 : -1}
            className="panel-tab"
            onClick={() => setActive(tab.key)}
            onKeyDown={(event) => move(event, index)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`${id}-panel-${open.key}`}
        aria-labelledby={`${id}-tab-${open.key}`}
        className="panel-tabpanel"
        tabIndex={0}
      >
        {open.content}
      </div>
    </div>
  );
}
