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
} from "lucide-react";

import { cn } from "@/lib/utils";
import {
  fetchBrandingConfig,
  fetchCurrentUser,
  type BrandingConfig,
  type CurrentUser,
} from "@/lib/api";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, enabled: true },
  { label: "AI Policy", href: "/policy", icon: ScrollText, enabled: true },
  { label: "AI Tools", href: null, icon: Grid3x3, enabled: false },
  { label: "Raise Alert", href: null, icon: AlertTriangle, enabled: false },
  { label: "Training", href: null, icon: GraduationCap, enabled: false },
  { label: "Settings", href: null, icon: Settings, enabled: false },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<CurrentUser | null | "loading">("loading");
  const [branding, setBranding] = useState<BrandingConfig | null>(null);

  useEffect(() => {
    fetchCurrentUser()
      .then((u) => {
        if (u === null) {
          router.replace("/");
        }
        setUser(u);
      })
      .catch(() => router.replace("/"));
    fetchBrandingConfig().then(setBranding);
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
          {NAV_ITEMS.map((item) => {
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
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 border-t border-sidebar-border px-2 pt-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
            {user.email.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-sidebar-foreground">{user.email}</p>
            <p className="truncate text-xs text-muted-foreground">{user.business_role}</p>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-8">{children}</main>
    </div>
  );
}
