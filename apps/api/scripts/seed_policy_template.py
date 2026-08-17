"""One-time setup: reads the local Enterprise_AI_Policy_Template.docx
(gitignored, repo root - never committed, see aboutproject.md Milestone 5),
programmatically replaces its ~20 marked insertion points with docxtpl
merge tags, and uploads the result to MinIO. Run once per fresh
deployment, same convention as seed_org.py / gen-license-keypair.sh:

    python -m apps.api.scripts.seed_policy_template

Tags are written by locating each paragraph/cell by its exact known
placeholder text and replacing runs directly - not by hand-editing the
docx in Word, which is how a docxtpl tag ends up silently split across
multiple XML runs and fails to render. See the plan's "Context variable
map" for the full tag contract this script and apps/api/modules/policy/
docgen.py must agree on.

docxtpl subtlety (confirmed by reading docxtpl/template.py's patch_xml -
docxtpl has no subdoc-specific API of its own; it runs plain Jinja2 as a
raw string substitution over the whole document.xml, and a subdoc's value
is literally the raw XML text of the subdoc's own paragraphs/tables):
a bare `{{ tag }}` only replaces text INSIDE the existing <w:t> run, so a
subdoc's <w:p>/<w:tbl> XML would land nested inside a <w:t> element -
invalid, and silently dropped when Word/python-docx re-reads it. The `p`
prefix (`{{p tag}}`) tells patch_xml to strip the enclosing <w:p> tags
first, so the substituted XML is spliced in as real sibling content
instead. Table-row repetition needs the same treatment at the row level,
via `{%tr %}`/`{%tr endfor %}` - but each must be the SOLE content of its
OWN row (not sharing a row with the data cells), since patch_xml collapses
each tagged row down to a bare Jinja tag: a for-row immediately before the
data row, and an endfor-row immediately after it.
"""
import copy
import io
import sys
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.table import _Row
from docx.text.paragraph import Paragraph

from apps.api.core import storage
from apps.api.modules.policy.constants import TEMPLATE_KEY

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = REPO_ROOT / "Enterprise_AI_Policy_Template.docx"

# paragraph.text (stripped) -> subdoc tag to render as the paragraph's sole content
WHOLE_PARAGRAPH_TAGS = {
    "[ALL THE OPTIONS SELECTED AS PER STEP 1, QUESTION 1.1]": "{{p scope_who_applies_block}}",
    "[ALL THE OPTIONS SELECTED BY USER AS PER STEP 1, QUESTION 1.2]": "{{p scope_ai_systems_block}}",
    "[ALL THE OPTIONS SELECTED BY USER AS PER STEP 1, QUESTION 1.3]": "{{p jurisdictions_block}}",
    "[Selected prechecked answer + any additional text from question 4.1 step 4]": "{{p permitted_uses_block}}",
    "[Selected prechecked answer + any additional text from question 4.2 step 4]": "{{p prohibited_conduct_block}}",
    "Selected prechecked answer + any additional text from question 5.2 step 5": "{{p ai_agent_oversight_block}}",
    "Selected prechecked answer + any additional text from question 6.1 step 6": "{{p reportable_incidents_block}}",
}

# heading text (the part of the paragraph to KEEP) -> subdoc tag for a new
# paragraph inserted right after it, replacing the "[table as described
# in step 2, question X.X]" second line that shares the same paragraph
# as the heading in the source doc.
HEADING_TABLE_TAGS = {
    "3.1  AI Governance Owner": "{{p governance_owner_table}}",
    "3.2  Department AI Leads": "{{p dept_leads_table}}",
    "3.3  Legal & Compliance Lead": "{{p legal_lead_table}}",
    "3.5  AI Governance approvers": "{{p governance_approvers_table}}",
}


def _set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    """Clears every run but the first (whose formatting is preserved) and
    sets the tag text into it - never trust a single run to already
    contain the whole placeholder string, since Word frequently splits
    text across multiple runs even within one paragraph."""
    for run in paragraph.runs[1:]:
        run._element.getparent().remove(run._element)
    if paragraph.runs:
        paragraph.runs[0].text = text
    else:
        paragraph.add_run(text)


def _strip_after_first_run(paragraph: Paragraph) -> None:
    for run in paragraph.runs[1:]:
        run._element.getparent().remove(run._element)


def _insert_paragraph_after(paragraph: Paragraph, text: str) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    new_para.add_run(text)
    return new_para


def _insert_row_before(table, ref_row: _Row) -> _Row:
    new_tr = copy.deepcopy(ref_row._tr)
    ref_row._tr.addprevious(new_tr)
    return _Row(new_tr, table)


def _insert_row_after(table, ref_row: _Row) -> _Row:
    new_tr = copy.deepcopy(ref_row._tr)
    ref_row._tr.addnext(new_tr)
    return _Row(new_tr, table)


def build_template(source_path: Path) -> bytes:
    doc = docx.Document(str(source_path))

    for paragraph in doc.paragraphs:
        stripped = paragraph.text.strip()
        if stripped in WHOLE_PARAGRAPH_TAGS:
            _set_paragraph_text(paragraph, WHOLE_PARAGRAPH_TAGS[stripped])
            continue
        for heading, tag in HEADING_TABLE_TAGS.items():
            if paragraph.text.startswith(heading) and "table as described" in paragraph.text:
                _strip_after_first_run(paragraph)
                _insert_paragraph_after(paragraph, tag)
                break

    # Table 1: cover metadata
    metadata_table = doc.tables[1]
    _set_paragraph_text(metadata_table.rows[0].cells[1].paragraphs[0], "{{ org_name }}")
    _set_paragraph_text(metadata_table.rows[1].cells[1].paragraphs[0], "{{ policy_owner_name }}")
    _set_paragraph_text(metadata_table.rows[2].cells[1].paragraphs[0], "{{ approver_name }}")
    _set_paragraph_text(metadata_table.rows[3].cells[1].paragraphs[0], "{{ effective_date }}")
    _set_paragraph_text(metadata_table.rows[4].cells[1].paragraphs[0], "{{ review_date }}")
    _set_paragraph_text(metadata_table.rows[5].cells[1].paragraphs[0], "{{ version }}")

    # Table 8: data tier examples + usage rule, rows 1-4 = Tier 1-4
    tier_table = doc.tables[8]
    for i in range(1, 5):
        _set_paragraph_text(tier_table.rows[i].cells[2].paragraphs[0], f"{{{{ tier{i}_examples }}}}")
        _set_paragraph_text(tier_table.rows[i].cells[3].paragraphs[0], f"{{{{ tier{i}_rule }}}}")

    # Table 12: human oversight - one templated row becomes N rows via a
    # dedicated for-row / data-row / endfor-row triple (see module
    # docstring - {%tr%} must be the sole content of its own row).
    oversight_table = doc.tables[12]
    data_row = oversight_table.rows[1]
    _set_paragraph_text(data_row.cells[0].paragraphs[0], "{{ row.use_case }}")
    _set_paragraph_text(data_row.cells[1].paragraphs[0], "{{ row.requirement }}")
    _set_paragraph_text(data_row.cells[2].paragraphs[0], "{{ row.qualification }}")

    for_row = _insert_row_before(oversight_table, data_row)
    _set_paragraph_text(for_row.cells[0].paragraphs[0], "{%tr for row in oversight_rows %}")
    endfor_row = _insert_row_after(oversight_table, data_row)
    _set_paragraph_text(endfor_row.cells[0].paragraphs[0], "{%tr endfor %}")

    # Table 15: incident severity, rows 1-3 = High/Medium/Low
    severity_table = doc.tables[15]
    for i, level in enumerate(("high", "medium", "low"), start=1):
        _set_paragraph_text(severity_table.rows[i].cells[1].paragraphs[0], f"{{{{ severity_{level}_definition }}}}")
        _set_paragraph_text(severity_table.rows[i].cells[2].paragraphs[0], f"{{{{ severity_{level}_timeline }}}}")

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def main() -> None:
    if not SOURCE_PATH.exists():
        print(f"Missing {SOURCE_PATH} - this script needs the real template file locally (never committed).")
        sys.exit(1)

    storage.ensure_bucket()
    tagged_bytes = build_template(SOURCE_PATH)
    storage.upload_bytes(
        TEMPLATE_KEY,
        tagged_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    print(f"Uploaded tagged template to MinIO: {TEMPLATE_KEY}")


if __name__ == "__main__":
    main()
