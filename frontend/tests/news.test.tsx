import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FavouriteProvider } from "../components/FavouriteProvider";
import NewsPanel from "../components/NewsPanel";
import type { NewsData, NewsItem } from "../lib/api";
import { filterNews, newsFlags, sortNews, sourceNote, topicLabels } from "../lib/news";
import { expectNoA11yViolations } from "./a11y";

const item = (over: Partial<NewsItem>): NewsItem => ({
  id: "1",
  source: "ESPN",
  title: "Headline",
  link: "https://example.com/a",
  published_at: "2026-10-17T14:05:00Z",
  players: [],
  teams: [],
  topics: [],
  roster_ids: [],
  ...over,
});

const data: NewsData = {
  sources: ["CBS Sports", "ESPN"],
  items: [
    item({ id: "a", title: "League wide note" }),
    item({
      id: "b",
      title: "Daniels questionable",
      source: "CBS Sports",
      topics: ["injury"],
      teams: ["WAS"],
      roster_ids: [2],
    }),
    item({ id: "c", title: "Eagles news", teams: ["PHI"] }),
  ],
};

describe("news helpers", () => {
  it("says why a headline matters to the viewer", () => {
    const b = data.items[1];
    expect(newsFlags(b, 2, null)).toEqual({ mine: true, favourite: false });
    expect(newsFlags(b, null, "WAS")).toEqual({ mine: false, favourite: true });
  });

  it("lists your headlines first, then your team's, keeping the newest-first order", () => {
    const order = sortNews(data.items, 2, "PHI").map((i) => i.id);
    expect(order).toEqual(["b", "c", "a"]);
  });

  it("words topics and sources", () => {
    expect(topicLabels(["injury", "nope", "trade"])).toEqual(["Injury", "Trade"]);
    expect(sourceNote(["ESPN", "CBS Sports"])).toBe("From ESPN and CBS Sports");
    expect(sourceNote([])).toBe("");
  });
});

describe("NewsPanel", () => {
  it("links every headline to its source and labels it", async () => {
    const ui = (
      <FavouriteProvider favourite="PHI">
        <NewsPanel data={data} myRosterId={2} />
      </FavouriteProvider>
    );
    render(ui);
    const list = screen.getByRole("list", { name: "Latest headlines" });
    const first = within(list).getAllByRole("listitem")[0];
    const link = within(first).getByRole("link", { name: /Daniels questionable/ });
    expect(link).toHaveAttribute("href", "https://example.com/a");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    expect(within(first).getByText("CBS Sports")).toBeInTheDocument();
    expect(within(first).getByText(/Your player/)).toBeInTheDocument();
    expect(within(first).getByText("Injury")).toBeInTheDocument();
    expect(screen.getByText(/Your favourite team/)).toBeInTheDocument();
    cleanup();
    await expectNoA11yViolations(ui);
  });

  it("says so when there is no news yet", () => {
    render(<NewsPanel data={{ items: [], sources: [] }} myRosterId={null} />);
    expect(screen.getByText(/No headlines have been collected/)).toBeInTheDocument();
  });
});

describe("news filters", () => {
  it("keeps only headlines about your players or your favourite team", () => {
    expect(filterNews(data.items, "all", 2, "PHI")).toHaveLength(3);
    expect(filterNews(data.items, "mine", 2, "PHI").map((i) => i.id)).toEqual(["b"]);
    expect(filterNews(data.items, "favourite", 2, "PHI").map((i) => i.id)).toEqual(["c"]);
    expect(filterNews(data.items, "mine", null, null)).toEqual([]);
  });

  it("buttons switch the list and say what is missing", async () => {
    const user = userEvent.setup();
    render(
      <FavouriteProvider favourite={null}>
        <NewsPanel data={data} myRosterId={2} />
      </FavouriteProvider>,
    );
    await user.click(screen.getByRole("button", { name: "My players" }));
    expect(screen.getByRole("button", { name: "My players" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getAllByRole("listitem").some((li) => li.textContent?.includes("Daniels"))).toBe(
      true,
    );
    expect(screen.queryByText("Eagles news")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Favourite team" }));
    expect(screen.getByRole("status")).toHaveTextContent("Pick a favourite NFL team");
  });
});
