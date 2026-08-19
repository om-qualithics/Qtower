export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) {
    throw new Error(`API health check failed: ${res.status}`);
  }
  return res.json();
}

export type CurrentUser = {
  id: string;
  email: string;
  business_role: string;
  system_role: string;
};

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const res = await fetch(`${API_BASE_URL}/identity/me`, { credentials: "include" });
  if (res.status === 401) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch current user: ${res.status}`);
  }
  return res.json();
}

export function loginUrl(): string {
  return `${API_BASE_URL}/identity/login`;
}

export type BrandingConfig = {
  org_display_name: string | null;
  logo_url: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  enabled_feature_modules: string[] | null;
};

export async function fetchBrandingConfig(): Promise<BrandingConfig | null> {
  const res = await fetch(`${API_BASE_URL}/branding/config`);
  if (!res.ok) {
    return null;
  }
  return res.json();
}

// --- AI Policy builder ---

export type Option = { value: string; label: string; checked_by_default: boolean };
export type Column = { key: string; label: string };

export type QuestionType = "checklist" | "single_select" | "text" | "table";

export type Question = {
  key: string;
  type: QuestionType;
  label: string;
  required: boolean;
  options: Option[];
  allow_other: boolean;
  category: string | null;
  columns: Column[];
  initial_rows: Record<string, string>[];
  addable: boolean;
  locked_rows: boolean;
};

export type PolicyStep = { id: number; title: string; questions: Question[] };

export type ChecklistAnswer = { selected: string[]; other: string[] };
export type TableAnswer = { rows: Record<string, string>[] };
export type SingleSelectAnswer = { selected: string | null };
export type TextAnswer = { value: string };
export type AnswerValue = ChecklistAnswer | TableAnswer | SingleSelectAnswer | TextAnswer;
export type Answers = Record<string, AnswerValue>;

export type PolicyStatus = "draft" | "active" | "archived";
export type PolicySource = "builder" | "upload";

export type Policy = {
  id: string;
  status: PolicyStatus;
  source: PolicySource;
  has_document: boolean;
  current_step: number;
  version: number;
  policy_owner_name: string | null;
  approver_name: string | null;
  answers: Answers;
  created_by: string | null;
  generated_at: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PolicyListItem = Omit<Policy, "answers" | "approver_name">;

export class PolicyGenerateValidationError extends Error {
  missingRequired: string[];
  constructor(missingRequired: string[]) {
    super("Policy is missing required answers");
    this.missingRequired = missingRequired;
  }
}

export class PermissionDeniedError extends Error {
  constructor() {
    super(
      "Your account doesn't have permission to do that. Ask an org admin to grant you the " +
        "right AI Policy role, or sign in with an account that already has it."
    );
  }
}

async function throwIfNotOk(res: Response, action: string): Promise<void> {
  if (res.ok) return;
  if (res.status === 403) {
    throw new PermissionDeniedError();
  }
  throw new Error(`${action}: ${res.status}`);
}

export async function fetchPolicySteps(): Promise<PolicyStep[]> {
  const res = await fetch(`${API_BASE_URL}/policy/questions`, { credentials: "include" });
  await throwIfNotOk(res, "Failed to fetch policy questions");
  return res.json();
}

export async function listPolicies(): Promise<PolicyListItem[]> {
  const res = await fetch(`${API_BASE_URL}/policy/`, { credentials: "include" });
  await throwIfNotOk(res, "Failed to list policies");
  return res.json();
}

export async function createPolicy(): Promise<Policy> {
  const res = await fetch(`${API_BASE_URL}/policy/`, { method: "POST", credentials: "include" });
  await throwIfNotOk(res, "Failed to create policy");
  return res.json();
}

export async function getPolicy(id: string): Promise<Policy> {
  const res = await fetch(`${API_BASE_URL}/policy/${id}`, { credentials: "include" });
  await throwIfNotOk(res, "Failed to fetch policy");
  return res.json();
}

export async function savePolicyStep(id: string, step: number, answers: Answers): Promise<Policy> {
  const res = await fetch(`${API_BASE_URL}/policy/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step, answers }),
  });
  await throwIfNotOk(res, "Failed to save policy step");
  return res.json();
}

export async function generatePolicy(id: string): Promise<Policy> {
  const res = await fetch(`${API_BASE_URL}/policy/${id}/generate`, {
    method: "POST",
    credentials: "include",
  });
  if (res.status === 400) {
    const body = await res.json();
    throw new PolicyGenerateValidationError(body.detail?.missing_required ?? []);
  }
  await throwIfNotOk(res, "Failed to generate policy");
  return res.json();
}

export async function approvePolicy(id: string): Promise<Policy> {
  const res = await fetch(`${API_BASE_URL}/policy/${id}/approve`, {
    method: "POST",
    credentials: "include",
  });
  await throwIfNotOk(res, "Failed to approve policy");
  return res.json();
}

export async function uploadPolicy(file: File): Promise<Policy> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/policy/upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (res.status === 400) {
    const body = await res.json();
    throw new Error(body.detail ?? "Failed to upload policy");
  }
  await throwIfNotOk(res, "Failed to upload policy");
  return res.json();
}

export async function getPolicyDownloadUrl(id: string): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/policy/${id}/download`, { credentials: "include" });
  await throwIfNotOk(res, "Failed to get download link");
  const body = await res.json();
  return body.download_url;
}

// --- AI Tools ---

export type ToolRequestType = "tool" | "feature" | "webextension";
export type ToolRequestStatus = "pending" | "approved" | "rejected";
export type ToolAssessmentStatus = "pending" | "complete" | "failed";
export type ToolAssessmentResult = "approvable" | "needs_review" | "cannot_approve";

export type ApprovedTool = {
  id: string;
  name: string;
  description: string;
  source_type: ToolRequestType;
  access_url: string;
  allowed_tiers: string[];
  details: string | null;
  created_at: string;
};

export type ToolRequest = {
  id: string;
  request_type: ToolRequestType;
  name: string;
  link: string;
  intended_use_case: string;
  status: ToolRequestStatus;
  ai_assessment_status: ToolAssessmentStatus;
  ai_assessment_result: ToolAssessmentResult | null;
  ai_assessment_explanation: string | null;
  requested_by: string;
  requested_by_email: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  resulting_tool_id: string | null;
  created_at: string;
  updated_at: string;
};

export class ToolRequestDuplicateError extends Error {}

export async function fetchApprovedTools(): Promise<ApprovedTool[]> {
  const res = await fetch(`${API_BASE_URL}/tools/approved`, { credentials: "include" });
  await throwIfNotOk(res, "Failed to fetch approved tools");
  return res.json();
}

export async function createToolRequest(
  requestType: ToolRequestType,
  name: string,
  link: string,
  intendedUseCase: string
): Promise<ToolRequest> {
  const res = await fetch(`${API_BASE_URL}/tools/requests`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_type: requestType, name, link, intended_use_case: intendedUseCase }),
  });
  if (res.status === 400) {
    const body = await res.json();
    throw new ToolRequestDuplicateError(body.detail ?? "This request could not be created");
  }
  await throwIfNotOk(res, "Failed to submit tool request");
  return res.json();
}

export async function fetchToolRequests(options: { mine?: boolean } = {}): Promise<ToolRequest[]> {
  const params = options.mine ? "?mine=true" : "";
  const res = await fetch(`${API_BASE_URL}/tools/requests${params}`, { credentials: "include" });
  await throwIfNotOk(res, "Failed to fetch tool requests");
  return res.json();
}

export async function approveToolRequest(
  id: string,
  description: string,
  allowedTiers: string[]
): Promise<ToolRequest> {
  const res = await fetch(`${API_BASE_URL}/tools/requests/${id}/approve`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, allowed_tiers: allowedTiers }),
  });
  if (res.status === 400) {
    const body = await res.json();
    throw new Error(body.detail ?? "Failed to approve request");
  }
  await throwIfNotOk(res, "Failed to approve request");
  return res.json();
}

export async function updateApprovedTool(
  id: string,
  name: string,
  description: string,
  accessUrl: string,
  allowedTiers: string[]
): Promise<ApprovedTool> {
  const res = await fetch(`${API_BASE_URL}/tools/approved/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, access_url: accessUrl, allowed_tiers: allowedTiers }),
  });
  await throwIfNotOk(res, "Failed to update tool");
  return res.json();
}

export async function deleteApprovedTool(id: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/tools/approved/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  await throwIfNotOk(res, "Failed to delete tool");
}

export async function rejectToolRequest(id: string, reason?: string): Promise<ToolRequest> {
  const res = await fetch(`${API_BASE_URL}/tools/requests/${id}/reject`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason ?? null }),
  });
  if (res.status === 400) {
    const body = await res.json();
    throw new Error(body.detail ?? "Failed to reject request");
  }
  await throwIfNotOk(res, "Failed to reject request");
  return res.json();
}

// --- Escalations ---

export type EscalationCategory = "policy_violation" | "unapproved_tool_use" | "data_exposure_concern" | "other";
export type EscalationStatus = "open" | "in_review" | "resolved";

export type Escalation = {
  id: string;
  category: EscalationCategory;
  description: string;
  related_tool_request_id: string | null;
  related_policy_id: string | null;
  status: EscalationStatus;
  reporter_id: string;
  reporter_email: string | null;
  assigned_to: string | null;
  resolution_note: string | null;
  has_attachment: boolean;
  attachment_filename: string | null;
  created_at: string;
  updated_at: string;
};

export async function createEscalation(
  category: EscalationCategory,
  description: string,
  file?: File | null
): Promise<Escalation> {
  const formData = new FormData();
  formData.append("category", category);
  formData.append("description", description);
  if (file) formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/escalations/`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (res.status === 400) {
    const body = await res.json();
    throw new Error(body.detail ?? "Failed to submit escalation");
  }
  await throwIfNotOk(res, "Failed to submit escalation");
  return res.json();
}

export async function getEscalationAttachmentUrl(id: string): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/escalations/${id}/attachment`, { credentials: "include" });
  await throwIfNotOk(res, "Failed to get attachment link");
  const body = await res.json();
  return body.download_url;
}

export async function fetchEscalations(options: { mine?: boolean } = {}): Promise<Escalation[]> {
  const params = options.mine ? "?mine=true" : "";
  const res = await fetch(`${API_BASE_URL}/escalations/${params}`, { credentials: "include" });
  await throwIfNotOk(res, "Failed to fetch escalations");
  return res.json();
}

export async function updateEscalation(
  id: string,
  updates: { status?: EscalationStatus; assigned_to?: string; resolution_note?: string }
): Promise<Escalation> {
  const res = await fetch(`${API_BASE_URL}/escalations/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (res.status === 400) {
    const body = await res.json();
    throw new Error(body.detail ?? "Failed to update escalation");
  }
  await throwIfNotOk(res, "Failed to update escalation");
  return res.json();
}
