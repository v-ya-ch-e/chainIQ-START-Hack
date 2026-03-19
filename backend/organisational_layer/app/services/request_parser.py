"""Parse raw text or binary files into structured purchase requests via Anthropic."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone

import anthropic

ANTHROPIC_MODEL = "claude-sonnet-4-6"

CANONICAL_SCHEMA: dict[str, object] = {
    "request_id": None,
    "created_at": None,
    "request_channel": None,
    "request_language": None,
    "business_unit": None,
    "country": None,
    "site": None,
    "requester_id": None,
    "requester_role": None,
    "submitted_for_id": None,
    "category_l1": None,
    "category_l2": None,
    "title": None,
    "request_text": None,
    "currency": None,
    "budget_amount": None,
    "quantity": None,
    "unit_of_measure": None,
    "required_by_date": None,
    "preferred_supplier_mentioned": None,
    "incumbent_supplier": None,
    "contract_type_requested": None,
    "delivery_countries": [],
    "data_residency_constraint": False,
    "esg_requirement": False,
    "status": "new",
    "scenario_tags": [],
}

FILLABLE_FIELDS = [
    "quantity", "budget_amount", "currency", "required_by_date",
    "unit_of_measure", "category_l1", "category_l2",
    "preferred_supplier_mentioned", "delivery_countries",
    "data_residency_constraint", "esg_requirement",
    "contract_type_requested", "title",
]

FILL_SYSTEM_PROMPT = """\
You are a procurement data extraction assistant. You receive the free-text \
`request_text` from a purchase request (which may be in any language: en, fr, \
de, es, pt, ja) and a list of field names whose values are currently missing.

Your job: for each missing field, extract its value ONLY if the text \
explicitly and directly states it. Be conservative — do NOT infer or guess.

Field definitions and expected types:
- quantity (number): the count of items/units requested
- budget_amount (number): the monetary budget stated
- currency (string): ISO currency code, e.g. "EUR", "USD", "CHF"
- required_by_date (string): delivery deadline as "YYYY-MM-DD"
- unit_of_measure (string): e.g. "device", "license", "consulting_day", "instance_hour"
- category_l1 (string): top-level procurement category, e.g. "IT", "Professional Services", "Facilities", "Marketing"
- category_l2 (string): sub-category, e.g. "Laptops", "Cloud Compute", "IT Project Management Services"
- preferred_supplier_mentioned (string): supplier name the requester explicitly asks for
- delivery_countries (list of strings): ISO country codes for delivery, e.g. ["DE", "FR"]
- data_residency_constraint (boolean): true only if text explicitly mentions data residency requirements
- esg_requirement (boolean): true only if text explicitly mentions ESG / sustainability requirements
- contract_type_requested (string): e.g. "purchase", "framework call-off", "lease"
- title (string): a short descriptive title for the request

Respond with ONLY a JSON object (no markdown fencing) mapping field names to \
extracted values. Use null for any field not directly stated in the text.\
"""

CONVERT_SYSTEM_PROMPT = """\
You are a procurement data extraction assistant. You receive the raw content \
of a file (email, memo, chat message, PDF text, etc.) that represents a \
purchase request. The content may be in any language: en, fr, de, es, pt, ja.

Your job: convert this content into a structured JSON purchase request with \
exactly the following fields. Extract values that are explicitly stated. Use \
null for anything not present. Do NOT infer or guess.

Required JSON structure:
{
  "request_id": null,
  "created_at": "<ISO 8601 timestamp if stated, else null>",
  "request_channel": "<how the request was sent: email, teams, portal, phone, etc., or null>",
  "request_language": "<ISO 639-1 language code of the content, e.g. en, fr, de>",
  "business_unit": "<organizational unit if stated, else null>",
  "country": "<ISO country code of the requester, e.g. DE, US, CH>",
  "site": "<city or office location if stated, else null>",
  "requester_id": null,
  "requester_role": "<job title/role if stated, else null>",
  "submitted_for_id": null,
  "category_l1": "<top-level category: IT, Professional Services, Facilities, or Marketing>",
  "category_l2": "<sub-category, e.g. Laptops, Cloud Compute, Cleaning Services>",
  "title": "<short descriptive title for the request>",
  "request_text": "<the original text content, preserved as-is>",
  "currency": "<ISO currency code: EUR, USD, CHF>",
  "budget_amount": "<number if stated, else null>",
  "quantity": "<number if stated, else null>",
  "unit_of_measure": "<e.g. device, license, consulting_day, instance_hour>",
  "required_by_date": "<YYYY-MM-DD if stated, else null>",
  "preferred_supplier_mentioned": "<supplier name if requester asks for one, else null>",
  "incumbent_supplier": null,
  "contract_type_requested": "<purchase, framework call-off, lease, or null>",
  "delivery_countries": ["<ISO country codes>"],
  "data_residency_constraint": false,
  "esg_requirement": false,
  "status": "new",
  "scenario_tags": []
}

Respond with ONLY the JSON object (no markdown fencing).\
"""


def _anthropic_client() -> anthropic.Anthropic:
    """Create Anthropic client with explicit key validation."""
    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is missing in organisational-layer environment")
    return anthropic.Anthropic(api_key=api_key)


def _ensure_schema(data: dict) -> dict:
    """Guarantee all canonical fields exist with correct defaults."""
    result = {}
    for field, default in CANONICAL_SCHEMA.items():
        if field in data and data[field] is not None:
            result[field] = data[field]
        elif isinstance(default, list):
            result[field] = data.get(field) if isinstance(data.get(field), list) else list(default)
        elif isinstance(default, bool):
            val = data.get(field)
            result[field] = val if isinstance(val, bool) else default
        elif default is not None:
            result[field] = data.get(field, default)
        else:
            result[field] = data.get(field)
    return result


def _extract_json(raw: str) -> dict:
    """Pull a JSON object from an LLM response, stripping markdown fences."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(raw[start:end])


def _find_missing_fields(data: dict) -> list[str]:
    """Return FILLABLE_FIELDS that are null, missing, or empty."""
    missing = []
    for field in FILLABLE_FIELDS:
        val = data.get(field)
        if val is None:
            missing.append(field)
        elif isinstance(val, list) and len(val) == 0:
            missing.append(field)
    return missing


def _fill_from_request_text(data: dict) -> dict:
    """Use Anthropic to fill null fields from request_text. Mutates and returns data."""
    request_text = data.get("request_text")
    if not request_text:
        return data

    missing = _find_missing_fields(data)
    if not missing:
        return data

    client = _anthropic_client()
    user_content = json.dumps({
        "request_text": request_text,
        "missing_fields": missing,
    }, ensure_ascii=False)

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=FILL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    extracted = _extract_json(response.content[0].text)

    for field in missing:
        val = extracted.get(field)
        if val is not None:
            data[field] = val

    return data


def _convert_unstructured(content: str) -> dict:
    """Use Anthropic to convert unstructured text content to the target schema."""
    client = _anthropic_client()

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=CONVERT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    return _extract_json(response.content[0].text)


def _convert_binary(file_bytes: bytes, media_type: str) -> dict:
    """Send a binary file (PDF, image, etc.) directly to Anthropic."""
    client = _anthropic_client()

    block_type = "image" if media_type.startswith("image/") else "document"

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=CONVERT_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": block_type,
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.standard_b64encode(file_bytes).decode("ascii"),
                    },
                },
                {
                    "type": "text",
                    "text": "Extract the purchase request from this document.",
                },
            ],
        }],
    )

    return _extract_json(response.content[0].text)


def _is_complete(data: dict) -> bool:
    """Check whether every canonical field has a non-null, non-empty value."""
    for field in CANONICAL_SCHEMA:
        val = data.get(field)
        if val is None:
            return False
        if isinstance(val, list) and len(val) == 0:
            return False
        if isinstance(val, str) and val.strip() == "":
            return False
    return True


def create_request(
    file_content: str | None = None,
    *,
    file_bytes: bytes | None = None,
    media_type: str | None = None,
) -> dict:
    """Convert text or a binary document into a structured purchase request.

    Pass either ``file_content`` (text) or ``file_bytes`` + ``media_type``
    (binary document such as PDF or image).

    Returns ``{"complete": bool, "request": dict}``.
    """
    if file_bytes is not None and media_type is not None:
        data = _convert_binary(file_bytes, media_type)
    elif file_content is not None:
        try:
            data = json.loads(file_content)
            if not isinstance(data, dict):
                raise ValueError("Top-level value is not a JSON object")
        except (json.JSONDecodeError, ValueError):
            data = _convert_unstructured(file_content)
    else:
        raise ValueError("Provide either file_content or file_bytes + media_type")

    data = _ensure_schema(data)
    data = _fill_from_request_text(data)

    if not data.get("created_at"):
        data["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "complete": _is_complete(data),
        "request": data,
    }
