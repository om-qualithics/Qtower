"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, CheckCircle2, AlertTriangle, XCircle, HelpCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { TIER_LABELS } from "@/lib/tiers";
import {
  approveProjectRequest,
  fetchCurrentUser,
  fetchProjectRequests,
  fetchProjects,
  rejectProjectRequest,
  type CurrentUser,
  type Project,
  type ProjectLinkOut,
  type ProjectRequest,
} from "@/lib/api";

function canRequest(user: CurrentUser | null): boolean {
  if (!user) return false;
  return (
    ["govern", "assure", "operator"].includes(user.business_role) ||
    ["admin", "super_admin"].includes(user.system_role)
  );
}

function canApprove(user: CurrentUser | null): boolean {
  if (!user) return false;
  return ["govern", "assure"].includes(user.business_role) || ["admin", "super_admin"].includes(user.system_role);
}

function requestStatusBadge(status: string) {
  const styles: Record<string, string> = {
    pending: "bg-secondary text-secondary-foreground",
    approved: "bg-primary/10 text-primary",
    rejected: "bg-destructive/10 text-destructive",
  };
  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-medium capitalize ${styles[status] ?? ""}`}>{status}</span>
  );
}

function assessmentBadge(status: string, result: string | null) {
  if (status === "pending") {
    return <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">AI reviewing...</span>;
  }
  if (status === "skipped") {
    return (
      <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
        No AI precheck - no active AI Policy yet
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="rounded-md bg-destructive/10 px-2 py-0.5 text-xs text-destructive">
        AI pre-check unavailable - manual review required
      </span>
    );
  }
  const styles: Record<string, { className: string; Icon: typeof CheckCircle2 }> = {
    approvable: { className: "bg-primary/10 text-primary", Icon: CheckCircle2 },
    needs_review: { className: "bg-accent/15 text-accent", Icon: AlertTriangle },
    cannot_approve: { className: "bg-destructive/10 text-destructive", Icon: XCircle },
  };
  const s = styles[result ?? ""] ?? { className: "bg-muted text-muted-foreground", Icon: HelpCircle };
  const Icon = s.Icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium capitalize ${s.className}`}>
      <Icon className="size-3.5" /> {(result ?? "unknown").replace("_", " ")}
    </span>
  );
}

function inventoryBadge(link: ProjectLinkOut) {
  if (link.in_inventory) return null;
  return (
    <span className="rounded-md bg-accent/15 px-2 py-0.5 text-xs font-medium text-accent">
      not registered in inventory
    </span>
  );
}

export default function AiProjectPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [projects, setProjects] = useState<Project[] | "loading">("loading");
  const [myRequests, setMyRequests] = useState<ProjectRequest[]>([]);
  const [pendingRequests, setPendingRequests] = useState<ProjectRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [viewRequestTarget, setViewRequestTarget] = useState<ProjectRequest | null>(null);

  const refresh = () => {
    fetchProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
    fetchProjectRequests({ mine: true })
      .then(setMyRequests)
      .catch(() => setMyRequests([]));
    if (canApprove(user)) {
      fetchProjectRequests()
        .then(setPendingRequests)
        .catch(() => setPendingRequests([]));
    }
  };

  useEffect(() => {
    fetchProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
    fetchProjectRequests({ mine: true })
      .then(setMyRequests)
      .catch(() => setMyRequests([]));
    fetchCurrentUser().then((u) => {
      setUser(u);
      if (canApprove(u)) {
        fetchProjectRequests()
          .then(setPendingRequests)
          .catch(() => setPendingRequests([]));
      }
    });
  }, []);

  const handleApprove = async (request: ProjectRequest) => {
    setBusy(true);
    setError(null);
    try {
      await approveProjectRequest(request.id);
      setViewRequestTarget(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async (request: ProjectRequest) => {
    setBusy(true);
    setError(null);
    try {
      await rejectProjectRequest(request.id);
      setViewRequestTarget(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  if (projects === "loading") {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">AI Project</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            AI use-cases and workflows, assessed against the org&apos;s active AI Policy.
          </p>
        </div>
        <div className="flex gap-2">
          {canRequest(user) && (
            <Button onClick={() => router.push("/ai-center/project/request")}>
              <Plus /> New Project
            </Button>
          )}
          <Button variant="outline" onClick={refresh}>
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Projects</h2>
        {projects.length === 0 ? (
          <p className="text-sm text-muted-foreground">No projects yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {projects.map((project) => (
              <div key={project.id} className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">{project.name}</span>
                  <span className="shrink-0 rounded-md bg-muted px-2 py-0.5 text-xs capitalize text-muted-foreground">
                    {project.lifecycle_stage}
                  </span>
                </div>
                <p className="line-clamp-2 text-xs text-muted-foreground">{project.description}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {canRequest(user) && myRequests.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">My Requests</h2>
          <div className="space-y-2">
            {myRequests.map((request) => (
              <button
                key={request.id}
                type="button"
                onClick={() => setViewRequestTarget(request)}
                className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 text-left hover:bg-muted"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm font-medium">{request.name}</span>
                  {assessmentBadge(request.project_assessment_status, request.project_assessment_result)}
                </div>
                {requestStatusBadge(request.status)}
              </button>
            ))}
          </div>
        </section>
      )}

      {canApprove(user) && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Pending Approvals</h2>
          {pendingRequests.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing pending approval.</p>
          ) : (
            <div className="space-y-2">
              {pendingRequests.map((request) => (
                <button
                  key={request.id}
                  type="button"
                  onClick={() => setViewRequestTarget(request)}
                  className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 text-left hover:bg-muted"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate text-sm font-medium">{request.name}</span>
                    {assessmentBadge(request.project_assessment_status, request.project_assessment_result)}
                  </div>
                  {requestStatusBadge(request.status)}
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      <RequestDetailDialog
        request={viewRequestTarget}
        currentUser={user}
        busy={busy}
        onOpenChange={(open) => !open && setViewRequestTarget(null)}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </div>
  );
}

function RequestDetailDialog({
  request,
  currentUser,
  busy,
  onOpenChange,
  onApprove,
  onReject,
}: {
  request: ProjectRequest | null;
  currentUser: CurrentUser | null;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove: (request: ProjectRequest) => void;
  onReject: (request: ProjectRequest) => void;
}) {
  const isOwn = !!request && currentUser?.id === request.requested_by;
  const canDecide = !!request && canApprove(currentUser) && request.status === "pending";

  return (
    <Dialog open={request !== null} onOpenChange={onOpenChange}>
      {request && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {request.name}
              {requestStatusBadge(request.status)}
            </DialogTitle>
            <DialogDescription>Requested by {request.requested_by_email ?? "unknown"}</DialogDescription>
          </DialogHeader>

          <div className="mb-4 space-y-3 text-sm">
            <div>
              <p className="text-xs font-medium text-muted-foreground">Description</p>
              <p>{request.description}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Business justification</p>
              <p>{request.business_justification}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Data flow</p>
              <p>{request.data_flow_description}</p>
            </div>
            {request.data_tiers.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-muted-foreground">Data tier(s)</p>
                <div className="flex flex-wrap gap-1.5">
                  {request.data_tiers.map((tier) => (
                    <span key={tier} className="rounded-md bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                      {TIER_LABELS[tier] ?? tier}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Human in the loop: <span className="font-medium text-foreground">{request.human_in_loop ? "Yes" : "No"}</span>
            </p>
          </div>

          <div className="mb-4">
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">AI pre-check (not a decision)</p>
            <div className="flex items-center gap-2">
              {assessmentBadge(request.project_assessment_status, request.project_assessment_result)}
            </div>
            {request.project_assessment_explanation && (
              <p className="mt-1.5 text-xs text-muted-foreground">{request.project_assessment_explanation}</p>
            )}
          </div>

          {(request.linked_tools.length > 0 || request.linked_vendors.length > 0) && (
            <div className="mb-4 space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Risk rollup</p>
              {[...request.linked_tools, ...request.linked_vendors].map((link) => (
                <div key={link.id} className="flex items-center justify-between gap-2 rounded-lg border border-border p-2 text-sm">
                  <span>{link.name}</span>
                  <div className="flex items-center gap-1.5">
                    {link.status && (
                      <span className="rounded-md bg-muted px-2 py-0.5 text-xs capitalize text-muted-foreground">
                        {link.status.replace("_", " ")}
                      </span>
                    )}
                    {inventoryBadge(link)}
                  </div>
                </div>
              ))}
            </div>
          )}

          {canDecide && (
            <DialogFooter>
              <Button
                variant="outline"
                disabled={busy || isOwn}
                title={isOwn ? "You cannot reject your own request" : undefined}
                onClick={() => onReject(request)}
              >
                Reject
              </Button>
              <Button
                disabled={busy || isOwn}
                title={isOwn ? "You cannot approve your own request" : undefined}
                onClick={() => onApprove(request)}
              >
                Approve
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      )}
    </Dialog>
  );
}
