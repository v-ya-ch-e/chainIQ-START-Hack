from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel


class RequestDeliveryCountryOut(BaseModel):
    id: int
    country_code: str

    model_config = {"from_attributes": True}


class RequestScenarioTagOut(BaseModel):
    id: int
    tag: str

    model_config = {"from_attributes": True}


class RequestBase(BaseModel):
    request_id: str
    created_at: datetime
    request_channel: str
    request_language: str
    business_unit: str
    country: str
    site: str
    requester_id: str
    requester_role: str | None
    submitted_for_id: str
    category_id: int
    title: str
    request_text: str
    currency: str
    budget_amount: Decimal | None
    quantity: Decimal | None
    unit_of_measure: str
    required_by_date: date
    preferred_supplier_mentioned: str | None
    incumbent_supplier: str | None
    contract_type_requested: str
    data_residency_constraint: bool
    esg_requirement: bool
    status: str


class RequestCreate(BaseModel):
    request_id: str
    created_at: datetime
    request_channel: str
    request_language: str
    business_unit: str
    country: str
    site: str
    requester_id: str
    requester_role: str | None = None
    submitted_for_id: str
    category_id: int
    title: str
    request_text: str
    currency: str
    budget_amount: Decimal | None = None
    quantity: Decimal | None = None
    unit_of_measure: str
    required_by_date: date
    preferred_supplier_mentioned: str | None = None
    incumbent_supplier: str | None = None
    contract_type_requested: str
    data_residency_constraint: bool = False
    esg_requirement: bool = False
    status: str = "new"
    delivery_countries: list[str] = []
    scenario_tags: list[str] = []


class RequestUpdate(BaseModel):
    title: str | None = None
    request_text: str | None = None
    currency: str | None = None
    budget_amount: Decimal | None = None
    quantity: Decimal | None = None
    unit_of_measure: str | None = None
    required_by_date: date | None = None
    preferred_supplier_mentioned: str | None = None
    incumbent_supplier: str | None = None
    contract_type_requested: str | None = None
    data_residency_constraint: bool | None = None
    esg_requirement: bool | None = None
    status: str | None = None


class RequestOut(RequestBase):
    model_config = {"from_attributes": True}


class RequestDetailOut(RequestBase):
    delivery_countries: list[RequestDeliveryCountryOut] = []
    scenario_tags: list[RequestScenarioTagOut] = []
    category_l1: str | None = None
    category_l2: str | None = None

    model_config = {"from_attributes": True}


class RequestListOut(BaseModel):
    items: list[RequestOut]
    total: int
    skip: int
    limit: int
