"""One-time setup: reads the local Enterprise_AI_Policy_Template.docx
(gitignored, repo root - never committed, see aboutproject.md Milestone 5),
programmatically replaces every `<<...>>` marked insertion point with a
docxtpl merge tag, and uploads the result to MinIO. Run once per fresh
deployment, or any time the template file changes, same convention as
seed_org.py / gen-license-keypair.sh:

    python -m apps.api.scripts.seed_policy_template

**Marker convention**: everything between `<<` and `>>` in the source
template is an instruction describing what belongs there - never literal
document text. This script finds every such marker (inline within a
sentence, or occupying a whole paragraph/cell on its own) and replaces it.
Two markers don't fit a simple text-substitution model and are handled as
dedicated structural transforms before the generic pass runs:
  - the human-oversight table (one templated row must become N rows), and
  - the optional "Department AI Leads" / "Legal & Compliance Lead"
    subsections (must be omitted from the document entirely, heading and
    all, when the user left that question blank - not just show a fallback
    sentence).
After both passes, the whole document is re-scanned for any leftover
`<<...>>` and the script fails loudly if it finds one - a marker with no
mapped handler is exactly the kind of thing that must never ship silently.

Tags are written by manipulating python-docx runs directly - not by
hand-editing the docx in Word, which is how a docxtpl tag ends up silently
split across multiple XML runs and fails to render. See
apps/api/modules/policy/docgen.py's module docstring for the render-side
half of this contract (context variable names must match exactly), and
that file's docstring for the docxtpl `{{p }}`/`{%tr %}` gotchas.
"""
import copy
import io
import re
import sys
from pathlib import Path

import docx
from docx.document import Document as DocxDocument
from docx.oxml import OxmlElement
from docx.table import Table, _Row
from docx.text.paragraph import Paragraph

from apps.api.core import storage
from apps.api.modules.policy.constants import TEMPLATE_KEY

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = REPO_ROOT / "Enterprise_AI_Policy_Template.docx"

MARKER_RE = re.compile(r"<<(.*?)>>", re.DOTALL)


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _tier_marker(question_num: int) -> str:
    return f"Selected prechecked answer + any additional text from question 3.{question_num} step 3"


# normalized marker text -> the tag that replaces it. Markers whose tag
# starts with "{{p " are subdoc insertion points and MUST be the sole
# content of their paragraph/cell (enforced structurally below, since
# these markers only ever appear alone in the source template) - see
# docgen.py's docstring for why that prefix matters.
SIMPLE_MARKERS: dict[str, str] = {
    "Use the ORGANIZATION NAME from above": "{{ org_name }}",
    "ALL THE OPTIONS SELECTED AS PER STEP 1, QUESTION 1.1": "{{p scope_who_applies_block}}",
    "ALL THE OPTIONS SELECTED BY USER AS PER STEP 1, QUESTION 1.2": "{{p scope_ai_systems_block}}",
    "ALL THE OPTIONS SELECTED BY USER AS PER STEP 1, QUESTION 1.3": "{{p jurisdictions_block}}",
    "Answer selected as per question 3.9 step 3": "{{ default_tier }}",
    "Selected prechecked answer + any additional text from question 4.1 step 4": "{{p permitted_uses_block}}",
    "Selected prechecked answer + any additional text from question 4.2 step 4": "{{p prohibited_conduct_block}}",
    "Selected prechecked answer + any additional text from question 5.2 step 5": "{{p ai_agent_oversight_block}}",
    "Selected prechecked answer + any additional text from question 6.1 step 6": "{{p reportable_incidents_block}}",
    "Same as version below": "{{ version }}",
    "INSERT DATE": "{{ effective_date }}",
    "One Year from effective date": "{{ next_review_date }}",
    "INHERITTED ORGANIZATION NAME": "{{ org_name }}",
    "Name of Policy Owner": "{{ policy_owner_name }}",
    "Name of Policy approver": "{{ approver_name }}",
    "DATE defined as per EST": "{{ effective_date }}",
    "Same as above for first draft": "{{ review_date }}",
}
for _tier_i, (_examples_q, _rule_q) in enumerate([(1, 2), (3, 4), (5, 6), (7, 8)], start=1):
    SIMPLE_MARKERS[_tier_marker(_examples_q)] = f"{{{{ tier{_tier_i}_examples }}}}"
    SIMPLE_MARKERS[_tier_marker(_rule_q)] = f"{{{{ tier{_tier_i}_rule }}}}"


def _set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    """Clears every run but the first (whose formatting is preserved) and
    sets the given text into it - never trust a single run to already
    contain a whole marker or heading, since Word frequently splits text
    across multiple runs even within one paragraph (confirmed here: even
    "3.2  Department AI Leads" alone is split across 2 runs)."""
    for run in paragraph.runs[1:]:
        run._element.getparent().remove(run._element)
    if paragraph.runs:
        paragraph.runs[0].text = text
    else:
        paragraph.add_run(text)


def _insert_paragraph_before(paragraph: Paragraph, text: str) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addprevious(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    new_para.add_run(text)
    return new_para


def _insert_paragraph_after(paragraph: Paragraph, text: str) -> Paragraph:
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    new_para.add_run(text)
    return new_para


def _insert_row_before(table: Table, ref_row: _Row) -> _Row:
    new_tr = copy.deepcopy(ref_row._tr)
    ref_row._tr.addprevious(new_tr)
    return _Row(new_tr, table)


def _insert_row_after(table: Table, ref_row: _Row) -> _Row:
    new_tr = copy.deepcopy(ref_row._tr)
    ref_row._tr.addnext(new_tr)
    return _Row(new_tr, table)


def _replace_markers_in_paragraph(paragraph: Paragraph) -> None:
    text = paragraph.text
    if "<<" not in text:
        return
    new_text = text
    for match in MARKER_RE.finditer(text):
        raw = match.group(0)
        inner = _normalize(match.group(1))
        if inner not in SIMPLE_MARKERS:
            raise ValueError(f"Unmapped template marker {inner!r} in paragraph: {text!r}")
        new_text = new_text.replace(raw, SIMPLE_MARKERS[inner])
    _set_paragraph_text(paragraph, new_text)


def _find_heading_paragraph(doc: DocxDocument, heading_prefix: str, marker_substr: str) -> Paragraph:
    for paragraph in doc.paragraphs:
        if paragraph.text.startswith(heading_prefix) and marker_substr in paragraph.text:
            return paragraph
    raise ValueError(f"Could not find heading paragraph starting with {heading_prefix!r}")


def _find_paragraph_by_exact_text(doc: DocxDocument, exact_text: str) -> Paragraph:
    for paragraph in doc.paragraphs:
        if paragraph.text.strip() == exact_text:
            return paragraph
    raise ValueError(f"Could not find paragraph with exact text: {exact_text!r}")


def _split_required_table_heading(doc: DocxDocument, heading_prefix: str, table_tag: str) -> None:
    """3.1 (governance owner) and 3.5 (approvers): required fields, always
    present, so just split the heading from its marker line and insert the
    subdoc tag as its own paragraph - no conditional needed."""
    heading = _find_heading_paragraph(doc, heading_prefix, "table as described")
    heading_text = heading.text.split("\n")[0]
    _set_paragraph_text(heading, heading_text)
    _insert_paragraph_after(heading, f"{{{{p {table_tag}}}}}")


def _wrap_optional_table_section(
    doc: DocxDocument, heading_prefix: str, condition_var: str, table_tag: str, last_bullet_text: str
) -> None:
    """3.2 (dept leads) and 3.3 (legal lead): optional - per the template's
    own updated instruction, the WHOLE subsection (heading through its
    description bullets) must be omitted, not just show a fallback
    sentence, when the user left that question blank. Wraps the heading
    paragraph through the subsection's last bullet in a Jinja if/endif."""
    heading = _find_heading_paragraph(doc, heading_prefix, "This section should only be included")
    heading_text = heading.text.split("\n")[0]
    _set_paragraph_text(heading, heading_text)

    _insert_paragraph_before(heading, f"{{%p if {condition_var} %}}")
    _insert_paragraph_after(heading, f"{{{{p {table_tag}}}}}")

    last_bullet = _find_paragraph_by_exact_text(doc, last_bullet_text)
    _insert_paragraph_after(last_bullet, "{%p endif %}")


def _restructure_oversight_row_loop(doc: DocxDocument) -> None:
    """Table 12 (human oversight): one templated row becomes N rows via a
    dedicated for-row / data-row / endfor-row triple - {%tr %} must be the
    SOLE content of its own row, so the for/endfor tags can't share the
    data row with the {{ }} value tags."""
    oversight_table = doc.tables[12]
    data_row = oversight_table.rows[1]
    _set_paragraph_text(data_row.cells[0].paragraphs[0], "{{ row.use_case }}")
    _set_paragraph_text(data_row.cells[1].paragraphs[0], "{{ row.requirement }}")
    _set_paragraph_text(data_row.cells[2].paragraphs[0], "{{ row.qualification }}")

    for_row = _insert_row_before(oversight_table, data_row)
    _set_paragraph_text(for_row.cells[0].paragraphs[0], "{%tr for row in oversight_rows %}")
    endfor_row = _insert_row_after(oversight_table, data_row)
    _set_paragraph_text(endfor_row.cells[0].paragraphs[0], "{%tr endfor %}")


def _fill_severity_table(doc: DocxDocument) -> None:
    """Table 14 (severity): each row's two marker cells (Definition,
    Response Timescale) contain IDENTICAL marker text (e.g. both say
    "<<Answer from question 6.2 step 6 for severity High>>"), so they can't
    go through the generic text->tag dict (which one would the value mean?)
    - filled directly by row/column position instead."""
    severity_table = doc.tables[14]
    for i, level in enumerate(("high", "medium", "low"), start=1):
        _set_paragraph_text(severity_table.rows[i].cells[1].paragraphs[0], f"{{{{ severity_{level}_definition }}}}")
        _set_paragraph_text(severity_table.rows[i].cells[2].paragraphs[0], f"{{{{ severity_{level}_timeline }}}}")


def _fill_version_cell(doc: DocxDocument) -> None:
    """Table 1's Version cell reads "1 for initial draft" with no <<>>
    marker of its own (Table 0's cover block cross-references it as
    "Same as version below" instead) - filled directly by position."""
    metadata_table = doc.tables[1]
    _set_paragraph_text(metadata_table.rows[5].cells[1].paragraphs[0], "{{ version }}")


def _find_remaining_markers(doc: DocxDocument) -> list[str]:
    remaining = []
    for paragraph in doc.paragraphs:
        remaining.extend(MARKER_RE.findall(paragraph.text))
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    remaining.extend(MARKER_RE.findall(paragraph.text))
    return remaining


def build_template(source_path: Path) -> bytes:
    doc = docx.Document(str(source_path))

    # Structural transforms first, so their target paragraphs/cells no
    # longer contain "<<" by the time the generic pass runs.
    _split_required_table_heading(doc, "3.1  AI Governance Owner", "governance_owner_table")
    _split_required_table_heading(doc, "3.5  AI Governance approvers", "governance_approvers_table")
    _wrap_optional_table_section(
        doc,
        "3.2  Department AI Leads",
        "dept_leads_rows",
        "dept_leads_table",
        "Reporting AI incidents or suspected violations to the AI Governance Owner",
    )
    _wrap_optional_table_section(
        doc,
        "3.3  Legal & Compliance Lead",
        "legal_lead_rows",
        "legal_lead_table",
        "Reviewing and signing off on policy updates",
    )
    _restructure_oversight_row_loop(doc)
    _fill_severity_table(doc)
    _fill_version_cell(doc)

    # Generic pass: every remaining <<...>> marker, inline or whole-paragraph.
    for paragraph in doc.paragraphs:
        _replace_markers_in_paragraph(paragraph)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    _replace_markers_in_paragraph(paragraph)

    remaining = _find_remaining_markers(doc)
    if remaining:
        raise ValueError(f"Unhandled template markers left after transform: {remaining}")

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
