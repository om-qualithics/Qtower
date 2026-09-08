"""Deterministic vendor scoring - a pure function, no DB session, no
Celery, no ai_gateway call. Vendor evaluation is already-structured Y/N
data (the checklist), so an LLM precheck would add latency/cost/a new
failure mode for a question that has one mechanically correct answer -
see AI_Center_Technical_Handoff.md §4.1 for the full reasoning. Called
synchronously from service.update_checklist_responses()."""

from dataclasses import dataclass

# Fixed default weighting for v1 - no org-level customization (handoff §9).
# Revisit only if a real customer asks.
GOOD_TO_HAVE_WEIGHT = 2
OPTIONAL_WEIGHT = 1
APPROVED_THRESHOLD = 0.7

_ANSWER_CREDIT = {"yes": 1.0, "partial": 0.5, "no": 0.0}


@dataclass
class ChecklistAnswer:
    """Minimal view of one response, decoupled from the ORM row so this
    module never imports SQLAlchemy models - keeps it a pure function."""

    checklist_item_id: str
    tier: str
    answer: str


def score_vendor(answers: list[ChecklistAnswer]) -> tuple[str, float]:
    """Returns (status, overall_score). Any must_have item answered "no"
    forces status="restricted" with a 0.0 score, regardless of every
    other answer - a must_have with no response yet, or answered
    "partial"/"not_applicable", does NOT trigger this (a vendor with an
    incomplete checklist stays "pending"/"needs_review", not
    "restricted" - restricted is reserved for a confirmed failure).
    Otherwise: weighted score from good_to_have (2x) + optional (1x)
    tiers only - must_have items are gate-only, never part of the score.
    not_applicable answers are excluded from the denominator entirely,
    never counted as a failure."""
    for a in answers:
        if a.tier == "must_have" and a.answer == "no":
            return "restricted", 0.0

    weighted_score = 0.0
    weighted_total = 0.0
    for a in answers:
        if a.tier == "must_have" or a.answer == "not_applicable":
            continue
        weight = GOOD_TO_HAVE_WEIGHT if a.tier == "good_to_have" else OPTIONAL_WEIGHT
        weighted_total += weight
        weighted_score += weight * _ANSWER_CREDIT.get(a.answer, 0.0)

    score = (weighted_score / weighted_total) if weighted_total > 0 else 0.0
    status = "approved" if score >= APPROVED_THRESHOLD else "needs_review"
    return status, round(score, 4)
