import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TeamAvatar from "../components/TeamAvatar";
import { teamPictureUrl } from "../lib/images";

describe("teamPictureUrl", () => {
  it("allows Sleeper's own hosts over https only", () => {
    expect(teamPictureUrl("https://sleepercdn.com/avatars/thumbs/abc")).toBe(
      "https://sleepercdn.com/avatars/thumbs/abc",
    );
    expect(teamPictureUrl("http://sleepercdn.com/a")).toBeNull();
    expect(teamPictureUrl("https://evil.example/sleepercdn.com")).toBeNull();
    expect(teamPictureUrl("https://sleepercdn.com.evil.example/a")).toBeNull();
    expect(teamPictureUrl("not a url")).toBeNull();
    expect(teamPictureUrl(null)).toBeNull();
  });
});

describe("TeamAvatar", () => {
  it("shows initials when the team has no picture", () => {
    const { container } = render(<TeamAvatar rosterId={1} name="Taco Tuesday" />);
    expect(container.querySelector("img")).toBeNull();
    expect(container).toHaveTextContent("TT");
  });

  it("shows the picture, and falls back to initials if it fails to load", () => {
    const { container } = render(
      <TeamAvatar
        rosterId={1}
        name="Taco Tuesday"
        picture="https://sleepercdn.com/avatars/thumbs/abc"
      />,
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("alt", "");
    fireEvent.error(img as HTMLImageElement);
    expect(container.querySelector("img")).toBeNull();
    expect(container).toHaveTextContent("TT");
  });

  it("ignores a picture from another host", () => {
    const { container } = render(
      <TeamAvatar rosterId={2} name="Dad Bods" picture="https://evil.example/x.png" />,
    );
    expect(container.querySelector("img")).toBeNull();
  });
});
