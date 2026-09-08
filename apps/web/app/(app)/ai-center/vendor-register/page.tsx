"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, ShieldCheck, ShieldAlert, ShieldX, ShieldQuestion, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LogoPlaceholder } from "@/components/ui/logo-placeholder";
import { ChecklistAnswerFieldset, CHECKLIST_TIER_LABELS as TIER_LABELS } from "@/components/vendor/checklist-answer-fieldset";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  approveVendorRequest,
  fetchCurrentUser,
  fetchVendor,
  fetchVendorChecklistItems,
  fetchVendorRequests,
  fetchVendors,
  rejectVendorRequest,
  resolveLogoUrl,
  updateVendorChecklistResponses,
  updateVendorLogoUrl,
  uploadVendorLogo,
  type ChecklistAnswerValue,
  type CurrentUser,
  type Vendor,
  type VendorChecklistItem,
  type VendorDetail,
  type VendorRequest,
  type VendorType,
} from "@/lib/api";

const TYPE_LABELS: Record<VendorType, string> = { commercial: "Commercial", open_source: "Open source" };
const ANSWER_LABELS: Record<ChecklistAnswerValue, string> = {
  yes: "Yes",
  no: "No",
  partial: "Partial",
  not_applicable: "N/A",
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

function canManage(user: CurrentUser | null): boolean {
  return canApprove(user);
}

function statusBadge(status: string) {
  const styles: Record<string, { className: string; Icon: typeof ShieldCheck }> = {
    approved: { className: "bg-primary/10 text-primary", Icon: ShieldCheck },
    needs_review: { className: "bg-accent/15 text-accent", Icon: ShieldAlert },
    restricted: { className: "bg-destructive/10 text-destructive", Icon: ShieldX },
    pending: { className: "bg-muted text-muted-foreground", Icon: ShieldQuestion },
  };
  const s = styles[status] ?? styles.pending;
  const Icon = s.Icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium capitalize ${s.className}`}>
      <Icon className="size-3.5" /> {status.replace("_", " ")}
    </span>
  );
}

function VendorLogo({ vendor, className }: { vendor: Vendor; className?: string }) {
  const src = resolveLogoUrl(vendor.logo_url);
  if (!src) return <LogoPlaceholder name={vendor.name} className={className} />;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={vendor.name} className={`shrink-0 rounded-lg object-cover ${className ?? "h-8 w-8"}`} />;
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

export default function VendorRegisterPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [vendors, setVendors] = useState<Vendor[] | "loading">("loading");
  const [checklistItems, setChecklistItems] = useState<VendorChecklistItem[]>([]);
  const [myRequests, setMyRequests] = useState<VendorRequest[]>([]);
  const [pendingRequests, setPendingRequests] = useState<VendorRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [detailVendorId, setDetailVendorId] = useState<string | null>(null);
  const [viewRequestTarget, setViewRequestTarget] = useState<VendorRequest | null>(null);

  const itemsById = useMemo(() => {
    const map = new Map<string, VendorChecklistItem>();
    for (const item of checklistItems) map.set(item.id, item);
    return map;
  }, [checklistItems]);

  const refresh = () => {
    fetchVendors()
      .then(setVendors)
      .catch(() => setVendors([]));
    fetchVendorRequests({ mine: true })
      .then(setMyRequests)
      .catch(() => setMyRequests([]));
    if (canApprove(user)) {
      fetchVendorRequests()
        .then(setPendingRequests)
        .catch(() => setPendingRequests([]));
    }
  };

  useEffect(() => {
    fetchVendors()
      .then(setVendors)
      .catch(() => setVendors([]));
    fetchVendorChecklistItems()
      .then(setChecklistItems)
      .catch(() => setChecklistItems([]));
    fetchVendorRequests({ mine: true })
      .then(setMyRequests)
      .catch(() => setMyRequests([]));
    fetchCurrentUser().then((u) => {
      setUser(u);
      if (canApprove(u)) {
        fetchVendorRequests()
          .then(setPendingRequests)
          .catch(() => setPendingRequests([]));
      }
    });
  }, []);

  const handleApprove = async (request: VendorRequest) => {
    setBusy(true);
    setError(null);
    try {
      await approveVendorRequest(request.id);
      setViewRequestTarget(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async (request: VendorRequest) => {
    setBusy(true);
    setError(null);
    try {
      await rejectVendorRequest(request.id);
      setViewRequestTarget(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  if (vendors === "loading") {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  const commercial = vendors.filter((v) => v.type === "commercial");
  const openSource = vendors.filter((v) => v.type === "open_source");

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Vendor Register</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Commercial and open-source AI vendors scored against a fixed compliance checklist.
          </p>
        </div>
        <div className="flex gap-2">
          {canRequest(user) && (
            <Button onClick={() => router.push("/ai-center/vendor-register/request")}>
              <Plus /> Request Vendor
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

      <VendorSection title="Commercial vendors" vendors={commercial} onSelect={setDetailVendorId} />
      <VendorSection title="Open-source vendors" vendors={openSource} onSelect={setDetailVendorId} />

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
                  <span className="shrink-0 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {TYPE_LABELS[request.type]}
                  </span>
                  {request.projected_status && statusBadge(request.projected_status)}
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
                    <span className="shrink-0 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {TYPE_LABELS[request.type]}
                    </span>
                    {request.projected_status && statusBadge(request.projected_status)}
                  </div>
                  {requestStatusBadge(request.status)}
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      <VendorDetailDialog
        vendorId={detailVendorId}
        itemsById={itemsById}
        canManage={canManage(user)}
        onOpenChange={(open) => !open && setDetailVendorId(null)}
        onChanged={refresh}
      />
      <RequestDetailDialog
        request={viewRequestTarget}
        itemsById={itemsById}
        currentUser={user}
        busy={busy}
        onOpenChange={(open) => !open && setViewRequestTarget(null)}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </div>
  );
}

function VendorSection({
  title,
  vendors,
  onSelect,
}: {
  title: string;
  vendors: Vendor[];
  onSelect: (id: string) => void;
}) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold text-muted-foreground">{title}</h2>
      {vendors.length === 0 ? (
        <p className="text-sm text-muted-foreground">No vendors here yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {vendors.map((vendor) => (
            <button
              key={vendor.id}
              type="button"
              onClick={() => onSelect(vendor.id)}
              className="flex flex-col items-start gap-2 rounded-2xl border border-border bg-card p-4 text-left hover:bg-muted"
            >
              <div className="flex w-full items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <VendorLogo vendor={vendor} className="h-6 w-6" />
                  <span className="truncate text-sm font-medium">{vendor.name}</span>
                </span>
                {statusBadge(vendor.status)}
              </div>
              {vendor.category && <p className="text-xs text-muted-foreground">{vendor.category}</p>}
              {vendor.overall_score !== null && (
                <p className="text-xs text-muted-foreground">Score: {Math.round(vendor.overall_score * 100)}%</p>
              )}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function RequestDetailDialog({
  request,
  itemsById,
  currentUser,
  busy,
  onOpenChange,
  onApprove,
  onReject,
}: {
  request: VendorRequest | null;
  itemsById: Map<string, VendorChecklistItem>;
  currentUser: CurrentUser | null;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove: (request: VendorRequest) => void;
  onReject: (request: VendorRequest) => void;
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
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                {TYPE_LABELS[request.type]}
              </span>
              {requestStatusBadge(request.status)}
            </DialogTitle>
            <DialogDescription>
              Requested by {request.requested_by_email ?? "unknown"}
              {request.website_url && (
                <>
                  {" · "}
                  <a href={request.website_url} target="_blank" rel="noopener noreferrer" className="underline">
                    {request.website_url}
                  </a>
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="mb-4 space-y-1 text-sm">
            <p className="text-xs font-medium text-muted-foreground">Business justification</p>
            <p>{request.business_justification}</p>
          </div>

          {request.projected_status && (
            <div className="mb-4 flex items-center gap-2 text-sm">
              <span className="text-xs font-medium text-muted-foreground">Projected outcome:</span>
              {statusBadge(request.projected_status)}
              {request.overall_score !== null && (
                <span className="text-xs text-muted-foreground">({Math.round(request.overall_score * 100)}%)</span>
              )}
            </div>
          )}

          {request.checklist_responses.length > 0 && (
            <div className="max-h-72 space-y-2 overflow-y-auto">
              {request.checklist_responses.map((r) => {
                const item = itemsById.get(r.checklist_item_id);
                return (
                  <div key={r.checklist_item_id} className="rounded-lg border border-border p-2.5 text-sm">
                    <div className="flex items-start justify-between gap-2">
                      <span className="flex-1">{item?.question ?? r.checklist_item_id}</span>
                      <span className="shrink-0 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {ANSWER_LABELS[r.answer]}
                      </span>
                    </div>
                    {r.evidence_note && <p className="mt-1 text-xs text-muted-foreground">{r.evidence_note}</p>}
                  </div>
                );
              })}
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

function VendorDetailDialog({
  vendorId,
  itemsById,
  canManage,
  onOpenChange,
  onChanged,
}: {
  vendorId: string | null;
  itemsById: Map<string, VendorChecklistItem>;
  canManage: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged: () => void;
}) {
  const [vendor, setVendor] = useState<VendorDetail | null>(null);
  const [editing, setEditing] = useState<false | "logo" | "checklist">(false);

  useEffect(() => {
    if (vendorId) {
      queueMicrotask(() => setEditing(false));
      fetchVendor(vendorId)
        .then(setVendor)
        .catch(() => setVendor(null));
    } else {
      queueMicrotask(() => setVendor(null));
    }
  }, [vendorId]);

  const responseByItemId = useMemo(() => {
    const map = new Map<string, VendorDetail["checklist_responses"][number]>();
    for (const r of vendor?.checklist_responses ?? []) map.set(r.checklist_item_id, r);
    return map;
  }, [vendor]);

  const tiers: Array<"must_have" | "good_to_have" | "optional"> = ["must_have", "good_to_have", "optional"];
  const relevantItems = Array.from(itemsById.values())
    .filter((item) => item.applies_to === "both" || item.applies_to === vendor?.type)
    .sort((a, b) => a.sort_order - b.sort_order);

  return (
    <Dialog open={vendorId !== null} onOpenChange={onOpenChange}>
      {vendor && (
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <VendorLogo vendor={vendor} className="h-6 w-6" />
              {vendor.name}
              {statusBadge(vendor.status)}
            </DialogTitle>
            <DialogDescription>
              {TYPE_LABELS[vendor.type]}
              {vendor.overall_score !== null && ` · Score: ${Math.round(vendor.overall_score * 100)}%`}
            </DialogDescription>
          </DialogHeader>

          {editing === "logo" && (
            <VendorLogoEditForm
              vendor={vendor}
              onSaved={() => {
                setEditing(false);
                onChanged();
                fetchVendor(vendor.id)
                  .then(setVendor)
                  .catch(() => {});
              }}
              onCancel={() => setEditing(false)}
            />
          )}

          {editing === "checklist" && (
            <ChecklistEditForm
              vendor={vendor}
              items={relevantItems}
              responseByItemId={responseByItemId}
              onSaved={(updated) => {
                setEditing(false);
                onChanged();
                fetchVendor(vendor.id)
                  .then(setVendor)
                  .catch(() => {});
                void updated;
              }}
              onCancel={() => setEditing(false)}
            />
          )}

          {!editing && (
            <>
              <div className="max-h-96 space-y-4 overflow-y-auto">
                {tiers.map((tier) => {
                  const tierItems = relevantItems.filter((i) => i.tier === tier);
                  if (tierItems.length === 0) return null;
                  return (
                    <div key={tier}>
                      <p className="mb-1.5 text-xs font-medium text-muted-foreground">{TIER_LABELS[tier]}</p>
                      <div className="space-y-2">
                        {tierItems.map((item) => {
                          const response = responseByItemId.get(item.id);
                          return (
                            <div key={item.id} className="rounded-lg border border-border p-2.5 text-sm">
                              <div className="flex items-start justify-between gap-2">
                                <span className="flex-1">{item.question}</span>
                                <span className="shrink-0 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                                  {response ? ANSWER_LABELS[response.answer] : "Unanswered"}
                                </span>
                              </div>
                              {response?.evidence_note && (
                                <p className="mt-1 text-xs text-muted-foreground">{response.evidence_note}</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
              {canManage && (
                <DialogFooter>
                  <Button variant="outline" onClick={() => setEditing("logo")}>
                    Edit Logo
                  </Button>
                  <Button onClick={() => setEditing("checklist")}>Edit Checklist</Button>
                </DialogFooter>
              )}
            </>
          )}
        </DialogContent>
      )}
    </Dialog>
  );
}

function VendorLogoEditForm({
  vendor,
  onSaved,
  onCancel,
}: {
  vendor: VendorDetail;
  onSaved: (vendor: Vendor) => void;
  onCancel: () => void;
}) {
  const [logoUrl, setLogoUrl] = useState(vendor.logo_url ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const updated = await uploadVendorLogo(vendor.id, file);
      setLogoUrl(updated.logo_url ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload logo.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      {error && (
        <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      <div className="flex items-center gap-3">
        <VendorLogo vendor={{ ...vendor, logo_url: logoUrl || null }} className="h-10 w-10" />
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/svg+xml"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) handleUpload(file);
          }}
        />
        <Button type="button" variant="outline" size="sm" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
          <Upload className="size-3.5" /> {uploading ? "Uploading..." : "Upload"}
        </Button>
      </div>
      <Input
        className="mt-2"
        value={logoUrl}
        onChange={(e) => setLogoUrl(e.target.value)}
        placeholder="Or paste a logo URL directly"
      />
      <DialogFooter>
        <Button variant="outline" disabled={submitting} onClick={onCancel}>
          Cancel
        </Button>
        <Button
          disabled={submitting}
          onClick={async () => {
            setSubmitting(true);
            setError(null);
            try {
              const updated = await updateVendorLogoUrl(vendor.id, logoUrl.trim() || null);
              onSaved(updated);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Something went wrong.");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          Save
        </Button>
      </DialogFooter>
    </>
  );
}

function ChecklistEditForm({
  vendor,
  items,
  responseByItemId,
  onSaved,
  onCancel,
}: {
  vendor: VendorDetail;
  items: VendorChecklistItem[];
  responseByItemId: Map<string, VendorDetail["checklist_responses"][number]>;
  onSaved: (vendor: Vendor) => void;
  onCancel: () => void;
}) {
  const [answers, setAnswers] = useState<Record<string, ChecklistAnswerValue>>(() => {
    const initial: Record<string, ChecklistAnswerValue> = {};
    for (const item of items) {
      initial[item.id] = responseByItemId.get(item.id)?.answer ?? "not_applicable";
    }
    return initial;
  });
  const [notes, setNotes] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const item of items) {
      initial[item.id] = responseByItemId.get(item.id)?.evidence_note ?? "";
    }
    return initial;
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <>
      {error && (
        <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      <ChecklistAnswerFieldset
        items={items}
        answers={answers}
        notes={notes}
        onAnswerChange={(itemId, answer) => setAnswers((prev) => ({ ...prev, [itemId]: answer }))}
        onNoteChange={(itemId, note) => setNotes((prev) => ({ ...prev, [itemId]: note }))}
      />
      <DialogFooter>
        <Button variant="outline" disabled={submitting} onClick={onCancel}>
          Cancel
        </Button>
        <Button
          disabled={submitting}
          onClick={async () => {
            setSubmitting(true);
            setError(null);
            try {
              const responses = items.map((item) => ({
                checklist_item_id: item.id,
                answer: answers[item.id],
                evidence_note: notes[item.id]?.trim() || null,
              }));
              const updated = await updateVendorChecklistResponses(vendor.id, responses);
              onSaved(updated);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Something went wrong.");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          Save & Rescore
        </Button>
      </DialogFooter>
    </>
  );
}
