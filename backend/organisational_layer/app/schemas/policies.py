from decimal import Decimal
from pydantic import BaseModel


# --- Approval Thresholds ---


class ApprovalThresholdManagerOut(BaseModel):
    id: int
    manager_role: str

    model_config = {"from_attributes": True}


class ApprovalThresholdDeviationApproverOut(BaseModel):
    id: int
    approver_role: str

    model_config = {"from_attributes": True}


class ApprovalThresholdOut(BaseModel):
    threshold_id: str
    currency: str
    min_amount: Decimal
    max_amount: Decimal | None
    min_supplier_quotes: int
    policy_note: str | None
    managers: list[ApprovalThresholdManagerOut] = []
    deviation_approvers: list[ApprovalThresholdDeviationApproverOut] = []

    model_config = {"from_attributes": True}


# --- Preferred Suppliers ---


class PreferredSupplierRegionScopeOut(BaseModel):
    id: int
    region: str

    model_config = {"from_attributes": True}


class PreferredSupplierPolicyOut(BaseModel):
    id: int
    supplier_id: str
    category_l1: str
    category_l2: str
    policy_note: str | None
    region_scopes: list[PreferredSupplierRegionScopeOut] = []

    model_config = {"from_attributes": True}


# --- Restricted Suppliers ---


class RestrictedSupplierScopeOut(BaseModel):
    id: int
    scope_value: str

    model_config = {"from_attributes": True}


class RestrictedSupplierPolicyOut(BaseModel):
    id: int
    supplier_id: str
    category_l1: str
    category_l2: str
    restriction_reason: str
    scopes: list[RestrictedSupplierScopeOut] = []

    model_config = {"from_attributes": True}


# --- Category Rules ---


class CategoryRuleOut(BaseModel):
    rule_id: str
    category_id: int
    rule_type: str
    rule_text: str

    model_config = {"from_attributes": True}


# --- Geography Rules ---


class GeographyRuleCountryOut(BaseModel):
    id: int
    country_code: str

    model_config = {"from_attributes": True}


class GeographyRuleAppliesToCategoryOut(BaseModel):
    id: int
    category_l1: str

    model_config = {"from_attributes": True}


class GeographyRuleOut(BaseModel):
    rule_id: str
    country: str | None
    region: str | None
    rule_type: str | None
    rule_text: str
    countries: list[GeographyRuleCountryOut] = []
    applies_to_categories: list[GeographyRuleAppliesToCategoryOut] = []

    model_config = {"from_attributes": True}


# --- Escalation Rules ---


class EscalationRuleCurrencyOut(BaseModel):
    id: int
    currency: str

    model_config = {"from_attributes": True}


class EscalationRuleOut(BaseModel):
    rule_id: str
    trigger_condition: str
    action: str
    escalate_to: str
    currencies: list[EscalationRuleCurrencyOut] = []

    model_config = {"from_attributes": True}
