"""Pydantic models for the script-backed endpoints (filter, rank, validate)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Filter Suppliers
# ------------------------------------------------------------------


class FilterSuppliersRequest(BaseModel):
    """Input for the filter-suppliers endpoint.

    Must include category_l1 and category_l2. Any additional fields from the
    purchase request are passed through to the script unchanged.
    """

    category_l1: str = Field(..., description="Level-1 category, e.g. 'IT'")
    category_l2: str = Field(..., description="Level-2 category, e.g. 'Hardware'")

    model_config = {"extra": "allow"}


class SupplierCategoryRow(BaseModel):
    """A single supplier-category row returned by the filter script."""

    id: int
    supplier_id: str
    category_id: int
    pricing_model: str | None = None
    quality_score: int
    risk_score: int
    esg_score: int
    preferred_supplier: bool = False
    is_restricted: bool = False
    restriction_reason: str | None = None
    data_residency_supported: bool = False
    notes: str | None = None

    model_config = {"extra": "allow"}


class FilterSuppliersResponse(BaseModel):
    """Output of the filter-suppliers endpoint."""

    suppliers: list[SupplierCategoryRow]
    category_l1: str
    category_l2: str
    count: int


# ------------------------------------------------------------------
# Rank Suppliers
# ------------------------------------------------------------------


class RankSuppliersRequest(BaseModel):
    """Input for the rank-suppliers endpoint.

    ``request`` is the purchase request dict (must contain category_l1,
    category_l2; optionally quantity, esg_requirement, delivery_countries,
    country).

    ``suppliers`` is the list of supplier dicts — typically the ``suppliers``
    array from the filter-suppliers response.
    """

    request: dict[str, Any] = Field(
        ..., description="Purchase request data with at least category_l1 and category_l2"
    )
    suppliers: list[dict[str, Any]] = Field(
        ..., description="Supplier rows from filter-suppliers output"
    )


class RankedSupplierRow(BaseModel):
    """A single ranked supplier row."""

    rank: int
    supplier_id: str
    true_cost: float | None = None
    overpayment: float | None = None
    quality_score: int
    risk_score: int
    esg_score: int
    total_price: float | None = None
    unit_price: float | None = None
    currency: str | None = None
    standard_lead_time_days: int | None = None
    expedited_lead_time_days: int | None = None
    preferred_supplier: bool = False
    is_restricted: bool = False

    model_config = {"extra": "allow"}


class RankSuppliersResponse(BaseModel):
    """Output of the rank-suppliers endpoint."""

    ranked: list[RankedSupplierRow]
    category_l1: str
    category_l2: str
    count: int


# ------------------------------------------------------------------
# Validate Request
# ------------------------------------------------------------------


class ValidateRequestRequest(BaseModel):
    """Input for the validate-request endpoint.

    A full purchase request dict. All fields are accepted; the script
    checks which required/optional fields are present and uses the
    Anthropic API to detect contradictions between structured fields
    and request_text.
    """

    model_config = {"extra": "allow"}


class ValidationIssue(BaseModel):
    """A single validation issue found by deterministic checks or the LLM."""

    field: str | None = None
    type: str
    message: str


class RequestInterpretation(BaseModel):
    """Structured interpretation of the purchase request."""

    category_l1: str | None = None
    category_l2: str | None = None
    quantity: float | None = None
    unit_of_measure: str | None = None
    budget_amount: float | None = None
    currency: str | None = None
    delivery_country: str | None = None
    required_by_date: str | None = None
    days_until_required: int | None = None
    data_residency_required: bool = False
    esg_requirement: bool = False
    preferred_supplier_stated: str | None = None
    incumbent_supplier: str | None = None
    requester_instruction: str | None = None


class ValidateRequestResponse(BaseModel):
    """Output of the validate-request endpoint."""

    completeness: bool
    issues: list[ValidationIssue]
    request_interpretation: RequestInterpretation
