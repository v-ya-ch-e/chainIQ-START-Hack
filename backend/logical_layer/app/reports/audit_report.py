"""PDF audit report generator for pipeline results.

Aggregates pipeline output, audit logs, and audit summary into a
professional A4 PDF document using reportlab.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Colour palette ──────────────────────────────────────────────

BRAND_DARK = colors.HexColor("#0f172a")
BRAND_PRIMARY = colors.HexColor("#1e40af")
BRAND_LIGHT = colors.HexColor("#dbeafe")
HEADER_BG = colors.HexColor("#1e293b")
ROW_ALT = colors.HexColor("#f8fafc")
ROW_WHITE = colors.white
BORDER = colors.HexColor("#cbd5e1")

SEVERITY_COLORS = {
    "critical": colors.HexColor("#dc2626"),
    "high": colors.HexColor("#ea580c"),
    "medium": colors.HexColor("#d97706"),
    "low": colors.HexColor("#2563eb"),
    "info": colors.HexColor("#6b7280"),
}

STATUS_COLORS = {
    "proceed": colors.HexColor("#16a34a"),
    "proceed_with_conditions": colors.HexColor("#d97706"),
    "cannot_proceed": colors.HexColor("#dc2626"),
    "processed": colors.HexColor("#16a34a"),
    "invalid": colors.HexColor("#dc2626"),
}

LEVEL_COLORS = {
    "error": colors.HexColor("#dc2626"),
    "critical": colors.HexColor("#dc2626"),
    "warn": colors.HexColor("#d97706"),
    "warning": colors.HexColor("#d97706"),
    "info": colors.HexColor("#2563eb"),
    "debug": colors.HexColor("#6b7280"),
}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def _get_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=20,
            leading=24,
            textColor=BRAND_DARK,
            spaceAfter=2 * mm,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=6 * mm,
        ),
        "h2": ParagraphStyle(
            "SectionH2",
            parent=base["Heading2"],
            fontSize=13,
            leading=16,
            textColor=BRAND_PRIMARY,
            spaceBefore=8 * mm,
            spaceAfter=3 * mm,
            borderPadding=(0, 0, 1 * mm, 0),
        ),
        "body": ParagraphStyle(
            "BodyText",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=BRAND_DARK,
        ),
        "small": ParagraphStyle(
            "SmallText",
            parent=base["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#475569"),
        ),
        "cell": ParagraphStyle(
            "CellText",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=BRAND_DARK,
        ),
        "cell_header": ParagraphStyle(
            "CellHeader",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.white,
            fontName="Helvetica-Bold",
        ),
        "badge_ok": ParagraphStyle(
            "BadgeOk",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#16a34a"),
            fontName="Helvetica-Bold",
        ),
        "badge_fail": ParagraphStyle(
            "BadgeFail",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#dc2626"),
            fontName="Helvetica-Bold",
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(str(text), style)


def _safe(val: Any, fallback: str = "—") -> str:
    if val is None or val == "" or val == []:
        return fallback
    return str(val)


def _table(
    data: list[list],
    col_widths: list[float] | None = None,
    *,
    first_row_header: bool = True,
) -> Table:
    """Build a styled table with alternating rows."""
    t = Table(data, colWidths=col_widths, repeatRows=1 if first_row_header else 0)
    cmds: list[tuple] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
    ]
    if first_row_header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), HEADER_BG))
        cmds.append(("TEXTCOLOR", (0, 0), (-1, 0), colors.white))
    for i in range(1 if first_row_header else 0, len(data)):
        bg = ROW_ALT if i % 2 == 0 else ROW_WHITE
        cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(cmds))
    return t


def _severity_para(sev: str, style: ParagraphStyle) -> Paragraph:
    c = SEVERITY_COLORS.get(sev, colors.HexColor("#6b7280"))
    return Paragraph(f'<font color="{c.hexval()}">{sev.upper()}</font>', style)


def _bool_str(val: Any) -> str:
    if isinstance(val, bool):
        return "Yes" if val else "No"
    return _safe(val)


# ── Section builders ────────────────────────────────────────────


def _build_header(
    result: dict, styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = []
    req_id = result.get("request_id", "Unknown")
    processed = result.get("processed_at", "")
    run_id = result.get("run_id", "")
    status = result.get("status", "unknown")

    elements.append(_p("ChainIQ — Audit Report", styles["title"]))

    status_color = STATUS_COLORS.get(status, colors.HexColor("#6b7280"))
    meta = (
        f"Request: <b>{req_id}</b> &nbsp;|&nbsp; "
        f"Status: <font color=\"{status_color.hexval()}\"><b>{status.upper()}</b></font> &nbsp;|&nbsp; "
        f"Processed: {processed}"
    )
    if run_id:
        meta += f" &nbsp;|&nbsp; Run: {run_id[:8]}…"
    elements.append(_p(meta, styles["subtitle"]))

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    elements.append(_p(f"Report generated: {generated}", styles["small"]))
    elements.append(Spacer(1, 4 * mm))
    return elements


def _build_request_interpretation(
    result: dict, styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = [_p("1. Request Interpretation", styles["h2"])]
    ri = result.get("request_interpretation") or {}
    rows = [
        ("Category", f'{_safe(ri.get("category_l1"))} / {_safe(ri.get("category_l2"))}'),
        ("Quantity", f'{_safe(ri.get("quantity"))} {_safe(ri.get("unit_of_measure"), "")}'),
        ("Budget", f'{_safe(ri.get("currency"))} {_safe(ri.get("budget_amount"))}'),
        ("Delivery Country", _safe(ri.get("delivery_country"))),
        ("Required By", f'{_safe(ri.get("required_by_date"))} ({_safe(ri.get("days_until_required"))} days)'),
        ("Data Residency Required", _bool_str(ri.get("data_residency_required"))),
        ("ESG Requirement", _bool_str(ri.get("esg_requirement"))),
        ("Preferred Supplier", _safe(ri.get("preferred_supplier_stated"))),
        ("Incumbent Supplier", _safe(ri.get("incumbent_supplier"))),
        ("Requester Instruction", _safe(ri.get("requester_instruction"))),
    ]
    data = [
        [_p("Field", styles["cell_header"]), _p("Value", styles["cell_header"])]
    ] + [
        [_p(label, styles["cell"]), _p(value, styles["cell"])]
        for label, value in rows
    ]
    elements.append(_table(data, col_widths=[CONTENT_W * 0.35, CONTENT_W * 0.65]))
    return elements


def _build_validation(
    result: dict, styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = [_p("2. Validation Results", styles["h2"])]
    val = result.get("validation") or {}
    comp = val.get("completeness", "unknown")
    comp_style = styles["badge_ok"] if comp == "pass" else styles["badge_fail"]
    elements.append(_p(f"Completeness: <b>{comp.upper()}</b>", comp_style))
    elements.append(Spacer(1, 2 * mm))

    issues = val.get("issues_detected") or []
    if not issues:
        elements.append(_p("No validation issues detected.", styles["body"]))
        return elements

    header = [
        _p("ID", styles["cell_header"]),
        _p("Severity", styles["cell_header"]),
        _p("Type", styles["cell_header"]),
        _p("Description", styles["cell_header"]),
        _p("Action Required", styles["cell_header"]),
    ]
    data = [header]
    for iss in issues:
        data.append([
            _p(_safe(iss.get("issue_id")), styles["cell"]),
            _severity_para(_safe(iss.get("severity")), styles["cell"]),
            _p(_safe(iss.get("type")), styles["cell"]),
            _p(_safe(iss.get("description")), styles["cell"]),
            _p(_safe(iss.get("action_required")), styles["cell"]),
        ])
    widths = [CONTENT_W * w for w in [0.07, 0.08, 0.12, 0.40, 0.33]]
    elements.append(_table(data, col_widths=widths))
    return elements


def _build_policy_evaluation(
    result: dict, styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = [_p("3. Policy Evaluation", styles["h2"])]
    pe = result.get("policy_evaluation") or {}

    # Approval threshold
    at = pe.get("approval_threshold") or {}
    if at.get("rule_applied"):
        elements.append(_p("<b>Approval Threshold</b>", styles["body"]))
        elements.append(Spacer(1, 1 * mm))
        at_rows = [
            ("Rule Applied", _safe(at.get("rule_applied"))),
            ("Basis", _safe(at.get("basis"))),
            ("Quotes Required", _safe(at.get("quotes_required"))),
            ("Approvers", ", ".join(at.get("approvers") or []) or "—"),
            ("Deviation Approval", _safe(at.get("deviation_approval"))),
        ]
        if at.get("note"):
            at_rows.append(("Note", at["note"]))
        data = [
            [_p("Field", styles["cell_header"]), _p("Value", styles["cell_header"])]
        ] + [
            [_p(l, styles["cell"]), _p(v, styles["cell"])] for l, v in at_rows
        ]
        elements.append(_table(data, col_widths=[CONTENT_W * 0.25, CONTENT_W * 0.75]))
        elements.append(Spacer(1, 3 * mm))

    # Preferred supplier
    ps = pe.get("preferred_supplier") or {}
    if ps.get("supplier"):
        elements.append(_p("<b>Preferred Supplier Assessment</b>", styles["body"]))
        elements.append(Spacer(1, 1 * mm))
        ps_rows = [
            ("Supplier", _safe(ps.get("supplier"))),
            ("Status", _safe(ps.get("status"))),
            ("Is Preferred", _bool_str(ps.get("is_preferred"))),
            ("Covers Delivery Country", _bool_str(ps.get("covers_delivery_country"))),
            ("Is Restricted", _bool_str(ps.get("is_restricted"))),
        ]
        if ps.get("policy_note"):
            ps_rows.append(("Policy Note", ps["policy_note"]))
        data = [
            [_p("Field", styles["cell_header"]), _p("Value", styles["cell_header"])]
        ] + [
            [_p(l, styles["cell"]), _p(v, styles["cell"])] for l, v in ps_rows
        ]
        elements.append(_table(data, col_widths=[CONTENT_W * 0.25, CONTENT_W * 0.75]))
        elements.append(Spacer(1, 3 * mm))

    # Restricted suppliers
    rs = pe.get("restricted_suppliers") or {}
    if rs:
        elements.append(_p("<b>Restricted Supplier Checks</b>", styles["body"]))
        elements.append(Spacer(1, 1 * mm))
        header = [
            _p("Supplier Key", styles["cell_header"]),
            _p("Restricted", styles["cell_header"]),
            _p("Note", styles["cell_header"]),
        ]
        data = [header]
        for key, val_dict in rs.items():
            if isinstance(val_dict, dict):
                data.append([
                    _p(key, styles["cell"]),
                    _p(_bool_str(val_dict.get("restricted")), styles["cell"]),
                    _p(_safe(val_dict.get("note")), styles["cell"]),
                ])
        if len(data) > 1:
            elements.append(_table(data, col_widths=[CONTENT_W * 0.30, CONTENT_W * 0.12, CONTENT_W * 0.58]))

    # Applied rules
    for rule_key, label in [
        ("category_rules_applied", "Category Rules"),
        ("geography_rules_applied", "Geography Rules"),
    ]:
        rules = pe.get(rule_key) or []
        if rules:
            elements.append(Spacer(1, 2 * mm))
            elements.append(_p(f"<b>{label}:</b> {len(rules)} rule(s) applied", styles["body"]))

    return elements


def _build_supplier_shortlist(
    result: dict, styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = [_p("4. Supplier Shortlist", styles["h2"])]
    suppliers = result.get("supplier_shortlist") or []
    if not suppliers:
        elements.append(_p("No compliant suppliers found.", styles["body"]))
        return elements

    currency = (result.get("request_interpretation") or {}).get("currency", "EUR")
    cur_lower = currency.lower() if currency else "eur"

    header = [
        _p("#", styles["cell_header"]),
        _p("Supplier", styles["cell_header"]),
        _p("Tier", styles["cell_header"]),
        _p("Unit Price", styles["cell_header"]),
        _p("Total", styles["cell_header"]),
        _p("Lead (std/exp)", styles["cell_header"]),
        _p("Qual", styles["cell_header"]),
        _p("Risk", styles["cell_header"]),
        _p("ESG", styles["cell_header"]),
        _p("Flags", styles["cell_header"]),
    ]
    data = [header]
    for s in suppliers:
        flags = []
        if s.get("preferred"):
            flags.append("Pref")
        if s.get("incumbent"):
            flags.append("Inc")
        if s.get("policy_compliant"):
            flags.append("Compl")

        unit_key = f"unit_price_{cur_lower}"
        total_key = f"total_price_{cur_lower}"
        unit = s.get(unit_key) or s.get("unit_price")
        total = s.get(total_key) or s.get("total_price")

        data.append([
            _p(str(s.get("rank", "")), styles["cell"]),
            _p(f'{_safe(s.get("supplier_name"))}\n({_safe(s.get("supplier_id"))})', styles["cell"]),
            _p(_safe(s.get("pricing_tier_applied")), styles["cell"]),
            _p(f"{currency} {unit:,.2f}" if unit else "—", styles["cell"]),
            _p(f"{currency} {total:,.2f}" if total else "—", styles["cell"]),
            _p(
                f'{_safe(s.get("standard_lead_time_days"))}d / {_safe(s.get("expedited_lead_time_days"))}d',
                styles["cell"],
            ),
            _p(str(s.get("quality_score", "—")), styles["cell"]),
            _p(str(s.get("risk_score", "—")), styles["cell"]),
            _p(str(s.get("esg_score", "—")), styles["cell"]),
            _p(", ".join(flags) or "—", styles["cell"]),
        ])

    widths = [CONTENT_W * w for w in [0.04, 0.16, 0.10, 0.10, 0.12, 0.11, 0.06, 0.06, 0.06, 0.09]]
    elements.append(_table(data, col_widths=widths))

    # Recommendation notes per supplier
    notes = [(s.get("supplier_name"), s.get("recommendation_note")) for s in suppliers if s.get("recommendation_note")]
    if notes:
        elements.append(Spacer(1, 2 * mm))
        for name, note in notes:
            elements.append(_p(f"<b>{name}:</b> {note}", styles["small"]))
            elements.append(Spacer(1, 1 * mm))

    return elements


def _build_excluded_suppliers(
    result: dict, styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = [_p("5. Excluded Suppliers", styles["h2"])]
    excluded = result.get("suppliers_excluded") or []
    if not excluded:
        elements.append(_p("No suppliers were excluded.", styles["body"]))
        return elements

    header = [
        _p("Supplier ID", styles["cell_header"]),
        _p("Name", styles["cell_header"]),
        _p("Exclusion Reason", styles["cell_header"]),
    ]
    data = [header] + [
        [
            _p(_safe(s.get("supplier_id")), styles["cell"]),
            _p(_safe(s.get("supplier_name")), styles["cell"]),
            _p(_safe(s.get("reason")), styles["cell"]),
        ]
        for s in excluded
    ]
    elements.append(_table(data, col_widths=[CONTENT_W * 0.15, CONTENT_W * 0.25, CONTENT_W * 0.60]))
    return elements


def _build_escalations(
    result: dict, styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = [_p("6. Escalations", styles["h2"])]
    escalations = result.get("escalations") or []
    if not escalations:
        elements.append(_p("No escalations triggered.", styles["body"]))
        return elements

    header = [
        _p("ID", styles["cell_header"]),
        _p("Rule", styles["cell_header"]),
        _p("Trigger", styles["cell_header"]),
        _p("Escalate To", styles["cell_header"]),
        _p("Blocking", styles["cell_header"]),
    ]
    data = [header]
    for e in escalations:
        blocking = e.get("blocking", False)
        blocking_text = "YES" if blocking else "No"
        blocking_color = colors.HexColor("#dc2626") if blocking else colors.HexColor("#16a34a")
        data.append([
            _p(_safe(e.get("escalation_id")), styles["cell"]),
            _p(_safe(e.get("rule")), styles["cell"]),
            _p(_safe(e.get("trigger")), styles["cell"]),
            _p(_safe(e.get("escalate_to")), styles["cell"]),
            Paragraph(
                f'<font color="{blocking_color.hexval()}"><b>{blocking_text}</b></font>',
                styles["cell"],
            ),
        ])
    widths = [CONTENT_W * w for w in [0.08, 0.08, 0.48, 0.20, 0.08]]
    elements.append(_table(data, col_widths=widths))
    return elements


def _build_recommendation(
    result: dict, styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = [_p("7. Recommendation", styles["h2"])]
    rec = result.get("recommendation") or {}
    status = rec.get("status", "unknown")
    status_color = STATUS_COLORS.get(status, colors.HexColor("#6b7280"))

    elements.append(
        _p(f'Decision: <font color="{status_color.hexval()}"><b>{status.upper().replace("_", " ")}</b></font>', styles["body"])
    )
    elements.append(Spacer(1, 2 * mm))

    rows = [("Rationale", _safe(rec.get("reason")))]
    if rec.get("preferred_supplier_if_resolved"):
        rows.append(("Preferred Supplier (if resolved)", rec["preferred_supplier_if_resolved"]))
    if rec.get("preferred_supplier_rationale"):
        rows.append(("Supplier Rationale", rec["preferred_supplier_rationale"]))
    if rec.get("minimum_budget_required") is not None:
        cur = rec.get("minimum_budget_currency", "")
        rows.append(("Minimum Budget Required", f"{cur} {rec['minimum_budget_required']:,.2f}"))
    if rec.get("confidence_score"):
        rows.append(("Confidence Score", f'{rec["confidence_score"]}%'))

    data = [
        [_p("Field", styles["cell_header"]), _p("Value", styles["cell_header"])]
    ] + [
        [_p(l, styles["cell"]), _p(v, styles["cell"])] for l, v in rows
    ]
    elements.append(_table(data, col_widths=[CONTENT_W * 0.30, CONTENT_W * 0.70]))
    return elements


def _build_audit_trail_summary(
    result: dict,
    audit_summary: dict | None,
    styles: dict[str, ParagraphStyle],
) -> list:
    elements: list = [_p("8. Audit Trail Summary", styles["h2"])]
    at = result.get("audit_trail") or {}

    rows = [
        ("Policies Checked", ", ".join(at.get("policies_checked") or []) or "—"),
        ("Suppliers Evaluated", ", ".join(at.get("supplier_ids_evaluated") or []) or "—"),
        ("Pricing Tiers Applied", _safe(at.get("pricing_tiers_applied"))),
        ("Data Sources Used", ", ".join(at.get("data_sources_used") or []) or "—"),
        ("Historical Awards Consulted", _bool_str(at.get("historical_awards_consulted"))),
    ]
    if at.get("historical_award_note"):
        rows.append(("Historical Award Note", at["historical_award_note"]))

    if audit_summary:
        rows.append(("Total Audit Entries", str(audit_summary.get("total_entries", 0))))
        rows.append(("Escalation Count", str(audit_summary.get("escalation_count", 0))))
        first = audit_summary.get("first_event")
        last = audit_summary.get("last_event")
        if first:
            rows.append(("First Event", str(first)))
        if last:
            rows.append(("Last Event", str(last)))

    data = [
        [_p("Field", styles["cell_header"]), _p("Value", styles["cell_header"])]
    ] + [
        [_p(l, styles["cell"]), _p(v, styles["cell"])] for l, v in rows
    ]
    elements.append(_table(data, col_widths=[CONTENT_W * 0.30, CONTENT_W * 0.70]))
    return elements


def _build_audit_log_table(
    audit_logs: list[dict], styles: dict[str, ParagraphStyle]
) -> list:
    elements: list = [_p("9. Detailed Audit Log", styles["h2"])]
    if not audit_logs:
        elements.append(_p("No audit log entries available.", styles["body"]))
        return elements

    header = [
        _p("Timestamp", styles["cell_header"]),
        _p("Level", styles["cell_header"]),
        _p("Category", styles["cell_header"]),
        _p("Step", styles["cell_header"]),
        _p("Message", styles["cell_header"]),
    ]
    data = [header]
    for entry in audit_logs[:100]:
        ts = entry.get("timestamp", "")
        if isinstance(ts, str) and len(ts) > 19:
            ts = ts[:19]
        level = entry.get("level", "")
        lvl_color = LEVEL_COLORS.get(level, colors.HexColor("#6b7280"))
        data.append([
            _p(ts, styles["cell"]),
            Paragraph(f'<font color="{lvl_color.hexval()}">{level.upper()}</font>', styles["cell"]),
            _p(_safe(entry.get("category")), styles["cell"]),
            _p(_safe(entry.get("step_name")), styles["cell"]),
            _p(_safe(entry.get("message")), styles["cell"]),
        ])

    widths = [CONTENT_W * w for w in [0.14, 0.07, 0.11, 0.12, 0.56]]
    elements.append(_table(data, col_widths=widths))

    if len(audit_logs) > 100:
        elements.append(Spacer(1, 2 * mm))
        elements.append(
            _p(f"Showing first 100 of {len(audit_logs)} entries.", styles["small"])
        )
    return elements


# ── Footer ──────────────────────────────────────────────────────


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#94a3b8"))
    canvas.drawString(
        MARGIN, 10 * mm, f"ChainIQ Audit Report — Page {doc.page}"
    )
    canvas.drawRightString(
        PAGE_W - MARGIN,
        10 * mm,
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    )
    canvas.restoreState()


# ── Public API ──────────────────────────────────────────────────


def generate_audit_report(
    pipeline_result: dict,
    audit_logs: list[dict] | None = None,
    audit_summary: dict | None = None,
) -> io.BytesIO:
    """Generate a PDF audit report and return it as a BytesIO buffer.

    Args:
        pipeline_result: Full PipelineOutput dict.
        audit_logs: List of audit log entries (from org layer).
        audit_summary: Audit summary dict (from org layer).

    Returns:
        BytesIO buffer containing the rendered PDF.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=16 * mm,
        title=f"Audit Report — {pipeline_result.get('request_id', 'Unknown')}",
        author="ChainIQ Procurement Engine",
    )

    styles = _get_styles()
    elements: list = []

    elements.extend(_build_header(pipeline_result, styles))
    elements.extend(_build_request_interpretation(pipeline_result, styles))
    elements.extend(_build_validation(pipeline_result, styles))
    elements.extend(_build_policy_evaluation(pipeline_result, styles))
    elements.extend(_build_supplier_shortlist(pipeline_result, styles))
    elements.extend(_build_excluded_suppliers(pipeline_result, styles))
    elements.extend(_build_escalations(pipeline_result, styles))
    elements.extend(_build_recommendation(pipeline_result, styles))
    elements.extend(_build_audit_trail_summary(pipeline_result, audit_summary, styles))
    elements.extend(_build_audit_log_table(audit_logs or [], styles))

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
