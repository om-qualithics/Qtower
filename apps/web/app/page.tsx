"use client";

import { useEffect, useState } from "react";
import { fetchHealth } from "@/lib/api";

export default function Home() {
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [dark, setDark] = useState(false);

  useEffect(() => {
    fetchHealth()
      .then((res) => setStatus(res.status === "ok" ? "ok" : "error"))
      .catch(() => setStatus("error"));
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
        <p className="mt-1 text-sm text-muted-foreground">
          AI governance hub &mdash; scaffold health check
        </p>

        <div className="mt-6 flex items-center gap-2 text-sm">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              status === "ok"
                ? "bg-accent"
                : status === "error"
                  ? "bg-destructive"
                  : "bg-muted-foreground"
            }`}
          />
          <span>
            API status:{" "}
            {status === "loading" ? "checking..." : status === "ok" ? "healthy" : "unreachable"}
          </span>
        </div>

        <button
          type="button"
          onClick={() => setDark((d) => !d)}
          className="mt-8 w-full rounded-lg border border-border bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition hover:bg-muted"
        >
          Toggle {dark ? "light" : "dark"} theme
        </button>
      </div>
    </main>
  );
}
