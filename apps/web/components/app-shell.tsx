"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ScrollText,
  Grid3x3,
  AlertTriangle,
  GraduationCap,
  Settings,
  LogOut,
  Moon,
  Sun,
} from "lucide-react";

import { cn } from "@/lib/utils";
import {
  API_BASE_URL,
  fetchBrandingConfig,
  fetchCurrentUser,
  fetchTrainingModules,
  type BrandingConfig,
  type CurrentUser,
} from "@/lib/api";
import { getStoredDark, setStoredDark } from "@/lib/theme";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, enabled: true },
  { label: "AI Policy", href: "/policy", icon: ScrollText, enabled: true },
  { label: "AI Tools", href: "/tools", icon: Grid3x3, enabled: true },
  { label: "Raise Alert", href: "/escalations", icon: AlertTriangle, enabled: true },
  { label: "Training", href: "/training", icon: GraduationCap, enabled: true },
  { label: "Settings", href: "/settings", icon: Settings, enabled: true },
];

// Settings currently only has branding/SSO sections (system admin only,
// see settings/page.tsx) - hidden entirely for anyone else, same "hide
// what has nothing to show" spirit as the dashboard's role-gated
// sections.
function canSeeSettings(user: CurrentUser | null): boolean {
  return !!user && ["admin", "super_admin"].includes(user.system_role);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<CurrentUser | null | "loading">("loading");
  const [branding, setBranding] = useState<BrandingConfig | null>(null);
  const [dark, setDark] = useState(false);
  const [trainingIncomplete, setTrainingIncomplete] = useState(false);

  useEffect(() => {
    const checkAuth = () =>
      fetchCurrentUser()
        .then((u) => {
          if (u === null) {
            router.replace("/");
          }
          setUser(u);
        })
        .catch(() => router.replace("/"));

    checkAuth();
    fetchBrandingConfig().then(setBranding);
    // Soft reminder for mandatory training (not a hard gate, see plan) - a
    // small nav dot whenever any module isn't completed yet.
    fetchTrainingModules()
      .then((modules) => setTrainingIncomplete(modules.some((m) => m.completion_status !== "completed")))
      .catch(() => setTrainingIncomplete(false));
    queueMicrotask(() => setDark(getStoredDark()));

    // Security fix: a browser Back navigation after Sign Out can restore
    // this page straight from bfcache - the whole React tree (including
    // this component's `user` state) comes back exactly as it was, with
    // no remount and no network request, so the mount effect above never
    // reruns and the stale "signed in" UI just sits there even though the
    // session cookie is gone server-side. `pageshow` with `persisted:
    // true` is the one event that reliably fires on a bfcache restore
    // (a plain re-mount effect does not) - re-checking auth there forces
    // a real fetchCurrentUser() call, which now 401s and redirects to "/"
    // instead of silently showing the previous user's data.
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) checkAuth();
    };
    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, [router]);

  const displayName = branding?.org_display_name || "Q Tower";
  const logoInitial = displayName.charAt(0).toUpperCase();

  if (user === "loading" || user === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="flex h-full w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-4 py-6">
        <div className="mb-8 flex items-center gap-3 px-2">
          {branding?.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={branding.logo_url} alt={displayName} className="h-9 w-9 rounded-lg object-cover" />
          ) : (
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sidebar-primary font-semibold text-sidebar-primary-foreground">
              {logoInitial}
            </div>
          )}
          <span className="font-semibold text-sidebar-foreground">{displayName}</span>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {NAV_ITEMS.filter((item) => item.label !== "Settings" || canSeeSettings(user)).map((item) => {
            const Icon = item.icon;
            const active = item.href !== null && pathname === item.href;
            if (!item.enabled || item.href === null) {
              return (
                <div
                  key={item.label}
                  className="flex cursor-not-allowed items-center justify-between rounded-lg px-3 py-2 text-sm text-muted-foreground/50"
                  title="Coming soon"
                >
                  <span className="flex items-center gap-2.5">
                    <Icon className="size-4" />
                    {item.label}
                  </span>
                </div>
              );
            }
            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent"
                )}
              >
                <Icon className="size-4" />
                {item.label}
                {item.label === "Training" && trainingIncomplete && (
                  <span
                    title="Mandatory training incomplete"
                    className="ml-auto size-1.5 shrink-0 rounded-full bg-destructive"
                  />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-sidebar-border pt-4">
          <div className="flex items-center gap-3 px-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
              {user.email.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-sidebar-foreground">{user.email}</p>
              <p className="truncate text-xs text-muted-foreground">{user.business_role}</p>
            </div>
          </div>

          <div className="mt-3 flex gap-2 px-2">
            <button
              type="button"
              onClick={() => {
                const next = !dark;
                setDark(next);
                setStoredDark(next);
              }}
              title={`Switch to ${dark ? "light" : "dark"} theme`}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
            >
              {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
            <form action={`${API_BASE_URL}/identity/logout`} method="post" className="flex-1">
              <button
                type="submit"
                className="flex h-8 w-full items-center justify-center gap-2 rounded-lg text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
              >
                <LogOut className="size-4" />
                Sign out
              </button>
            </form>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-8">{children}</main>
    </div>
  );
}
