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
          <>
            <a
              href={loginUrl()}
              className="mt-8 block w-full rounded-lg bg-primary px-4 py-2 text-center text-sm font-medium text-primary-foreground transition hover:opacity-90"
            >
              Sign in
            </a>

            {!showAdminLogin ? (
              <button
                type="button"
                onClick={() => setShowAdminLogin(true)}
                className="mt-3 w-full text-center text-xs text-muted-foreground underline-offset-2 hover:underline"
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
