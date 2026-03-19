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


# --- Rule Definitions + Versions ---


class RuleVersionOut(BaseModel):
    version_id: str
    rule_id: str
    version_num: int
    rule_config: dict = {}
    valid_from: str | None = None
    valid_to: str | None = None
    changed_by: str | None = None
    change_reason: str | None = None

    model_config = {"from_attributes": True}


class RuleDefinitionOut(BaseModel):
    rule_id: str
    rule_type: str
    rule_name: str
    scope: str = "request"
    evaluation_mode: str = "expression"
    is_skippable: bool = False
    source: str = "custom"
    severity: str = "high"
    is_blocking: bool = True
    breaks_completeness: bool = False
    action_type: str = "escalate"
    action_target: str | None = None
    trigger_template: str | None = None
    action_required: str | None = None
    field_ref: str | None = None
    description: str | None = None
    active: bool = True
    sort_order: int = 100
    current_version: RuleVersionOut | None = None

    model_config = {"from_attributes": True}


class RuleDefinitionCreate(BaseModel):
    rule_id: str
    rule_type: str
    rule_name: str
    scope: str = "request"
    evaluation_mode: str = "expression"
    is_skippable: bool = False
    source: str = "custom"
    severity: str = "high"
    is_blocking: bool = True
    breaks_completeness: bool = False
    action_type: str = "escalate"
    action_target: str | None = None
    trigger_template: str | None = None
    action_required: str | None = None
    field_ref: str | None = None
    description: str | None = None
    active: bool = True
    sort_order: int = 100
    rule_config: dict = {}


class RuleDefinitionUpdate(BaseModel):
    rule_type: str | None = None
    rule_name: str | None = None
    scope: str | None = None
    evaluation_mode: str | None = None
    is_skippable: bool | None = None
    source: str | None = None
    severity: str | None = None
    is_blocking: bool | None = None
    breaks_completeness: bool | None = None
    action_type: str | None = None
    action_target: str | None = None
    trigger_template: str | None = None
    action_required: str | None = None
    field_ref: str | None = None
    description: str | None = None
    active: bool | None = None
    sort_order: int | None = None


class RuleVersionCreate(BaseModel):
    rule_config: dict = {}
    changed_by: str | None = None
    change_reason: str | None = None
