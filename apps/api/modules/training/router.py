from fastapi import APIRouter, Cookie, Depends, HTTPException

from apps.api.modules.authz import service as authz_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.licensing.service import require_valid_license
from apps.api.modules.training import service as training_service
from apps.api.modules.training.schemas import (
    TrainingModuleCreate,
    TrainingModuleOut,
    TrainingModuleUpdate,
    TrainingModuleSummary,
    TrainingProgressUpdate,
    TrainingSummaryOut,
)
from apps.api.modules.training.service import ModuleView, TrainingLockedError, TrainingValidationError

router = APIRouter(prefix="/training", tags=["training"], dependencies=[Depends(require_valid_license)])


def _require_user(session_token: str | None):
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _to_module_out(view: ModuleView) -> TrainingModuleOut:
    m = view.module
    return TrainingModuleOut(
        id=str(m.id),
        order_index=m.order_index,
        key=m.key,
        title=m.title,
        description=m.description,
        body_text=m.body_text,
        video_type=m.video_type,
        video_url=m.video_url,
        questions=m.questions,
        completion_status=view.completion_status,
        answers=view.answers,
        is_locked=view.is_locked,
    )


@router.get("/modules", response_model=list[TrainingModuleOut])
def list_modules(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "training.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    return [_to_module_out(v) for v in training_service.list_modules(org, user)]


@router.get("/modules/{module_id}", response_model=TrainingModuleOut)
def get_module(module_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "training.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        view = training_service.get_module(org, user, module_id)
    except TrainingLockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if view is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return _to_module_out(view)


@router.patch("/modules/{module_id}/progress", response_model=TrainingModuleOut)
def save_progress(module_id: str, body: TrainingProgressUpdate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "training.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        training_service.save_progress(org, user, module_id, body.answers)
    except TrainingLockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TrainingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    view = training_service.get_module(org, user, module_id)
    assert view is not None
    return _to_module_out(view)


@router.post("/modules/{module_id}/complete", response_model=TrainingModuleOut)
def complete_module(module_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "training.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        training_service.complete_module(org, user, module_id)
    except TrainingLockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TrainingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    view = training_service.get_module(org, user, module_id)
    assert view is not None
    return _to_module_out(view)


@router.post("/modules", response_model=TrainingModuleOut)
def create_module(body: TrainingModuleCreate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "training.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        module = training_service.create_module(
            order_index=body.order_index,
            key=body.key,
            title=body.title,
            description=body.description,
            body_text=body.body_text,
            video_type=body.video_type,
            video_url=body.video_url,
            questions=[q.model_dump() for q in body.questions],
        )
    except TrainingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_module_out(ModuleView(module=module, completion_status="not_started", answers={}, is_locked=False))


@router.patch("/modules/{module_id}", response_model=TrainingModuleOut)
def update_module(module_id: str, body: TrainingModuleUpdate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "training.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    fields = body.model_dump(exclude_unset=True)
    if "questions" in fields and fields["questions"] is not None:
        fields["questions"] = [q if isinstance(q, dict) else q.model_dump() for q in fields["questions"]]
    try:
        module = training_service.update_module(module_id, **fields)
    except TrainingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return _to_module_out(ModuleView(module=module, completion_status="not_started", answers={}, is_locked=False))


@router.get("/summary", response_model=TrainingSummaryOut)
def get_summary(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "training.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    modules, counts, total_users = training_service.get_completion_summary(org)

    module_summaries = []
    total_pairs = 0
    total_completed = 0
    for m in modules:
        completed = counts.get(m.id, 0)
        pct = (completed / total_users * 100) if total_users else 0.0
        module_summaries.append(
            TrainingModuleSummary(module_id=str(m.id), title=m.title, total_users=total_users, completed_count=completed, completion_pct=round(pct, 1))
        )
        total_pairs += total_users
        total_completed += completed

    org_pct = (total_completed / total_pairs * 100) if total_pairs else 0.0
    return TrainingSummaryOut(modules=module_summaries, org_completion_pct=round(org_pct, 1))
