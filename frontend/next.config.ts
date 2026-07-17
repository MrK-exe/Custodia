import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async redirects() {
    // The product is Arabic-first, so "/" is not a page, it is a decision.
    return [{ source: "/", destination: "/ar", permanent: false }];
  },
  async rewrites() {
    // Same-origin proxy to FastAPI: no CORS preflight, no mixed-origin cookies,
    // and the browser never needs to know the backend's port.
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};

export default nextConfig;
