"""Centralized normalization helpers used across all pipeline steps."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

COUNTRY_TO_REGION: dict[str, str] = {
    "DE": "EU", "FR": "EU", "NL": "EU", "BE": "EU", "AT": "EU",
    "IT": "EU", "ES": "EU", "PL": "EU", "UK": "EU",
    "CH": "CH",
    "US": "Americas", "CA": "Americas", "BR": "Americas", "MX": "Americas",
    "SG": "APAC", "AU": "APAC", "IN": "APAC", "JP": "APAC",
    "UAE": "MEA", "ZA": "MEA",
}

MAX_STR_LEN = 500
MAX_DICT_KEYS = 30
MAX_LIST_SAMPLE = 3
MAX_LIST_LEN = 5
MAX_DEPTH = 3
MAX_ERROR_LEN = 2000


def country_to_region(country_code: str) -> str:
    """Map ISO country code to pricing region."""
    return COUNTRY_TO_REGION.get(country_code, "EU")


def normalize_delivery_countries(raw: list | None) -> list[str]:
    """Handle both ['DE'] and [{'country_code': 'DE'}] formats."""
    if not raw:
        return []
    if isinstance(raw[0], str):
        return raw
    return [item["country_code"] for item in raw if isinstance(item, dict) and "country_code" in item]


def normalize_scenario_tags(raw: list | None) -> list[str]:
    """Handle both ['standard'] and [{'tag': 'standard'}] formats."""
    if not raw:
        return []
    if isinstance(raw[0], str):
        return raw
    return [item["tag"] for item in raw if isinstance(item, dict) and "tag" in item]


def coerce_budget(val: Any) -> float | None:
    """Safely convert budget string/number to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def coerce_quantity(val: Any) -> int | None:
    """Safely convert quantity string/number to int (handles '240.0')."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def primary_delivery_country(request_data: dict) -> str:
    """Extract the primary delivery country from request data."""
    countries = normalize_delivery_countries(request_data.get("delivery_countries", []))
    if countries:
        return countries[0]
    return request_data.get("country", "DE")


def compute_days_until_required(required_by_date: str | None, created_at: str | None) -> int | None:
    """Compute days between created_at and required_by_date."""
    if not required_by_date:
        return None
    try:
        req_date = _parse_date(required_by_date)
        if created_at:
            base_date = _parse_date(created_at)
        else:
            base_date = date.today()
        return (req_date - base_date).days
    except (ValueError, TypeError):
        return None


def _parse_date(val: str) -> date:
    """Parse an ISO date or datetime string into a date object."""
    if "T" in val:
        return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
    return date.fromisoformat(val)


def truncate_for_log(obj: Any, depth: int = 0) -> Any:
    """Recursively truncate data for safe storage in log summaries."""
    if depth > MAX_DEPTH:
        return "<truncated>"

    if isinstance(obj, str):
        return obj[:MAX_STR_LEN] if len(obj) > MAX_STR_LEN else obj

    if isinstance(obj, dict):
        keys = list(obj.keys())[:MAX_DICT_KEYS]
        return {k: truncate_for_log(obj[k], depth + 1) for k in keys}

    if isinstance(obj, (list, tuple)):
        if len(obj) <= MAX_LIST_LEN:
            return [truncate_for_log(item, depth + 1) for item in obj]
        return {
            "_type": "list",
            "_length": len(obj),
            "_sample": [truncate_for_log(item, depth + 1) for item in obj[:MAX_LIST_SAMPLE]],
        }

    return obj


def truncate_error(msg: str) -> str:
    """Truncate error messages for log storage."""
    return msg[:MAX_ERROR_LEN] if len(msg) > MAX_ERROR_LEN else msg
