"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL, fetchCurrentUser, loginUrl, type CurrentUser } from "@/lib/api";

export default function Home() {
  const [user, setUser] = useState<CurrentUser | null | "loading">("loading");
  const [dark, setDark] = useState(false);

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return (
    <main className="flex flex-1 items-center justify-center bg-background p-8">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 text-card-foreground shadow-sm">
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground font-semibold">
          M
        </div>
        <h1 className="text-xl font-semibold">Project Misty</h1>
        <p className="mt-1 text-sm text-muted-foreground">AI governance hub</p>

        {user === "loading" && (
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

        {user && user !== "loading" && (
          <div className="mt-8 space-y-4">
            <div>
              <p className="text-sm font-medium">{user.email}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {user.business_role} &middot; {user.system_role}
              </p>
            </div>
            <form action={`${API_BASE_URL}/identity/logout`} method="post">
              <button
                type="submit"
                className="w-full rounded-lg border border-border bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition hover:bg-muted"
              >
                Sign out
              </button>
            </form>
          </div>
        )}

        <button
          type="button"
          onClick={() => setDark((d) => !d)}
          className="mt-4 w-full rounded-lg border border-border px-4 py-2 text-xs text-muted-foreground transition hover:bg-muted"
        >
          Toggle {dark ? "light" : "dark"} theme
        </button>
      </div>
    </main>
  );
}
