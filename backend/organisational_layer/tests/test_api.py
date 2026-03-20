"""Integration tests for all organisational-layer API endpoints.

Run with:  cd backend/organisational_layer && pytest tests/ -v
Requires a live MySQL database (configured via .env).
"""

import uuid

import pytest

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class TestCategories:
    def test_list_categories(self, client):
        r = client.get("/api/categories/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 30

    def test_get_category_existing(self, client):
        r = client.get("/api/categories/1")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 1
        assert "category_l1" in body
        assert "category_l2" in body

    def test_get_category_not_found(self, client):
        r = client.get("/api/categories/99999")
        assert r.status_code == 404

    def test_crud_category(self, client):
        payload = {
            "category_l1": "TEST",
            "category_l2": "TestSub",
            "category_description": "Test category",
            "typical_unit": "unit",
            "pricing_model": "per_unit",
        }
        r = client.post("/api/categories/", json=payload)
        assert r.status_code == 201
        cat_id = r.json()["id"]

        r = client.put(f"/api/categories/{cat_id}", json={"category_description": "Updated"})
        assert r.status_code == 200
        assert r.json()["category_description"] == "Updated"

        r = client.delete(f"/api/categories/{cat_id}")
        assert r.status_code == 204

        r = client.get(f"/api/categories/{cat_id}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


class TestSuppliers:
    def test_list_suppliers(self, client):
        r = client.get("/api/suppliers/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 40

    def test_list_suppliers_filter_country(self, client):
        r = client.get("/api/suppliers/", params={"country_hq": "DE"})
        assert r.status_code == 200
        for s in r.json():
            assert s["country_hq"] == "DE"

    def test_list_suppliers_filter_currency(self, client):
        r = client.get("/api/suppliers/", params={"currency": "EUR"})
        assert r.status_code == 200
        for s in r.json():
            assert s["currency"] == "EUR"

    def test_get_supplier_existing(self, client):
        r = client.get("/api/suppliers/SUP-0001")
        assert r.status_code == 200
        body = r.json()
        assert body["supplier_id"] == "SUP-0001"
        assert "categories" in body
        assert "service_regions" in body

    def test_get_supplier_not_found(self, client):
        r = client.get("/api/suppliers/SUP-NONEXIST")
        assert r.status_code == 404

    def test_crud_supplier(self, client):
        sid = f"SUP-TEST-{uuid.uuid4().hex[:6]}"
        payload = {
            "supplier_id": sid,
            "supplier_name": "Test Supplier",
            "country_hq": "CH",
            "currency": "CHF",
            "contract_status": "active",
            "capacity_per_month": 100,
        }
        r = client.post("/api/suppliers/", json=payload)
        assert r.status_code == 201
        assert r.json()["supplier_id"] == sid

        r = client.post("/api/suppliers/", json=payload)
        assert r.status_code == 409

        r = client.put(f"/api/suppliers/{sid}", json={"supplier_name": "Updated"})
        assert r.status_code == 200
        assert r.json()["supplier_name"] == "Updated"

        r = client.delete(f"/api/suppliers/{sid}")
        assert r.status_code == 204

    def test_get_supplier_categories(self, client):
        r = client.get("/api/suppliers/SUP-0001/categories")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "quality_score" in data[0]

    def test_get_supplier_categories_not_found(self, client):
        r = client.get("/api/suppliers/SUP-NONEXIST/categories")
        assert r.status_code == 404

    def test_get_supplier_regions(self, client):
        r = client.get("/api/suppliers/SUP-0001/regions")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "country_code" in data[0]

    def test_get_supplier_pricing(self, client):
        r = client.get("/api/suppliers/SUP-0001/pricing")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_supplier_pricing_not_found(self, client):
        r = client.get("/api/suppliers/SUP-NONEXIST/pricing")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class TestRequests:
    def test_list_requests(self, client):
        r = client.get("/api/requests/")
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 304
        assert len(body["items"]) <= 50

    def test_list_requests_pagination(self, client):
        r = client.get("/api/requests/", params={"skip": 0, "limit": 5})
        assert r.status_code == 200
        assert len(r.json()["items"]) == 5

    def test_list_requests_filter_country(self, client):
        r = client.get("/api/requests/", params={"country": "DE"})
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["country"] == "DE"

    def test_get_request_existing(self, client):
        r = client.get("/api/requests/REQ-000004")
        assert r.status_code == 200
        body = r.json()
        assert body["request_id"] == "REQ-000004"
        assert "delivery_countries" in body
        assert "scenario_tags" in body
        assert "category_l1" in body

    def test_get_request_not_found(self, client):
        r = client.get("/api/requests/REQ-NONEXIST")
        assert r.status_code == 404

    def test_crud_request(self, client):
        rid = f"REQ-TEST-{uuid.uuid4().hex[:4]}"
        payload = {
            "request_id": rid,
            "created_at": "2026-03-19T10:00:00",
            "request_channel": "portal",
            "request_language": "en",
            "business_unit": "IT",
            "country": "DE",
            "site": "Berlin",
            "requester_id": "USR-TEST",
            "submitted_for_id": "USR-TEST",
            "category_id": 1,
            "title": "Test Request",
            "request_text": "Need 10 laptops for new hires",
            "currency": "EUR",
            "budget_amount": "5000.00",
            "quantity": "10",
            "unit_of_measure": "device",
            "required_by_date": "2026-04-15",
            "contract_type_requested": "purchase",
            "data_residency_constraint": False,
            "esg_requirement": False,
            "status": "new",
            "delivery_countries": ["DE"],
            "scenario_tags": ["standard"],
        }
        r = client.post("/api/requests/", json=payload)
        assert r.status_code == 201
        assert r.json()["request_id"] == rid

        r = client.post("/api/requests/", json=payload)
        assert r.status_code == 409

        r = client.put(f"/api/requests/{rid}", json={
            "title": "Updated Title",
            "delivery_countries": ["DE", "FR"],
            "scenario_tags": ["edge_case"],
        })
        assert r.status_code == 200
        assert r.json()["title"] == "Updated Title"

        detail = client.get(f"/api/requests/{rid}")
        assert detail.status_code == 200
        countries = [dc["country_code"] for dc in detail.json()["delivery_countries"]]
        assert set(countries) == {"DE", "FR"}

        r = client.delete(f"/api/requests/{rid}")
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# Historical Awards
# ---------------------------------------------------------------------------


class TestAwards:
    def test_list_awards(self, client):
        r = client.get("/api/awards/")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 590

    def test_list_awards_filter_request(self, client):
        r = client.get("/api/awards/", params={"request_id": "REQ-000004"})
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["request_id"] == "REQ-000004"

    def test_list_awards_filter_awarded(self, client):
        r = client.get("/api/awards/", params={"awarded": True})
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["awarded"] is True

    def test_get_awards_by_request(self, client):
        r = client.get("/api/awards/by-request/REQ-000004")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        ranks = [a["award_rank"] for a in data]
        assert ranks == sorted(ranks)

    def test_get_awards_by_request_empty(self, client):
        r = client.get("/api/awards/by-request/REQ-000200")
        assert r.status_code == 200

    def test_get_award_by_id(self, client):
        list_r = client.get("/api/awards/", params={"limit": 1})
        aid = list_r.json()["items"][0]["award_id"]
        r = client.get(f"/api/awards/{aid}")
        assert r.status_code == 200
        assert r.json()["award_id"] == aid

    def test_get_award_not_found(self, client):
        r = client.get("/api/awards/AWD-NONEXIST")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


class TestPolicies:
    def test_list_approval_thresholds(self, client):
        r = client.get("/api/policies/approval-thresholds")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 15

    def test_list_approval_thresholds_filter_currency(self, client):
        r = client.get("/api/policies/approval-thresholds", params={"currency": "EUR"})
        assert r.status_code == 200
        for t in r.json():
            assert t["currency"] == "EUR"

    def test_get_approval_threshold(self, client):
        r = client.get("/api/policies/approval-thresholds/AT-001")
        assert r.status_code == 200
        body = r.json()
        assert body["threshold_id"] == "AT-001"
        assert "managers" in body
        assert "deviation_approvers" in body

    def test_get_approval_threshold_not_found(self, client):
        r = client.get("/api/policies/approval-thresholds/AT-NONE")
        assert r.status_code == 404

    def test_list_preferred_suppliers(self, client):
        r = client.get("/api/policies/preferred-suppliers")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert "region_scopes" in data[0]

    def test_list_preferred_suppliers_filter(self, client):
        r = client.get("/api/policies/preferred-suppliers", params={"category_l1": "IT"})
        assert r.status_code == 200
        for p in r.json():
            assert p["category_l1"] == "IT"

    def test_get_preferred_supplier_not_found(self, client):
        r = client.get("/api/policies/preferred-suppliers/99999")
        assert r.status_code == 404

    def test_list_restricted_suppliers(self, client):
        r = client.get("/api/policies/restricted-suppliers")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 5
        assert "scopes" in data[0]

    def test_get_restricted_supplier_not_found(self, client):
        r = client.get("/api/policies/restricted-suppliers/99999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


class TestRules:
    def test_list_category_rules(self, client):
        r = client.get("/api/rules/category")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 10

    def test_list_category_rules_filter(self, client):
        r = client.get("/api/rules/category", params={"category_id": 1})
        assert r.status_code == 200
        for rule in r.json():
            assert rule["category_id"] == 1

    def test_get_category_rule(self, client):
        rules = client.get("/api/rules/category").json()
        if rules:
            rid = rules[0]["rule_id"]
            r = client.get(f"/api/rules/category/{rid}")
            assert r.status_code == 200

    def test_get_category_rule_not_found(self, client):
        r = client.get("/api/rules/category/CR-NONE")
        assert r.status_code == 404

    def test_list_geography_rules(self, client):
        r = client.get("/api/rules/geography")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 8

    def test_list_geography_rules_filter_country(self, client):
        r = client.get("/api/rules/geography", params={"country": "CH"})
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_get_geography_rule(self, client):
        rules = client.get("/api/rules/geography").json()
        if rules:
            rid = rules[0]["rule_id"]
            r = client.get(f"/api/rules/geography/{rid}")
            assert r.status_code == 200
            body = r.json()
            assert "countries" in body
            assert "applies_to_categories" in body

    def test_get_geography_rule_not_found(self, client):
        r = client.get("/api/rules/geography/GR-NONE")
        assert r.status_code == 404

    def test_list_escalation_rules(self, client):
        r = client.get("/api/rules/escalation")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 8

    def test_get_escalation_rule(self, client):
        r = client.get("/api/rules/escalation/ER-001")
        assert r.status_code == 200
        body = r.json()
        assert body["rule_id"] == "ER-001"
        assert "currencies" in body

    def test_get_escalation_rule_not_found(self, client):
        r = client.get("/api/rules/escalation/ER-NONE")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------


class TestEscalations:
    def test_get_escalation_queue(self, client):
        r = client.get("/api/escalations/queue")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "escalation_id" in item
            assert "rule_id" in item
            assert "escalate_to" in item
            assert "recommendation_status" in item

    def test_get_by_request_existing(self, client):
        r = client.get("/api/escalations/by-request/REQ-000001")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_by_request_not_found(self, client):
        r = client.get("/api/escalations/by-request/REQ-NONEXIST")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class TestAnalytics:
    def test_compliant_suppliers(self, client):
        r = client.get("/api/analytics/compliant-suppliers", params={
            "category_l1": "IT",
            "category_l2": "Laptops",
            "delivery_country": "DE",
        })
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for s in data:
            assert "supplier_id" in s
            assert "quality_score" in s

    def test_compliant_suppliers_empty(self, client):
        r = client.get("/api/analytics/compliant-suppliers", params={
            "category_l1": "NONEXISTENT",
            "category_l2": "Nothing",
            "delivery_country": "XX",
        })
        assert r.status_code == 200
        assert r.json() == []

    def test_pricing_lookup(self, client):
        suppliers = client.get("/api/analytics/compliant-suppliers", params={
            "category_l1": "IT",
            "category_l2": "Laptops",
            "delivery_country": "DE",
        }).json()
        if suppliers:
            sid = suppliers[0]["supplier_id"]
            r = client.get("/api/analytics/pricing-lookup", params={
                "supplier_id": sid,
                "category_l1": "IT",
                "category_l2": "Laptops",
                "region": "EU",
                "quantity": 10,
            })
            assert r.status_code == 200
            data = r.json()
            assert isinstance(data, list)
            for p in data:
                assert "total_price" in p
                assert "standard_lead_time_days" in p

    def test_approval_tier(self, client):
        r = client.get("/api/analytics/approval-tier", params={
            "currency": "EUR",
            "amount": "50000",
        })
        assert r.status_code == 200
        body = r.json()
        assert "threshold_id" in body
        assert "managers" in body
        assert "deviation_approvers" in body

    def test_approval_tier_not_found(self, client):
        r = client.get("/api/analytics/approval-tier", params={
            "currency": "XYZ",
            "amount": "1",
        })
        assert r.status_code == 404

    def test_check_restricted(self, client):
        r = client.get("/api/analytics/check-restricted", params={
            "supplier_id": "SUP-0008",
            "category_l1": "IT",
            "category_l2": "Laptops",
            "delivery_country": "DE",
        })
        assert r.status_code == 200
        body = r.json()
        assert "is_restricted" in body

    def test_check_restricted_not_restricted(self, client):
        r = client.get("/api/analytics/check-restricted", params={
            "supplier_id": "SUP-0001",
            "category_l1": "IT",
            "category_l2": "Laptops",
            "delivery_country": "DE",
        })
        assert r.status_code == 200
        assert r.json()["is_restricted"] is False

    def test_check_preferred(self, client):
        r = client.get("/api/analytics/check-preferred", params={
            "supplier_id": "SUP-0001",
            "category_l1": "IT",
            "category_l2": "Laptops",
        })
        assert r.status_code == 200
        body = r.json()
        assert "is_preferred" in body

    def test_applicable_rules(self, client):
        r = client.get("/api/analytics/applicable-rules", params={
            "category_l1": "IT",
            "category_l2": "Laptops",
            "delivery_country": "DE",
        })
        assert r.status_code == 200
        body = r.json()
        assert "category_rules" in body
        assert "geography_rules" in body

    def test_request_overview(self, client):
        r = client.get("/api/analytics/request-overview/REQ-000004")
        assert r.status_code == 200
        body = r.json()
        assert "request" in body
        assert "compliant_suppliers" in body
        assert "pricing" in body
        assert "applicable_rules" in body
        assert body["request"]["request_id"] == "REQ-000004"

    def test_request_overview_not_found(self, client):
        r = client.get("/api/analytics/request-overview/REQ-NONEXIST")
        assert r.status_code == 404

    def test_spend_by_category(self, client):
        r = client.get("/api/analytics/spend-by-category")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "total_spend" in data[0]

    def test_spend_by_supplier(self, client):
        r = client.get("/api/analytics/spend-by-supplier")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_supplier_win_rates(self, client):
        r = client.get("/api/analytics/supplier-win-rates")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        for s in data:
            assert "win_rate" in s
            assert "total_evaluations" in s


# ---------------------------------------------------------------------------
# Pipeline Logs
# ---------------------------------------------------------------------------


class TestPipelineLogs:
    def test_run_lifecycle(self, client):
        run_id = str(uuid.uuid4())
        r = client.post("/api/logs/runs", json={
            "run_id": run_id,
            "request_id": "REQ-000001",
            "started_at": "2026-03-19T10:00:00",
        })
        assert r.status_code == 201
        assert r.json()["run_id"] == run_id
        assert r.json()["status"] == "running"

        r = client.patch(f"/api/logs/runs/{run_id}", json={
            "status": "completed",
            "completed_at": "2026-03-19T10:00:05",
            "total_duration_ms": 5000,
            "steps_completed": 3,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

        r = client.get(f"/api/logs/runs/{run_id}")
        assert r.status_code == 200
        assert r.json()["run_id"] == run_id

        r = client.get("/api/logs/by-request/REQ-000001")
        assert r.status_code == 200
        run_ids = [run["run_id"] for run in r.json()]
        assert run_id in run_ids

    def test_get_run_not_found(self, client):
        r = client.get("/api/logs/runs/nonexistent-uuid")
        assert r.status_code == 404

    def test_list_runs(self, client):
        r = client.get("/api/logs/runs")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_entry_lifecycle(self, client):
        run_id = str(uuid.uuid4())
        client.post("/api/logs/runs", json={
            "run_id": run_id,
            "request_id": "REQ-000001",
            "started_at": "2026-03-19T10:00:00",
        })

        r = client.post("/api/logs/entries", json={
            "run_id": run_id,
            "step_name": "test_step",
            "step_order": 1,
            "started_at": "2026-03-19T10:00:01",
        })
        assert r.status_code == 201
        entry_id = r.json()["id"]

        r = client.patch(f"/api/logs/entries/{entry_id}", json={
            "status": "completed",
            "completed_at": "2026-03-19T10:00:02",
            "duration_ms": 1000,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_patch_entry_not_found(self, client):
        r = client.patch("/api/logs/entries/999999", json={"status": "failed"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------


class TestAuditLogs:
    def test_create_audit_log(self, client):
        r = client.post("/api/logs/audit", json={
            "request_id": "REQ-000001",
            "timestamp": "2026-03-19T10:00:00",
            "level": "info",
            "category": "test",
            "message": "Test audit log entry",
        })
        assert r.status_code == 201
        assert r.json()["message"] == "Test audit log entry"

    def test_create_audit_logs_batch(self, client):
        r = client.post("/api/logs/audit/batch", json={
            "entries": [
                {
                    "request_id": "REQ-000001",
                    "timestamp": "2026-03-19T10:00:00",
                    "level": "info",
                    "category": "batch_test",
                    "message": "Batch entry 1",
                },
                {
                    "request_id": "REQ-000001",
                    "timestamp": "2026-03-19T10:00:01",
                    "level": "warn",
                    "category": "batch_test",
                    "message": "Batch entry 2",
                },
            ]
        })
        assert r.status_code == 201
        assert len(r.json()) == 2

    def test_get_audit_logs_by_request(self, client):
        r = client.get("/api/logs/audit/by-request/REQ-000001")
        assert r.status_code == 200
        assert "items" in r.json()
        assert "total" in r.json()

    def test_get_audit_log_summary(self, client):
        r = client.get("/api/logs/audit/summary/REQ-000001")
        assert r.status_code == 200
        body = r.json()
        assert "total_entries" in body
        assert "by_level" in body
        assert "by_category" in body

    def test_get_audit_log_summary_empty(self, client):
        r = client.get("/api/logs/audit/summary/REQ-NONEXIST-AUDIT")
        assert r.status_code == 200
        assert r.json()["total_entries"] == 0

    def test_list_audit_logs(self, client):
        r = client.get("/api/logs/audit")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_list_audit_logs_with_filters(self, client):
        r = client.get("/api/logs/audit", params={"level": "info", "limit": 5})
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["level"] == "info"


# ---------------------------------------------------------------------------
# Rule Versions
# ---------------------------------------------------------------------------


class TestRuleVersions:
    def test_list_definitions(self, client):
        r = client.get("/api/rule-versions/definitions")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 30

    def test_get_definition(self, client):
        r = client.get("/api/rule-versions/definitions/HR-001")
        assert r.status_code == 200
        assert r.json()["rule_id"] == "HR-001"

    def test_get_definition_not_found(self, client):
        r = client.get("/api/rule-versions/definitions/XX-999")
        assert r.status_code == 404

    def test_list_versions(self, client):
        r = client.get("/api/rule-versions/versions")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 30
        assert "rule_name" in data[0]
        assert "rule_type" in data[0]

    def test_list_versions_filter_rule(self, client):
        r = client.get("/api/rule-versions/versions", params={"rule_id": "HR-001"})
        assert r.status_code == 200
        for v in r.json():
            assert v["rule_id"] == "HR-001"

    def test_list_versions_active_only(self, client):
        r = client.get("/api/rule-versions/versions", params={"active_only": True})
        assert r.status_code == 200
        for v in r.json():
            assert v["valid_to"] is None

    def test_get_active_version(self, client):
        r = client.get("/api/rule-versions/versions/active/HR-001")
        assert r.status_code == 200
        assert r.json()["rule_id"] == "HR-001"
        assert r.json()["valid_to"] is None

    def test_get_active_version_not_found(self, client):
        r = client.get("/api/rule-versions/versions/active/XX-999")
        assert r.status_code == 404

    def test_get_version_by_id(self, client):
        active = client.get("/api/rule-versions/versions/active/HR-001").json()
        vid = active["version_id"]
        r = client.get(f"/api/rule-versions/versions/{vid}")
        assert r.status_code == 200
        assert r.json()["version_id"] == vid

    def test_get_version_not_found(self, client):
        r = client.get("/api/rule-versions/versions/nonexistent-uuid")
        assert r.status_code == 404

    def test_list_hard_rule_checks(self, client):
        r = client.get("/api/rule-versions/hard-rule-checks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_policy_checks(self, client):
        r = client.get("/api/rule-versions/policy-checks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_rule_change_logs(self, client):
        r = client.get("/api/rule-versions/logs/rule-change")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_policy_check_logs(self, client):
        r = client.get("/api/rule-versions/logs/policy-check")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_crud_definition(self, client):
        rule_id = f"XT-{uuid.uuid4().hex[:3].upper()}"
        r = client.post("/api/rule-versions/definitions", json={
            "rule_id": rule_id,
            "rule_type": "hard_rule",
            "rule_name": "Test rule",
        })
        assert r.status_code == 201
        assert r.json()["rule_id"] == rule_id

        r = client.post("/api/rule-versions/definitions", json={
            "rule_id": rule_id,
            "rule_type": "hard_rule",
            "rule_name": "Duplicate",
        })
        assert r.status_code == 409

        r = client.patch(f"/api/rule-versions/definitions/{rule_id}", json={
            "rule_name": "Updated name",
        })
        assert r.status_code == 200
        assert r.json()["rule_name"] == "Updated name"

        r = client.delete(f"/api/rule-versions/definitions/{rule_id}")
        assert r.status_code == 204

        r = client.get(f"/api/rule-versions/definitions/{rule_id}")
        assert r.status_code == 200
        assert r.json()["active"] is False


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


class TestIntake:
    def test_extract_basic(self, client):
        r = client.post("/api/intake/extract", json={
            "source_text": "Need 50 laptops, budget EUR 25000, deliver to DE by 2026-06-01",
        })
        assert r.status_code == 200
        body = r.json()
        assert "draft" in body
        assert "field_status" in body
        assert "missing_required" in body
        assert "warnings" in body
        assert "extraction_strength" in body
        assert body["draft"]["quantity"] == 50.0
        assert body["draft"]["currency"] == "EUR"

    def test_extract_empty(self, client):
        r = client.post("/api/intake/extract", json={
            "source_text": "",
        })
        assert r.status_code == 200
        body = r.json()
        assert "categoryId" in body["missing_required"]
        assert any(w["code"] == "EMPTY_SOURCE" for w in body["warnings"])

    def test_extract_with_data_residency(self, client):
        r = client.post("/api/intake/extract", json={
            "source_text": "Require cloud storage with data residency in CH, budget CHF 10000",
        })
        assert r.status_code == 200
        assert r.json()["draft"]["dataResidencyConstraint"] is True
        assert r.json()["draft"]["currency"] == "CHF"

    def test_extract_with_esg(self, client):
        r = client.post("/api/intake/extract", json={
            "source_text": "Need sustainable office furniture, ESG certified, budget EUR 5000",
        })
        assert r.status_code == 200
        assert r.json()["draft"]["esgRequirement"] is True
