from fastapi import APIRouter, HTTPException, UploadFile, File

from app.schemas.parse import ParseResponse, ParseTextRequest
from app.services.request_parser import create_request

router = APIRouter(prefix="/api/parse", tags=["Parse"])

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
    try:
        result = create_request(file_content=payload.text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Parsing failed: {exc}") from exc
    return result


@router.post("/file", response_model=ParseResponse)
async def parse_file(file: UploadFile = File(...)):
    """Convert an uploaded file (PDF or image) into a structured purchase request."""
    content_type = file.content_type or "application/octet-stream"

    if content_type not in ACCEPTED_MEDIA_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{content_type}'. Accepted: {', '.join(sorted(ACCEPTED_MEDIA_TYPES))}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        result = create_request(file_bytes=file_bytes, media_type=content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Parsing failed: {exc}") from exc
    return result
