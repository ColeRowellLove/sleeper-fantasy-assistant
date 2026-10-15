import Link from "next/link";
import type { ReactNode } from "react";
import { Archivo, Instrument_Sans } from "next/font/google";

import "./globals.css";

const display = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  variable: "--font-display-face",
  display: "swap",
});

const body = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-body-face",
  display: "swap",
});

// Absolute URL for share-card images. Vercel exposes the production domain at build time.
const host = process.env.VERCEL_PROJECT_PRODUCTION_URL ?? process.env.VERCEL_URL;
const siteUrl = host ? `https://${host}` : "http://localhost:3000";

const description = "Standings, rosters and weekly lineups for your Sleeper fantasy football league.";

export const metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "Sleeper Assistant", template: "%s | Sleeper Assistant" },
  description,
  robots: { index: false },
  openGraph: {
    type: "website",
    siteName: "Sleeper Assistant",
    title: "Sleeper Assistant",
    description,
  },
  twitter: {
    card: "summary_large_image",
    title: "Sleeper Assistant",
    description,
    images: ["/opengraph-image"],
  },
};

const MARK = ["qb", "rb", "wr", "te", "k", "def"];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <div className="container">
            <Link className="wordmark" href="/">
              <span className="mark" aria-hidden="true">
                {MARK.map((p) => (
                  <i key={p} className={`pos-${p}`} />
                ))}
              </span>
              Sleeper Assistant
            </Link>
            <nav className="site-nav" aria-label="Site">
              <a href="https://github.com/ColeRowellLove/sleeper-fantasy-assistant">Source</a>
            </nav>
          </div>
        </header>
        {children}
        <footer className="site-footer">
          <div className="container">
            <p>
              Unofficial, and not affiliated with Sleeper. League data comes from Sleeper&apos;s
              public API.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
