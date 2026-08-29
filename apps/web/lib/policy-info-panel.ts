/**
 * Per-step "what/why/how to adapt" copy for the AI Policy wizard's info
 * panel (an AWS-console-style right rail). Content authored by the user in
 * policy_builder.md §12 - kept here as plain TS data (not fetched from the
 * backend, not hardcoded per-component) so it's a single source of truth
 * matching the "catalog as code" pattern already used for the question
 * catalog itself (questions.py) and authz's permission matrix. Keyed by
 * wizard step id (1-6) - must stay in sync with STEPS in
 * apps/api/modules/policy/questions.py if a step is ever added/reordered.
 */
export type PolicyInfoPanelEntry = {
  title: string;
  whatIsThis: string;
  whyItMatters: string;
  adaptation: string[];
};

export const POLICY_INFO_PANEL: Record<number, PolicyInfoPanelEntry> = {
  1: {
    title: "Purpose & Scope",
    whatIsThis: "Establishes why the policy exists and exactly who and what it covers.",
    whyItMatters:
      "Ambiguity about scope is the most common reason AI policies fail to provide organization direction or legal protection.",
    adaptation: [
      "Review the technology scope, modify if something is missing",
      "Confirm that the scope covers all intended aspects within organization",
    ],
  },
  2: {
    title: "Governance & Accountability",
    whatIsThis: "Assigns named accountability for AI governance across the organization.",
    whyItMatters: "Governance without owners is just a document, not a governance system.",
    adaptation: [
      "Assign name/title to governance responsibility",
      "Create governance committee if required",
      "Align with existing org structure, do not create roles that conflict with existing authority",
    ],
  },
  3: {
    title: "Data Classification & AI Usage Rules",
    whatIsThis: "Defines data tiers and specifies which AI tools may process data at each tier.",
    whyItMatters:
      "Prevents data leakage and unplanned AI exposure, creates a decision filter users can apply quickly.",
    adaptation: [
      "Review org use case under each defined tier",
      "Add industry-specific data types",
      "Confirm which enterprise AI features are in scope",
    ],
  },
  4: {
    title: "Permission vs Prohibition",
    whatIsThis: "Defines specifically what employees may and may not do with AI tools.",
    whyItMatters:
      "Users need a clear positive list and negative list - policies that only define \"use AI responsibly\" are not enforceable and do not change behavior.",
    adaptation: [
      "Define acceptable AI tools, assisted content generation & AI outputs",
      "Categorize prohibited conduct, restricted data, sharing AI outputs, using AI to make decisions etc.",
    ],
  },
  5: {
    title: "Human Oversight and Review",
    whatIsThis: "Human review is required before AI output is used.",
    whyItMatters: "AI must never replace human judgment. All decisions remain the responsibility of organization.",
    adaptation: [
      "Ensure oversight process is integrated when AI is part of:",
      "External and internal communications",
      "AI generated documents, reports or correspondence",
      "Operation decisions and assessments",
      "Physical activity, etc",
    ],
  },
  6: {
    title: "Incident Reporting",
    whatIsThis: "Defines what constitutes an AI incident, how to report it, and what happens next.",
    whyItMatters: "Incidents that go unreported cannot be investigated, remediated, or prevented from recurring.",
    adaptation: [
      "Define reporting contact and email address",
      "Align incident severity definitions with your existing incident response framework",
      "Add sector specific regulatory notification if any",
    ],
  },
};
