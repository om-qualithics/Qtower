"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ScrollText, Wrench } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  API_BASE_URL,
  fetchCurrentUser,
  fetchDashboardSummary,
  type CurrentUser,
  type DashboardSummary,
} from "@/lib/api";

function isGovern(user: CurrentUser | null): boolean {
  return !!user && (user.business_role === "govern" || ["admin", "super_admin"].includes(user.system_role));
}

// Same role set as tools.approve/tools.manage AND escalations.manage
// (govern/assure/admin) - one helper covers "can this user see the
// governance-work queue" across both. The server applies the same
// predicate when building the DashboardSummary, so this is purely a
// client-side convenience over data that's already role-filtered.
function canApproveTools(user: CurrentUser | null): boolean {
  return (
    !!user && (["govern", "assure"].includes(user.business_role) || ["admin", "super_admin"].includes(user.system_role))
  );
}

const ESCALATION_STATUS_LABELS: Record<string, string> = { open: "Open", in_review: "In review", resolved: "Resolved" };
const TOOL_REQUEST_STATUS_LABELS: Record<string, string> = { pending: "Pending", approved: "Approved", rejected: "Rejected" };

function isOperator(user: CurrentUser | null): boolean {
  return !!user && user.business_role === "operator";
}

type NotificationCategory = "policy" | "tool" | "alert";

// Distinct background tint per category, reusing the existing theme
// tokens (no new colors) - purple/gold/red already carry these meanings
// elsewhere in the app (primary accent, active-nav gold, destructive red).
const CATEGORY_STYLES: Record<NotificationCategory, { label: string; className: string }> = {
  policy: { label: "Policy", className: "bg-primary/10 text-primary" },
  tool: { label: "Tool", className: "bg-accent/15 text-accent" },
  alert: { label: "Alert", className: "bg-destructive/10 text-destructive" },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function NotificationCard({
  category,
  title,
  subtitle,
  date,
  href,
}: {
  category: NotificationCategory;
  title: string;
  subtitle?: string;
  date: string;
  href: string;
}) {
  const style = CATEGORY_STYLES[category];
  return (
    <Link
      href={href}
      className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-card p-3.5 text-sm hover:bg-muted"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-medium ${style.className}`}>{style.label}</span>
          <span className="truncate font-medium">{title}</span>
        </div>
        {subtitle && <p className="mt-1 truncate text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      <span className="shrink-0 text-xs text-muted-foreground">{formatDate(date)}</span>
    </Link>
  );
}

function CountBars({ counts, labels }: { counts: Record<string, number>; labels: Record<string, string> }) {
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  return (
    <div className="space-y-2.5">
      {Object.entries(labels).map(([key, label]) => {
        const count = counts[key] ?? 0;
        const pct = total ? (count / total) * 100 : 0;
        return (
          <div key={key}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span>{label}</span>
              <span className="text-muted-foreground">{count}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    fetchCurrentUser().then((u) => {
      setUser(u);
      if (!u) return;
      fetchDashboardSummary()
        .then(setSummary)
        .catch(() => setSummary(null));
    });
  }, []);

  const showPendingApproval = canApproveTools(user) && !isOperator(user);
  const showMyPendingRequests = !isGovern(user) || isOperator(user);

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
          <Button
            variant="outline"
            render={
              <a href="/tools">
                <Wrench /> Go to AI Tools
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

      {showPendingApproval && summary?.training_summary && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Overview</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-border bg-card p-4">
              <p className="mb-3 text-xs font-medium text-muted-foreground">Tool Requests</p>
              <CountBars counts={summary.tool_request_counts} labels={TOOL_REQUEST_STATUS_LABELS} />
            </div>
            <div className="rounded-2xl border border-border bg-card p-4">
              <p className="mb-3 text-xs font-medium text-muted-foreground">Escalations</p>
              <CountBars counts={summary.escalation_counts} labels={ESCALATION_STATUS_LABELS} />
            </div>
            <div className="rounded-2xl border border-border bg-card p-4">
              <p className="mb-1 text-xs font-medium text-muted-foreground">Training Completion</p>
              <p className="mb-3 text-sm">
                <span className="font-medium">{summary.training_summary.org_completion_pct}%</span> overall
              </p>
              <div className="space-y-2.5">
                {summary.training_summary.modules.map((m) => (
                  <div key={m.module_id}>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="truncate pr-2">{m.title}</span>
                      <span className="shrink-0 text-muted-foreground">
                        {m.completed_count}/{m.total_users}
                      </span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${Math.min(m.completion_pct, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {showPendingApproval && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Pending Your Approval</h2>
          {!summary ||
          (summary.pending_tool_requests.length === 0 &&
            summary.pending_policy_drafts.length === 0 &&
            summary.pending_alerts.length === 0) ? (
            <p className="text-sm text-muted-foreground">Nothing pending approval.</p>
          ) : (
            <div className="space-y-2">
              {summary.pending_policy_drafts.map((policy) => (
                <NotificationCard
                  key={policy.id}
                  category="policy"
                  title="AI Policy draft awaiting approval"
                  subtitle={policy.policy_owner_name ? `Owned by ${policy.policy_owner_name}` : undefined}
                  date={policy.created_at}
                  href="/policy"
                />
              ))}
              {summary.pending_tool_requests.map((request) => (
                <NotificationCard
                  key={request.id}
                  category="tool"
                  title={`"${request.name}" awaiting approval`}
                  date={request.created_at}
                  href="/tools"
                />
              ))}
              {summary.pending_alerts.map((alert) => (
                <NotificationCard
                  key={alert.id}
                  category="alert"
                  title={alert.description}
                  subtitle={ESCALATION_STATUS_LABELS[alert.status]}
                  date={alert.created_at}
                  href="/escalations"
                />
              ))}
            </div>
          )}
        </section>
      )}

      {showMyPendingRequests && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Your Pending Requests</h2>
          {!summary || (summary.my_tool_requests.length === 0 && summary.my_policy_drafts.length === 0) ? (
            <p className="text-sm text-muted-foreground">You have no requests pending approval.</p>
          ) : (
            <div className="space-y-2">
              {summary.my_policy_drafts.map((policy) => (
                <NotificationCard
                  key={policy.id}
                  category="policy"
                  title="Your AI Policy draft is awaiting approval"
                  date={policy.created_at}
                  href="/policy"
                />
              ))}
              {summary.my_tool_requests.map((request) => (
                <NotificationCard
                  key={request.id}
                  category="tool"
                  title={`Your request for "${request.name}" is pending approval`}
                  date={request.created_at}
                  href="/tools"
                />
              ))}
            </div>
          )}
        </section>
      )}

      {summary && summary.my_training.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Your Training</h2>
          <Link
            href="/training"
            className="block rounded-xl border border-border bg-card p-3 text-sm hover:bg-muted"
          >
            {summary.my_training.filter((m) => m.completion_status === "completed").length} of{" "}
            {summary.my_training.length} modules completed
          </Link>
        </section>
      )}

      {summary && summary.my_alerts.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Your Alerts</h2>
          <div className="space-y-2">
            {summary.my_alerts.map((alert) => (
              <Link
                key={alert.id}
                href="/escalations"
                className="block rounded-xl border border-border bg-card p-3 text-sm hover:bg-muted"
              >
                <span className="font-medium">{ESCALATION_STATUS_LABELS[alert.status]}</span> — {alert.description}
                {alert.status === "resolved" && alert.resolution_note && (
                  <p className="mt-1 text-xs text-muted-foreground">Resolution: {alert.resolution_note}</p>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
