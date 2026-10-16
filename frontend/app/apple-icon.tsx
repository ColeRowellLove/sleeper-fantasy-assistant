import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

const BARS = [
  { color: "#f472b6", height: 120 },
  { color: "#34d399", height: 94 },
  { color: "#60a5fa", height: 108 },
  { color: "#fb923c", height: 74 },
  { color: "#a78bfa", height: 90 },
  { color: "#d4a373", height: 60 },
];

// iOS applies its own rounded mask, so this one is a full-bleed square.
export default function AppleIcon() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        gap: 8,
        background: "#0e1120",
        paddingBottom: 30,
      }}
    >
      {BARS.map((bar) => (
        <div
          key={bar.color}
          style={{ width: 16, height: bar.height, background: bar.color, borderRadius: 3 }}
        />
      ))}
    </div>,
    { ...size },
  );
}
