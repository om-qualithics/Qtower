"""Renders a scan's findings as a downloadable PDF - the one genuinely
new capability this feature needs (nothing in this codebase generates
PDFs today, only .docx via docxtpl for policy documents). HTML+CSS via
Jinja2 (already a transitive dependency of docxtpl, used directly here)
rendered to PDF via weasyprint - chosen over a programmatic drawing API
(reportlab) since a findings table with grouping/styling is far easier
to get "clean and understandable" from HTML+CSS than from draw calls.
A fixed light theme is used regardless of the viewer's app theme - a PDF
export doesn't chase live theme state, same as any other static document
export."""

from datetime import datetime, timezone

from jinja2 import Template

from apps.api.modules.codescan.taxonomy import TIER1_CATEGORIES, category_label

# weasyprint is imported lazily inside render_report_pdf(), not at module
# load time: it dlopen()s native Pango/GObject libraries on import, which
# aren't present on a native Windows dev machine (this app otherwise runs
# entirely natively there, no Docker, per this repo's dev convention) -
# importing it eagerly here would crash the whole API process on startup
# rather than failing only when a PDF is actually rendered. The real
# scanning pipeline (and this function) only ever runs inside the Linux
# Docker deployment, where infra/Dockerfile.api installs weasyprint's
# system dependencies.

_SEVERITY_COLOR = {"critical": "#B3261E", "high": "#E0A33C", "medium": "#5B4FCF", "low": "#6B6558"}

# Matches Qtower_CodeScan_Phase1_Handoff.md's "## Report structure" section
# exactly: an executive summary (severity counts, unchanged from before),
# then a full 30-item taxonomy table (issue | found yes/no | occurrence
# count - a checklist against every Tier 1 category, not just the ones that
# fired), then findings grouped by SEVERITY (critical -> high -> medium ->
# low), each severity's table columns being Issue category | File | line |
# description | tool used | confidence - a deliberate change from the
# previous "grouped by category, severities mixed" layout, since the point
# of this structure is "what needs fixing first," not "what kind of bug is
# this."
_TEMPLATE = Template(
    """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; color: #1F1A14; font-size: 11px; }
  h1 { color: #5B4FCF; font-size: 22px; margin-bottom: 4px; }
  .subtitle { color: #6B6558; font-size: 12px; margin-bottom: 24px; }
  .summary { display: flex; gap: 12px; margin-bottom: 24px; }
  .stat { border: 1px solid #E5DEC9; border-radius: 8px; padding: 10px 16px; }
  .stat .n { font-size: 20px; font-weight: bold; }
  .stat .label { font-size: 10px; color: #6B6558; text-transform: uppercase; }
  h2 { color: #1F1A14; font-size: 15px; border-bottom: 2px solid #E5DEC9; padding-bottom: 4px; margin-top: 28px; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  th { text-align: left; background: #F6F4EE; padding: 6px 8px; font-size: 10px; text-transform: uppercase; color: #6B6558; }
  td { padding: 6px 8px; border-bottom: 1px solid #E5DEC9; vertical-align: top; }
  .sev { display: inline-block; padding: 2px 8px; border-radius: 10px; color: white; font-size: 9px; font-weight: bold; text-transform: uppercase; }
  .trend { color: #6B6558; font-size: 11px; margin-bottom: 16px; }
  .found-yes { color: #B3261E; font-weight: bold; }
  .found-no { color: #6B6558; }
  .footer { margin-top: 30px; font-size: 9px; color: #999; }
  .empty { color: #6B6558; font-style: italic; padding: 8px 0; }
</style>
</head>
<body>
  <h1>Q Tower — Code Scan Report</h1>
  <div class="subtitle">{{ repo_full_name }} @ {{ commit_sha[:8] if commit_sha else "unknown" }} &middot; Scanned {{ scanned_at }}</div>

  <div class="summary">
    {% for sev in ["critical", "high", "medium", "low"] %}
    <div class="stat">
      <div class="n" style="color: {{ severity_color[sev] }}">{{ counts.get(sev, 0) }}</div>
      <div class="label">{{ sev }}</div>
    </div>
    {% endfor %}
  </div>

  {% if trend_note %}<div class="trend">{{ trend_note }}</div>{% endif %}

  <h2>Summary — Tier 1 taxonomy (30 categories)</h2>
  <table>
    <tr><th>#</th><th>Issue</th><th>Found</th><th>Number</th></tr>
    {% for row in taxonomy_summary %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ row.label }}</td>
      <td class="{{ 'found-yes' if row.count > 0 else 'found-no' }}">{{ "Yes" if row.count > 0 else "No" }}</td>
      <td>{{ row.count }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>Findings by severity</h2>
  {% for sev in ["critical", "high", "medium", "low"] %}
  <h3 style="font-size: 12px; margin-top: 16px; text-transform: capitalize;">{{ sev }} severity findings</h3>
  {% set group = findings_by_severity.get(sev, []) %}
  {% if group %}
  <table>
    <tr><th>Issue category</th><th>File</th><th>Line</th><th>Description</th><th>Tool used</th><th>Confidence</th></tr>
    {% for f in group %}
    <tr>
      <td>{{ category_label(f.category) }}</td>
      <td>{{ f.file_path }}</td>
      <td>{{ f.line_start or "-" }}</td>
      <td>{{ f.description }}</td>
      <td>{{ f.sources|join(", ") }}</td>
      <td>{{ f.confidence }}</td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p class="empty">No {{ sev }} severity findings.</p>
  {% endif %}
  {% endfor %}

  <div class="footer">Generated by Q Tower AI Code Scan (Phase 1) - detection and reporting only, not a merge/deploy gate.</div>
</body>
</html>
"""
)


def render_report_pdf(
    *,
    repo_full_name: str,
    commit_sha: str | None,
    findings: list[dict],
    counts: dict[str, int],
    trend_note: str | None,
) -> bytes:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ordered_findings = sorted(findings, key=lambda f: severity_rank.get(f["severity"], 99))

    by_severity: dict[str, list[dict]] = {"critical": [], "high": [], "medium": [], "low": []}
    for f in ordered_findings:
        by_severity.setdefault(f["severity"], []).append(f)

    category_counts: dict[str, int] = {}
    for f in findings:
        category_counts[f["category"]] = category_counts.get(f["category"], 0) + 1
    taxonomy_summary = [{"label": c.label, "count": category_counts.get(c.key, 0)} for c in TIER1_CATEGORIES]

    html_content = _TEMPLATE.render(
        repo_full_name=repo_full_name,
        commit_sha=commit_sha,
        scanned_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        counts=counts,
        trend_note=trend_note,
        taxonomy_summary=taxonomy_summary,
        findings_by_severity=by_severity,
        severity_color=_SEVERITY_COLOR,
        category_label=category_label,
    )
    from weasyprint import HTML  # see module docstring - imported lazily on purpose

    return HTML(string=html_content).write_pdf()
