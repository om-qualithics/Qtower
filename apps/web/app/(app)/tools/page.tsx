"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Link2, Plus, Pencil, Trash2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  approveToolRequest,
  createToolRequest,
  deleteApprovedTool,
  fetchApprovedTools,
  fetchCurrentUser,
  fetchToolRequests,
  rejectToolRequest,
  updateApprovedTool,
  ToolRequestDuplicateError,
  type ApprovedTool,
  type CurrentUser,
  type ToolRequest,
  type ToolRequestType,
} from "@/lib/api";

const TIER_KEYS = ["restricted", "confidential", "internal", "public"] as const;
const TIER_LABELS: Record<string, string> = {
  restricted: "Restricted (Tier 1)",
  confidential: "Confidential (Tier 2)",
  internal: "Internal (Tier 3)",
  public: "Public (Tier 4)",
};
const REQUEST_TYPE_LABELS: Record<ToolRequestType, string> = {
  tool: "Tool",
  feature: "Feature",
  webextension: "Web extension",
};
const ASSESSMENT_LABELS: Record<string, string> = {
  approvable: "Approvable",
  needs_review: "Needs additional review",
  cannot_approve: "Cannot be approved",
};

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

function canManageCatalog(user: CurrentUser | null): boolean {
  return canApprove(user);
}

function statusBadge(status: string) {
  const styles: Record<string, string> = {
    pending: "bg-secondary text-secondary-foreground",
    approved: "bg-primary/10 text-primary",
    rejected: "bg-destructive/10 text-destructive",
  };
  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-medium capitalize ${styles[status] ?? ""}`}>{status}</span>
  );
}

function AssessmentNote({ request, size = "text-xs" }: { request: ToolRequest; size?: "text-xs" | "text-sm" }) {
  if (request.ai_assessment_status === "pending") {
    return <p className={`mt-1 ${size} text-muted-foreground`}>AI reviewing...</p>;
  }
  if (request.ai_assessment_status === "failed") {
    return <p className={`mt-1 ${size} text-muted-foreground`}>AI pre-check unavailable — manual review required.</p>;
  }
  if (request.ai_assessment_status === "skipped") {
    return <p className={`mt-1 ${size} text-muted-foreground`}>No AI precheck — no active AI Policy yet.</p>;
  }
  return (
    <p className={`mt-1 ${size} text-muted-foreground`}>
      <span className="font-medium text-foreground">AI pre-check (not a decision):</span>{" "}
      {ASSESSMENT_LABELS[request.ai_assessment_result ?? ""] ?? request.ai_assessment_result} —{" "}
      {request.ai_assessment_explanation}
    </p>
  );
}

function classificationBadge(request: ToolRequest): { label: string; className: string } {
  if (request.ai_assessment_status === "pending") {
    return { label: "AI reviewing...", className: "bg-secondary text-secondary-foreground" };
  }
  if (request.ai_assessment_status === "failed") {
    return { label: "Precheck unavailable", className: "bg-muted text-muted-foreground" };
  }
  if (request.ai_assessment_status === "skipped") {
    return { label: "No precheck", className: "bg-muted text-muted-foreground" };
  }
  const styles: Record<string, string> = {
    approvable: "bg-primary/10 text-primary",
    needs_review: "bg-accent/15 text-accent",
    cannot_approve: "bg-destructive/10 text-destructive",
  };
  const result = request.ai_assessment_result ?? "";
  return { label: ASSESSMENT_LABELS[result] ?? result, className: styles[result] ?? "bg-muted text-muted-foreground" };
}

export default function ToolsPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [tools, setTools] = useState<ApprovedTool[] | "loading">("loading");
  const [myRequests, setMyRequests] = useState<ToolRequest[]>([]);
  const [pendingRequests, setPendingRequests] = useState<ToolRequest[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedTool, setSelectedTool] = useState<ApprovedTool | null>(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const [detailTarget, setDetailTarget] = useState<ToolRequest | null>(null);
  const [viewTarget, setViewTarget] = useState<ToolRequest | null>(null);
  const [approveTarget, setApproveTarget] = useState<ToolRequest | null>(null);
  const [editTool, setEditTool] = useState<ApprovedTool | null>(null);

  const handleReject = async (request: ToolRequest) => {
    const reason = window.prompt("Optional reason for rejecting this request:") ?? undefined;
    setBusy(true);
    setError(null);
    try {
      await rejectToolRequest(request.id, reason || undefined);
      setDetailTarget(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const refresh = () => {
    fetchApprovedTools()
      .then(setTools)
      .catch(() => setTools([]));
    fetchToolRequests({ mine: true })
      .then(setMyRequests)
      .catch(() => setMyRequests([]));
    // Only fetched for roles that can actually see it - an operator
    // hitting this would 403 (tools.approve), which is expected but
    // pointless to request in the first place.
    if (canApprove(user)) {
      fetchToolRequests()
        .then(setPendingRequests)
        .catch(() => setPendingRequests([]));
    }
  };

  useEffect(() => {
    fetchApprovedTools()
      .then(setTools)
      .catch(() => setTools([]));
    fetchToolRequests({ mine: true })
      .then(setMyRequests)
      .catch(() => setMyRequests([]));
    fetchCurrentUser().then((u) => {
      setUser(u);
      if (canApprove(u)) {
        fetchToolRequests()
          .then(setPendingRequests)
          .catch(() => setPendingRequests([]));
      }
    });
  }, []);

  if (tools === "loading") {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">AI Tools</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Browse approved AI tools and features, or request access to something new.
          </p>
        </div>
        <div className="flex gap-2">
          {canRequest(user) && (
            <Button onClick={() => setRequestOpen(true)}>
              <Plus /> Request Access
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
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Approved AI Tools</h2>
        {tools.length === 0 ? (
          <p className="text-sm text-muted-foreground">No AI tools approved yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {tools.map((tool) => (
              <div
                key={tool.id}
                className="flex flex-col justify-between rounded-2xl border border-border bg-card p-4"
              >
                <button
                  type="button"
                  onClick={() => setSelectedTool(tool)}
                  className="text-left"
                >
                  <span className="text-sm font-medium">{tool.name}</span>
                  <p className="mt-1 text-xs text-muted-foreground">{tool.description}</p>
                </button>
                <div className="mt-3 flex items-center justify-between">
                  {tool.source_type === "tool" ? (
                    <Button
                      size="sm"
                      render={
                        <a href={tool.access_url} target="_blank" rel="noopener noreferrer">
                          <ExternalLink /> Access Now
                        </a>
                      }
                      nativeButton={false}
                    />
                  ) : (
                    <a
                      href={tool.access_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                    >
                      <Link2 className="size-3.5" /> View link
                    </a>
                  )}
                  {canManageCatalog(user) && (
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon-sm" onClick={() => setEditTool(tool)} title="Edit">
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title="Remove"
                        onClick={async () => {
                          if (!window.confirm(`Remove "${tool.name}" from the Approved AI Tools list?`)) return;
                          await deleteApprovedTool(tool.id);
                          refresh();
                        }}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  )}
                </div>
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
                onClick={() => setViewTarget(request)}
                className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 text-left hover:bg-muted"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm font-medium">{request.name}</span>
                  <span className="shrink-0 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {REQUEST_TYPE_LABELS[request.request_type]}
                  </span>
                </div>
                {statusBadge(request.status)}
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
              {pendingRequests.map((request) => {
                const badge = classificationBadge(request);
                return (
                  <button
                    key={request.id}
                    type="button"
                    onClick={() => setDetailTarget(request)}
                    className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 text-left hover:bg-muted"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate text-sm font-medium">{request.name}</span>
                      <span className="shrink-0 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {REQUEST_TYPE_LABELS[request.request_type]}
                      </span>
                    </div>
                    <span className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-medium ${badge.className}`}>
                      {badge.label}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </section>
      )}

      <RequestAccessDialog
        open={requestOpen}
        onOpenChange={setRequestOpen}
        onSubmitted={refresh}
        setError={setError}
      />
      <ToolDetailDialog tool={selectedTool} onOpenChange={(open) => !open && setSelectedTool(null)} />
      <RequestDetailDialog
        mode="approve"
        request={detailTarget}
        currentUser={user}
        busy={busy}
        onOpenChange={(open) => !open && setDetailTarget(null)}
        onApproveClick={(request) => {
          setDetailTarget(null);
          setApproveTarget(request);
        }}
        onReject={handleReject}
      />
      <RequestDetailDialog
        mode="view"
        request={viewTarget}
        currentUser={user}
        busy={busy}
        onOpenChange={(open) => !open && setViewTarget(null)}
        onApproveClick={() => {}}
        onReject={() => {}}
      />
      <ApproveDialog
        request={approveTarget}
        onOpenChange={(open) => !open && setApproveTarget(null)}
        onApproved={refresh}
        setError={setError}
      />
      <EditToolDialog
        tool={editTool}
        onOpenChange={(open) => !open && setEditTool(null)}
        onSaved={refresh}
        setError={setError}
      />
    </div>
  );
}

function RequestAccessDialog({
  open,
  onOpenChange,
  onSubmitted,
  setError,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmitted: () => void;
  setError: (msg: string | null) => void;
}) {
  const [requestType, setRequestType] = useState<ToolRequestType>("tool");
  const [name, setName] = useState("");
  const [link, setLink] = useState("");
  const [useCase, setUseCase] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const reset = () => {
    setRequestType("tool");
    setName("");
    setLink("");
    setUseCase("");
    setLocalError(null);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Request Access</DialogTitle>
          <DialogDescription>
            Ask for approval to use an AI tool, feature, or web extension not already on the approved list.
          </DialogDescription>
        </DialogHeader>

        {localError && (
          <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {localError}
          </div>
        )}

        <div className="space-y-3">
          <div>
            <Label className="mb-1.5 block text-xs">Approval request for?</Label>
            <Select value={requestType} onChange={(e) => setRequestType(e.target.value as ToolRequestType)}>
              <option value="tool">Tool</option>
              <option value="feature">Feature</option>
              <option value="webextension">Web extension</option>
            </Select>
          </div>
          <div>
            <Label className="mb-1.5 block text-xs">Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Claude" />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs">Link</Label>
            <Input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://..." />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs">Intended use case</Label>
            <Textarea value={useCase} onChange={(e) => setUseCase(e.target.value)} rows={3} />
          </div>
        </div>

        <DialogFooter>
          <Button
            disabled={submitting || !name.trim() || !link.trim() || !useCase.trim()}
            onClick={async () => {
              setSubmitting(true);
              setLocalError(null);
              try {
                await createToolRequest(requestType, name, link, useCase);
                reset();
                onOpenChange(false);
                onSubmitted();
              } catch (err) {
                if (err instanceof ToolRequestDuplicateError) {
                  setLocalError(err.message);
                } else {
                  setError(err instanceof Error ? err.message : "Something went wrong.");
                  onOpenChange(false);
                }
              } finally {
                setSubmitting(false);
              }
            }}
          >
            Send for Approval
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ToolDetailDialog({ tool, onOpenChange }: { tool: ApprovedTool | null; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={tool !== null} onOpenChange={onOpenChange}>
      {tool && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="size-4 text-primary" /> {tool.name}
            </DialogTitle>
            <DialogDescription>{tool.description}</DialogDescription>
          </DialogHeader>
          {tool.details && <p className="mb-4 text-sm text-muted-foreground">{tool.details}</p>}
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">Approved data tiers</p>
            <div className="flex flex-wrap gap-1.5">
              {tool.allowed_tiers.length === 0 && <span className="text-xs text-muted-foreground">None specified.</span>}
              {tool.allowed_tiers.map((tier) => (
                <span key={tier} className="rounded-md bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                  {TIER_LABELS[tier] ?? tier}
                </span>
              ))}
            </div>
          </div>
          <DialogFooter>
            {tool.source_type === "tool" ? (
              <Button
                render={
                  <a href={tool.access_url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink /> Access Now
                  </a>
                }
                nativeButton={false}
              />
            ) : (
              <Button
                variant="outline"
                render={
                  <a href={tool.access_url} target="_blank" rel="noopener noreferrer">
                    <Link2 /> View link
                  </a>
                }
                nativeButton={false}
              />
            )}
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}

function RequestDetailDialog({
  mode,
  request,
  currentUser,
  busy,
  onOpenChange,
  onApproveClick,
  onReject,
}: {
  mode: "approve" | "view";
  request: ToolRequest | null;
  currentUser: CurrentUser | null;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onApproveClick: (request: ToolRequest) => void;
  onReject: (request: ToolRequest) => void;
}) {
  const isOwn = !!request && currentUser?.id === request.requested_by;

  return (
    <Dialog open={request !== null} onOpenChange={onOpenChange}>
      {request && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {request.name}
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                {REQUEST_TYPE_LABELS[request.request_type]}
              </span>
              {mode === "view" && statusBadge(request.status)}
            </DialogTitle>
            <DialogDescription>
              Requested by {request.requested_by_email ?? "unknown"} ·{" "}
              <a href={request.link} target="_blank" rel="noopener noreferrer" className="underline">
                {request.link}
              </a>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 text-sm">
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">Intended use case</p>
              <p>{request.intended_use_case}</p>
            </div>
            <AssessmentNote request={request} size="text-sm" />
          </div>

          {mode === "approve" && (
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
                onClick={() => onApproveClick(request)}
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

function ApproveDialog({
  request,
  onOpenChange,
  onApproved,
  setError,
}: {
  request: ToolRequest | null;
  onOpenChange: (open: boolean) => void;
  onApproved: () => void;
  setError: (msg: string | null) => void;
}) {
  const [description, setDescription] = useState("");
  const [tiers, setTiers] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (request) {
      queueMicrotask(() => {
        setDescription(request.intended_use_case);
        setTiers([]);
      });
    }
  }, [request]);

  return (
    <Dialog open={request !== null} onOpenChange={onOpenChange}>
      {request && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve &quot;{request.name}&quot;</DialogTitle>
            <DialogDescription>
              This adds it to the Approved AI Tools catalog everyone can browse.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div>
              <Label className="mb-1.5 block text-xs">Catalog description</Label>
              <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Allowed data tiers</Label>
              <div className="space-y-2">
                {TIER_KEYS.map((tier) => (
                  <label key={tier} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={tiers.includes(tier)}
                      onCheckedChange={(checked) =>
                        setTiers((prev) => (checked ? [...prev, tier] : prev.filter((t) => t !== tier)))
                      }
                    />
                    {TIER_LABELS[tier]}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              disabled={submitting || !description.trim()}
              onClick={async () => {
                setSubmitting(true);
                try {
                  await approveToolRequest(request.id, description, tiers);
                  onOpenChange(false);
                  onApproved();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Something went wrong.");
                  onOpenChange(false);
                } finally {
                  setSubmitting(false);
                }
              }}
            >
              Confirm Approval
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}

function EditToolDialog({
  tool,
  onOpenChange,
  onSaved,
  setError,
}: {
  tool: ApprovedTool | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  setError: (msg: string | null) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [accessUrl, setAccessUrl] = useState("");
  const [tiers, setTiers] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (tool) {
      queueMicrotask(() => {
        setName(tool.name);
        setDescription(tool.description);
        setAccessUrl(tool.access_url);
        setTiers(tool.allowed_tiers);
      });
    }
  }, [tool]);

  return (
    <Dialog open={tool !== null} onOpenChange={onOpenChange}>
      {tool && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit &quot;{tool.name}&quot;</DialogTitle>
          </DialogHeader>

          <div className="space-y-3">
            <div>
              <Label className="mb-1.5 block text-xs">Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Description</Label>
              <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Access link</Label>
              <Input value={accessUrl} onChange={(e) => setAccessUrl(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Allowed data tiers</Label>
              <div className="space-y-2">
                {TIER_KEYS.map((tier) => (
                  <label key={tier} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={tiers.includes(tier)}
                      onCheckedChange={(checked) =>
                        setTiers((prev) => (checked ? [...prev, tier] : prev.filter((t) => t !== tier)))
                      }
                    />
                    {TIER_LABELS[tier]}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              disabled={submitting || !name.trim()}
              onClick={async () => {
                setSubmitting(true);
                try {
                  await updateApprovedTool(tool.id, name, description, accessUrl, tiers);
                  onOpenChange(false);
                  onSaved();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Something went wrong.");
                  onOpenChange(false);
                } finally {
                  setSubmitting(false);
                }
              }}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}
