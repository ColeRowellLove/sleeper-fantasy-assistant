import type { NextConfig } from "next";

import { resolveApiUrl } from "./lib/apiUrl";

// The browser only talks to this origin; Next proxies /api/* to the backend (no CORS needed).
const API_URL = resolveApiUrl();

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
