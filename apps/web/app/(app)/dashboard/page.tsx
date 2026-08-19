"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ScrollText, Wrench } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  API_BASE_URL,
  fetchCurrentUser,
  fetchEscalations,
  fetchToolRequests,
  listPolicies,
  type CurrentUser,
  type Escalation,
  type PolicyListItem,
  type ToolRequest,
} from "@/lib/api";

function isGovern(user: CurrentUser | null): boolean {
  return !!user && (user.business_role === "govern" || ["admin", "super_admin"].includes(user.system_role));
}

// Same role set as tools.approve/tools.manage AND escalations.manage
// (govern/assure/admin) - one helper covers "can this user see the
// governance-work queue" across both.
function canApproveTools(user: CurrentUser | null): boolean {
  return (
    !!user && (["govern", "assure"].includes(user.business_role) || ["admin", "super_admin"].includes(user.system_role))
  );
}

const ESCALATION_STATUS_LABELS: Record<string, string> = { open: "Open", in_review: "In review", resolved: "Resolved" };

function isAssure(user: CurrentUser | null): boolean {
  return !!user && user.business_role === "assure";
}

function isOperator(user: CurrentUser | null): boolean {
  return !!user && user.business_role === "operator";
}

export default function DashboardPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [myPendingRequests, setMyPendingRequests] = useState<ToolRequest[]>([]);
  const [pendingApprovalRequests, setPendingApprovalRequests] = useState<ToolRequest[]>([]);
  const [myPolicyDrafts, setMyPolicyDrafts] = useState<PolicyListItem[]>([]);
  const [pendingPolicyDrafts, setPendingPolicyDrafts] = useState<PolicyListItem[]>([]);
  const [myAlerts, setMyAlerts] = useState<Escalation[]>([]);
  const [pendingAlerts, setPendingAlerts] = useState<Escalation[]>([]);

  useEffect(() => {
    fetchCurrentUser().then((u) => {
      setUser(u);
      if (!u) return;

      fetchToolRequests({ mine: true })
        .then((requests) => setMyPendingRequests(requests.filter((r) => r.status === "pending")))
        .catch(() => setMyPendingRequests([]));

      fetchEscalations({ mine: true })
        .then(setMyAlerts)
        .catch(() => setMyAlerts([]));

      if (canApproveTools(u)) {
        fetchToolRequests()
          .then(setPendingApprovalRequests)
          .catch(() => setPendingApprovalRequests([]));

        fetchEscalations()
          .then((alerts) => setPendingAlerts(alerts.filter((a) => a.status !== "resolved")))
          .catch(() => setPendingAlerts([]));
      }

      listPolicies()
        .then((policies) => {
          const awaitingApproval = policies.filter((p) => p.status === "draft" && p.has_document);
          if (isAssure(u)) {
            setMyPolicyDrafts(awaitingApproval.filter((p) => p.created_by === u.id));
          }
          if (isGovern(u)) {
            setPendingPolicyDrafts(awaitingApproval);
          }
        })
        .catch(() => {});
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

      {showPendingApproval && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Pending Your Approval</h2>
          {pendingApprovalRequests.length === 0 && pendingPolicyDrafts.length === 0 && pendingAlerts.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing pending approval.</p>
          ) : (
            <div className="space-y-2">
              {pendingPolicyDrafts.map((policy) => (
                <Link
                  key={policy.id}
                  href="/policy"
                  className="block rounded-xl border border-border bg-card p-3 text-sm hover:bg-muted"
                >
                  AI Policy draft awaiting approval
                  {policy.policy_owner_name ? ` — owned by ${policy.policy_owner_name}` : ""}
                </Link>
              ))}
              {pendingApprovalRequests.map((request) => (
                <Link
                  key={request.id}
                  href="/tools"
                  className="block rounded-xl border border-border bg-card p-3 text-sm hover:bg-muted"
                >
                  Tool request &quot;{request.name}&quot; awaiting approval
                </Link>
              ))}
              {pendingAlerts.map((alert) => (
                <Link
                  key={alert.id}
                  href="/escalations"
                  className="block rounded-xl border border-border bg-card p-3 text-sm hover:bg-muted"
                >
                  Alert needs addressing — {ESCALATION_STATUS_LABELS[alert.status]}: {alert.description}
                </Link>
              ))}
            </div>
          )}
        </section>
      )}

      {showMyPendingRequests && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Your Pending Requests</h2>
          {myPendingRequests.length === 0 && myPolicyDrafts.length === 0 ? (
            <p className="text-sm text-muted-foreground">You have no requests pending approval.</p>
          ) : (
            <div className="space-y-2">
              {myPolicyDrafts.map((policy) => (
                <Link
                  key={policy.id}
                  href="/policy"
                  className="block rounded-xl border border-border bg-card p-3 text-sm hover:bg-muted"
                >
                  Your AI Policy draft is awaiting approval
                </Link>
              ))}
              {myPendingRequests.map((request) => (
                <Link
                  key={request.id}
                  href="/tools"
                  className="block rounded-xl border border-border bg-card p-3 text-sm hover:bg-muted"
                >
                  Your request for &quot;{request.name}&quot; is pending approval
                </Link>
              ))}
            </div>
          )}
        </section>
      )}

      {myAlerts.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Your Alerts</h2>
          <div className="space-y-2">
            {myAlerts.map((alert) => (
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
