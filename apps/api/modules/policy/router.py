from fastapi import APIRouter, Cookie, HTTPException

from apps.api.modules.authz import service as authz_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.policy import service as policy_service
from apps.api.modules.policy.questions import STEPS
from apps.api.modules.policy.schemas import (
    ColumnOut,
    OptionOut,
    PolicyDownloadOut,
    PolicyListItemOut,
    PolicyOut,
    PolicyStepUpdate,
    QuestionOut,
    StepOut,
)
from apps.api.modules.policy.service import PolicyValidationError

router = APIRouter(prefix="/policy", tags=["policy"])


def _require_user(session_token: str | None):
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _to_policy_out(policy) -> PolicyOut:
    return PolicyOut(
        id=str(policy.id),
        status=policy.status,
        current_step=policy.current_step,
        version=policy.version,
        policy_owner_name=policy.policy_owner_name,
        approver_name=policy.approver_name,
        answers=policy.answers,
        generated_at=policy.generated_at,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get("/questions", response_model=list[StepOut])
def get_questions(misty_session: str | None = Cookie(default=None)):
    _require_user(misty_session)
    return [
        StepOut(
            id=step.id,
            title=step.title,
            questions=[
                QuestionOut(
                    key=q.key,
                    type=q.type,
                    label=q.label,
                    required=q.required,
                    options=[OptionOut(value=o.value, label=o.label, checked_by_default=o.checked_by_default) for o in q.options],
                    allow_other=q.allow_other,
                    category=q.category,
                    columns=[ColumnOut(key=c.key, label=c.label) for c in q.columns],
                    initial_rows=q.initial_rows,
                    addable=q.addable,
                    locked_rows=q.locked_rows,
                )
                for q in step.questions
            ],
        )
        for step in STEPS
    ]


@router.get("/", response_model=list[PolicyListItemOut])
def list_policies(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "policy.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    policies = policy_service.list_policies(org)
    return [
        PolicyListItemOut(
            id=str(p.id),
            status=p.status,
            current_step=p.current_step,
            version=p.version,
            policy_owner_name=p.policy_owner_name,
            generated_at=p.generated_at,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in policies
    ]


@router.post("/", response_model=PolicyOut)
def create_policy(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "policy.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    policy = policy_service.create_draft(org, user)
    return _to_policy_out(policy)


@router.get("/{policy_id}", response_model=PolicyOut)
def get_policy(policy_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "policy.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    policy = policy_service.get_policy(org, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _to_policy_out(policy)


@router.patch("/{policy_id}", response_model=PolicyOut)
def update_policy_step(policy_id: str, body: PolicyStepUpdate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "policy.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    policy = policy_service.update_step(org, policy_id, body.step, body.answers)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _to_policy_out(policy)


@router.post("/{policy_id}/generate", response_model=PolicyOut)
def generate_policy(policy_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "policy.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        policy = policy_service.generate(org, policy_id)
    except PolicyValidationError as exc:
        raise HTTPException(status_code=400, detail={"missing_required": exc.missing_required}) from exc
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _to_policy_out(policy)


@router.get("/{policy_id}/download", response_model=PolicyDownloadOut)
def download_policy(policy_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "policy.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    url = policy_service.get_download_url(org, policy_id)
    if url is None:
        raise HTTPException(status_code=404, detail="Policy not found or not yet generated")
    return PolicyDownloadOut(download_url=url)
