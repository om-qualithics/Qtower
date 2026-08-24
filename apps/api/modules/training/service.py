import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.identity import service as identity_service
from apps.api.modules.identity.models import Org, User
from apps.api.modules.training.constants import VIDEO_TYPES
from apps.api.modules.training.models import TrainingCompletion, TrainingModule


class TrainingValidationError(Exception):
    pass


class TrainingLockedError(Exception):
    pass


@dataclass
class ModuleView:
    module: TrainingModule
    completion_status: str
    answers: dict[str, str]
    is_locked: bool


@contextmanager
def _catalog_session() -> Generator[Session, None, None]:
    """training_module has no org_id and no RLS policy (see models.py) -
    it's shared platform content, not tenant data - so it's read/written
    through a plain session, never org_scoped_session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _validate_fields(video_type: str | None, questions: list[dict] | None) -> None:
    if video_type is not None and video_type not in VIDEO_TYPES:
        raise TrainingValidationError(f"Unknown video_type: {video_type!r}")
    if questions is not None:
        for q in questions:
            if not q.get("id") or not q.get("prompt"):
                raise TrainingValidationError("Every question needs an id and a prompt")


def _previous_active_module(db: Session, order_index: int) -> TrainingModule | None:
    return db.scalars(
        select(TrainingModule)
        .where(TrainingModule.is_active.is_(True), TrainingModule.order_index < order_index)
        .order_by(TrainingModule.order_index.desc())
    ).first()


def _assert_unlocked(org: Org, user: User, module: TrainingModule) -> None:
    with _catalog_session() as db:
        prev = _previous_active_module(db, module.order_index)
        if prev is not None:
            db.expunge(prev)
    if prev is None:
        return

    with org_scoped_session(str(org.id)) as db:
        completion = db.scalars(
            select(TrainingCompletion).where(
                TrainingCompletion.org_id == org.id,
                TrainingCompletion.user_id == user.id,
                TrainingCompletion.module_id == prev.id,
            )
        ).first()
        completed = completion is not None and completion.status == "completed"

    if not completed:
        raise TrainingLockedError(f'Complete "{prev.title}" before starting this module')


def _find_completion(db: Session, org: Org, user: User, module_id) -> TrainingCompletion | None:
    return db.scalars(
        select(TrainingCompletion).where(
            TrainingCompletion.org_id == org.id,
            TrainingCompletion.user_id == user.id,
            TrainingCompletion.module_id == module_id,
        )
    ).first()


def _get_or_create_completion(db: Session, org: Org, user: User, module_id) -> TrainingCompletion:
    """Two autosave calls for the same module (e.g. the browser firing
    onBlur for two questions within milliseconds of each other) can both
    see "no row yet" and both try to insert - the second one loses to the
    unique constraint. A SAVEPOINT lets us catch that race without
    poisoning the caller's outer transaction: on conflict, the other
    insert has necessarily already committed (Postgres blocks the second
    inserting statement on the unique index until the first transaction
    resolves), so a re-SELECT is guaranteed to find it."""
    completion = _find_completion(db, org, user, module_id)
    if completion is not None:
        return completion
    try:
        with db.begin_nested():
            completion = TrainingCompletion(org_id=org.id, user_id=user.id, module_id=module_id)
            db.add(completion)
            db.flush()
    except IntegrityError:
        completion = _find_completion(db, org, user, module_id)
        assert completion is not None
    return completion


def _get_module_or_none(module_id: str) -> TrainingModule | None:
    with _catalog_session() as db:
        try:
            module = db.get(TrainingModule, uuid.UUID(module_id))
        except ValueError:
            return None
        if module is None:
            return None
        db.expunge(module)
        return module


def list_modules(org: Org, user: User) -> list[ModuleView]:
    with _catalog_session() as db:
        modules = db.scalars(
            select(TrainingModule).where(TrainingModule.is_active.is_(True)).order_by(TrainingModule.order_index)
        ).all()
        for m in modules:
            db.expunge(m)

    with org_scoped_session(str(org.id)) as db:
        completions = db.scalars(
            select(TrainingCompletion).where(TrainingCompletion.org_id == org.id, TrainingCompletion.user_id == user.id)
        ).all()
        by_module = {c.module_id: c for c in completions}
        for c in completions:
            db.expunge(c)

    views: list[ModuleView] = []
    previous_completed = True
    for module in modules:
        completion = by_module.get(module.id)
        status = completion.status if completion else "not_started"
        views.append(
            ModuleView(
                module=module,
                completion_status=status,
                answers=completion.answers if completion else {},
                is_locked=not previous_completed,
            )
        )
        previous_completed = status == "completed"
    return views


def get_module(org: Org, user: User, module_id: str) -> ModuleView | None:
    module = _get_module_or_none(module_id)
    if module is None or not module.is_active:
        return None
    _assert_unlocked(org, user, module)

    with org_scoped_session(str(org.id)) as db:
        completion = db.scalars(
            select(TrainingCompletion).where(
                TrainingCompletion.org_id == org.id, TrainingCompletion.user_id == user.id, TrainingCompletion.module_id == module.id
            )
        ).first()
        status = completion.status if completion else "not_started"
        answers = completion.answers if completion else {}

    return ModuleView(module=module, completion_status=status, answers=answers, is_locked=False)


def save_progress(org: Org, user: User, module_id: str, answers: dict[str, str]) -> TrainingCompletion:
    module = _get_module_or_none(module_id)
    if module is None or not module.is_active:
        raise TrainingValidationError("Module not found")
    _assert_unlocked(org, user, module)

    with org_scoped_session(str(org.id)) as db:
        completion = _get_or_create_completion(db, org, user, module.id)
        completion.answers = {**completion.answers, **answers}
        if completion.status == "not_started":
            completion.status = "in_progress"
        completion.updated_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(completion)
        db.expunge(completion)
        return completion


def complete_module(org: Org, user: User, module_id: str) -> TrainingCompletion:
    module = _get_module_or_none(module_id)
    if module is None or not module.is_active:
        raise TrainingValidationError("Module not found")
    _assert_unlocked(org, user, module)

    with org_scoped_session(str(org.id)) as db:
        completion = _get_or_create_completion(db, org, user, module.id)
        missing = [
            q["id"] for q in module.questions if not str(completion.answers.get(q["id"], "")).strip()
        ]
        if missing:
            raise TrainingValidationError(f"Answer every checkpoint question first (missing: {len(missing)})")

        completion.status = "completed"
        completion.completed_at = datetime.now(timezone.utc)
        completion.updated_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(completion)
        db.expunge(completion)
        return completion


def create_module(
    *,
    order_index: int,
    key: str,
    title: str,
    description: str,
    body_text: str,
    video_type: str = "placeholder",
    video_url: str | None = None,
    questions: list[dict] | None = None,
) -> TrainingModule:
    _validate_fields(video_type, questions)
    with _catalog_session() as db:
        module = TrainingModule(
            order_index=order_index,
            key=key,
            title=title,
            description=description,
            body_text=body_text,
            video_type=video_type,
            video_url=video_url,
            questions=questions or [],
        )
        db.add(module)
        db.flush()
        db.refresh(module)
        db.expunge(module)
        return module


def update_module(module_id: str, **fields) -> TrainingModule | None:
    _validate_fields(fields.get("video_type"), fields.get("questions"))
    with _catalog_session() as db:
        try:
            module = db.get(TrainingModule, uuid.UUID(module_id))
        except ValueError:
            return None
        if module is None:
            return None
        for key, value in fields.items():
            if value is not None:
                setattr(module, key, value)
        module.updated_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(module)
        db.expunge(module)
        return module


def get_completion_summary(org: Org) -> tuple[list[TrainingModule], dict, int]:
    """Returns (active modules ordered, {module_id: completed_count},
    total_active_users) - the router assembles this into TrainingSummaryOut."""
    with _catalog_session() as db:
        modules = db.scalars(
            select(TrainingModule).where(TrainingModule.is_active.is_(True)).order_by(TrainingModule.order_index)
        ).all()
        for m in modules:
            db.expunge(m)

    total_users = len(identity_service.list_active_users(org))

    counts: dict = {}
    with org_scoped_session(str(org.id)) as db:
        completions = db.scalars(
            select(TrainingCompletion).where(TrainingCompletion.org_id == org.id, TrainingCompletion.status == "completed")
        ).all()
        for c in completions:
            counts[c.module_id] = counts.get(c.module_id, 0) + 1

    return modules, counts, total_users
