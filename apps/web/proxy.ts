import { NextResponse } from "next/server";

// Renamed from middleware.ts/`middleware()` - Next.js 16 deprecated the
// "middleware" file convention in favor of "proxy" (the export function
// must now be named `proxy`, though the underlying mechanism is
// unchanged). See node_modules/next/dist/docs/.../file-conventions/proxy.md.
//
// Defense-in-depth alongside the pageshow/bfcache fix in app-shell.tsx:
// tells the browser never to disk-cache authenticated pages (or the
// login page, whose content also depends on session state) at all, so a
// Back navigation - or opening dev tools' "disable cache" off, or any
// other caching path - can't resurrect a signed-out user's page from an
// HTTP cache either, not just from bfcache. Restated (identically) in
// next.config.ts's headers() too - that turned out to be the header
// source that actually survives Next's own response pipeline in
// production; this file is kept for the matcher-scoped intent and as a
// second, redundant application of the same value (harmless - setting an
// identical header twice is a no-op for the browser).
export function proxy() {
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "no-store, must-revalidate");
  return response;
}

export const config = {
  matcher: ["/", "/dashboard/:path*", "/policy/:path*", "/tools/:path*", "/escalations/:path*", "/training/:path*", "/settings/:path*"],
};
