import re
import logging
from datetime import date, timedelta

from fastapi import APIRouter

from app.schemas.intake import (
    IntakeExtractIn,
    IntakeExtractOut,
    IntakeFieldStatusOut,
    IntakeWarningOut,
)

router = APIRouter(prefix="/api/intake", tags=["Intake"])
logger = logging.getLogger(__name__)


def _today_plus_days(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _extract_currency(text: str) -> str | None:
    upper = text.upper()
    for token in ("CHF", "EUR", "USD"):
        if token in upper:
            return token
    return None


def _extract_budget(text: str) -> float | None:
    pattern = re.compile(
        r"(?:budget|up to|max(?:imum)?|cap)\s*[:\-]?\s*(?:CHF|EUR|USD)?\s*([0-9][0-9,\.]*)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    raw_value = match.group(1).replace(",", "")
    try:
        return float(raw_value)
    except ValueError:
        return None


def _extract_quantity(text: str) -> float | None:
    pattern = re.compile(
        r"(?:qty|quantity|need|needs|for)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_required_date(text: str) -> str | None:
    iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso_match:
        return iso_match.group(1)
    slash_match = re.search(r"\b(\d{2})/(\d{2})/(20\d{2})\b", text)
    if slash_match:
        day, month, year = slash_match.groups()
        return f"{year}-{month}-{day}"
    return None


def _extract_country(text: str) -> str | None:
    upper = text.upper()
    for code in ("CH", "DE", "FR", "US", "UK", "ES", "IT", "PT", "JP"):
        if re.search(rf"\b{code}\b", upper):
            return code
    return None


def _infer_language(text: str) -> str:
    if re.search(r"[äöüß]", text, flags=re.IGNORECASE):
        return "de"
    if re.search(r"[éèàç]", text, flags=re.IGNORECASE):
        return "fr"
    if re.search(r"\b(hola|gracias|solicitud)\b", text, flags=re.IGNORECASE):
        return "es"
    return "en"


def _extraction_strength(missing_required: list[str], confident_fields: int) -> str:
    if len(missing_required) == 0 and confident_fields >= 8:
        return "strong"
    if confident_fields >= 4:
        return "partial"
    return "low"


@router.post("/extract", response_model=IntakeExtractOut)
def extract_intake(payload: IntakeExtractIn):
    source_text = (payload.source_text or "").strip()
    logger.info(
        "intake.extract request received source_type=%s source_text_length=%s request_channel=%s note_length=%s file_count=%s",
        payload.source_type,
        len(source_text),
        payload.request_channel,
        len(payload.note or ""),
        len(payload.file_names),
    )
    lines = [line.strip() for line in source_text.splitlines() if line.strip()]
    title = (lines[0] if lines else "New sourcing case")[:120]
    request_channel = payload.request_channel or "portal"

    currency = _extract_currency(source_text) or "CHF"
    budget_amount = _extract_budget(source_text)
    quantity = _extract_quantity(source_text)
    required_by_date = _extract_required_date(source_text) or _today_plus_days(14)
    country = _extract_country(source_text) or "CH"
    language = _infer_language(source_text)
    logger.info(
        "intake.extract heuristic summary title=%r country=%s language=%s currency=%s budget_amount=%s quantity=%s required_by_date=%s",
        title,
        country,
        language,
        currency,
        budget_amount,
        quantity,
        required_by_date,
    )

    draft: dict[str, object | None] = {
        "title": title,
        "requestText": source_text,
        "requestChannel": request_channel,
        "requestLanguage": language,
        "businessUnit": "General",
        "country": country,
        "site": "HQ",
        "requesterId": "UNKNOWN",
        "requesterRole": "Not specified",
        "submittedForId": "SELF",
        "categoryId": None,
        "quantity": quantity,
        "unitOfMeasure": "unit",
        "currency": currency,
        "budgetAmount": budget_amount,
        "requiredByDate": required_by_date,
        "deliveryCountries": [country] if country else [],
        "preferredSupplierMentioned": None,
        "incumbentSupplier": None,
        "contractTypeRequested": "one_time",
        "dataResidencyConstraint": bool(
            re.search(r"(data residency|data-residency|local data)", source_text, re.IGNORECASE)
        ),
        "esgRequirement": bool(re.search(r"\b(esg|sustainab)", source_text, re.IGNORECASE)),
        "requesterInstruction": payload.note,
        "scenarioTags": ["standard"],
        "status": "new",
    }

    field_status: dict[str, IntakeFieldStatusOut] = {}

    def set_status(field: str, value: object | None, inferred: bool = False):
        if value is None or value == "" or value == []:
            field_status[field] = IntakeFieldStatusOut(
                status="missing",
                confidence=0.0,
                reason="Value not found in source input.",
            )
            return
        field_status[field] = IntakeFieldStatusOut(
            status="inferred" if inferred else "confident",
            confidence=0.65 if inferred else 0.9,
            reason="Derived from request content." if inferred else "Directly extracted.",
        )

    set_status("title", draft["title"])
    set_status("requestText", draft["requestText"])
    set_status("requestChannel", draft["requestChannel"], inferred=payload.request_channel is None)
    set_status("requestLanguage", draft["requestLanguage"], inferred=True)
    set_status("businessUnit", draft["businessUnit"], inferred=True)
    set_status("country", draft["country"], inferred=True)
    set_status("site", draft["site"], inferred=True)
    set_status("requesterId", draft["requesterId"], inferred=True)
    set_status("requesterRole", draft["requesterRole"], inferred=True)
    set_status("submittedForId", draft["submittedForId"], inferred=True)
    set_status("categoryId", draft["categoryId"])
    set_status("quantity", draft["quantity"], inferred=True)
    set_status("unitOfMeasure", draft["unitOfMeasure"], inferred=True)
    set_status("currency", draft["currency"], inferred=True)
    set_status("budgetAmount", draft["budgetAmount"], inferred=True)
    set_status("requiredByDate", draft["requiredByDate"], inferred=True)
    set_status("deliveryCountries", draft["deliveryCountries"], inferred=True)
    set_status("contractTypeRequested", draft["contractTypeRequested"], inferred=True)

    required_fields = [
        "title",
        "requestText",
        "requestChannel",
        "requestLanguage",
        "businessUnit",
        "country",
        "site",
        "requesterId",
        "submittedForId",
        "categoryId",
        "unitOfMeasure",
        "currency",
        "requiredByDate",
        "contractTypeRequested",
    ]

    missing_required = [
        field
        for field in required_fields
        if field_status.get(field, IntakeFieldStatusOut(status="missing", confidence=0.0)).status
        == "missing"
    ]

    warnings: list[IntakeWarningOut] = []
    if "categoryId" in missing_required:
        warnings.append(
            IntakeWarningOut(
                code="CATEGORY_MISSING",
                severity="high",
                message="Category could not be extracted. Please select it manually.",
            )
        )
    if budget_amount is None:
        warnings.append(
            IntakeWarningOut(
                code="BUDGET_UNCLEAR",
                severity="medium",
                message="Budget amount was not confidently extracted from source text.",
            )
        )
    if source_text == "" and payload.source_type != "manual":
        warnings.append(
            IntakeWarningOut(
                code="EMPTY_SOURCE",
                severity="high",
                message="Input content is empty. Please provide source text or complete manually.",
            )
        )

    confident_fields = len(
        [entry for entry in field_status.values() if entry.status in {"confident", "inferred"}]
    )
    extraction_strength = _extraction_strength(missing_required, confident_fields)
    logger.info(
        "intake.extract response summary extraction_strength=%s missing_required=%s warning_codes=%s category_id=%s",
        extraction_strength,
        missing_required,
        [warning.code for warning in warnings],
        draft["categoryId"],
    )

    return IntakeExtractOut(
        draft=draft,
        field_status=field_status,
        missing_required=missing_required,
        warnings=warnings,
        extraction_strength=extraction_strength,
    )
