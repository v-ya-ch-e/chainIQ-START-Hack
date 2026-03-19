-- V6: Seed rule definitions and initial rule versions
--
-- source='given': From policies.json (approval_thresholds, escalation_rules, etc.)
-- source='custom': Derived from challenge scenario types (contradictory, restricted)
-- and known data quirks (preferred supplier category/geo mismatch, quantity/text discrepancy).
--
-- Note: policies.json has inconsistent schema (EUR/CHF: min_amount/max_amount;
-- USD: min_value/max_value). Application must read policies.json directly for thresholds.

INSERT IGNORE INTO rule_definitions (rule_id, rule_type, rule_name, is_skippable, source) VALUES
('HR-001', 'hard_rule',  'Budget ceiling check',                      TRUE,  'given'),
('HR-002', 'hard_rule',  'Delivery deadline feasibility',             TRUE,  'given'),
('HR-003', 'hard_rule',  'Supplier monthly capacity',                 TRUE,  'given'),
('HR-004', 'hard_rule',  'Minimum order quantity',                    TRUE,  'given'),
('HR-005', 'hard_rule',  'Pricing tier validity window',              TRUE,  'given'),
('HR-006', 'hard_rule',  'Quantity/text discrepancy',                 TRUE,  'given'),
('HR-007', 'hard_rule',  'Currency consistency',                      TRUE,  'custom'),  -- request.currency vs supplier.currency
('PC-001', 'policy',     'Approval tier determination',               FALSE, 'given'),
('PC-002', 'policy',     'Quote count requirement',                   FALSE, 'given'),
('PC-003', 'policy',     'Preferred supplier check',                  FALSE, 'given'),
('PC-004', 'policy',     'Restricted supplier global',                FALSE, 'given'),
('PC-005', 'policy',     'Restricted supplier country-scoped',        FALSE, 'given'),
('PC-006', 'policy',     'Restricted supplier value-conditional',     FALSE, 'given'),
('PC-007', 'policy',     'Category sourcing rules',                   FALSE, 'given'),
('PC-008', 'policy',     'Data residency constraint',                 FALSE, 'given'),
('PC-009', 'policy',     'Geography/delivery compliance',             FALSE, 'given'),
('PC-010', 'policy',     'ESG requirement coverage',                  FALSE, 'given'),
('PC-011', 'policy',     'Supplier registration/sanction',            FALSE, 'given'),
('PC-012', 'policy',     'Preferred supplier category mismatch',      FALSE, 'custom'),  -- challenge: "detect and discard"
('PC-013', 'policy',     'Preferred supplier geo mismatch',           FALSE, 'custom'),  -- challenge: preferred not in delivery country
('ER-001', 'escalation', 'Missing required info',                     FALSE, 'given'),
('ER-002', 'escalation', 'Preferred supplier restricted',             FALSE, 'given'),
('ER-003', 'escalation', 'Contract value exceeds tier',               FALSE, 'given'),
('ER-004', 'escalation', 'No compliant supplier found',               FALSE, 'given'),
('ER-005', 'escalation', 'Data residency unsatisfiable',              FALSE, 'given'),
('ER-006', 'escalation', 'Quantity exceeds capacity',                 FALSE, 'given'),
('ER-007', 'escalation', 'Brand safety concern',                      FALSE, 'given'),
('ER-008', 'escalation', 'Supplier not registered/sanctioned',        FALSE, 'given'),
('ER-009', 'escalation', 'Contradictory request content',             FALSE, 'custom'),  -- scenario_tag: contradictory
('ER-010', 'escalation', 'Preferred supplier mismatch',               FALSE, 'custom');  -- scenario_tag: restricted (wrong category/region)

INSERT IGNORE INTO rule_versions (version_id, rule_id, version_num, rule_config, valid_from) VALUES
(UUID(), 'HR-001', 1, '{"supported_budget_types":["upper_limit","range","null"],"null_action":"skip_raise_ER001","range_strategy":"use_max_conservative"}', NOW()),
(UUID(), 'HR-002', 1, '{"min_lead_time_days_standard":1,"expedited_allowed":true,"null_date_action":"skip_raise_ER001"}', NOW()),
(UUID(), 'HR-003', 1, '{"check":"requested_quantity <= supplier.capacity_per_month","exceed_action":"raise_ER006"}', NOW()),
(UUID(), 'HR-004', 1, '{"check":"requested_quantity >= pricing.moq","source_table":"pricing_tiers"}', NOW()),
(UUID(), 'HR-005', 1, '{"check":"evaluation_date BETWEEN pricing.valid_from AND pricing.valid_to"}', NOW()),
(UUID(), 'HR-006', 1, '{"check":"quantity_field matches quantity_in_request_text","mismatch_action":"raise_ER009"}', NOW()),
(UUID(), 'HR-007', 1, '{"check":"request.currency matches supplier.currency OR conversion_applied","allowed_currencies":["EUR","CHF","USD"]}', NOW()),
(UUID(), 'PC-001', 1, '{"tiers":{"EUR":[{"tier":1,"max":25000,"approver":"Business"},{"tier":2,"max":100000,"approver":"Business + Procurement"},{"tier":3,"max":500000,"approver":"Head of Category"},{"tier":4,"max":5000000,"approver":"Head of Strategic Sourcing"},{"tier":5,"max":null,"approver":"CPO"}],"CHF":[{"tier":1,"max":27500},{"tier":2,"max":110000},{"tier":3,"max":550000},{"tier":4,"max":5500000},{"tier":5,"max":null}],"USD":[{"tier":1,"max":27000},{"tier":2,"max":108000},{"tier":3,"max":540000},{"tier":4,"max":5400000},{"tier":5,"max":null}]}}', NOW()),
(UUID(), 'PC-002', 1, '{"quotes_required":{"tier1":1,"tier2":2,"tier3":3,"tier4":3,"tier5":3}}', NOW()),
(UUID(), 'PC-003', 1, '{"check":"prefer preferred_supplier if policy_compliant and commercially_competitive"}', NOW()),
(UUID(), 'PC-004', 1, '{"check":"supplier.is_restricted = false for global restrictions"}', NOW()),
(UUID(), 'PC-005', 1, '{"check":"restriction applies in delivery_country"}', NOW()),
(UUID(), 'PC-006', 1, '{"check":"contract_value <= restriction_value_threshold"}', NOW()),
(UUID(), 'PC-007', 1, '{"check":"category_rules applied: security_review, cv_review, brand_safety per category"}', NOW()),
(UUID(), 'PC-008', 1, '{"check":"data_residency_constraint satisfied by supplier region","raise_on_fail":"ER-005"}', NOW()),
(UUID(), 'PC-009', 1, '{"check":"supplier.service_regions covers all delivery_countries"}', NOW()),
(UUID(), 'PC-010', 1, '{"min_esg_score":60,"check":"esg_requirement = false OR supplier.esg_score >= min_esg_score"}', NOW()),
(UUID(), 'PC-011', 1, '{"check":"supplier registered and sanction-screened in each delivery_country"}', NOW()),
(UUID(), 'PC-012', 1, '{"check":"preferred_supplier_mentioned.category matches request.category"}', NOW()),
(UUID(), 'PC-013', 1, '{"check":"preferred_supplier_mentioned.service_regions covers request.delivery_countries"}', NOW()),
(UUID(), 'ER-001', 1, '{"trigger":"budget_amount IS NULL OR quantity IS NULL","target":"Requester","event_type":"NOTIFY_REQUESTER"}', NOW()),
(UUID(), 'ER-002', 1, '{"trigger":"preferred supplier is restricted","target":"Procurement Manager","event_type":"NOTIFY_PROCUREMENT"}', NOW()),
(UUID(), 'ER-003', 1, '{"trigger":"contract_value exceeds tier threshold","target":"Head of Strategic Sourcing","event_type":"REQUEST_EXCEPTION_APPROVAL"}', NOW()),
(UUID(), 'ER-004', 1, '{"trigger":"no compliant supplier identified","target":"Head of Category","event_type":"BLOCK_AWARD"}', NOW()),
(UUID(), 'ER-005', 1, '{"trigger":"data residency cannot be satisfied","target":"Security/Compliance","event_type":"SECURITY_REVIEW"}', NOW()),  -- README: Security/Compliance
(UUID(), 'ER-006', 1, '{"trigger":"quantity > supplier.capacity_per_month","target":"Sourcing Excellence Lead","event_type":"NOTIFY_PROCUREMENT"}', NOW()),
(UUID(), 'ER-007', 1, '{"trigger":"category = Marketing AND brand_safety_concern","target":"Marketing Governance Lead","event_type":"COMPLIANCE_REVIEW"}', NOW()),
(UUID(), 'ER-008', 1, '{"trigger":"supplier not registered or sanction-screened in delivery_country","target":"Regional Compliance Lead","event_type":"COMPLIANCE_REVIEW"}', NOW()),
(UUID(), 'ER-009', 1, '{"trigger":"quantity_field != quantity_in_text OR budget_insufficient_for_spec","target":"Requester","event_type":"NOTIFY_REQUESTER"}', NOW()),
(UUID(), 'ER-010', 1, '{"trigger":"preferred_supplier category or geo mismatch","target":"Procurement Manager","event_type":"NOTIFY_PROCUREMENT"}', NOW());
