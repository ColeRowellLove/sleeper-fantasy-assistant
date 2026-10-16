import { describe, expect, it } from "vitest";

import { resolveApiUrl } from "../lib/apiUrl";

describe("resolveApiUrl", () => {
  it("always prefers an explicit API_URL", () => {
    expect(resolveApiUrl({ API_URL: "https://api.example.com", VERCEL_ENV: "preview" })).toBe(
      "https://api.example.com",
    );
    expect(resolveApiUrl({ API_URL: "https://api.example.com", VERCEL_ENV: "production" })).toBe(
      "https://api.example.com",
    );
  });

  it("sends previews to the develop API when nothing is configured", () => {
    expect(resolveApiUrl({ VERCEL_ENV: "preview" })).toBe(
      "https://api-git-develop-cole-b6ee.vercel.app",
    );
    expect(
      resolveApiUrl({ VERCEL_ENV: "preview", DEVELOP_API_URL: "https://dev.example.com" }),
    ).toBe("https://dev.example.com");
  });

  it("never points production at the develop API", () => {
    expect(resolveApiUrl({ VERCEL_ENV: "production" })).toBe("http://localhost:8000");
  });

  it("uses a local API for local development", () => {
    expect(resolveApiUrl({})).toBe("http://localhost:8000");
  });
});
