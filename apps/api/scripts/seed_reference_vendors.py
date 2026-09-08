"""Idempotent one-time setup: pre-populates the Vendor Register with the 5
reference vendors from `Vendor Checklist.xlsx`'s "Current Analysis of
market" sheet (ChatGPT Enterprise, Claude Enterprise, Gemini Workspace,
M365 Copilot, AWS Nova/Bedrock) - so a fresh org starts with real
checklist data, not a blank register (handoff §6/§10).

Must run AFTER seed_vendor_checklist.py (needs the checklist item rows to
exist first - this script looks them up by key). BYOK and on-premise
deployment are unanswered for every vendor in the source sheet - seeded
as not_applicable for all 5 rather than guessed, per this session's
review of the actual spreadsheet data.

    python -m apps.api.scripts.seed_vendor_checklist
    python -m apps.api.scripts.seed_reference_vendors
"""
from sqlalchemy import select

from apps.api.core.db import org_scoped_session
from apps.api.modules.identity import service as identity_service
from apps.api.modules.vendors import service as vendors_service
from apps.api.modules.vendors.models import Vendor

# answer: "yes" (✅) / "partial" (⚠) / "no" (❌) / "not_applicable" (unanswered in the sheet)
VENDOR_DATA: dict[str, dict[str, tuple[str, str]]] = {
    "ChatGPT Enterprise": {
        "no_training_on_data": ("yes", "Enterprise & API default"),
        "dpa_signed": ("yes", "Updated Jan 2026. Covers Enterprise, API, Business."),
        "soc2_type_ii": ("yes", "Enterprise & API services. Available via Trust Portal."),
        "encryption_standards": ("yes", "TLS 1.2+, AES-256. Enterprise Key Management available."),
        "retention_configurable": ("yes", "Enterprise admin controls retention. Deletions within 30 days."),
        "gdpr_dpa_eu_residency": ("partial", "DPA with SCCs available. EU residency: Enterprise/API/Team only."),
        "subprocessor_list": ("yes", "Published at openai.com/policies/subprocessors."),
        "deletion_certificate": ("partial", "Process documented. Certificate on request - not automatic."),
        "zero_data_retention": ("partial", "Not standard. Temporary chat mode limits retention. Enterprise configurable."),
        "iso_42001": ("no", "Not confirmed as of Q2 2026."),
        "audit_rights": ("partial", "SOC reports + Trust Portal. On-site audit not standard."),
        "hipaa_baa": ("yes", "Available for Enterprise and API customers."),
        "fedramp": ("no", "Not FedRAMP authorized as of Q2 2026."),
        "byok": ("not_applicable", "Not answered in source checklist."),
        "on_prem_deployment": ("not_applicable", "Not answered in source checklist."),
    },
    "Claude Enterprise": {
        "no_training_on_data": ("yes", "Enterprise & API. Consumer opt-out required since 2025."),
        "dpa_signed": ("yes", "Commercial Terms + DPA with SCCs auto-incorporated."),
        "soc2_type_ii": ("yes", "SOC 2 Type II + ISO 27001 + ISO 42001. Trust Portal (NDA)."),
        "encryption_standards": ("yes", "TLS 1.2+, AES-256. BYOK in rollout H1 2026."),
        "retention_configurable": ("yes", "API: 7-day default. Enterprise: configurable. ZDR available."),
        "gdpr_dpa_eu_residency": ("partial", "DPA with SCCs. No EU data residency currently."),
        "subprocessor_list": ("partial", "Referenced in DPA. Full list on request via enterprise agreement."),
        "deletion_certificate": ("partial", "ZDR ensures no storage. Formal cert requires legal request."),
        "zero_data_retention": ("yes", "ZDR available for API and Enterprise. Configurable per deployment."),
        "iso_42001": ("yes", "ISO 42001:2023 certified (independent analysis, 2026)."),
        "audit_rights": ("partial", "SOC 2 report under NDA. Pen test on request. On-site: negotiate."),
        "hipaa_baa": ("yes", "Enterprise accounts configurable for HIPAA. BAA available."),
        "fedramp": ("no", "Not FedRAMP authorized as of Q2 2026."),
        "byok": ("not_applicable", "Not answered in source checklist."),
        "on_prem_deployment": ("not_applicable", "Not answered in source checklist."),
    },
    "Gemini Workspace": {
        "no_training_on_data": ("yes", "Workspace Enterprise confirmed in writing"),
        "dpa_signed": ("yes", "Google Cloud DPA + Service Terms §17 training restriction."),
        "soc2_type_ii": ("yes", "SOC 1/2/3 + ISO 27001 + ISO 42001. Compliance Reports Manager."),
        "encryption_standards": ("yes", "TLS, AES-256. Customer-managed keys via Cloud KMS."),
        "retention_configurable": ("yes", "Vertex AI ZDR available. Workspace: admin configurable."),
        "gdpr_dpa_eu_residency": ("yes", "Full DPA. EU Data Boundary. Strong EU posture."),
        "subprocessor_list": ("yes", "Google Cloud subprocessor page. Primarily Google subsidiaries."),
        "deletion_certificate": ("partial", "Deletion procedures in DPA. Cert via Google Cloud support."),
        "zero_data_retention": ("yes", "Vertex AI ZDR available. Configurable per project / model."),
        "iso_42001": ("yes", "Awarded May 2025. Covers Gemini Cloud, Vertex AI, Code Assist."),
        "audit_rights": ("partial", "SOC reports downloadable. Vertex AI audit logs. On-site: not standard."),
        "hipaa_baa": ("yes", "Available via Google Cloud / Workspace with signed BAA."),
        "fedramp": ("yes", "FedRAMP High via Google Cloud (Jul 2025)."),
        "byok": ("not_applicable", "Not answered in source checklist."),
        "on_prem_deployment": ("not_applicable", "Not answered in source checklist."),
    },
    "M365 Copilot": {
        "no_training_on_data": ("yes", "Confirmed in DPA. Not used to train foundation models."),
        "dpa_signed": ("yes", "Microsoft Products & Services DPA covers Copilot workloads."),
        "soc2_type_ii": ("partial", "SOC 2 Type I confirmed. Type II roadmap for 2026."),
        "encryption_standards": ("yes", "TLS 1.2+, AES-256. BYOK / customer-managed keys available."),
        "retention_configurable": ("partial", "Retention inherited from M365. Copilot config requires Purview."),
        "gdpr_dpa_eu_residency": ("yes", "Full DPA. EU Data Boundary live since Feb 2024. Requires config."),
        "subprocessor_list": ("no", "~150 US subprocessors on Trust Center. Requires monthly monitoring."),
        "deletion_certificate": ("partial", "Standard Microsoft deletion procedures. Copilot-specific cert not standard."),
        "zero_data_retention": ("partial", "Not standard for Copilot. Requires Purview configuration."),
        "iso_42001": ("no", "Not confirmed for Copilot specifically as of Q2 2026."),
        "audit_rights": ("no", "SOC 2 report access only. On-site explicitly not permitted."),
        "hipaa_baa": ("yes", "Available via Microsoft enterprise agreement."),
        "fedramp": ("partial", "Some M365 services FedRAMP authorized. Copilot-specific - verify."),
        "byok": ("not_applicable", "Not answered in source checklist."),
        "on_prem_deployment": ("not_applicable", "Not answered in source checklist."),
    },
    "AWS Nova (Bedrock)": {
        "no_training_on_data": ("yes", "Contractual guarantee. Never trains on customer data."),
        "dpa_signed": ("yes", "AWS DPA covers all Bedrock models - single DPA for all."),
        "soc2_type_ii": ("yes", "SOC 1/2/3 + ISO 27001 + FedRAMP High. AWS Artifact."),
        "encryption_standards": ("yes", "TLS, AES-256. AWS KMS with customer-managed keys."),
        "retention_configurable": ("yes", "API: stateless, zero retention by default. Knowledge Bases: customer-controlled."),
        "gdpr_dpa_eu_residency": ("yes", "AWS DPA with SCCs. EU regions available for all Bedrock models."),
        "subprocessor_list": ("yes", "AWS subprocessor list published. Single DPA covers all models."),
        "deletion_certificate": ("yes", "AWS provides deletion confirmation. CloudTrail supports audit evidence."),
        "zero_data_retention": ("yes", "Default API is stateless (ZDR by default). No retention unless features enabled."),
        "iso_42001": ("partial", "AWS ISO program - verify current scope for Bedrock."),
        "audit_rights": ("yes", "AWS Artifact. CloudTrail + CloudWatch provide deep operational logs."),
        "hipaa_baa": ("yes", "AWS BAA covers Bedrock / HIPAA eligible."),
        "fedramp": ("yes", "FedRAMP High authorized."),
        "byok": ("not_applicable", "Not answered in source checklist."),
        "on_prem_deployment": ("not_applicable", "Not answered in source checklist."),
    },
}


def seed_reference_vendors() -> None:
    org = identity_service.get_org()
    items = vendors_service.list_checklist_items()
    item_id_by_key = {item.key: str(item.id) for item in items}

    for name, answers in VENDOR_DATA.items():
        with org_scoped_session(str(org.id)) as db:
            vendor = db.scalars(select(Vendor).where(Vendor.org_id == org.id, Vendor.name == name)).first()
            if vendor is None:
                vendor = Vendor(org_id=org.id, name=name, type="commercial", category="LLM/AI assistant")
                db.add(vendor)
                db.flush()
                print(f"Created vendor: {name}")
            else:
                print(f"Vendor already exists: {name}")
            vendor_id = str(vendor.id)

        responses = [
            {
                "checklist_item_id": item_id_by_key[key],
                "answer": answer,
                "evidence_note": note,
            }
            for key, (answer, note) in answers.items()
            if key in item_id_by_key
        ]
        vendor = vendors_service.update_checklist_responses(org, vendor_id, responses)
        assert vendor is not None
        print(f"  -> status={vendor.status} score={vendor.overall_score}")


if __name__ == "__main__":
    seed_reference_vendors()
