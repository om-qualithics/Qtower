"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  fetchBrandingConfig,
  fetchCurrentUser,
  loginUrl,
  superAdminLogin,
  type PublicBrandingConfig,
  type CurrentUser,
} from "@/lib/api";
import { getStoredDark, setStoredDark } from "@/lib/theme";
import { ParticleBackground } from "@/components/particle-background";
import { Moon, Sun } from "lucide-react";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null | "loading">("loading");
  const [branding, setBranding] = useState<PublicBrandingConfig | null>(null);
  const [dark, setDark] = useState(false);
  const [showAdminLogin, setShowAdminLogin] = useState(false);
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminError, setAdminError] = useState<string | null>(null);
  const [adminSubmitting, setAdminSubmitting] = useState(false);

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
  const hasCustomLogo = Boolean(branding?.logo_url);

  return (
    <main className="relative flex flex-1 items-center justify-center overflow-hidden bg-background p-8">
      <ParticleBackground dark={dark} />
      {/*
        Desktop-only fluid sizing - this app is never opened on mobile, so
        there's no small-screen tier here. Every dimension below is a
        clamp(min, viewport-scaled, max) instead of Tailwind's stepped
        breakpoint variants (lg:/xl:/2xl:/...): the card needs to keep
        growing smoothly from a laptop screen up through a 27-32" external
        monitor (commonly 2560px-wide QHD, or 4K scaled to ~2560 logical
        px), and Tailwind v4's custom-breakpoint media queries turned out
        not to sort by width the way named ones do - a wider custom tier's
        rule can lose the cascade to the built-in 2xl rule even though
        both matched (see aboutproject.md). clamp() sidesteps that whole
        class of bug: one utility class, no @media ordering to get wrong,
        and it scales continuously rather than in visible steps.
      */}
      <div className="relative z-10 rounded-2xl border border-border bg-card text-card-foreground shadow-lg w-[clamp(20rem,8rem+17vw,40rem)] p-[clamp(1.25rem,0.5rem+1.1vw,2.5rem)]">
        <div className="flex flex-col items-center text-center">
          {hasCustomLogo ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={branding!.logo_url!}
                alt={displayName}
                className="mb-2 rounded-xl object-cover h-[clamp(3.75rem,1.5rem+3vw,6rem)] w-[clamp(3.75rem,1.5rem+3vw,6rem)]"
              />
              <h1 className="font-semibold text-[clamp(1.125rem,0.9rem+0.4vw,1.5rem)]">{displayName}</h1>
            </>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src="/logo/qtower.svg"
              alt={displayName}
              className="mb-2 rounded-2xl object-contain h-[clamp(5.25rem,2.25rem+4.5vw,12rem)] w-[clamp(5.25rem,2.25rem+4.5vw,12rem)]"
            />
          )}
          <p className="mt-1 text-muted-foreground text-[clamp(0.75rem,0.6rem+0.4vw,1.125rem)]">
            Your AI governance hub
          </p>
        </div>

        {(user === "loading") && (
          <p className="mt-6 text-center text-muted-foreground text-[clamp(0.875rem,0.75rem+0.35vw,1.125rem)]">
            Checking session...
          </p>
        )}

        {user === null && (
          <>
            <a
              href={loginUrl()}
              className="mt-6 block w-full rounded-lg bg-primary text-center font-medium text-primary-foreground transition hover:opacity-90 py-[clamp(0.5rem,0.3rem+0.6vw,0.875rem)] text-[clamp(0.875rem,0.75rem+0.35vw,1.125rem)]"
            >
              Sign in
            </a>

            {!showAdminLogin ? (
              <button
                type="button"
                onClick={() => setShowAdminLogin(true)}
                className="mt-3 w-full text-center text-muted-foreground underline-offset-2 hover:underline text-[clamp(0.75rem,0.65rem+0.25vw,1rem)]"
              >
                Sign in with admin credentials
              </button>
            ) : (
              <div className="mt-3 space-y-2 rounded-lg border border-border p-3">
                <input
                  type="email"
                  placeholder="Email"
                  value={adminEmail}
                  onChange={(e) => setAdminEmail(e.target.value)}
                  className="h-8 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring"
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  className="h-8 w-full rounded-md border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring"
                />
                {adminError && <p className="text-xs text-destructive">{adminError}</p>}
                <button
                  type="button"
                  disabled={adminSubmitting || !adminEmail.trim() || !adminPassword}
                  onClick={async () => {
                    setAdminSubmitting(true);
                    setAdminError(null);
                    try {
                      await superAdminLogin(adminEmail.trim(), adminPassword);
                      router.replace("/dashboard");
                    } catch (err) {
                      setAdminError(err instanceof Error ? err.message : "Sign-in failed.");
                    } finally {
                      setAdminSubmitting(false);
                    }
                  }}
                  className="h-8 w-full rounded-md bg-primary text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
                >
                  Sign in
                </button>
              </div>
            )}
          </>
        )}

        <div className="mt-6 flex items-center justify-between rounded-lg border border-border px-4 py-[clamp(0.75rem,0.6rem+0.4vw,1.25rem)]">
          <span className="flex items-center gap-2 text-muted-foreground text-[clamp(0.875rem,0.75rem+0.35vw,1.125rem)]">
            {dark ? <Moon className="size-4" /> : <Sun className="size-4" />}
            {dark ? "Dark theme" : "Light theme"}
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={dark}
            aria-label="Toggle dark theme"
            onClick={() => {
              const next = !dark;
              setDark(next);
              setStoredDark(next);
            }}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
              dark ? "bg-primary" : "bg-muted"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                dark ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </div>
    </main>
  );
}
