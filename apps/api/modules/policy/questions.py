"""The AI Policy wizard's question catalog - fixed product logic (same
footing as authz's permission matrix), not per-org data. Both the API and
the frontend's generic question renderer read from this single source of
truth. Every answer is stored under `Policy.answers[question.key]` in a
shape matching the question's type:
  - checklist:     {"selected": [...values], "other": [...free text]}
  - single_select: {"selected": "value"}
  - text:          {"value": "..."}
  - table:         {"rows": [{...column values...}, ...]}
"""
from dataclasses import dataclass, field


@dataclass
class Option:
    value: str
    label: str
    checked_by_default: bool = False


@dataclass
class Column:
    key: str
    label: str


@dataclass
class Question:
    key: str
    type: str  # "checklist" | "single_select" | "text" | "table"
    label: str
    required: bool = False
    options: list[Option] = field(default_factory=list)
    allow_other: bool = False
    category: str | None = None  # sub-heading for grouped checklists (4.2)
    columns: list[Column] = field(default_factory=list)
    initial_rows: list[dict] = field(default_factory=list)
    addable: bool = True
    locked_rows: bool = False  # rows fixed (severity table) - values only, no add/remove


@dataclass
class Step:
    id: int
    title: str
    questions: list[Question]


def _checklist(key: str, label: str, options: list[tuple[str, str, bool]], allow_other: bool = True) -> Question:
    return Question(
        key=key,
        type="checklist",
        label=label,
        allow_other=allow_other,
        options=[Option(value=v, label=lbl, checked_by_default=checked) for v, lbl, checked in options],
    )


NAME_TITLE_COLUMNS = [Column("name", "Name"), Column("title", "Title")]
NAME_DEPT_TITLE_COLUMNS = [Column("name", "Name"), Column("department", "Department"), Column("title", "Title")]

OVERSIGHT_DEFAULT_ROWS = [
    {
        "use_case": "External customer communications",
        "requirement": "Review and verify accuracy before sending",
        "qualification": "Employee with subject matter knowledge of the content",
    },
    {
        "use_case": "Legal documents, contracts, filings, correspondence",
        "requirement": "Review and verify all facts, citations, and legal conclusions",
        "qualification": "Qualified legal professional or named legal reviewer",
    },
    {
        "use_case": "Financial reports, code, models, analyses, recommendations",
        "requirement": "Review and verify all figures, assumptions, and conclusions",
        "qualification": "Subject matter experts",
    },
    {
        "use_case": "Hiring decisions, candidate screening, or performance assessments",
        "requirement": "Review AI recommendation against independent assessment",
        "qualification": "Trained HR professional",
    },
    {
        "use_case": "Medical, clinical, or health-related guidance",
        "requirement": "Review and verify all clinical content before patient use",
        "qualification": "Licensed clinical professional",
    },
    {
        "use_case": "Public-facing content, press releases, marketing materials",
        "requirement": "Review and verify all factual claims before publication",
        "qualification": "Communications or marketing approver",
    },
    {
        "use_case": "Regulatory filings, compliance submissions",
        "requirement": "Review and verify all content before submission",
        "qualification": "Compliance officer or legal reviewer",
    },
    {
        "use_case": "Automated decisions affecting individuals' rights or significant interests",
        "requirement": "Human must review and have authority to override the decision",
        "qualification": "Decision authority for that process",
    },
]

SEVERITY_DEFAULT_ROWS = [
    {
        "level": "High",
        "definition": (
            "Data breach or suspected data exposure involving Tier 1 data; regulatory trigger; "
            "AI-driven decision with material harm to an individual; security compromise of an AI system"
        ),
        "timeline": (
            "Immediate escalation to AI Governance Owner and Management. Incident response team "
            "activated within 2 hours. External notification obligations assessed within 24 hours."
        ),
    },
    {
        "level": "Medium",
        "definition": (
            "Hallucination impact on external communications or formal submissions; unauthorized AI use "
            "in critical business processes; suspected bias in a High-Risk AI Use"
        ),
        "timeline": (
            "AI Governance Owner & Management notified within 24 hours. Investigation initiated within "
            "48 hours. Remediation plan within 5 working days."
        ),
    },
    {
        "level": "Low",
        "definition": (
            "Unintentional minor policy violations; shadow AI use without data exposure; AI output "
            "quality issues without external impact"
        ),
        "timeline": "Acknowledged within 48 hours. Reviewed within 5 working days. Educational follow-up with employee.",
    },
]

STEPS: list[Step] = [
    Step(
        id=1,
        title="Purpose & Scope",
        questions=[
            Question(key="policy_owner_name", type="text", label="Name of Policy Owner", required=True),
            Question(key="approver_name", type="text", label="Name of Policy Approver", required=True),
            _checklist(
                "q1_1_who_applies",
                "Who does this AI Policy apply to?",
                [
                    ("fulltime_employees", "Fulltime employees", True),
                    ("part_time_employees", "Part time employees", True),
                    ("contractors", "Contractors, consultants, interns and temporary workers", True),
                    ("third_parties", "Third parties (accessing Organization systems or data)", True),
                    (
                        "board_investors",
                        "Members of the board of directors and investors (when acting in an "
                        "organizational capacity involving AI)",
                        False,
                    ),
                ],
                allow_other=False,
            ),
            _checklist(
                "q1_2_ai_systems",
                "What AI systems does this policy govern?",
                [
                    ("conversational_ai", "Conversational AI and large language model tools (e.g. ChatGPT, Claude, Gemini)", True),
                    ("writing_tools", "AI writing, editing, and summarization tools", True),
                    ("code_gen", "AI-powered code generation and development tools", True),
                    ("analytics", "AI analytics, forecasting, and decision-support tools", True),
                    ("media_gen", "Image, video, or audio generation tools powered by AI", True),
                    (
                        "embedded_ai",
                        "AI features embedded in enterprise software (Microsoft 365 Copilot, Salesforce "
                        "Einstein, Zoom AI, Slack AI, Google Workspace AI, etc.)",
                        True,
                    ),
                    ("agents", "AI agents or autonomous systems that take actions on behalf of users", True),
                ],
            ),
            _checklist(
                "q1_3_jurisdictions",
                "Any specific jurisdictions or compliance the organization must align with?",
                [
                    ("gdpr", "General Data Protection Regulation (GDPR)", True),
                    ("eu_ai_act", "EU AI Act", True),
                    ("iso42001", "ISO 42001", True),
                ],
            ),
        ],
    ),
    Step(
        id=2,
        title="Governance & Accountability",
        questions=[
            Question(
                key="q2_1_governance_owner",
                type="table",
                label="Name and title of AI governance owner(s)",
                required=True,
                columns=NAME_TITLE_COLUMNS,
            ),
            Question(
                key="q2_2_dept_leads",
                type="table",
                label="Departmental AI Lead(s) (optional)",
                columns=NAME_DEPT_TITLE_COLUMNS,
            ),
            Question(
                key="q2_3_legal_lead",
                type="table",
                label="Legal & Compliance Lead (optional)",
                columns=NAME_DEPT_TITLE_COLUMNS,
            ),
            Question(
                key="q2_4_approvers",
                type="table",
                label="Name and title of AI governance approver(s)",
                required=True,
                columns=NAME_TITLE_COLUMNS,
            ),
        ],
    ),
    Step(
        id=3,
        title="Data Classification & AI Usage Rules",
        questions=[
            _checklist(
                "q3_1_restricted_examples",
                "What classifies as Restricted (Tier 1) data?",
                [
                    ("pii", "PII", True),
                    ("phi", "PHI", True),
                    ("source_code", "Source code", True),
                    ("legal_privilege", "Legal privilege", True),
                    ("trade_secrets", "Trade secrets", True),
                    ("auth_credentials", "Authentication credentials", True),
                    ("financial_account_data", "Financial account data", True),
                ],
            ),
            _checklist(
                "q3_2_restricted_rule",
                "AI usage rule for Restricted (Tier 1) data",
                [
                    ("no_ai_tools", "No AI tools/features", True),
                    ("security_approved_only", "Only AI tools/features explicitly approved by security team or management", True),
                    ("redact_before_processing", "Redact information before processing", True),
                ],
            ),
            _checklist(
                "q3_3_confidential_examples",
                "What classifies as Confidential (Tier 2) data?",
                [
                    ("business_strategy", "Business strategy", True),
                    ("pricing_models", "Pricing models", True),
                    ("ma_activity", "M&A activity", True),
                    ("employee_performance", "Employee performance", True),
                    ("unpublished_financials", "Unpublished financials", True),
                    ("customer_contracts", "Customer contracts", True),
                ],
            ),
            _checklist(
                "q3_4_confidential_rule",
                "AI usage rule for Confidential (Tier 2) data",
                [
                    ("enterprise_tools_only", "Enterprise AI tools only", True),
                    ("signed_dpa", "Approved vendors with signed DPA", True),
                    ("training_opt_out", "Confirmed training opt-out", True),
                    ("no_consumer_tier", "No consumer-tier accounts", True),
                ],
            ),
            _checklist(
                "q3_5_internal_examples",
                "What classifies as Internal (Tier 3) data?",
                [
                    ("internal_comms", "Internal communications and announcements", True),
                    ("process_docs", "General business process documentation", True),
                    ("project_materials", "Non-sensitive project materials", True),
                    ("meeting_notes", "Internal meeting notes (without confidential content)", True),
                    ("business_procedures", "General business procedures", True),
                ],
            ),
            _checklist(
                "q3_6_internal_rule",
                "AI usage rule for Internal (Tier 3) data",
                [
                    ("company_accounts_only", "Approved enterprise AI tools with company-issued accounts only", True),
                    ("no_personal_accounts", "Cannot use personal/free-tier account", True),
                    ("deletion_opt_out", "Need data deletion and training opt-out protection", True),
                ],
            ),
            _checklist(
                "q3_7_public_examples",
                "What classifies as Public (Tier 4) data?",
                [
                    ("marketing_materials", "Officially approved marketing materials", True),
                    ("published_reports", "Published reports/use case materials", True),
                    ("press_releases", "Press releases", True),
                    ("product_docs", "General product documentation approved for public release", True),
                    ("public_social_content", "Social media content or content already in the public domain", True),
                ],
            ),
            _checklist(
                "q3_8_public_rule",
                "AI usage rule for Public (Tier 4) data",
                [
                    ("any_approved_tool", "Any approved AI tool", True),
                    ("personal_tier_allowed", "Allow personal/free-tier account in some cases", True),
                    ("standard_acceptable_use", "Standard acceptable use rules", True),
                    ("protection_optional", "Data deletion and training opt-out protection optional", True),
                ],
            ),
            Question(
                key="q3_9_default_tier",
                type="single_select",
                label="Default data tier when uncertain",
                required=True,
                options=[
                    Option("public", "Public"),
                    Option("internal", "Internal"),
                    Option("confidential", "Confidential"),
                    Option("restricted", "Restricted"),
                ],
            ),
        ],
    ),
    Step(
        id=4,
        title="Permission vs Prohibition",
        questions=[
            _checklist(
                "q4_1_permitted_uses",
                "What are permitted use cases of AI?",
                [
                    ("drafting", "Drafting, editing, summarizing, or reformatting content (subject to human review before external use)", True),
                    ("research", "Research and information gathering from publicly available data", True),
                    ("data_analysis", "Data analysis, visualization, or pattern identification from approved data sets", True),
                    ("code_gen", "Code generation, testing, review, and documentation (subject to human review before deployment)", True),
                    ("brainstorming", "Brainstorming, ideation, and exploratory creative work", True),
                    ("automation", "Automating routine, low-risk tasks as approved by manager and/or upper management", True),
                    ("translation", "Translation or language assistance for approved content", True),
                    ("social_media", "Social media content (subject to human review before external use)", True),
                ],
            ),
            _checklist(
                "q4_2_data_handling",
                "Prohibited conduct: Data handling",
                [
                    ("restricted_into_ai", "Entering Restricted data into any AI tool", True),
                    ("personal_accounts", "Sending data into personal or free-tier AI accounts", True),
                    ("sharing_credentials", "Sharing authentication credentials, encryption keys, or access tokens into any AI tool", True),
                    ("combining_fields", "Combining multiple data fields to create a data set that would classify at a higher tier than any individual field", True),
                ],
                allow_other=True,
            ),
            _checklist(
                "q4_2_output_communication",
                "Prohibited conduct: Output and Communication",
                [
                    ("sharing_unreviewed", "Sharing AI outputs externally without human review and verification of accuracy", True),
                    ("original_work", "Representing AI-generated content as original work", True),
                    ("non_disclosure", "Non-disclosure of AI where it is required by professional rules, client agreements, or Organization policy", True),
                    ("facts_without_review", "Using AI-generated facts for actions and/or decisions without human review", True),
                    ("misleading_content", "Using AI to generate, modify, or distribute misleading, deceptive, or impersonated content", True),
                ],
                allow_other=True,
            ),
            _checklist(
                "q4_2_decision_making",
                "Prohibited conduct: Decision-Making",
                [
                    ("sole_decision_maker", "Using AI as the sole or final decision-maker for any high risk use case without required human oversight", True),
                    ("consequential_no_verification", "Relying on AI outputs for consequential financial, legal, medical, or operational decisions without independent verification", True),
                ],
                allow_other=True,
            ),
            _checklist(
                "q4_2_tool_access",
                "Prohibited conduct: Tool and Access",
                [
                    ("unapproved_install", "Installing, enabling, or connecting AI tools, browser extensions, or plugins to Organization systems without governance review and approval", True),
                    ("bypass_security", "Using AI tools to attempt to bypass, circumvent, test, or probe Organization security controls", True),
                    ("excess_access", "Granting AI tools access to Organization systems, files, or accounts beyond approved limits", True),
                    ("circumvent_access_controls", "Using AI tools to process data on behalf of another employee in a way that circumvents that employee's access controls", True),
                ],
                allow_other=True,
            ),
            Question(
                key="q4_2_custom_categories",
                type="table",
                label="Additional prohibited-conduct categories (optional)",
                columns=[Column("category", "Category"), Column("prohibited_use_case", "Prohibited use case")],
            ),
        ],
    ),
    Step(
        id=5,
        title="Human Oversight and Review",
        questions=[
            Question(
                key="q5_1_human_oversight",
                type="table",
                label="When human review is required",
                required=True,
                columns=[
                    Column("use_case", "Use case"),
                    Column("requirement", "Human review requirement"),
                    Column("qualification", "Reviewer qualification"),
                ],
                initial_rows=OVERSIGHT_DEFAULT_ROWS,
            ),
            _checklist(
                "q5_2_agent_oversight",
                "AI agents and autonomous systems",
                [
                    ("least_privilege", "AI agents must operate with least-privilege access (only the minimum permissions required for their approved function)", True),
                    ("irreversible_approval", "Actions with irreversible consequences require human approval before execution", True),
                    ("logged_audit", "All AI agent actions must be logged and available for audit", True),
                    ("escalation_path", "AI agents must have a defined escalation path for actions that fall outside their approved parameters", True),
                ],
            ),
        ],
    ),
    Step(
        id=6,
        title="Incident Reporting",
        questions=[
            _checklist(
                "q6_1_reportable_incidents",
                "What constitutes a reportable AI incident?",
                [
                    ("data_exposure", "Data exposure - entering Tier 1 or Tier 2 data into an unauthorized or inadequately evaluated AI tool, or discovering that such exposure has occurred", True),
                    ("hallucination_impact", "Hallucination impact - an AI output that was acted upon, shared externally, or submitted formally contained materially incorrect information", True),
                    ("unauthorized_use", "Unauthorized AI use - AI tools used outside the Approved AI Tools Register, particularly in business-critical processes", True),
                    ("bias_output", "Bias or discriminatory output - AI output that appears to discriminate on the basis of protected characteristics", True),
                    ("security_anomaly", "Security anomaly - unexpected AI behavior, suspected prompt injection, AI tool compromise, or unauthorized AI-to-system access", True),
                    ("regulatory_trigger", "Regulatory trigger - any AI-related event that may require regulatory notification", True),
                ],
            ),
            Question(
                key="q6_2_severity",
                type="table",
                label="Incident response: severity and timescales",
                columns=[Column("definition", "Definition"), Column("timeline", "Response timeline")],
                initial_rows=SEVERITY_DEFAULT_ROWS,
                addable=False,
                locked_rows=True,
            ),
        ],
    ),
]


def default_answers() -> dict:
    """Computed defaults for a freshly created draft - checklists start
    with their prechecked options selected, table questions start with
    their initial_rows, matching the source doc's own "prechecked" design
    rather than opening the wizard blank."""
    answers: dict = {}
    for step in STEPS:
        for question in step.questions:
            if question.type == "checklist":
                answers[question.key] = {
                    "selected": [o.value for o in question.options if o.checked_by_default],
                    "other": [],
                }
            elif question.type == "table":
                answers[question.key] = {"rows": [dict(row) for row in question.initial_rows]}
            elif question.type == "single_select":
                answers[question.key] = {"selected": None}
            elif question.type == "text":
                answers[question.key] = {"value": ""}
    return answers


def required_keys() -> list[str]:
    return [q.key for step in STEPS for q in step.questions if q.required]
