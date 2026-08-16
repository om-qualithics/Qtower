"use client";

import { useEffect } from "react";
import { fetchBrandingConfig } from "@/lib/api";

/**
 * Overrides the CSS custom properties defined in globals.css with
 * per-org branding, when set (handoff §2.4: branding is data, never
 * hardcoded in components). Fields left null in deployment_config fall
 * back to the Design/-derived defaults already in globals.css.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    fetchBrandingConfig().then((config) => {
      if (!config) return;
      const root = document.documentElement.style;
      if (config.primary_color) {
        root.setProperty("--primary", config.primary_color);
        root.setProperty("--ring", config.primary_color);
        root.setProperty("--sidebar-primary", config.primary_color);
        root.setProperty("--sidebar-ring", config.primary_color);
      }
      if (config.secondary_color) {
        root.setProperty("--accent", config.secondary_color);
      }
    });
  }, []);

  return <>{children}</>;
}
