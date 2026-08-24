import type { NextConfig } from "next";

// Security headers as config-level rules (not just proxy.ts, formerly
// middleware.ts) - Next's header-merging for matched routes is the
// reliable place to set these; proxy.ts's Cache-Control write was
// observed not reaching the browser in dev (Next's dev server
// deliberately overrides it - see node_modules/next/dist/server/
// base-server.js's `if (this.dev)` branch - a DX feature for smooth
// back/forward during development, confirmed not to happen in a
// production build), so it's restated here as the primary source of
// truth for both cache and framing/MIME/CSP protections.
const apiOrigin = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const isDev = process.env.NODE_ENV === "development";

// Non-nonce CSP (Next's own documented "Without Nonces" pattern - see
// node_modules/next/dist/docs/.../content-security-policy.md). A
// nonce-based strict CSP was considered and deliberately not used: it
// requires forcing every page into dynamic (per-request) rendering to
// receive a fresh nonce, which throws away this app's existing static
// page optimization for no real benefit here - this is a self-hosted,
// authenticated internal tool with Cache-Control: no-store already
// forcing revalidation on every load, not a CDN-cached public site.
// 'unsafe-inline' on script/style is the deliberate cost of that
// trade-off; everything else below (object-src, base-uri, frame-ancestors,
// the explicit connect-src/form-action allowlist) still meaningfully
// restricts what a successful injection could do.
//
// - connect-src/form-action must include the API origin, not just
//   'self': every data fetch (apps/web/lib/api.ts) and the sidebar/
//   dashboard sign-out forms (`<form action={API_BASE_URL}/identity/logout}>`
//   in app-shell.tsx and dashboard/page.tsx) target the backend directly,
//   which is a different origin in dev (port 8000 vs 3000) and may be a
//   different host entirely in a real deployment.
// - img-src allows any https: source (plus data:/blob:) because
//   deployment_config.logo_url (Settings -> Branding) is an admin-pasted
//   arbitrary URL by design (Milestone 3) - there's no fixed logo host to
//   allowlist.
const cspDirectives = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin}`,
  `form-action 'self' ${apiOrigin}`,
  "object-src 'none'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
];

const securityHeaders = [
  { key: "Cache-Control", value: "no-store, must-revalidate" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Content-Security-Policy", value: cspDirectives.join("; ") },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
