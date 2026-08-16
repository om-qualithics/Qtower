export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) {
    throw new Error(`API health check failed: ${res.status}`);
  }
  return res.json();
}

export type CurrentUser = {
  id: string;
  email: string;
  business_role: string;
  system_role: string;
};

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const res = await fetch(`${API_BASE_URL}/identity/me`, { credentials: "include" });
  if (res.status === 401) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch current user: ${res.status}`);
  }
  return res.json();
}

export function loginUrl(): string {
  return `${API_BASE_URL}/identity/login`;
}

export type BrandingConfig = {
  org_display_name: string | null;
  logo_url: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  enabled_feature_modules: string[] | null;
};

export async function fetchBrandingConfig(): Promise<BrandingConfig | null> {
  const res = await fetch(`${API_BASE_URL}/branding/config`);
  if (!res.ok) {
    return null;
  }
  return res.json();
}
