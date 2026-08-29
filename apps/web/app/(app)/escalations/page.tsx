"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Paperclip, Plus, UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
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
  createEscalation,
  fetchCurrentUser,
  fetchEscalations,
  getEscalationAttachmentUrl,
  updateEscalation,
  type CurrentUser,
  type Escalation,
  type EscalationCategory,
  type EscalationStatus,
} from "@/lib/api";

const CATEGORY_LABELS: Record<EscalationCategory, string> = {
  policy_violation: "Policy violation",
  unapproved_tool_use: "Unapproved tool use",
  data_exposure_concern: "Data exposure concern",
  other: "Other",
};

const STATUS_LABELS: Record<EscalationStatus, string> = {
  open: "Open",
  in_review: "In review",
  resolved: "Resolved",
};

function canManage(user: CurrentUser | null): boolean {
  return !!user && (["govern", "assure"].includes(user.business_role) || ["admin", "super_admin"].includes(user.system_role));
}

function statusBadge(status: EscalationStatus) {
  const styles: Record<EscalationStatus, string> = {
    open: "bg-destructive/10 text-destructive",
    in_review: "bg-secondary text-secondary-foreground",
    resolved: "bg-primary/10 text-primary",
  };
  return <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${styles[status]}`}>{STATUS_LABELS[status]}</span>;
}

function AttachmentLink({ alert }: { alert: Escalation }) {
  if (!alert.has_attachment) return null;
  return (
    <button
      type="button"
      onClick={async () => {
        const url = await getEscalationAttachmentUrl(alert.id);
        window.open(url, "_blank", "noopener,noreferrer");
      }}
      className="mt-1 flex items-center gap-1 text-xs text-primary hover:underline"
    >
      <Paperclip className="size-3.5" /> {alert.attachment_filename ?? "Attachment"}
    </button>
  );
}

type Tab = "current" | "resolved";

export default function EscalationsPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [tab, setTab] = useState<Tab>("current");
  const [current, setCurrent] = useState<Escalation[]>([]);
  const [resolved, setResolved] = useState<Escalation[]>([]);
  const [raiseOpen, setRaiseOpen] = useState(false);
  const [respondTarget, setRespondTarget] = useState<Escalation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshCurrent = () => fetchEscalations({ resolved: false }).then(setCurrent).catch(() => setCurrent([]));
  const refreshResolved = () => fetchEscalations({ resolved: true }).then(setResolved).catch(() => setResolved([]));

  useEffect(() => {
    fetchCurrentUser().then(setUser);
    refreshCurrent();
    refreshResolved();
  }, []);

  const refreshAll = () => {
    refreshCurrent();
    refreshResolved();
  };

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Raise Alert</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Report a concern about AI use. Alerts are fully anonymous - no one, including your governance team,
            can see who raised one.
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setRaiseOpen(true)}>
            <Plus /> Raise an Alert
          </Button>
          <Button variant="outline" onClick={refreshAll}>
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="mb-6 flex gap-1 border-b border-border">
        <button
          type="button"
          onClick={() => setTab("current")}
          className={`px-3 py-2 text-sm font-medium transition ${
            tab === "current" ? "border-b-2 border-primary text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Current Escalations{current.length > 0 ? ` (${current.length})` : ""}
        </button>
        <button
          type="button"
          onClick={() => setTab("resolved")}
          className={`px-3 py-2 text-sm font-medium transition ${
            tab === "resolved" ? "border-b-2 border-primary text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Resolved Escalations{resolved.length > 0 ? ` (${resolved.length})` : ""}
        </button>
      </div>

      {tab === "current" && (
        <section>
          {current.length === 0 ? (
            <p className="text-sm text-muted-foreground">No open escalations right now.</p>
          ) : (
            <div className="space-y-3">
              {current.map((alert) => (
                <div key={alert.id} className="rounded-2xl border border-border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                          {CATEGORY_LABELS[alert.category]}
                        </span>
                        {statusBadge(alert.status)}
                      </div>
                      <p className="mt-2 text-sm">{alert.description}</p>
                      <AttachmentLink alert={alert} />
                    </div>
                    {canManage(user) && (
                      <div className="flex shrink-0 items-center gap-2">
                        {alert.assigned_to !== user?.id && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={async () => {
                              setBusy(true);
                              setError(null);
                              try {
                                await updateEscalation(alert.id, { assigned_to: user?.id });
                                refreshAll();
                              } catch (err) {
                                setError(err instanceof Error ? err.message : "Something went wrong.");
                              } finally {
                                setBusy(false);
                              }
                            }}
                          >
                            <UserPlus /> Assign to me
                          </Button>
                        )}
                        <Button size="sm" onClick={() => setRespondTarget(alert)}>
                          Respond
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {tab === "resolved" && (
        <section>
          {resolved.length === 0 ? (
            <p className="text-sm text-muted-foreground">No escalations have been resolved yet.</p>
          ) : (
            <div className="space-y-3">
              {resolved.map((alert) => (
                <div key={alert.id} className="rounded-2xl border border-border bg-card p-4">
                  <div className="flex items-center gap-2">
                    <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {CATEGORY_LABELS[alert.category]}
                    </span>
                    {statusBadge(alert.status)}
                  </div>
                  <p className="mt-2 text-sm">{alert.description}</p>
                  <AttachmentLink alert={alert} />
                  <p className="mt-2 rounded-lg bg-muted/60 p-2.5 text-sm">
                    <span className="font-medium text-foreground">Resolution:</span> {alert.resolution_note}
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <RaiseAlertDialog open={raiseOpen} onOpenChange={setRaiseOpen} onSubmitted={refreshAll} setError={setError} />
      <RespondDialog
        alert={respondTarget}
        onOpenChange={(open) => !open && setRespondTarget(null)}
        onSaved={refreshAll}
      />
    </div>
  );
}

function RaiseAlertDialog({
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
  const [category, setCategory] = useState<EscalationCategory>("other");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setCategory("other");
    setDescription("");
    setFile(null);
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
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="size-4 text-destructive" /> Raise an Alert
          </DialogTitle>
          <DialogDescription>
            Describe your concern - it&apos;s completely anonymous. Nothing here is linked back to your account.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <Label className="mb-1.5 block text-xs">Category</Label>
            <Select value={category} onChange={(e) => setCategory(e.target.value as EscalationCategory)}>
              <option value="policy_violation">Policy violation</option>
              <option value="unapproved_tool_use">Unapproved tool use</option>
              <option value="data_exposure_concern">Data exposure concern</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div>
            <Label className="mb-1.5 block text-xs">Description</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs">Supporting document (optional)</Label>
            <input
              type="file"
              accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-lg file:border file:border-border file:bg-background file:px-2.5 file:py-1 file:text-sm file:font-medium file:text-foreground hover:file:bg-muted"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Avoid attaching anything that could identify you (e.g. a file named after you).
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            disabled={submitting || !description.trim()}
            onClick={async () => {
              setSubmitting(true);
              try {
                await createEscalation(category, description, file);
                reset();
                onOpenChange(false);
                onSubmitted();
              } catch (err) {
                setError(err instanceof Error ? err.message : "Something went wrong.");
                onOpenChange(false);
              } finally {
                setSubmitting(false);
              }
            }}
          >
            Submit Alert
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RespondDialog({
  alert,
  onOpenChange,
  onSaved,
}: {
  alert: Escalation | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [status, setStatus] = useState<EscalationStatus>("in_review");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (alert) {
      queueMicrotask(() => {
        setStatus(alert.status === "open" ? "in_review" : alert.status);
        setNote(alert.resolution_note ?? "");
        setLocalError(null);
      });
    }
  }, [alert]);

  return (
    <Dialog open={alert !== null} onOpenChange={onOpenChange}>
      {alert && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Respond to Alert</DialogTitle>
            <DialogDescription>{alert.description}</DialogDescription>
          </DialogHeader>

          {alert.has_attachment && (
            <div className="mb-3">
              <AttachmentLink alert={alert} />
            </div>
          )}

          {localError && (
            <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {localError}
            </div>
          )}

          <div className="space-y-3">
            <div>
              <Label className="mb-1.5 block text-xs">Status</Label>
              <Select value={status} onChange={(e) => setStatus(e.target.value as EscalationStatus)}>
                <option value="open">Open</option>
                <option value="in_review">In review</option>
                <option value="resolved">Resolved</option>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">
                Note{status === "resolved" ? " (required — visible to everyone once resolved)" : " (optional)"}
              </Label>
              <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} />
            </div>
          </div>

          <DialogFooter>
            <Button
              disabled={submitting || (status === "resolved" && !note.trim())}
              onClick={async () => {
                setSubmitting(true);
                setLocalError(null);
                try {
                  await updateEscalation(alert.id, { status, resolution_note: note || undefined });
                  onOpenChange(false);
                  onSaved();
                } catch (err) {
                  setLocalError(err instanceof Error ? err.message : "Something went wrong.");
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
