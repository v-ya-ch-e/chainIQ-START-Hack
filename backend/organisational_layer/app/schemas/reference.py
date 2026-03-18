from decimal import Decimal
from datetime import date
from pydantic import BaseModel


# --- Categories ---


class CategoryBase(BaseModel):
    category_l1: str
    category_l2: str
    category_description: str
    typical_unit: str
    pricing_model: str


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    category_l1: str | None = None
    category_l2: str | None = None
    category_description: str | None = None
    typical_unit: str | None = None
    pricing_model: str | None = None


class CategoryOut(CategoryBase):
    id: int

    model_config = {"from_attributes": True}


# --- Suppliers ---


class SupplierBase(BaseModel):
    supplier_id: str
    supplier_name: str
    country_hq: str
    currency: str
    contract_status: str
    capacity_per_month: int


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    supplier_name: str | None = None
    country_hq: str | None = None
    currency: str | None = None
    contract_status: str | None = None
    capacity_per_month: int | None = None


class SupplierOut(SupplierBase):
    model_config = {"from_attributes": True}


class SupplierServiceRegionOut(BaseModel):
    supplier_id: str
    country_code: str

    model_config = {"from_attributes": True}


class SupplierCategoryOut(BaseModel):
    id: int
    supplier_id: str
    category_id: int
    pricing_model: str
    quality_score: int
    risk_score: int
    esg_score: int
    preferred_supplier: bool
    is_restricted: bool
    restriction_reason: str | None
    data_residency_supported: bool
    notes: str | None

    model_config = {"from_attributes": True}


class SupplierDetailOut(SupplierOut):
    categories: list[SupplierCategoryOut] = []
    service_regions: list[SupplierServiceRegionOut] = []

    model_config = {"from_attributes": True}


# --- Pricing Tiers ---


class PricingTierBase(BaseModel):
    pricing_id: str
    supplier_id: str
    category_id: int
    region: str
    currency: str
    pricing_model: str
    min_quantity: int
    max_quantity: int
    unit_price: Decimal
    moq: int
    standard_lead_time_days: int
    expedited_lead_time_days: int
    expedited_unit_price: Decimal
    valid_from: date
    valid_to: date
    notes: str | None


class PricingTierOut(PricingTierBase):
    model_config = {"from_attributes": True}
