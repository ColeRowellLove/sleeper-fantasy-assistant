import type { ReactNode } from "react";

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
