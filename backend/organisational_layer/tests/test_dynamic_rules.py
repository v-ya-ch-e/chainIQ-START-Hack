"""Integration tests for the dynamic rules CRUD API.

Run with:  cd backend/organisational_layer && pytest tests/test_dynamic_rules.py -v
Requires a live MySQL database with dynamic_rules tables created.
"""

import uuid

import pytest


PREFIX = "/api/dynamic-rules"


def _test_rule_id():
    return f"TEST-{uuid.uuid4().hex[:6].upper()}"


def _make_rule_payload(**overrides):
    defaults = {
        "rule_id": _test_rule_id(),
        "rule_name": "Test rule",
        "description": "A test rule",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "validate",
        "eval_config": {
            "left_field": "budget_amount",
            "operator": ">=",
            "right_field": "min_total_price",
            "right_constant": None,
            "condition": None,
        },
        "action_on_fail": "warn",
        "severity": "high",
        "is_blocking": False,
        "is_active": True,
        "priority": 50,
        "created_by": "test",
    }
    defaults.update(overrides)
    return defaults


class TestListRules:
    def test_list_all(self, client):
        r = client.get(f"{PREFIX}/")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_list_filter_by_stage(self, client):
        r = client.get(f"{PREFIX}/", params={"stage": "validate"})
        assert r.status_code == 200
        data = r.json()
        for rule in data:
            assert rule["pipeline_stage"] == "validate"

    def test_list_filter_by_category(self, client):
        r = client.get(f"{PREFIX}/", params={"category": "hard_rule"})
        assert r.status_code == 200
        for rule in r.json():
            assert rule["rule_category"] == "hard_rule"

    def test_list_active(self, client):
        r = client.get(f"{PREFIX}/active")
        assert r.status_code == 200
        for rule in r.json():
            assert rule["is_active"] is True

    def test_list_active_with_stage(self, client):
        r = client.get(f"{PREFIX}/active", params={"stage": "comply"})
        assert r.status_code == 200
        for rule in r.json():
            assert rule["is_active"] is True
            assert rule["pipeline_stage"] == "comply"


class TestCreateRule:
    def test_create_success(self, client):
        payload = _make_rule_payload()
        r = client.post(f"{PREFIX}/", json=payload)
        assert r.status_code == 201
        body = r.json()
        assert body["rule_id"] == payload["rule_id"]
        assert body["version"] == 1
        assert body["is_active"] is True

        # Cleanup
        client.delete(f"{PREFIX}/{payload['rule_id']}")

    def test_create_duplicate_fails(self, client):
        payload = _make_rule_payload()
        r = client.post(f"{PREFIX}/", json=payload)
        assert r.status_code == 201

        r2 = client.post(f"{PREFIX}/", json=payload)
        assert r2.status_code == 409

        client.delete(f"{PREFIX}/{payload['rule_id']}")

    def test_create_invalid_eval_type(self, client):
        payload = _make_rule_payload(eval_type="invalid_type")
        r = client.post(f"{PREFIX}/", json=payload)
        assert r.status_code == 400

    def test_create_invalid_stage(self, client):
        payload = _make_rule_payload(pipeline_stage="invalid")
        r = client.post(f"{PREFIX}/", json=payload)
        assert r.status_code == 400

    def test_create_invalid_scope(self, client):
        payload = _make_rule_payload(scope="invalid")
        r = client.post(f"{PREFIX}/", json=payload)
        assert r.status_code == 400

    def test_create_creates_version_1(self, client):
        payload = _make_rule_payload()
        r = client.post(f"{PREFIX}/", json=payload)
        assert r.status_code == 201

        rv = client.get(f"{PREFIX}/{payload['rule_id']}/versions")
        assert rv.status_code == 200
        versions = rv.json()
        assert len(versions) == 1
        assert versions[0]["version"] == 1
        assert versions[0]["snapshot"]["rule_name"] == "Test rule"

        client.delete(f"{PREFIX}/{payload['rule_id']}")


class TestGetRule:
    def test_get_existing(self, client):
        payload = _make_rule_payload()
        client.post(f"{PREFIX}/", json=payload)

        r = client.get(f"{PREFIX}/{payload['rule_id']}")
        assert r.status_code == 200
        assert r.json()["rule_id"] == payload["rule_id"]

        client.delete(f"{PREFIX}/{payload['rule_id']}")

    def test_get_not_found(self, client):
        r = client.get(f"{PREFIX}/NONEXISTENT-999")
        assert r.status_code == 404


class TestUpdateRule:
    def test_update_bumps_version(self, client):
        payload = _make_rule_payload()
        client.post(f"{PREFIX}/", json=payload)

        r = client.put(
            f"{PREFIX}/{payload['rule_id']}",
            json={"rule_name": "Updated name", "changed_by": "tester", "change_reason": "test update"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["rule_name"] == "Updated name"
        assert body["version"] == 2

        rv = client.get(f"{PREFIX}/{payload['rule_id']}/versions")
        versions = rv.json()
        assert len(versions) == 2
        assert versions[0]["valid_to"] is not None
        assert versions[1]["valid_to"] is None

        client.delete(f"{PREFIX}/{payload['rule_id']}")

    def test_update_eval_config(self, client):
        payload = _make_rule_payload()
        client.post(f"{PREFIX}/", json=payload)

        new_config = {"left_field": "quantity", "operator": ">=", "right_constant": 10}
        r = client.put(
            f"{PREFIX}/{payload['rule_id']}",
            json={"eval_config": new_config},
        )
        assert r.status_code == 200
        assert r.json()["eval_config"]["left_field"] == "quantity"

        client.delete(f"{PREFIX}/{payload['rule_id']}")

    def test_update_not_found(self, client):
        r = client.put(f"{PREFIX}/NONEXISTENT-999", json={"rule_name": "x"})
        assert r.status_code == 404

    def test_update_no_fields(self, client):
        payload = _make_rule_payload()
        client.post(f"{PREFIX}/", json=payload)

        r = client.put(f"{PREFIX}/{payload['rule_id']}", json={})
        assert r.status_code == 400

        client.delete(f"{PREFIX}/{payload['rule_id']}")


class TestDeleteRule:
    def test_soft_delete(self, client):
        payload = _make_rule_payload()
        client.post(f"{PREFIX}/", json=payload)

        r = client.delete(f"{PREFIX}/{payload['rule_id']}")
        assert r.status_code == 204

        rg = client.get(f"{PREFIX}/{payload['rule_id']}")
        assert rg.status_code == 200
        assert rg.json()["is_active"] is False

    def test_delete_not_found(self, client):
        r = client.delete(f"{PREFIX}/NONEXISTENT-999")
        assert r.status_code == 404


class TestVersionHistory:
    def test_version_history(self, client):
        payload = _make_rule_payload()
        client.post(f"{PREFIX}/", json=payload)
        client.put(f"{PREFIX}/{payload['rule_id']}", json={"severity": "critical"})
        client.put(f"{PREFIX}/{payload['rule_id']}", json={"severity": "low"})

        rv = client.get(f"{PREFIX}/{payload['rule_id']}/versions")
        assert rv.status_code == 200
        versions = rv.json()
        assert len(versions) == 3
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2
        assert versions[2]["version"] == 3

        client.delete(f"{PREFIX}/{payload['rule_id']}")

    def test_version_not_found(self, client):
        r = client.get(f"{PREFIX}/NONEXISTENT-999/versions")
        assert r.status_code == 404


class TestEvaluationResults:
    def test_store_and_retrieve(self, client):
        payload = _make_rule_payload()
        client.post(f"{PREFIX}/", json=payload)

        run_id = str(uuid.uuid4())
        result_id = str(uuid.uuid4())
        results_payload = {
            "results": [
                {
                    "result_id": result_id,
                    "run_id": run_id,
                    "rule_id": payload["rule_id"],
                    "rule_version": 1,
                    "scope": "request",
                    "result": "passed",
                    "message": "Test passed",
                }
            ]
        }

        r = client.post(f"{PREFIX}/evaluation-results", json=results_payload)
        assert r.status_code == 201
        assert r.json()["stored"] == 1

        rr = client.get(f"{PREFIX}/evaluation-results/by-run/{run_id}")
        assert rr.status_code == 200
        data = rr.json()
        assert len(data) == 1
        assert data[0]["result_id"] == result_id
        assert data[0]["result"] == "passed"

        client.delete(f"{PREFIX}/{payload['rule_id']}")


class TestSeededRules:
    """Verify that migration-seeded rules are present and well-formed."""

    def test_seeded_rules_exist(self, client):
        r = client.get(f"{PREFIX}/")
        assert r.status_code == 200
        rules = r.json()
        rule_ids = {r["rule_id"] for r in rules}
        for expected in ["VAL-001", "HR-001", "HR-003", "PC-004", "ER-001", "ER-004"]:
            assert expected in rule_ids, f"Expected seeded rule {expected} not found"

    def test_seeded_rules_have_valid_config(self, client):
        r = client.get(f"{PREFIX}/active")
        assert r.status_code == 200
        for rule in r.json():
            assert rule["eval_type"] in ("compare", "required", "threshold", "set_membership", "custom_llm")
            assert rule["pipeline_stage"] in ("validate", "comply", "policy", "escalate")
            assert rule["scope"] in ("request", "supplier")
            assert isinstance(rule["eval_config"], dict)

    def test_comply_rules_are_supplier_scoped(self, client):
        r = client.get(f"{PREFIX}/active", params={"stage": "comply"})
        assert r.status_code == 200
        for rule in r.json():
            assert rule["scope"] == "supplier"
