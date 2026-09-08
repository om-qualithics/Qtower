from sqlalchemy import select

from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.identity.models import Org, User
from apps.api.modules.vendors import service
from apps.api.modules.vendors.models import (
    Vendor,
    VendorChecklistResponse,
    VendorRequest,
    VendorRequestChecklistResponse,
)
from apps.api.modules.vendors.scoring import ChecklistAnswer, score_vendor
from apps.api.modules.vendors.service import VendorApprovalError, VendorRequestDuplicateError, VendorValidationError
from apps.api.scripts.seed_vendor_checklist import seed_vendor_checklist


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


def _make_user(org: Org, email: str, business_role: str = "assure") -> User:
    with org_scoped_session(str(org.id)) as db:
        user = User(org_id=org.id, email=email, business_role=business_role)
        db.add(user)
        db.flush()
        db.refresh(user)
        db.expunge(user)
        return user


def _delete_org(org: Org) -> None:
    with org_scoped_session(str(org.id)) as db:
        # vendor_request.resulting_vendor_id <-> vendor.created_from_request_id
        # is a genuine circular FK, same shape as tool_request/approved_tool -
        # both sides must be nulled before either table can be deleted.
        db.query(VendorRequest).filter(VendorRequest.org_id == org.id).update(
            {VendorRequest.resulting_vendor_id: None}, synchronize_session=False
        )
        db.query(Vendor).filter(Vendor.org_id == org.id).update(
            {Vendor.created_from_request_id: None}, synchronize_session=False
        )
        db.query(VendorChecklistResponse).filter(VendorChecklistResponse.org_id == org.id).delete(
            synchronize_session=False
        )
        db.query(VendorRequestChecklistResponse).filter(VendorRequestChecklistResponse.org_id == org.id).delete(
            synchronize_session=False
        )
        db.query(VendorRequest).filter(VendorRequest.org_id == org.id).delete(synchronize_session=False)
        db.query(Vendor).filter(Vendor.org_id == org.id).delete(synchronize_session=False)
        db.query(User).filter(User.org_id == org.id).delete(synchronize_session=False)
    db = SessionLocal()
    try:
        db.query(Org).filter(Org.id == org.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# --- scoring.py (pure function) ---


def test_score_vendor_any_must_have_no_forces_restricted() -> None:
    base = [
        ChecklistAnswer("good-1", "good_to_have", "yes"),
        ChecklistAnswer("opt-1", "optional", "yes"),
    ]
    for must_have_answer in ("no",):
        answers = base + [ChecklistAnswer("must-1", "must_have", must_have_answer)]
        status, score = score_vendor(answers)
        assert status == "restricted"
        assert score == 0.0


def test_score_vendor_must_have_no_overrides_perfect_other_answers() -> None:
    answers = [
        ChecklistAnswer("must-1", "must_have", "no"),
        ChecklistAnswer("must-2", "must_have", "yes"),
        ChecklistAnswer("good-1", "good_to_have", "yes"),
        ChecklistAnswer("good-2", "good_to_have", "yes"),
        ChecklistAnswer("opt-1", "optional", "yes"),
    ]
    status, score = score_vendor(answers)
    assert status == "restricted"
    assert score == 0.0


def test_score_vendor_all_must_haves_yes_high_optional_score_approved() -> None:
    answers = [
        ChecklistAnswer("must-1", "must_have", "yes"),
        ChecklistAnswer("good-1", "good_to_have", "yes"),
        ChecklistAnswer("good-2", "good_to_have", "yes"),
        ChecklistAnswer("opt-1", "optional", "yes"),
    ]
    status, score = score_vendor(answers)
    assert status == "approved"
    assert score == 1.0


def test_score_vendor_low_optional_score_needs_review() -> None:
    answers = [
        ChecklistAnswer("must-1", "must_have", "yes"),
        ChecklistAnswer("good-1", "good_to_have", "no"),
        ChecklistAnswer("opt-1", "optional", "no"),
    ]
    status, score = score_vendor(answers)
    assert status == "needs_review"
    assert score == 0.0


def test_score_vendor_not_applicable_excluded_from_denominator() -> None:
    # A single "not_applicable" good_to_have shouldn't drag the score down
    # the way a "no" would - it's excluded from both numerator and
    # denominator entirely.
    with_na = [
        ChecklistAnswer("must-1", "must_have", "yes"),
        ChecklistAnswer("good-1", "good_to_have", "yes"),
        ChecklistAnswer("good-2", "good_to_have", "not_applicable"),
    ]
    status, score = score_vendor(with_na)
    assert status == "approved"
    assert score == 1.0


def test_score_vendor_incomplete_must_have_does_not_force_restricted() -> None:
    # A must_have with no response at all (not answered "no") shouldn't
    # trigger restricted - reserved for a confirmed failure, not an
    # incomplete checklist.
    answers = [ChecklistAnswer("good-1", "good_to_have", "yes")]
    status, score = score_vendor(answers)
    assert status != "restricted"


# --- service.py (real DB) ---


def test_create_vendor_request_rejects_duplicate_name() -> None:
    org = _make_org("Vendors Duplicate Org")
    try:
        requester = _make_user(org, "requester-dup@example.com")
        with org_scoped_session(str(org.id)) as db:
            db.add(Vendor(org_id=org.id, name="Acme AI", type="commercial"))
            db.flush()

        try:
            service.create_vendor_request(org, requester, "acme ai", "commercial", None, "need it")
            assert False, "expected VendorRequestDuplicateError"
        except VendorRequestDuplicateError as exc:
            assert exc.existing_vendor.name == "Acme AI"
    finally:
        _delete_org(org)


def test_approve_vendor_request_rejects_self_approval() -> None:
    org = _make_org("Vendors Self Approve Org")
    try:
        requester = _make_user(org, "requester-self@example.com")
        request = service.create_vendor_request(org, requester, "Self Vendor", "commercial", None, "justification")
        try:
            service.approve_vendor_request(org, str(request.id), requester)
            assert False, "expected VendorApprovalError"
        except VendorApprovalError as exc:
            assert "own request" in str(exc)
    finally:
        _delete_org(org)


def test_approve_vendor_request_creates_catalog_entry() -> None:
    org = _make_org("Vendors Approve Org")
    try:
        requester = _make_user(org, "requester-approve@example.com")
        approver = _make_user(org, "approver-approve@example.com", "govern")
        request = service.create_vendor_request(
            org, requester, "New Vendor Co", "open_source", "https://example.com", "justification"
        )
        approved = service.approve_vendor_request(org, str(request.id), approver)
        assert approved.status == "approved"
        assert approved.resulting_vendor_id is not None

        vendors = service.list_vendors(org)
        assert any(v.id == approved.resulting_vendor_id for v in vendors)
    finally:
        _delete_org(org)


def test_delete_vendor_nulls_both_sides_of_circular_fk() -> None:
    """Mirrors test_update_and_delete_approved_tool_direct_curation's
    circular-FK assertion for tool_request/approved_tool, adapted for
    vendor_request/vendor."""
    org = _make_org("Vendors Delete Org")
    try:
        requester = _make_user(org, "requester-delete@example.com")
        approver = _make_user(org, "approver-delete@example.com", "govern")
        request = service.create_vendor_request(org, requester, "Doomed Vendor", "commercial", None, "justification")
        approved = service.approve_vendor_request(org, str(request.id), approver)
        vendor_id = str(approved.resulting_vendor_id)

        deleted = service.delete_vendor(org, vendor_id)
        assert deleted is True

        with org_scoped_session(str(org.id)) as db:
            assert db.get(Vendor, approved.resulting_vendor_id) is None
            surviving_request = db.get(VendorRequest, request.id)
            assert surviving_request is not None
            assert surviving_request.resulting_vendor_id is None
    finally:
        _delete_org(org)


def test_update_vendor_logo_url_sets_and_clears() -> None:
    org = _make_org("Vendors Logo URL Org")
    try:
        requester = _make_user(org, "requester-logo-url@example.com")
        approver = _make_user(org, "approver-logo-url@example.com", "govern")
        request = service.create_vendor_request(org, requester, "Logo Vendor", "commercial", None, "justification")
        approved = service.approve_vendor_request(org, str(request.id), approver)
        vendor_id = str(approved.resulting_vendor_id)

        updated = service.update_vendor_logo_url(org, vendor_id, "https://cdn.example.com/vendor-logo.png")
        assert updated.logo_url == "https://cdn.example.com/vendor-logo.png"

        cleared = service.update_vendor_logo_url(org, vendor_id, None)
        assert cleared.logo_url is None
    finally:
        _delete_org(org)


def test_upload_vendor_logo_round_trips_bytes_and_content_type() -> None:
    org = _make_org("Vendors Logo Upload Org")
    try:
        requester = _make_user(org, "requester-logo-upload@example.com")
        approver = _make_user(org, "approver-logo-upload@example.com", "govern")
        request = service.create_vendor_request(org, requester, "Upload Logo Vendor", "commercial", None, "justification")
        approved = service.approve_vendor_request(org, str(request.id), approver)
        vendor_id = str(approved.resulting_vendor_id)

        svg_bytes = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
        updated = service.upload_vendor_logo(org, vendor_id, "image/svg+xml", svg_bytes)
        assert updated is not None
        assert updated.logo_url == f"/vendors/{vendor_id}/logo-file"

        data, content_type = service.get_vendor_logo_bytes(org, vendor_id)
        assert data == svg_bytes
        assert content_type == "image/svg+xml"
    finally:
        _delete_org(org)


def test_create_vendor_request_scores_from_submitted_responses() -> None:
    org = _make_org("Vendors Request Scoring Org")
    try:
        requester = _make_user(org, "requester-score@example.com")
        items = service.list_checklist_items(applies_to="commercial")
        must_have_item = next(i for i in items if i.tier == "must_have")

        request = service.create_vendor_request(
            org,
            requester,
            "Scored At Request Vendor",
            "commercial",
            None,
            "justification",
            [{"checklist_item_id": str(must_have_item.id), "answer": "no"}],
        )
        assert request.projected_status == "restricted"
        assert float(request.overall_score) == 0.0

        responses = service.get_vendor_request_responses(org, str(request.id))
        assert len(responses) == 1
        assert responses[0].answer == "no"
    finally:
        _delete_org(org)


def test_create_vendor_request_rejects_answer_for_wrong_vendor_type() -> None:
    org = _make_org("Vendors Wrong Type Org")
    try:
        requester = _make_user(org, "requester-wrongtype@example.com")
        os_only_item = next(
            i for i in service.list_checklist_items(applies_to="open_source") if i.applies_to == "open_source"
        )
        try:
            service.create_vendor_request(
                org,
                requester,
                "Mismatched Vendor",
                "commercial",
                None,
                "justification",
                [{"checklist_item_id": str(os_only_item.id), "answer": "yes"}],
            )
            assert False, "expected VendorValidationError"
        except VendorValidationError:
            pass
    finally:
        _delete_org(org)


def test_approve_vendor_request_copies_checklist_answers_to_new_vendor() -> None:
    org = _make_org("Vendors Copy On Approve Org")
    try:
        requester = _make_user(org, "requester-copy@example.com")
        approver = _make_user(org, "approver-copy@example.com", "govern")
        items = service.list_checklist_items(applies_to="commercial")
        must_have_item = next(i for i in items if i.tier == "must_have")

        request = service.create_vendor_request(
            org,
            requester,
            "Copy Answers Vendor",
            "commercial",
            None,
            "justification",
            [{"checklist_item_id": str(must_have_item.id), "answer": "yes"}],
        )
        approved = service.approve_vendor_request(org, str(request.id), approver)

        vendor_responses = service.get_vendor_responses(org, str(approved.resulting_vendor_id))
        assert len(vendor_responses) == 1
        assert vendor_responses[0].answer == "yes"
        assert vendor_responses[0].checklist_item_id == must_have_item.id

        vendor = service.get_vendor(org, str(approved.resulting_vendor_id))
        assert vendor is not None
        assert vendor.status != "restricted"
    finally:
        _delete_org(org)


def test_update_checklist_responses_rescores_synchronously() -> None:
    org = _make_org("Vendors Scoring Org")
    try:
        with org_scoped_session(str(org.id)) as db:
            vendor = Vendor(org_id=org.id, name="Scored Vendor", type="commercial")
            db.add(vendor)
            db.flush()
            vendor_id = str(vendor.id)
            assert vendor.status == "pending"

        items = service.list_checklist_items(applies_to="commercial")
        must_have_item = next(i for i in items if i.tier == "must_have")

        result = service.update_checklist_responses(
            org, vendor_id, [{"checklist_item_id": str(must_have_item.id), "answer": "no"}]
        )
        assert result is not None
        assert result.status == "restricted"
        assert float(result.overall_score) == 0.0
    finally:
        _delete_org(org)


def test_seed_vendor_checklist_produces_expected_item_counts_and_is_idempotent() -> None:
    """Milestone 18 replaced the 5 placeholder open-source items with the
    real 20-question set from AI_Center_Technical_Handoff.md - confirms the
    seed script lands on the right counts/tiers and stays idempotent on a
    second run (no duplicates, no re-orphaning)."""
    seed_vendor_checklist()
    items = service.list_checklist_items()
    commercial = [i for i in items if i.applies_to == "commercial"]
    open_source = [i for i in items if i.applies_to == "open_source"]
    assert len(commercial) == 15
    assert len(open_source) == 20
    tiers = {}
    for i in open_source:
        tiers[i.tier] = tiers.get(i.tier, 0) + 1
    assert tiers == {"must_have": 6, "good_to_have": 8, "optional": 6}

    seed_vendor_checklist()
    items_again = service.list_checklist_items()
    assert len(items_again) == len(items)
