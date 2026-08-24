import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.identity.models import Org, User
from apps.api.modules.training import service
from apps.api.modules.training.models import TrainingCompletion, TrainingModule
from apps.api.modules.training.service import TrainingLockedError, TrainingValidationError

# Test-only order_index/key values, well outside the real seeded curriculum
# (1-5 / choosing.../reporting) - training_module has no org_id, so its
# uniqueness constraints are global across the whole deployment, and tests
# run against the real configured database (see other modules' tests).
# Locking looks at the immediately-preceding *active* module by
# order_index across the WHOLE catalog (by design - it's one global
# sequence, see service.py), so these must sit *below* the real curriculum
# (order_index 1-5), not above it, or a test module would inherit a lock
# dependency on the real "Reporting" module.
TEST_ORDER_BASE = -9000


def _make_org(name: str) -> Org:
    db = SessionLocal()
    try:
        org = Org(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)
        return org
    finally:
        db.close()


def _make_user(org: Org, email: str, business_role: str = "operator") -> User:
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email, business_role=business_role)
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _delete_module(module_id) -> None:
    # training_completion has FORCE ROW LEVEL SECURITY - it can only be
    # touched through org_scoped_session, never a plain SessionLocal. Call
    # this *after* _delete_org(org), which already clears that org's
    # completion rows, so nothing should reference this module by the
    # time we get here.
    db = SessionLocal()
    try:
        db.query(TrainingModule).filter(TrainingModule.id == module_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        db.query(TrainingCompletion).filter(TrainingCompletion.org_id == org.id).delete(synchronize_session=False)
        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_save_progress_upserts_and_merges_answers() -> None:
    org = _make_org("Training Progress Org")
    suffix = uuid.uuid4().hex[:8]
    module = service.create_module(
        order_index=TEST_ORDER_BASE + 1,
        key=f"test-progress-{suffix}",
        title="Test Module",
        description="desc",
        body_text="body",
        questions=[{"id": "q1", "prompt": "?"}, {"id": "q2", "prompt": "?"}],
    )
    try:
        user = _make_user(org, "progress@example.com")

        completion = service.save_progress(org, user, str(module.id), {"q1": "answer one"})
        assert completion.status == "in_progress"
        assert completion.answers == {"q1": "answer one"}

        completion = service.save_progress(org, user, str(module.id), {"q2": "answer two"})
        assert completion.answers == {"q1": "answer one", "q2": "answer two"}
    finally:
        _delete_org(org)
        _delete_module(module.id)


def test_complete_module_requires_every_question_answered() -> None:
    org = _make_org("Training Complete Org")
    suffix = uuid.uuid4().hex[:8]
    module = service.create_module(
        order_index=TEST_ORDER_BASE + 2,
        key=f"test-complete-{suffix}",
        title="Test Module 2",
        description="desc",
        body_text="body",
        questions=[{"id": "q1", "prompt": "?"}, {"id": "q2", "prompt": "?"}],
    )
    try:
        user = _make_user(org, "complete@example.com")

        with pytest.raises(TrainingValidationError):
            service.complete_module(org, user, str(module.id))

        service.save_progress(org, user, str(module.id), {"q1": "a", "q2": "b"})
        completion = service.complete_module(org, user, str(module.id))
        assert completion.status == "completed"
        assert completion.completed_at is not None
    finally:
        _delete_org(org)
        _delete_module(module.id)


def test_second_module_locked_until_first_is_completed() -> None:
    org = _make_org("Training Lock Org")
    suffix = uuid.uuid4().hex[:8]
    module_1 = service.create_module(
        order_index=TEST_ORDER_BASE + 10,
        key=f"test-lock-1-{suffix}",
        title="First",
        description="desc",
        body_text="body",
        questions=[{"id": "q1", "prompt": "?"}],
    )
    module_2 = service.create_module(
        order_index=TEST_ORDER_BASE + 11,
        key=f"test-lock-2-{suffix}",
        title="Second",
        description="desc",
        body_text="body",
        questions=[{"id": "q1", "prompt": "?"}],
    )
    try:
        user = _make_user(org, "lock@example.com")

        with pytest.raises(TrainingLockedError):
            service.get_module(org, user, str(module_2.id))
        with pytest.raises(TrainingLockedError):
            service.save_progress(org, user, str(module_2.id), {"q1": "a"})
        with pytest.raises(TrainingLockedError):
            service.complete_module(org, user, str(module_2.id))

        service.save_progress(org, user, str(module_1.id), {"q1": "a"})
        service.complete_module(org, user, str(module_1.id))

        view = service.get_module(org, user, str(module_2.id))
        assert view is not None
        assert view.is_locked is False

        service.save_progress(org, user, str(module_2.id), {"q1": "a"})
        completion = service.complete_module(org, user, str(module_2.id))
        assert completion.status == "completed"
    finally:
        _delete_org(org)
        _delete_module(module_2.id)
        _delete_module(module_1.id)


def test_list_modules_reflects_lock_state_and_status() -> None:
    org = _make_org("Training List Org")
    suffix = uuid.uuid4().hex[:8]
    module_1 = service.create_module(
        order_index=TEST_ORDER_BASE + 20,
        key=f"test-list-1-{suffix}",
        title="First",
        description="desc",
        body_text="body",
        questions=[],
    )
    module_2 = service.create_module(
        order_index=TEST_ORDER_BASE + 21,
        key=f"test-list-2-{suffix}",
        title="Second",
        description="desc",
        body_text="body",
        questions=[],
    )
    try:
        user = _make_user(org, "list@example.com")
        views = {v.module.id: v for v in service.list_modules(org, user)}
        assert views[module_1.id].is_locked is False
        assert views[module_2.id].is_locked is True

        service.complete_module(org, user, str(module_1.id))
        views = {v.module.id: v for v in service.list_modules(org, user)}
        assert views[module_2.id].is_locked is False
    finally:
        _delete_org(org)
        _delete_module(module_2.id)
        _delete_module(module_1.id)


def test_concurrent_save_progress_does_not_violate_unique_constraint() -> None:
    """Two autosave calls landing at nearly the same instant (e.g. two
    checkpoint questions blurring within milliseconds) used to both see
    "no completion row yet" and both try to INSERT, and the loser crashed
    with a raw IntegrityError instead of just merging in - see
    _get_or_create_completion's savepoint-based fix."""
    org = _make_org("Training Concurrent Org")
    suffix = uuid.uuid4().hex[:8]
    module = service.create_module(
        order_index=TEST_ORDER_BASE + 40,
        key=f"test-concurrent-{suffix}",
        title="Concurrent Module",
        description="desc",
        body_text="body",
        questions=[{"id": "q1", "prompt": "?"}, {"id": "q2", "prompt": "?"}],
    )
    try:
        user = _make_user(org, "concurrent@example.com")

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(service.save_progress, org, user, str(module.id), {"q1": "a"})
            f2 = pool.submit(service.save_progress, org, user, str(module.id), {"q2": "b"})
            result1 = f1.result()
            result2 = f2.result()

        assert result1.id == result2.id
        with org_scoped_session(str(org.id)) as db:
            rows = db.query(TrainingCompletion).filter(TrainingCompletion.module_id == module.id).all()
            assert len(rows) == 1
    finally:
        _delete_org(org)
        _delete_module(module.id)


def test_get_completion_summary_counts_completed_users_per_module() -> None:
    org = _make_org("Training Summary Org")
    suffix = uuid.uuid4().hex[:8]
    module = service.create_module(
        order_index=TEST_ORDER_BASE + 30,
        key=f"test-summary-{suffix}",
        title="Summary Module",
        description="desc",
        body_text="body",
        questions=[],
    )
    try:
        user_a = _make_user(org, "summary-a@example.com")
        user_b = _make_user(org, "summary-b@example.com")

        service.complete_module(org, user_a, str(module.id))

        modules, counts, total_users = service.get_completion_summary(org)
        assert total_users == 2
        assert counts.get(module.id, 0) == 1
    finally:
        _delete_org(org)
        _delete_module(module.id)
