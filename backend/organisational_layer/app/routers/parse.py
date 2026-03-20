import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.schemas.parse import ParseResponse, ParseTextRequest
from app.services.request_parser import create_request

router = APIRouter(prefix="/api/parse", tags=["Parse"])
logger = logging.getLogger(__name__)

ACCEPTED_MEDIA_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}


@router.post("/text", response_model=ParseResponse)
async def parse_text(payload: ParseTextRequest):
    """Convert raw procurement text into a structured purchase request."""
    logger.info(
        "parse.text request received text_length=%s",
        len(payload.text),
    )
    try:
        result = create_request(file_content=payload.text)
    except Exception as exc:
        logger.exception("parse.text failed")
        raise HTTPException(status_code=502, detail=f"Parsing failed: {exc}") from exc
    logger.info(
        "parse.text response complete=%s request_keys=%s category_l1=%r category_l2=%r",
        result.get("complete"),
        list((result.get("request") or {}).keys()),
        (result.get("request") or {}).get("category_l1"),
        (result.get("request") or {}).get("category_l2"),
    )
    return result


@router.post("/file", response_model=ParseResponse)
async def parse_file(
    file: UploadFile = File(...),
    context_text: str | None = Form(default=None),
):
    """Convert an uploaded file (PDF or image) into a structured purchase request."""
    content_type = file.content_type or "application/octet-stream"
    normalized_context_text = context_text.strip() if context_text else None
    logger.info(
        "parse.file request received filename=%r content_type=%s context_text_length=%s",
        file.filename,
        content_type,
        len(normalized_context_text) if normalized_context_text else 0,
    )

    if content_type not in ACCEPTED_MEDIA_TYPES:
        logger.warning(
            "parse.file unsupported media type filename=%r content_type=%s",
            file.filename,
            content_type,
        )
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{content_type}'. Accepted: {', '.join(sorted(ACCEPTED_MEDIA_TYPES))}",
        )

    file_bytes = await file.read()
    logger.info(
        "parse.file payload read filename=%r size=%s",
        file.filename,
        len(file_bytes),
    )
    if not file_bytes:
        logger.warning("parse.file empty upload filename=%r", file.filename)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        result = create_request(
            file_bytes=file_bytes,
            media_type=content_type,
            context_text=normalized_context_text,
        )
    except Exception as exc:
        logger.exception("parse.file failed filename=%r", file.filename)
        raise HTTPException(status_code=502, detail=f"Parsing failed: {exc}") from exc
    logger.info(
        "parse.file response filename=%r complete=%s request_keys=%s category_l1=%r category_l2=%r",
        file.filename,
        result.get("complete"),
        list((result.get("request") or {}).keys()),
        (result.get("request") or {}).get("category_l1"),
        (result.get("request") or {}).get("category_l2"),
    )
    return result
