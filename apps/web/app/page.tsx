"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  fetchBrandingConfig,
  fetchCurrentUser,
  loginUrl,
  type BrandingConfig,
  type CurrentUser,
} from "@/lib/api";
import { getStoredDark, setStoredDark } from "@/lib/theme";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null | "loading">("loading");
  const [branding, setBranding] = useState<BrandingConfig | null>(null);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    fetchCurrentUser()
      .then((u) => {
        if (u) {
          router.replace("/dashboard");
          return;
        }
        setUser(u);
      })
      .catch(() => setUser(null));
    fetchBrandingConfig().then(setBranding);
    queueMicrotask(() => setDark(getStoredDark()));
  }, [router]);

  const displayName = branding?.org_display_name || "Q Tower";
  const logoInitial = displayName.charAt(0).toUpperCase();

  return (
    <main className="flex flex-1 items-center justify-center bg-background p-8">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 text-card-foreground shadow-sm">
        {branding?.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={branding.logo_url}
            alt={displayName}
            className="mb-6 h-12 w-12 rounded-xl object-cover"
          />
        ) : (
          <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground font-semibold">
            {logoInitial}
          </div>
        )}
        <h1 className="text-xl font-semibold">{displayName}</h1>
        <p className="mt-1 text-sm text-muted-foreground">AI governance hub</p>

        {(user === "loading") && (
          <p className="mt-8 text-sm text-muted-foreground">Checking session...</p>
        )}

        {user === null && (
          <a
            href={loginUrl()}
            className="mt-8 block w-full rounded-lg bg-primary px-4 py-2 text-center text-sm font-medium text-primary-foreground transition hover:opacity-90"
          >
            Sign in
          </a>
        )}

        <button
          type="button"
          onClick={() => {
            const next = !dark;
            setDark(next);
            setStoredDark(next);
          }}
          className="mt-4 w-full rounded-lg border border-border px-4 py-2 text-xs text-muted-foreground transition hover:bg-muted"
        >
          Toggle {dark ? "light" : "dark"} theme
        </button>
      </div>
    </main>
  );
}
