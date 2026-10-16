import { ImageResponse } from "next/og";

export const size = { width: 64, height: 64 };
export const contentType = "image/png";

// The six position colors as bars: the same mark as the site header.
const BARS = [
  { color: "#f472b6", height: 44 },
  { color: "#34d399", height: 34 },
  { color: "#60a5fa", height: 40 },
  { color: "#fb923c", height: 27 },
  { color: "#a78bfa", height: 33 },
  { color: "#d4a373", height: 22 },
];

export default function Icon() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        gap: 3,
        background: "#0e1120",
        borderRadius: 14,
        paddingBottom: 10,
      }}
    >
      {BARS.map((bar) => (
        <div
          key={bar.color}
          style={{ width: 6, height: bar.height, background: bar.color, borderRadius: 1 }}
        />
      ))}
    </div>,
    { ...size },
  );
}
