"use client";

import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { API_BASE_URL, fetchCurrentUser, type CurrentUser } from "@/lib/api";

export default function DashboardPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    fetchCurrentUser().then(setUser);
  }, []);

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-1 text-sm text-muted-foreground">Governance at a glance.</p>

      <div className="mt-6 rounded-2xl border border-border bg-card p-6">
        <p className="text-sm font-medium">{user?.email}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {user?.business_role} &middot; {user?.system_role}
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Button
            render={
              <a href="/policy">
                <ScrollText /> Go to AI Policy
              </a>
            }
            nativeButton={false}
          />
          <form action={`${API_BASE_URL}/identity/logout`} method="post">
            <Button type="submit" variant="outline">
              Sign out
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
