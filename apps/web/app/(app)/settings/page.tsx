"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  createSsoConnection,
  fetchAdminBrandingConfig,
  fetchBrandingConfig,
  fetchCurrentUser,
  fetchLicenseStatus,
  fetchOrgUsers,
  fetchSsoConnectionStatus,
  updateBrandingConfig,
  updateUserRole,
  type BrandingConfig,
  type CurrentUser,
  type LicenseStatus,
  type OrgUser,
  type PublicBrandingConfig,
  type SsoConnectionStatus,
} from "@/lib/api";

const BUSINESS_ROLES = ["govern", "assure", "operator"] as const;
const ASSIGNABLE_SYSTEM_ROLES = ["user", "admin"] as const;

const DEFAULT_ESCALATION_TEMPLATE = {
  subject: "[Q Tower] New escalation: {{category}}",
  body: "{{reporter_email}} raised a new escalation.\n\nCategory: {{category}}\n\n{{description}}",
};

// Kept in sync with tools/prompts.py::DEFAULT_TOOL_ASSESSMENT_PROMPT -
// this is only the fallback shown before a saved override loads (or after
// "Reset to default"); the backend is the actual source of truth used at
// assessment time.
const DEFAULT_TOOL_ASSESSMENT_PROMPT = `You are being given a carefully structured prompt. Follow it precisely.

## Role
You are AI co-ordinator of organization

## Task
Your task is to look at the following {{request}}, analyze it with respect to ai policy set by organization and give a pre approval evaluation to approver so they can make easy decision.
Your analysis should include and be limited to just 2 things. Request classification and rational behind classification.
Request should be classified into one of 3 categories, approvable, needs review, unapprovable.

## Action
1. Look at the following {{request}}.
2. {{request}} contains name of tool, feature or webextension and an intended use case.
3. Draw on your general knowledge of this tool, feature, or extension.
4. Evaluate the {{request}} against the organization policy available under {{ai_policy}}.
5. Based on your evaluation classify the requested tool, feature or web extension for defined use case under one of the ["Approvable", "Need Review", "Unapprovable"].
6. Present your rational or justification for classification as well

## Expected output
Respond with exactly this JSON shape - no other keys, no text outside the JSON object:
{"classification": "<Approvable|Need Review|Unapprovable>", "rational": "<your justification, under 300 words>"}

## constraints
1. Always follow the above instruction do no deviate
2. "request_classification" should always be one of following ["Approvable", "Need Review", "Unapprovable"]
3. "classification_rational" should be less than 300 words
4. Please format your response as valid JSON.
5. Think carefully about the request before responding. Consider edge cases and nuances.

## {{request}} = "concat request body"
`;

function canManageBranding(user: CurrentUser | null): boolean {
  return !!user && ["admin", "super_admin"].includes(user.system_role);
}

function canManageSso(user: CurrentUser | null): boolean {
  return !!user && ["admin", "super_admin"].includes(user.system_role);
}

function canManageUsers(user: CurrentUser | null): boolean {
  return !!user && ["admin", "super_admin"].includes(user.system_role);
}

export default function SettingsPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .finally(() => setLoaded(true));
  }, []);

  if (!loaded) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  const showBranding = canManageBranding(user);
  const showSso = canManageSso(user);
  const showUsers = canManageUsers(user);

  if (!showBranding && !showSso && !showUsers) {
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You don&apos;t have access to any settings sections.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <p className="mt-1 text-sm text-muted-foreground">Deployment configuration.</p>

      {showBranding && (
        <>
          <BrandingSection />
          <EmailTemplatesSection />
          <AiPrecheckPromptSection />
          <LicenseSection />
        </>
      )}
      {showSso && <SsoSection />}
      {showUsers && <ManageUsersSection />}
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-sm font-semibold text-muted-foreground">{title}</h2>
      <div className="rounded-2xl border border-border bg-card p-4">{children}</div>
    </section>
  );
}

function BrandingSection() {
  const [config, setConfig] = useState<PublicBrandingConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchBrandingConfig().then(setConfig);
  }, []);

  if (!config) return <SectionCard title="Branding">Loading...</SectionCard>;

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateBrandingConfig({
        org_display_name: config.org_display_name,
        logo_url: config.logo_url,
      });
      setConfig(updated);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard title="Branding">
      <div className="space-y-3">
        <div>
          <Label className="mb-1.5 block text-xs">Organization display name</Label>
          <Input
            value={config.org_display_name ?? ""}
            onChange={(e) => setConfig({ ...config, org_display_name: e.target.value || null })}
          />
        </div>
        <div>
          <Label className="mb-1.5 block text-xs">Logo URL</Label>
          <Input
            value={config.logo_url ?? ""}
            onChange={(e) => setConfig({ ...config, logo_url: e.target.value || null })}
          />
        </div>
        <div className="flex items-center gap-3 pt-1">
          <Button size="sm" disabled={saving} onClick={save}>
            Save
          </Button>
          {saved && <span className="text-xs text-muted-foreground">Saved.</span>}
        </div>
      </div>
    </SectionCard>
  );
}

function EmailTemplatesSection() {
  const [config, setConfig] = useState<BrandingConfig | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchAdminBrandingConfig().then((c) => {
      setConfig(c);
      const override = c?.email_templates?.escalation_raised;
      setSubject(override?.subject ?? DEFAULT_ESCALATION_TEMPLATE.subject);
      setBody(override?.body ?? DEFAULT_ESCALATION_TEMPLATE.body);
    });
  }, []);

  if (!config) return <SectionCard title="Email templates">Loading...</SectionCard>;

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateBrandingConfig({
        email_templates: { ...(config.email_templates ?? {}), escalation_raised: { subject, body } },
      });
      setConfig(updated);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  const resetToDefault = () => {
    setSubject(DEFAULT_ESCALATION_TEMPLATE.subject);
    setBody(DEFAULT_ESCALATION_TEMPLATE.body);
  };

  return (
    <SectionCard title="Email templates">
      <p className="mb-3 text-sm font-medium">Escalation raised</p>
      <div className="space-y-3">
        <div>
          <Label className="mb-1.5 block text-xs">Subject</Label>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </div>
        <div>
          <Label className="mb-1.5 block text-xs">Body</Label>
          <Textarea rows={4} value={body} onChange={(e) => setBody(e.target.value)} />
        </div>
        <p className="text-xs text-muted-foreground">
          Available placeholders: <code>{"{{reporter_email}}"}</code>, <code>{"{{category}}"}</code>,{" "}
          <code>{"{{description}}"}</code>
        </p>
        <div className="flex items-center gap-3 pt-1">
          <Button size="sm" disabled={saving} onClick={save}>
            Save
          </Button>
          <Button size="sm" variant="outline" disabled={saving} onClick={resetToDefault}>
            Reset to default
          </Button>
          {saved && <span className="text-xs text-muted-foreground">Saved.</span>}
        </div>
      </div>
    </SectionCard>
  );
}

function AiPrecheckPromptSection() {
  const [config, setConfig] = useState<BrandingConfig | null>(null);
  const [prompt, setPrompt] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchAdminBrandingConfig().then((c) => {
      setConfig(c);
      setPrompt(c?.tool_assessment_prompt ?? DEFAULT_TOOL_ASSESSMENT_PROMPT);
    });
  }, []);

  if (!config) return <SectionCard title="AI Precheck Prompt">Loading...</SectionCard>;

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateBrandingConfig({ tool_assessment_prompt: prompt });
      setConfig(updated);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <SectionCard title="AI Precheck Prompt">
      <p className="mb-3 text-sm text-muted-foreground">
        Sent to the AI when a new AI Tools request is submitted, to pre-classify it for the human approver. Only
        runs when an AI Policy is currently active.
      </p>
      <div className="space-y-3">
        <div>
          <Label className="mb-1.5 block text-xs">Prompt</Label>
          <Textarea rows={16} className="font-mono text-xs" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </div>
        <p className="text-xs text-muted-foreground">
          Available placeholders: <code>{"{{request}}"}</code> (type/name/link/use case), <code>{"{{ai_policy}}"}</code>{" "}
          (the active policy&apos;s text).
        </p>
        <div className="flex items-center gap-3 pt-1">
          <Button size="sm" disabled={saving} onClick={save}>
            Save
          </Button>
          <Button size="sm" variant="outline" disabled={saving} onClick={() => setPrompt(DEFAULT_TOOL_ASSESSMENT_PROMPT)}>
            Reset to default
          </Button>
          {saved && <span className="text-xs text-muted-foreground">Saved.</span>}
        </div>
      </div>
    </SectionCard>
  );
}

function LicenseSection() {
  const [status, setStatus] = useState<LicenseStatus | null>(null);

  useEffect(() => {
    fetchLicenseStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status) return <SectionCard title="License">Loading...</SectionCard>;

  return (
    <SectionCard title="License">
      <div className="space-y-1.5 text-sm">
        <p>
          Status:{" "}
          <span className={status.license_valid ? "font-medium text-primary" : "font-medium text-destructive"}>
            {status.license_valid ? "Valid" : "Invalid"}
          </span>
        </p>
        <p className="text-muted-foreground">Seats: {status.license_seat_count ?? "—"}</p>
        <p className="text-muted-foreground">
          Expires: {status.license_expires_at ? new Date(status.license_expires_at).toLocaleDateString() : "—"}
        </p>
        <p className="text-muted-foreground">
          Last validated:{" "}
          {status.license_validated_at ? new Date(status.license_validated_at).toLocaleString() : "—"}
        </p>
      </div>
    </SectionCard>
  );
}

function SsoSection() {
  const [status, setStatus] = useState<SsoConnectionStatus | null>(null);
  const [metadataUrl, setMetadataUrl] = useState("");
  const [metadataXml, setMetadataXml] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    fetchSsoConnectionStatus()
      .then(setStatus)
      .catch(() => setStatus(null));

  useEffect(() => {
    refresh();
  }, []);

  if (!status) return <SectionCard title="SSO connection">Loading...</SectionCard>;

  return (
    <SectionCard title="SSO connection">
      <p className="mb-3 text-sm">
        Status:{" "}
        {status.configured ? (
          <span className="font-medium text-primary">
            Configured ({status.connection_type}
            {status.created_at ? `, since ${new Date(status.created_at).toLocaleDateString()}` : ""})
          </span>
        ) : (
          <span className="font-medium text-muted-foreground">Not configured</span>
        )}
      </p>
      <p className="mb-3 text-xs text-muted-foreground">
        Replacing the connection switches every future login to the new IdP - existing
        users tied to the old one won&apos;t be able to sign in fresh afterward.
      </p>
      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
      <div className="space-y-3">
        <div>
          <Label className="mb-1.5 block text-xs">IdP metadata URL</Label>
          <Input
            placeholder="https://..."
            value={metadataUrl}
            onChange={(e) => {
              setMetadataUrl(e.target.value);
              if (e.target.value) setMetadataXml("");
            }}
          />
        </div>
        <div>
          <Label className="mb-1.5 block text-xs">
            Or paste IdP metadata XML (for IdPs that only offer a downloadable file, e.g. Google Workspace)
          </Label>
          <Textarea
            rows={4}
            className="font-mono text-xs"
            placeholder="<EntityDescriptor ...>"
            value={metadataXml}
            onChange={(e) => {
              setMetadataXml(e.target.value);
              if (e.target.value) setMetadataUrl("");
            }}
          />
        </div>
        <Button
          size="sm"
          disabled={saving || (!metadataUrl.trim() && !metadataXml.trim())}
          onClick={async () => {
            setSaving(true);
            setError(null);
            try {
              await createSsoConnection({ metadataUrl: metadataUrl.trim(), metadataXml: metadataXml.trim() });
              setMetadataUrl("");
              setMetadataXml("");
              await refresh();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Failed to save connection.");
            } finally {
              setSaving(false);
            }
          }}
        >
          Save connection
        </Button>
      </div>
    </SectionCard>
  );
}

function ManageUsersSection() {
  const [users, setUsers] = useState<OrgUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, { business_role: string; system_role: string }>>({});

  const refresh = () =>
    fetchOrgUsers()
      .then((list) => {
        setUsers(list);
        setDrafts(
          Object.fromEntries(list.map((u) => [u.id, { business_role: u.business_role, system_role: u.system_role }]))
        );
      })
      .catch(() => setUsers([]));

  useEffect(() => {
    refresh();
  }, []);

  if (!users) return <SectionCard title="Manage Users">Loading...</SectionCard>;

  return (
    <SectionCard title="Manage Users">
      <p className="mb-3 text-xs text-muted-foreground">
        Governs what each person can see and approve. &quot;Synced&quot; roles came from an
        SSO group mapping; &quot;manual&quot; roles were set here and won&apos;t be
        overwritten by a future sync.
      </p>
      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
      <div className="space-y-2">
        {users.map((u) => {
          const draft = drafts[u.id] ?? { business_role: u.business_role, system_role: u.system_role };
          const dirty = draft.business_role !== u.business_role || draft.system_role !== u.system_role;
          const isSuperAdmin = u.system_role === "super_admin";
          return (
            <div key={u.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3">
              <span className="min-w-0 flex-1 truncate text-sm">{u.email}</span>
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {u.role_source}
              </span>
              {isSuperAdmin ? (
                <span className="text-xs text-muted-foreground">super_admin (break-glass account)</span>
              ) : (
                <>
                  <Select
                    className="w-32"
                    value={draft.business_role}
                    onChange={(e) => setDrafts((d) => ({ ...d, [u.id]: { ...draft, business_role: e.target.value } }))}
                  >
                    {BUSINESS_ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </Select>
                  <Select
                    className="w-28"
                    value={draft.system_role}
                    onChange={(e) => setDrafts((d) => ({ ...d, [u.id]: { ...draft, system_role: e.target.value } }))}
                  >
                    {ASSIGNABLE_SYSTEM_ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </Select>
                  <Button
                    size="sm"
                    disabled={!dirty || savingId === u.id}
                    onClick={async () => {
                      setSavingId(u.id);
                      setError(null);
                      try {
                        await updateUserRole(u.id, draft.business_role, draft.system_role);
                        await refresh();
                      } catch (err) {
                        setError(err instanceof Error ? err.message : "Failed to update role.");
                      } finally {
                        setSavingId(null);
                      }
                    }}
                  >
                    Save
                  </Button>
                </>
              )}
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}
