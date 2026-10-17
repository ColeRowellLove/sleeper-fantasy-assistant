import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LocalTime from "../components/LocalTime";
import { localDateTime, localTime, utcDateTime } from "../lib/time";

const ISO = "2026-10-17T16:05:00Z";

describe("time helpers", () => {
  it("writes UTC the same way everywhere, for the server", () => {
    expect(utcDateTime(ISO)).toBe("Sat, Oct 17, 4:05 PM UTC");
    expect(utcDateTime("nonsense")).toBe("");
    expect(utcDateTime(null)).toBe("");
  });

  it("writes the viewer's own zone with its name, and the time of day alone", () => {
    const local = localDateTime(ISO);
    expect(local).toMatch(/Oct 17/);
    expect(local).toMatch(/\d{1,2}:05/);
    expect(local).toMatch(/[A-Z]{2,5}|GMT[+-]\d+|UTC/); // the zone is named
    expect(localTime(ISO)).toMatch(/^\d{1,2}:05/);
    expect(localDateTime("nonsense")).toBe("");
    expect(localTime(undefined)).toBe("");
  });
});

describe("LocalTime", () => {
  it("shows the moment in the viewer's zone and keeps the machine-readable time", () => {
    render(<LocalTime iso={ISO} />);
    const el = screen.getByText(/Oct 17/);
    expect(el.tagName).toBe("TIME");
    expect(el).toHaveAttribute("datetime", ISO);
    expect(el.textContent).toBe(localDateTime(ISO));
  });

  it("renders nothing for a time it cannot read", () => {
    const { container } = render(<LocalTime iso="nonsense" />);
    expect(container).toBeEmptyDOMElement();
  });
});
