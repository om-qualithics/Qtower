"""Renders a Policy row's answers into the real docx, via the docxtpl
template seeded into MinIO by apps/api/scripts/seed_policy_template.py.
Context variable names here MUST match that script's tag placement
exactly - see the plan's "Context variable map" for the full contract.
"""
import io
from datetime import datetime, timedelta, timezone

from docxtpl import DocxTemplate

from apps.api.core import storage
from apps.api.modules.identity.models import Org
from apps.api.modules.policy.constants import TEMPLATE_KEY
from apps.api.modules.policy.models import Policy
from apps.api.modules.policy.questions import (
    NAME_DEPT_TITLE_COLUMNS,
    NAME_TITLE_COLUMNS,
    STEPS,
    Column,
    Question,
)

_QUESTIONS_BY_KEY = {q.key: q for step in STEPS for q in step.questions}

_TIER_QUESTION_KEYS = [
    (1, "q3_1_restricted_examples", "q3_2_restricted_rule"),
    (2, "q3_3_confidential_examples", "q3_4_confidential_rule"),
    (3, "q3_5_internal_examples", "q3_6_internal_rule"),
    (4, "q3_7_public_examples", "q3_8_public_rule"),
]

_PROHIBITED_CATEGORIES = [
    ("Data handling", "q4_2_data_handling"),
    ("Output and Communication", "q4_2_output_communication"),
    ("Decision-Making", "q4_2_decision_making"),
    ("Tool and Access", "q4_2_tool_access"),
]


def _selected_labels(question: Question, answer: dict) -> list[str]:
    selected_values = set(answer.get("selected", []))
    labels = [o.label for o in question.options if o.value in selected_values]
    labels.extend(item for item in answer.get("other", []) if item)
    return labels


def _joined_text(question: Question, answer: dict) -> str:
    labels = _selected_labels(question, answer)
    return "; ".join(labels) if labels else "Not specified."


def _severity_value(answers: dict, level: str, field: str) -> str:
    rows = answers.get("q6_2_severity", {}).get("rows", [])
    for row in rows:
        if row.get("level") == level:
            return row.get(field, "") or ""
    return ""


def _single_select_label(question: Question, answer: dict) -> str:
    selected = answer.get("selected")
    for option in question.options:
        if option.value == selected:
            return option.label
    return "Not specified."


def _bullet_subdoc(tpl: DocxTemplate, items: list[str]):
    subdoc = tpl.new_subdoc()
    if not items:
        subdoc.add_paragraph("Not specified.")
        return subdoc
    for item in items:
        subdoc.add_paragraph(f"• {item}")
    return subdoc


def _people_table_subdoc(tpl: DocxTemplate, rows: list[dict], columns: list[Column], empty_message: str):
    subdoc = tpl.new_subdoc()
    if not rows:
        subdoc.add_paragraph(empty_message)
        return subdoc

    table = subdoc.add_table(rows=1, cols=len(columns))
    try:
        table.style = "Table Grid"
    except KeyError:
        pass
    header_cells = table.rows[0].cells
    for i, col in enumerate(columns):
        header_cells[i].text = col.label
    for row in rows:
        cells = table.add_row().cells
        for i, col in enumerate(columns):
            cells[i].text = str(row.get(col.key, "") or "")
    return subdoc


def _prohibited_conduct_subdoc(tpl: DocxTemplate, answers: dict):
    subdoc = tpl.new_subdoc()
    any_content = False

    for heading, key in _PROHIBITED_CATEGORIES:
        items = _selected_labels(_QUESTIONS_BY_KEY[key], answers.get(key, {}))
        if not items:
            continue
        any_content = True
        heading_p = subdoc.add_paragraph()
        heading_p.add_run(heading).bold = True
        for item in items:
            subdoc.add_paragraph(f"• {item}")

    custom_rows = answers.get("q4_2_custom_categories", {}).get("rows", [])
    by_category: dict[str, list[str]] = {}
    for row in custom_rows:
        category = (row.get("category") or "Other").strip() or "Other"
        use_case = (row.get("prohibited_use_case") or "").strip()
        if use_case:
            by_category.setdefault(category, []).append(use_case)

    for category, items in by_category.items():
        any_content = True
        heading_p = subdoc.add_paragraph()
        heading_p.add_run(category).bold = True
        for item in items:
            subdoc.add_paragraph(f"• {item}")

    if not any_content:
        subdoc.add_paragraph("Not specified.")
    return subdoc


def render(org: Org, policy: Policy) -> bytes:
    template_bytes = storage.download_bytes(TEMPLATE_KEY)
    tpl = DocxTemplate(io.BytesIO(template_bytes))
    answers = policy.answers or {}
    now = datetime.now(timezone.utc)

    context: dict = {
        "org_name": org.name,
        "policy_owner_name": policy.policy_owner_name or "",
        "approver_name": policy.approver_name or "",
        "effective_date": now.strftime("%B %d, %Y"),
        "review_date": now.strftime("%B %d, %Y"),
        "next_review_date": (now + timedelta(days=365)).strftime("%B %d, %Y"),
        "version": str(policy.version),
        "default_tier": _single_select_label(_QUESTIONS_BY_KEY["q3_9_default_tier"], answers.get("q3_9_default_tier", {})),
        "dept_leads_rows": answers.get("q2_2_dept_leads", {}).get("rows", []),
        "legal_lead_rows": answers.get("q2_3_legal_lead", {}).get("rows", []),
        "scope_who_applies_block": _bullet_subdoc(
            tpl, _selected_labels(_QUESTIONS_BY_KEY["q1_1_who_applies"], answers.get("q1_1_who_applies", {}))
        ),
        "scope_ai_systems_block": _bullet_subdoc(
            tpl, _selected_labels(_QUESTIONS_BY_KEY["q1_2_ai_systems"], answers.get("q1_2_ai_systems", {}))
        ),
        "jurisdictions_block": _bullet_subdoc(
            tpl, _selected_labels(_QUESTIONS_BY_KEY["q1_3_jurisdictions"], answers.get("q1_3_jurisdictions", {}))
        ),
        "governance_owner_table": _people_table_subdoc(
            tpl, answers.get("q2_1_governance_owner", {}).get("rows", []), NAME_TITLE_COLUMNS, "To be designated."
        ),
        "dept_leads_table": _people_table_subdoc(
            tpl,
            answers.get("q2_2_dept_leads", {}).get("rows", []),
            NAME_DEPT_TITLE_COLUMNS,
            "Department AI Leads will be designated within 30 days of policy adoption.",
        ),
        "legal_lead_table": _people_table_subdoc(
            tpl, answers.get("q2_3_legal_lead", {}).get("rows", []), NAME_DEPT_TITLE_COLUMNS, "To be designated."
        ),
        "governance_approvers_table": _people_table_subdoc(
            tpl, answers.get("q2_4_approvers", {}).get("rows", []), NAME_TITLE_COLUMNS, "To be designated."
        ),
        "permitted_uses_block": _bullet_subdoc(
            tpl, _selected_labels(_QUESTIONS_BY_KEY["q4_1_permitted_uses"], answers.get("q4_1_permitted_uses", {}))
        ),
        "prohibited_conduct_block": _prohibited_conduct_subdoc(tpl, answers),
        "ai_agent_oversight_block": _bullet_subdoc(
            tpl, _selected_labels(_QUESTIONS_BY_KEY["q5_2_agent_oversight"], answers.get("q5_2_agent_oversight", {}))
        ),
        "reportable_incidents_block": _bullet_subdoc(
            tpl,
            _selected_labels(_QUESTIONS_BY_KEY["q6_1_reportable_incidents"], answers.get("q6_1_reportable_incidents", {})),
        ),
        "oversight_rows": answers.get("q5_1_human_oversight", {}).get("rows", []),
    }

    for i, examples_key, rule_key in _TIER_QUESTION_KEYS:
        context[f"tier{i}_examples"] = _joined_text(_QUESTIONS_BY_KEY[examples_key], answers.get(examples_key, {}))
        context[f"tier{i}_rule"] = _joined_text(_QUESTIONS_BY_KEY[rule_key], answers.get(rule_key, {}))

    for level in ("High", "Medium", "Low"):
        level_key = level.lower()
        context[f"severity_{level_key}_definition"] = _severity_value(answers, level, "definition")
        context[f"severity_{level_key}_timeline"] = _severity_value(answers, level, "timeline")

    # autoescape=True: answers are arbitrary user text that can contain XML
    # special characters (e.g. "M&A activity"), and docxtpl runs Jinja
    # directly over raw XML with autoescape off by default - an
    # unescaped "&" corrupts the document. Subdoc values are unaffected:
    # Subdoc defines __html__() specifically so Jinja's autoescape treats
    # its raw XML as already-safe and passes it through untouched.
    tpl.render(context, autoescape=True)
    buffer = io.BytesIO()
    tpl.save(buffer)
    return buffer.getvalue()
