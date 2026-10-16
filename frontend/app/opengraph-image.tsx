import { ImageResponse } from "next/og";

export const alt = "Sleeper Assistant: every lineup in your league, side by side";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Position colors (dark theme values), the same hues the site uses for QB, RB, WR, TE, K, DEF.
const BARS = [
  { color: "#f472b6", height: 150 },
  { color: "#34d399", height: 117 },
  { color: "#60a5fa", height: 135 },
  { color: "#fb923c", height: 93 },
  { color: "#a78bfa", height: 111 },
  { color: "#d4a373", height: 75 },
];

export default function Image() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: "#0e1120",
        color: "#eef0f8",
        padding: 80,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 150 }}>
        {BARS.map((bar) => (
          <div
            key={bar.color}
            style={{ width: 26, height: bar.height, background: bar.color, borderRadius: 3 }}
          />
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ fontSize: 84, fontWeight: 800, lineHeight: 1.05, letterSpacing: -2 }}>
          Every lineup in your league, side by side.
        </div>
        <div style={{ fontSize: 34, color: "#9aa1c0", marginTop: 28 }}>
          Sleeper Assistant: standings, rosters and weekly matchups
        </div>
      </div>
    </div>,
    { ...size },
  );
}
