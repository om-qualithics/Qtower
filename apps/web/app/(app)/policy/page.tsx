"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Download, FileText, Upload, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  approvePolicy,
  createPolicy,
  fetchCurrentUser,
  getPolicyDownloadUrl,
  listPolicies,
  uploadPolicy,
  type CurrentUser,
  type PolicyListItem,
} from "@/lib/api";

const HISTORY_LIMIT = 2;

function canManage(user: CurrentUser | null): boolean {
  if (!user) return false;
  return (
    ["govern", "assure"].includes(user.business_role) || ["admin", "super_admin"].includes(user.system_role)
  );
}

function canApprove(user: CurrentUser | null): boolean {
  if (!user) return false;
  return user.business_role === "govern" || ["admin", "super_admin"].includes(user.system_role);
}

function AuthorApprovalTags({ policy }: { policy: PolicyListItem }) {
  if (!policy.created_by_email && !policy.approved_by_email) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {policy.created_by_email && (
        <span className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground">
          Authored by {policy.created_by_email}
        </span>
      )}
      {policy.approved_by_email && (
        <span className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground">
          Approved by {policy.approved_by_email}
        </span>
      )}
    </div>
  );
}

export default function PolicyListPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [policies, setPolicies] = useState<PolicyListItem[] | "loading">("loading");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    listPolicies()
      .then(setPolicies)
      .catch(() => setPolicies([]));
  };

  useEffect(() => {
    fetchCurrentUser().then(setUser);
    refresh();
  }, []);

  const startNewPolicy = async () => {
    setBusy(true);
    setError(null);
    try {
      const policy = await createPolicy();
      router.push(`/policy/new?id=${policy.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const handleUpload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      await uploadPolicy(file);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async (id: string) => {
    if (!window.confirm("Approve this policy as the live AI Policy? It will replace the current active version.")) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await approvePolicy(id);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const download = async (id: string) => {
    const url = await getPolicyDownloadUrl(id);
    window.location.assign(url);
  };

  if (policies === "loading") {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  const active = policies.find((p) => p.status === "active") ?? null;
  const drafts = policies.filter((p) => p.status === "draft");
  const archivedAll = policies
    .filter((p) => p.status === "archived")
    .sort((a, b) => b.version - a.version);
  const archived = archivedAll.slice(0, HISTORY_LIMIT);
  const hiddenHistoryCount = archivedAll.length - archived.length;

  return (
    <div className="mx-auto w-[clamp(28rem,26rem+21vw,64rem)] max-w-full">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">AI Policy</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Build and manage your organization&apos;s AI governance policy.
          </p>
        </div>
        {canManage(user) && (
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".docx"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) handleUpload(file);
              }}
            />
            <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={busy}>
              <Upload /> Upload Policy
            </Button>
            <Button onClick={startNewPolicy} disabled={busy}>
              <Plus /> New Policy
            </Button>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <section className="mb-6">
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Active Policy</h2>
        {active ? (
          <div className="flex items-center justify-between rounded-2xl border border-border bg-card p-4">
            <div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="size-4 text-primary" />
                <span className="text-sm font-medium">Version {active.version}</span>
                <span className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
                  Active
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {active.approved_at ? `Approved ${new Date(active.approved_at).toLocaleDateString()}` : ""}
              </p>
              <AuthorApprovalTags policy={active} />
            </div>
            <Button variant="outline" size="sm" onClick={() => download(active.id)}>
              <Download /> Download
            </Button>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-border p-8 text-center">
            <FileText className="mx-auto mb-3 size-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              No AI policy has been approved yet.
              {canManage(user) && " Build or upload one below, then approve it to make it live."}
            </p>
          </div>
        )}
      </section>

      {canManage(user) && drafts.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Drafts</h2>
          <div className="space-y-3">
            {drafts.map((policy) => (
              <div
                key={policy.id}
                className="flex items-center justify-between rounded-2xl border border-border bg-card p-4"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      {policy.policy_owner_name ? `Policy owned by ${policy.policy_owner_name}` : "Untitled policy"}
                    </span>
                    <span className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
                      {policy.source === "upload" ? "Uploaded" : "Draft"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Last updated {new Date(policy.updated_at).toLocaleDateString()}
                  </p>
                  <AuthorApprovalTags policy={policy} />
                </div>
                <div className="flex gap-2">
                  {policy.source === "builder" && !policy.has_document && (
                    <Button variant="outline" size="sm" onClick={() => router.push(`/policy/new?id=${policy.id}`)}>
                      Continue
                    </Button>
                  )}
                  {policy.has_document && (
                    <Button variant="outline" size="sm" onClick={() => download(policy.id)}>
                      <Download /> Download
                    </Button>
                  )}
                  {policy.has_document && canApprove(user) && (
                    <Button size="sm" onClick={() => handleApprove(policy.id)} disabled={busy}>
                      Approve
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">History</h2>
        {archived.length === 0 ? (
          <p className="text-sm text-muted-foreground">No previous versions yet.</p>
        ) : (
          <div className="space-y-3">
            {archived.map((policy) => (
              <div
                key={policy.id}
                className="flex items-center justify-between rounded-2xl border border-border bg-card p-4"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">Version {policy.version}</span>
                    <span className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
                      Archived
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {policy.approved_at ? `Was approved ${new Date(policy.approved_at).toLocaleDateString()}` : ""}
                  </p>
                  <AuthorApprovalTags policy={policy} />
                </div>
                <Button variant="outline" size="sm" onClick={() => download(policy.id)}>
                  <Download /> Download
                </Button>
              </div>
            ))}
            {hiddenHistoryCount > 0 && (
              <p className="text-xs text-muted-foreground">
                {hiddenHistoryCount} earlier version{hiddenHistoryCount > 1 ? "s" : ""} not shown.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
