from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParseTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw procurement request text")


class ParsedRequest(BaseModel):
    """Canonical purchase-request fields returned by the parser."""

    request_id: Any = None
    created_at: Any = None
    request_channel: Any = None
    request_language: Any = None
    business_unit: Any = None
    country: Any = None
    site: Any = None
    requester_id: Any = None
    requester_role: Any = None
    submitted_for_id: Any = None
    category_l1: Any = None
    category_l2: Any = None
    title: Any = None
    request_text: Any = None
    currency: Any = None
    budget_amount: Any = None
    quantity: Any = None
    unit_of_measure: Any = None
    required_by_date: Any = None
    preferred_supplier_mentioned: Any = None
    incumbent_supplier: Any = None
    contract_type_requested: Any = None
    delivery_countries: list = Field(default_factory=list)
    data_residency_constraint: bool = False
    esg_requirement: bool = False
    status: str = "new"
    scenario_tags: list = Field(default_factory=list)

    model_config = {"extra": "allow"}


class ParseResponse(BaseModel):
    complete: bool
    request: ParsedRequest
