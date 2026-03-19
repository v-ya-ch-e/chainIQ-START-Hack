"""Pipeline status, result, and audit read endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.clients.organisational import OrganisationalClient
from app.dependencies import get_org_client, get_pipeline_runner
from app.pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Status"])


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_text(value: str, width: int = 96) -> list[str]:
    if len(value) <= width:
        return [value]
    chunks: list[str] = []
    cursor = 0
    while cursor < len(value):
        chunks.append(value[cursor: cursor + width])
        cursor += width
    return chunks


def _render_simple_pdf(lines: list[str]) -> bytes:
    rendered_lines = ["BT", "/F1 11 Tf", "50 760 Td", "14 TL"]
    for line in lines:
        for chunk in _wrap_text(line):
            rendered_lines.append(f"({_escape_pdf_text(chunk)}) Tj")
            rendered_lines.append("T*")
    rendered_lines.append("ET")
    stream = "\n".join(rendered_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    parts: list[bytes] = [header]
    offsets = [0]
    current_offset = len(header)

    for index, body in enumerate(objects, start=1):
        obj = f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        offsets.append(current_offset)
        parts.append(obj)
        current_offset += len(obj)

    xref_offset = current_offset
    xref = [f"xref\n0 {len(offsets)}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode("ascii"))

    trailer = (
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")

    return b"".join(parts + xref + [trailer])


@router.get("/status/{request_id}")
async def get_pipeline_status(
    request_id: str,
    org: OrganisationalClient = Depends(get_org_client),
    runner: PipelineRunner = Depends(get_pipeline_runner),
):
    """Get the latest processing status for a request."""
    try:
        runs = await org.get_runs_by_request(request_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")

    if not runs:
        response: dict = {
            "request_id": request_id,
            "latest_run": None,
            "state": "not_started",
            "message": "No pipeline runs found",
        }
        cached = runner.get_cached_result(request_id)
        if cached:
            response["recommendation_status"] = cached.recommendation.status
            response["escalation_count"] = len(cached.escalations)
            response["confidence_score"] = cached.recommendation.confidence_score
        return response

    latest = runs[0] if isinstance(runs, list) else runs
    if isinstance(runs, list) and runs:
        latest = runs[0]

    cached = runner.get_cached_result(request_id)

    response: dict = {
        "request_id": request_id,
        "latest_run": latest,
        "state": (
            latest.get("status")
            if isinstance(latest, dict) and isinstance(latest.get("status"), str)
            else "unknown"
        ),
    }

    if cached:
        response["recommendation_status"] = cached.recommendation.status
        response["escalation_count"] = len(cached.escalations)
        response["confidence_score"] = cached.recommendation.confidence_score

    return response


@router.get("/report/{request_id}")
async def get_audit_report(
    request_id: str,
    org: OrganisationalClient = Depends(get_org_client),
    runner: PipelineRunner = Depends(get_pipeline_runner),
):
    """Generate and download a PDF audit report for a request."""
    try:
        runs = await org.get_runs_by_request(request_id)
        summary = await org.get_audit_summary(request_id)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 404:
            raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
        detail = f"Failed to build audit report: upstream returned {status}"
        raise HTTPException(status_code=502, detail=detail)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")

    if not runs:
        raise HTTPException(
            status_code=404,
            detail="No pipeline runs found for this request; cannot build audit report.",
        )

    latest_run = runs[0] if isinstance(runs, list) else runs
    if isinstance(runs, list) and runs:
        latest_run = runs[0]

    cached = runner.get_cached_result(request_id)
    summary_record = summary if isinstance(summary, dict) else {}
    latest_record = latest_run if isinstance(latest_run, dict) else {}

    report_lines = [
        "ChainIQ Audit Report",
        "",
        f"Generated UTC: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"Request ID: {request_id}",
        f"Latest Run ID: {latest_record.get('run_id', 'n/a')}",
        f"Run Status: {latest_record.get('status', 'unknown')}",
        f"Run Started At: {latest_record.get('started_at', 'n/a')}",
        f"Run Finished At: {latest_record.get('ended_at', 'n/a')}",
        "",
        "Audit Summary",
        f"Total Entries: {summary_record.get('total_entries', 0)}",
        f"Info Entries: {summary_record.get('info_entries', 0)}",
        f"Warning Entries: {summary_record.get('warning_entries', 0)}",
        f"Error Entries: {summary_record.get('error_entries', 0)}",
        "",
    ]
    if cached:
        report_lines.extend(
            [
                "Recommendation Snapshot",
                f"Recommendation Status: {cached.recommendation.status}",
                f"Confidence Score: {cached.recommendation.confidence_score}",
                f"Escalation Count: {len(cached.escalations)}",
            ]
        )
    else:
        report_lines.extend(
            [
                "Recommendation Snapshot",
                "No cached pipeline result available in current logical service instance.",
            ]
        )

    pdf_bytes = _render_simple_pdf(report_lines)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{request_id}-audit-report.pdf"',
        },
    )


@router.get("/result/{request_id}")
async def get_pipeline_result(
    request_id: str,
    runner: PipelineRunner = Depends(get_pipeline_runner),
):
    """Get the full pipeline result from the latest successful run."""
    cached = runner.get_cached_result(request_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail="No pipeline result found. Process the request first.",
        )
    return cached.model_dump()


@router.get("/runs")
async def list_runs(
    request_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    org: OrganisationalClient = Depends(get_org_client),
):
    """List all pipeline runs with filters."""
    try:
        return await org.get_runs(
            request_id=request_id, status=status, skip=skip, limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    org: OrganisationalClient = Depends(get_org_client),
):
    """Get a specific run with all step details."""
    try:
        return await org.get_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")


@router.get("/audit/{request_id}")
async def get_audit_trail(
    request_id: str,
    level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    step_name: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    org: OrganisationalClient = Depends(get_org_client),
):
    """Get full audit trail for a request."""
    try:
        return await org.get_audit_by_request(
            request_id,
            level=level,
            category=category,
            run_id=run_id,
            step_name=step_name,
            skip=skip,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")


@router.get("/audit/{request_id}/summary")
async def get_audit_summary(
    request_id: str,
    org: OrganisationalClient = Depends(get_org_client),
):
    """Get aggregated audit summary for a request."""
    try:
        return await org.get_audit_summary(request_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Org Layer unreachable: {exc}")
