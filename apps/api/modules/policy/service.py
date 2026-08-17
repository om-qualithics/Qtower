import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from apps.api.core import storage
from apps.api.core.db import org_scoped_session
from apps.api.modules.identity.models import Org, User
from apps.api.modules.policy import docgen
from apps.api.modules.policy.constants import policy_storage_key
from apps.api.modules.policy.models import Policy
from apps.api.modules.policy.questions import STEPS, Question, default_answers, required_keys


class PolicyValidationError(Exception):
    def __init__(self, missing_required: list[str]) -> None:
        self.missing_required = missing_required
        super().__init__(f"Missing required answers: {missing_required}")


_QUESTIONS_BY_KEY = {q.key: q for step in STEPS for q in step.questions}


def create_draft(org: Org, user: User) -> Policy:
    with org_scoped_session(str(org.id)) as db:
        policy = Policy(org_id=org.id, answers=default_answers(), created_by=user.id, current_step=1)
        db.add(policy)
        db.flush()
        db.refresh(policy)
        db.expunge(policy)
        return policy


def list_policies(org: Org) -> list[Policy]:
    with org_scoped_session(str(org.id)) as db:
        policies = db.scalars(select(Policy).where(Policy.org_id == org.id).order_by(Policy.created_at.desc())).all()
        for policy in policies:
            db.expunge(policy)
        return list(policies)


def get_policy(org: Org, policy_id: str) -> Policy | None:
    with org_scoped_session(str(org.id)) as db:
        policy = db.get(Policy, uuid.UUID(policy_id))
        if policy is None or str(policy.org_id) != str(org.id):
            return None
        db.expunge(policy)
        return policy


def update_step(org: Org, policy_id: str, step: int, step_answers: dict) -> Policy | None:
    with org_scoped_session(str(org.id)) as db:
        policy = db.get(Policy, uuid.UUID(policy_id))
        if policy is None or str(policy.org_id) != str(org.id):
            return None

        merged = dict(policy.answers or {})
        merged.update(step_answers)
        policy.answers = merged
        policy.current_step = step

        if "policy_owner_name" in step_answers:
            policy.policy_owner_name = step_answers["policy_owner_name"].get("value") or None
        if "approver_name" in step_answers:
            policy.approver_name = step_answers["approver_name"].get("value") or None

        db.flush()
        db.refresh(policy)
        db.expunge(policy)
        return policy


def _is_answered(question: Question, answer: dict | None) -> bool:
    if not answer:
        return False
    if question.type == "checklist":
        return bool(answer.get("selected")) or bool(answer.get("other"))
    if question.type == "table":
        return bool(answer.get("rows"))
    if question.type == "single_select":
        return bool(answer.get("selected"))
    if question.type == "text":
        return bool((answer.get("value") or "").strip())
    return False


def generate(org: Org, policy_id: str) -> Policy | None:
    policy = get_policy(org, policy_id)
    if policy is None:
        return None

    answers = policy.answers or {}
    missing = [
        key
        for key in required_keys()
        if key not in ("policy_owner_name", "approver_name") and not _is_answered(_QUESTIONS_BY_KEY[key], answers.get(key))
    ]
    if not policy.policy_owner_name:
        missing.append("policy_owner_name")
    if not policy.approver_name:
        missing.append("approver_name")
    if missing:
        raise PolicyValidationError(missing)

    docx_bytes = docgen.render(org, policy)
    storage_key = policy_storage_key(str(org.id), str(policy.id), policy.version)
    storage.upload_bytes(
        storage_key,
        docx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    with org_scoped_session(str(org.id)) as db:
        db_policy = db.get(Policy, policy.id)
        assert db_policy is not None  # fetched successfully via get_policy() moments ago
        db_policy.status = "generated"
        db_policy.storage_key = storage_key
        db_policy.generated_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(db_policy)
        db.expunge(db_policy)
        return db_policy


def get_download_url(org: Org, policy_id: str) -> str | None:
    policy = get_policy(org, policy_id)
    if policy is None or not policy.storage_key:
        return None
    return storage.presigned_url(policy.storage_key, expires_seconds=300)
