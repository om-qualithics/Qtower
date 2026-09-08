"""Idempotent one-time setup: seeds the Vendor Register's checklist catalog
(vendor_checklist_item has no org_id/RLS - shared reference data, same
precedent as training_module). The first 15 items are transcribed verbatim
from `Vendor Checklist.xlsx` (repo root, gitignored) - tiers/wording match
that sheet exactly. Items 16-35 are the real 20-question open-source
checklist from AI_Center_Technical_Handoff.md's "Request forms" section
(Milestone 18) - a full replacement of the 5 placeholder open-source items
guessed at in Milestone 14 (confirmed via direct DB check before this
replacement that zero vendor_checklist_response/vendor_request_checklist_
response rows referenced any of those 5, so no data-loss concern).

Every question is phrased so "yes" always means compliant/good - kept
consistent so scoring.py's ANSWER_CREDIT mapping ("yes"=1.0) never needs a
per-question inversion.

    python -m apps.api.scripts.seed_vendor_checklist
"""
from sqlalchemy import select

from apps.api.core.db import SessionLocal
from apps.api.modules.vendors.models import VendorChecklistItem

ITEMS = [
    # --- Commercial (Vendor Checklist.xlsx, sheet "Vendor Checklist") ---
    dict(
        sort_order=1,
        key="no_training_on_data",
        tier="must_have",
        applies_to="commercial",
        question=(
            "Does this vendor confirm in writing - contractually, not just a settings toggle - "
            "that our data is NOT used to train their AI models?"
        ),
    ),
    dict(
        sort_order=2,
        key="dpa_signed",
        tier="must_have",
        applies_to="commercial",
        question="Is a Data Processing Agreement (DPA) available and signed? Does it cover this specific product and tier?",
    ),
    dict(
        sort_order=3,
        key="soc2_type_ii",
        tier="must_have",
        applies_to="commercial",
        question=(
            "Does the vendor hold a current SOC 2 Type II attestation? "
            "(Type I with a documented Type II roadmap is acceptable.)"
        ),
    ),
    dict(
        sort_order=4,
        key="encryption_standards",
        tier="must_have",
        applies_to="commercial",
        question=(
            "Are encryption standards specified for data in transit and at rest? "
            "(Require specifics - TLS version, AES-256 or equivalent. 'Industry standard' is not sufficient.)"
        ),
    ),
    dict(
        sort_order=5,
        key="retention_configurable",
        tier="must_have",
        applies_to="commercial",
        question=(
            "Is the data retention window configurable? Can we set how long queries, inputs, and outputs "
            "are retained? Does this cover backup copies and derived data?"
        ),
    ),
    dict(
        sort_order=6,
        key="gdpr_dpa_eu_residency",
        tier="good_to_have",
        applies_to="commercial",
        question=(
            "Is a GDPR-compliant DPA with EU data residency available for our tier? (Required if processing "
            "EU personal data. Strongly recommended for all organizations given Brussels Effect.)"
        ),
    ),
    dict(
        sort_order=7,
        key="subprocessor_list",
        tier="good_to_have",
        applies_to="commercial",
        question=(
            "Is the vendor's subprocessor list published or available on request? Can we receive "
            "notification of new subprocessors before they are engaged?"
        ),
    ),
    dict(
        sort_order=8,
        key="deletion_certificate",
        tier="good_to_have",
        applies_to="commercial",
        question=(
            "Is a formal data deletion certificate available at contract end - covering backup copies and "
            "model-derived artifacts, not just primary storage?"
        ),
    ),
    dict(
        sort_order=9,
        key="zero_data_retention",
        tier="good_to_have",
        applies_to="commercial",
        question=(
            "Is a Zero Data Retention (ZDR) mode available - where prompts and responses are not stored "
            "beyond the immediate request lifecycle?"
        ),
    ),
    dict(
        sort_order=10,
        key="iso_42001",
        tier="optional",
        applies_to="commercial",
        question="Does the vendor hold ISO 42001 certification? (Increasingly relevant for procurement requirements.)",
    ),
    dict(
        sort_order=11,
        key="audit_rights",
        tier="optional",
        applies_to="commercial",
        question=(
            "Are audit rights available beyond certification reports? Can we request configuration "
            "attestations, access logs, or pen test summaries?"
        ),
    ),
    dict(
        sort_order=12,
        key="hipaa_baa",
        tier="optional",
        applies_to="commercial",
        question="Is a HIPAA BAA available? (Required for healthcare use cases involving PHI.)",
    ),
    dict(
        sort_order=13,
        key="fedramp",
        tier="optional",
        applies_to="commercial",
        question="Is FedRAMP authorization confirmed? (Required for US government or regulated federal deployments.)",
    ),
    dict(
        sort_order=14,
        key="byok",
        tier="optional",
        applies_to="commercial",
        question="Is a customer-managed encryption key (BYOK) option available? (Relevant for highly sensitive or regulated data.)",
    ),
    dict(
        sort_order=15,
        key="on_prem_deployment",
        tier="optional",
        applies_to="commercial",
        question="Is on-premise or private cloud deployment available? (Relevant for air-gapped or sovereign data requirements.)",
    ),
    # --- Open source: Must Have (hard gate - any "No" blocks approval) ---
    # AI_Center_Technical_Handoff.md "Request forms" > "opensource request form"
    dict(
        sort_order=16,
        key="os_license_permissive",
        tier="must_have",
        applies_to="open_source",
        question="Is the license a permissive/commercial-compatible type (MIT, Apache 2.0, BSD)?",
    ),
    dict(
        sort_order=17,
        key="os_copyleft_legal_review",
        tier="must_have",
        applies_to="open_source",
        question="If copyleft (GPL/AGPL), has legal confirmed it doesn't trigger disclosure obligations for our use case?",
    ),
    dict(
        sort_order=18,
        key="os_verified_repo",
        tier="must_have",
        applies_to="open_source",
        question="Is the source from an official/verified repo (not an unverified fork or mirror)?",
    ),
    dict(
        sort_order=19,
        key="os_no_critical_high_cves",
        tier="must_have",
        applies_to="open_source",
        question="Are there zero unpatched Critical/High CVEs in the version we intend to run?",
    ),
    dict(
        sort_order=20,
        key="os_identifiable_maintainer",
        tier="must_have",
        applies_to="open_source",
        question="Does the project have an identifiable maintainer or maintaining organization (not fully anonymous)?",
    ),
    dict(
        sort_order=21,
        key="os_selfhosted_no_telemetry",
        tier="must_have",
        applies_to="open_source",
        question=(
            "Can it run fully self-hosted/air-gapped, with no telemetry or data phoning home by default "
            "(or can that be disabled)?"
        ),
    ),
    # --- Open source: Good to Have (weighted, not a hard block) ---
    dict(
        sort_order=22,
        key="os_recent_activity",
        tier="good_to_have",
        applies_to="open_source",
        question="Has there been a commit or release within the last 6 months?",
    ),
    dict(
        sort_order=23,
        key="os_multiple_maintainers",
        tier="good_to_have",
        applies_to="open_source",
        question="Does the project have more than one active maintainer (bus-factor > 1)?",
    ),
    dict(
        sort_order=24,
        key="os_security_policy",
        tier="good_to_have",
        applies_to="open_source",
        question="Does it have a documented security policy / responsible-disclosure process (e.g., SECURITY.md)?",
    ),
    dict(
        sort_order=25,
        key="os_security_audit_or_scrutiny",
        tier="good_to_have",
        applies_to="open_source",
        question=(
            "Has the project had a third-party security audit, or is it widely adopted enough to have "
            "informal community scrutiny (e.g., high star count, used by known companies)?"
        ),
    ),
    dict(
        sort_order=26,
        key="os_verifiable_release_process",
        tier="good_to_have",
        applies_to="open_source",
        question="Is there a signed/verifiable release process (checksums, GPG-signed tags, SLSA provenance)?",
    ),
    dict(
        sort_order=27,
        key="os_model_card",
        tier="good_to_have",
        applies_to="open_source",
        question=(
            "Does the model/library have a published model card or equivalent documentation of training "
            "data, known limitations, and intended use?"
        ),
    ),
    dict(
        sort_order=28,
        key="os_dependency_hygiene",
        tier="good_to_have",
        applies_to="open_source",
        question="Is dependency hygiene reasonable (no long list of abandoned/unmaintained transitive dependencies)?",
    ),
    dict(
        sort_order=29,
        key="os_active_issue_tracker",
        tier="good_to_have",
        applies_to="open_source",
        question=(
            "Does it have an active issue tracker with reasonable response times (not hundreds of stale, "
            "unanswered security-relevant issues)?"
        ),
    ),
    # --- Open source: Optional / use-case specific ---
    dict(
        sort_order=30,
        key="os_commercial_support",
        tier="optional",
        applies_to="open_source",
        question=(
            "Is commercial support available (paid support tier from the maintaining org, even if the "
            "software itself is free)?"
        ),
    ),
    dict(
        sort_order=31,
        key="os_infra_compatible",
        tier="optional",
        applies_to="open_source",
        question="Is it compatible with our existing infra (containerizable, runs on our current stack without exotic dependencies)?",
    ),
    dict(
        sort_order=32,
        key="os_byok",
        tier="optional",
        applies_to="open_source",
        question="Does it support BYOK/local key management if it has any cryptographic component?",
    ),
    dict(
        sort_order=33,
        key="os_enterprise_hosted_option",
        tier="optional",
        applies_to="open_source",
        question=(
            "Is there an enterprise/hosted version available from the same maintainers, in case we want to "
            "switch deployment models later?"
        ),
    ),
    dict(
        sort_order=34,
        key="os_governance_model",
        tier="optional",
        applies_to="open_source",
        question=(
            "Does the project have a clear governance model (foundation-backed like Apache/Linux Foundation "
            "projects, vs. single-company-controlled)?"
        ),
    ),
    dict(
        sort_order=35,
        key="os_training_data_provenance",
        tier="optional",
        applies_to="open_source",
        question=(
            "If it's a model (not a library), is training data provenance disclosed (helps assess "
            "IP/copyright risk downstream)?"
        ),
    ),
]

# The 5 Milestone 14 placeholder open-source items, superseded entirely by
# the 20-item set above (Milestone 18) - deleted rather than left orphaned.
# Confirmed via a direct DB check before this replacement that zero
# vendor_checklist_response/vendor_request_checklist_response rows
# reference any of these keys.
STALE_KEYS = (
    "os_license_type",
    "os_maintainer_activity",
    "os_no_unpatched_cves",
    "os_provenance",
    "os_deployment_mode",
)


def seed_vendor_checklist() -> None:
    db = SessionLocal()
    try:
        for spec in ITEMS:
            existing = db.scalars(select(VendorChecklistItem).where(VendorChecklistItem.key == spec["key"])).first()
            if existing is not None:
                for field in ("sort_order", "tier", "applies_to", "question"):
                    setattr(existing, field, spec[field])
                print(f"Updated checklist item: {spec['key']}")
            else:
                db.add(VendorChecklistItem(**spec))
                print(f"Created checklist item: {spec['key']}")

        for stale_key in STALE_KEYS:
            stale = db.scalars(select(VendorChecklistItem).where(VendorChecklistItem.key == stale_key)).first()
            if stale is not None:
                db.delete(stale)
                print(f"Deleted stale checklist item: {stale_key}")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_vendor_checklist()
