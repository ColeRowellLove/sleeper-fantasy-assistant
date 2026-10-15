import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "Sleeper Fantasy Assistant",
  robots: { index: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
