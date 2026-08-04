import type { NextConfig } from "next";

const BACKEND = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
const STATIC = process.env.STATIC_EXPORT === "1";

// Two shapes from one file:
//  - default (dev / `next start`): proxy /api to the FastAPI backend, redirect "/".
//  - STATIC_EXPORT=1: a fully static site for GitHub Pages under /Custodia, reading
//    baked JSON with no backend. redirects()/rewrites() are server features and are
//    intentionally omitted from the export config.
const nextConfig: NextConfig = STATIC
  ? {
      output: "export",
      basePath: "/Custodia",
      trailingSlash: true,
      images: { unoptimized: true },
      env: {
        NEXT_PUBLIC_STATIC: "1",
        NEXT_PUBLIC_BASE_PATH: "/Custodia",
      },
    }
  : {
      async redirects() {
        return [{ source: "/", destination: "/ar", permanent: false }];
      },
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
      },
    };

export default nextConfig;
