"use client";

import { useEffect, useState } from "react";
import { Bug, Download, GitBranch, Play, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  createGithubConnection,
  createScan,
  fetchCurrentUser,
  fetchGithubConnectionStatus,
  fetchGithubRepos,
  fetchScanDetail,
  fetchScanReportUrl,
  fetchScans,
  type CurrentUser,
  type Finding,
  type GithubConnectionStatus,
  type Repo,
  type ScanDetail,
  type ScanRun,
  type ScanStatus,
} from "@/lib/api";

function canConnect(user: CurrentUser | null): boolean {
  return !!user && (user.business_role === "assure" || ["admin", "super_admin"].includes(user.system_role));
}

const STATUS_LABELS: Record<ScanStatus, string> = {
  queued: "Queued",
  running: "Running",
  complete: "Complete",
  failed: "Failed",
};

function statusBadge(status: ScanStatus) {
  const styles: Record<ScanStatus, string> = {
    queued: "bg-secondary text-secondary-foreground",
    running: "bg-accent/15 text-accent",
    complete: "bg-primary/10 text-primary",
    failed: "bg-destructive/10 text-destructive",
  };
  return <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${styles[status]}`}>{STATUS_LABELS[status]}</span>;
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-destructive/10 text-destructive",
  high: "bg-accent/15 text-accent",
  medium: "bg-primary/10 text-primary",
  low: "bg-secondary text-secondary-foreground",
};

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-medium uppercase ${SEVERITY_STYLES[severity] ?? "bg-secondary"}`}>
      {severity}
    </span>
  );
}

function FindingCountsRow({ counts }: { counts: Record<string, number> }) {
  const order = ["critical", "high", "medium", "low"];
  return (
    <div className="flex gap-2 text-xs">
      {order.map((sev) => (
        <span key={sev} className={`rounded-md px-1.5 py-0.5 font-medium ${SEVERITY_STYLES[sev]}`}>
          {counts[sev] ?? 0} {sev}
        </span>
      ))}
    </div>
  );
}

function ConnectionSection({
  status,
  onConnected,
}: {
  status: GithubConnectionStatus;
  onConnected: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [appId, setAppId] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [installationId, setInstallationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await createGithubConnection({ appId, privateKey, installationId });
      setOpen(false);
      setAppId("");
      setPrivateKey("");
      setInstallationId("");
      onConnected();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch className="size-5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">
              {status.configured ? `Connected${status.account_login ? ` — ${status.account_login}` : ""}` : "Not connected"}
            </p>
            <p className="text-xs text-muted-foreground">
              {status.configured
                ? "Repos are discovered live from this installation's grant."
                : "Create a GitHub App inside your own GitHub org and install it to connect."}
            </p>
          </div>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
            {status.configured ? "Reconnect" : "Connect GitHub"}
          </Button>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Connect GitHub</DialogTitle>
              <DialogDescription>
                In your GitHub org: Settings → Developer settings → GitHub Apps → New GitHub App. No callback/webhook
                URL is needed — leave those blank.
              </DialogDescription>
            </DialogHeader>
            <div className="mb-3 rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
              <p className="mb-1 font-medium text-foreground">Required permission</p>
              <p>
                Under <span className="font-mono">Repository permissions</span>, set{" "}
                <span className="font-mono">Contents</span> to <span className="font-mono">Read-only</span> — that's
                the only one this needs (it's what lets us clone the repo to scan it).{" "}
                <span className="font-mono">Metadata: Read-only</span> is included automatically by GitHub and needs
                no action. Nothing else — no write access, no Issues/Actions/PRs, no webhooks.
              </p>
              <p className="mt-2">
                Then install the App into your org (choose "All repositories" or select specific ones), generate a
                private key, and paste the three values below.
              </p>
            </div>
            <div className="space-y-3">
              <div>
                <Label className="mb-1.5 block text-xs">App ID</Label>
                <Input value={appId} onChange={(e) => setAppId(e.target.value)} />
              </div>
              <div>
                <Label className="mb-1.5 block text-xs">Installation ID</Label>
                <Input value={installationId} onChange={(e) => setInstallationId(e.target.value)} />
              </div>
              <div>
                <Label className="mb-1.5 block text-xs">Private key (.pem contents)</Label>
                <Textarea
                  rows={6}
                  className="font-mono text-xs"
                  placeholder="-----BEGIN RSA PRIVATE KEY-----"
                  value={privateKey}
                  onChange={(e) => setPrivateKey(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>
            <DialogFooter>
              <Button disabled={busy || !appId || !privateKey || !installationId} onClick={submit}>
                {busy ? "Connecting…" : "Connect"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}

function RunScanSection({ configured, onScanCreated }: { configured: boolean; onScanCreated: () => void }) {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selected, setSelected] = useState("");
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRepos = () => {
    if (!configured) return;
    setLoadingRepos(true);
    setError(null);
    fetchGithubRepos()
      .then((r) => {
        setRepos(r);
        if (r.length && !selected) setSelected(r[0].full_name);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to list repos"))
      .finally(() => setLoadingRepos(false));
  };

  useEffect(loadRepos, [configured]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await createScan(selected);
      onScanCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start scan");
    } finally {
      setBusy(false);
    }
  };

  if (!configured) return null;

  return (
    <div className="mt-6 rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center gap-3">
        <Select className="max-w-md" value={selected} onChange={(e) => setSelected(e.target.value)} disabled={loadingRepos}>
          {repos.map((r) => (
            <option key={r.full_name} value={r.full_name}>
              {r.full_name}
            </option>
          ))}
        </Select>
        <Button size="sm" variant="outline" onClick={loadRepos} disabled={loadingRepos}>
          <RefreshCw className="size-3.5" />
        </Button>
        <Button size="sm" disabled={busy || !selected} onClick={run}>
          <Play className="size-3.5" /> {busy ? "Starting…" : "Run Scan"}
        </Button>
      </div>
      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
    </div>
  );
}

type SeverityFilter = "all" | "critical" | "high" | "medium" | "low";

const SEVERITY_FILTERS: SeverityFilter[] = ["all", "critical", "high", "medium", "low"];

function SeverityFilterTags({
  value,
  onChange,
  counts,
}: {
  value: SeverityFilter;
  onChange: (next: SeverityFilter) => void;
  counts: Record<string, number>;
}) {
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  return (
    <div className="mb-3 flex flex-wrap gap-1.5">
      {SEVERITY_FILTERS.map((sev) => {
        const count = sev === "all" ? total : counts[sev] ?? 0;
        const active = value === sev;
        return (
          <button
            key={sev}
            type="button"
            onClick={() => onChange(sev)}
            className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
              active
                ? sev === "all"
                  ? "bg-primary text-primary-foreground"
                  : SEVERITY_STYLES[sev]
                : "bg-muted text-muted-foreground hover:bg-muted/70"
            }`}
          >
            {sev} {count}
          </button>
        );
      })}
    </div>
  );
}

function ScanDetailDialog({ scanId, onClose }: { scanId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<ScanDetail | null>(null);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");

  useEffect(() => {
    setSeverityFilter("all");
    fetchScanDetail(scanId).then(setDetail).catch(() => setDetail(null));
  }, [scanId]);

  const download = async () => {
    const url = await fetchScanReportUrl(scanId);
    window.open(url, "_blank", "noopener,noreferrer");
  };

  // Findings already arrive sorted critical -> high -> medium -> low from
  // the API (codescan/service.py::list_findings) - filtering here doesn't
  // need to re-sort, just narrow the already-ordered list.
  const filteredFindings =
    detail?.findings.filter((f) => severityFilter === "all" || f.severity === severityFilter) ?? [];

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{detail?.repo_full_name ?? "Scan"}</DialogTitle>
          <DialogDescription>
            {detail ? statusBadge(detail.status) : "Loading…"}
            {detail?.commit_sha && <span className="ml-2 font-mono text-xs">{detail.commit_sha.slice(0, 8)}</span>}
          </DialogDescription>
        </DialogHeader>
        {detail?.status === "failed" && detail.error_message && (
          <p className="mb-3 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{detail.error_message}</p>
        )}
        {detail?.status === "complete" && (
          <>
            <div className="mb-3 flex items-center justify-between">
              <FindingCountsRow counts={detail.finding_counts} />
              <Button size="sm" variant="outline" onClick={download}>
                <Download className="size-3.5" /> Download report
              </Button>
            </div>
            <SeverityFilterTags value={severityFilter} onChange={setSeverityFilter} counts={detail.finding_counts} />
            <div className="max-h-96 space-y-2 overflow-y-auto">
              {filteredFindings.map((f: Finding) => (
                <div key={f.id} className="rounded-lg border border-border p-3 text-sm">
                  <div className="mb-1 flex items-center gap-2">
                    <SeverityBadge severity={f.severity} />
                    <span className="text-xs text-muted-foreground">{f.category_label}</span>
                  </div>
                  <p className="font-mono text-xs text-muted-foreground">
                    {f.file_path}
                    {f.line_start ? `:${f.line_start}` : ""}
                  </p>
                  <p className="mt-1">{f.description}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Detected by {f.sources.join(", ")} · {f.confidence} confidence
                  </p>
                </div>
              ))}
              {detail.findings.length === 0 && (
                <p className="text-sm text-muted-foreground">No findings — clean scan.</p>
              )}
              {detail.findings.length > 0 && filteredFindings.length === 0 && (
                <p className="text-sm text-muted-foreground">No {severityFilter} findings.</p>
              )}
            </div>
          </>
        )}
        {(detail?.status === "queued" || detail?.status === "running") && (
          <p className="text-sm text-muted-foreground">Scan in progress — refresh to check back.</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function CodeScanPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<GithubConnectionStatus | null>(null);
  const [scans, setScans] = useState<ScanRun[]>([]);
  const [openScanId, setOpenScanId] = useState<string | null>(null);

  const refreshStatus = () => fetchGithubConnectionStatus().then(setStatus).catch(() => setStatus(null));
  const refreshScans = () => fetchScans().then(setScans).catch(() => setScans([]));

  useEffect(() => {
    fetchCurrentUser().then(setUser);
    refreshStatus();
    refreshScans();
  }, []);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Bug className="size-6" /> Code Scan
          </h1>
          <p className="text-sm text-muted-foreground">
            Scan a connected repository for common security issues (Phase 1: Semgrep, Bandit, Gitleaks, Trivy).
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={refreshScans}>
          <RefreshCw className="size-3.5" /> Refresh
        </Button>
      </div>

      {canConnect(user) && status && <ConnectionSection status={status} onConnected={refreshStatus} />}

      <RunScanSection configured={!!status?.configured} onScanCreated={refreshScans} />

      <div className="mt-6">
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Scan history</h2>
        {scans.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {status?.configured ? "No scans yet — run one above." : "Connect GitHub to run your first scan."}
          </p>
        )}
        <div className="space-y-2">
          {scans.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setOpenScanId(s.id)}
              className="flex w-full items-center justify-between rounded-2xl border border-border bg-card p-4 text-left transition-colors hover:bg-muted/50"
            >
              <div>
                <p className="text-sm font-medium">{s.repo_full_name}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(s.created_at).toLocaleString()}
                  {s.triggered_by_email ? ` · ${s.triggered_by_email}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {s.status === "complete" && <FindingCountsRow counts={s.finding_counts} />}
                {statusBadge(s.status)}
              </div>
            </button>
          ))}
        </div>
      </div>

      {openScanId && <ScanDetailDialog scanId={openScanId} onClose={() => setOpenScanId(null)} />}
    </div>
  );
}
