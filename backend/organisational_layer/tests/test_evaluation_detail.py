"""Tests for evaluation detail endpoint — supplier_shortlist & suppliers_excluded fields.

Covers Felix's "details navigator" feature: the GET /api/rule-versions/evaluations/{run_id}
endpoint now extracts supplier_shortlist and suppliers_excluded from the evaluation run's
output_snapshot JSON and returns them in the response.

Run with:  cd backend/organisational_layer && pytest tests/test_evaluation_detail.py -v
"""

import uuid

import pytest


def _make_run_id() -> str:
    return str(uuid.uuid4())


def _make_output_snapshot(
    *,
    supplier_shortlist: list | None = None,
    suppliers_excluded: list | None = None,
) -> dict:
    """Build a minimal output_snapshot with the fields under test."""
    snap = {
        "request_interpretation": {
            "category_l1": "IT Hardware",
            "category_l2": "Laptops & Notebooks",
            "quantity": 10,
            "currency": "EUR",
            "budget_amount": 10000.0,
        },
        "supplier_shortlist": supplier_shortlist or [],
        "suppliers_excluded": suppliers_excluded or [],
        "escalations": [],
        "policy_evaluation": {},
        "validation": {"completeness": "pass", "issues_detected": []},
    }
    return snap


class TestEvaluationDetailSnapshot:
    """Tests for supplier_shortlist/suppliers_excluded in evaluation detail."""

    def _create_eval_run(self, client, run_id: str, output_snapshot: dict) -> dict:
        """Helper: create an evaluation run via the full endpoint."""
        resp = client.post(
            "/api/rule-versions/evaluations/full",
            json={
                "run_id": run_id,
                "request_id": "REQ-000004",
                "triggered_by": "test",
                "agent_version": "test-1.0",
                "status": "completed",
                "output_snapshot": output_snapshot,
                "hard_rule_checks": [],
                "policy_checks": [],
                "supplier_evaluations": [],
                "escalations": [],
            },
        )
        return resp

    def _cleanup_run(self, db, run_id: str):
        """Remove the test evaluation run and its dependents."""
        from app.models.evaluations import EvaluationRun, EvaluationRunLog
        db.query(EvaluationRunLog).filter(EvaluationRunLog.run_id == run_id).delete()
        db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).delete()
        db.commit()

    def test_detail_includes_shortlist_and_excluded(self, client, db):
        """Evaluation detail returns supplier_shortlist + suppliers_excluded from snapshot."""
        run_id = _make_run_id()
        shortlist = [
            {"supplier_id": "SUP-0001", "supplier_name": "Dell Technologies", "rank": 1},
            {"supplier_id": "SUP-0007", "supplier_name": "Bechtle", "rank": 2},
        ]
        excluded = [
            {"supplier_id": "SUP-0010", "supplier_name": "Restricted Corp", "reason": "Globally restricted"},
        ]
        snapshot = _make_output_snapshot(
            supplier_shortlist=shortlist,
            suppliers_excluded=excluded,
        )

        try:
            create_resp = self._create_eval_run(client, run_id, snapshot)
            assert create_resp.status_code == 200, create_resp.text

            r = client.get(f"/api/rule-versions/evaluations/{run_id}")
            assert r.status_code == 200
            body = r.json()

            assert body["run_id"] == run_id
            assert body["supplier_shortlist"] == shortlist
            assert len(body["suppliers_excluded"]) == 1
            assert body["suppliers_excluded"][0]["supplier_id"] == "SUP-0010"
            assert body["suppliers_excluded"][0]["reason"] == "Globally restricted"
        finally:
            self._cleanup_run(db, run_id)

    def test_detail_empty_snapshot_returns_empty_lists(self, client, db):
        """When output_snapshot has no shortlist/excluded, response returns empty lists."""
        run_id = _make_run_id()
        snapshot = _make_output_snapshot()

        try:
            create_resp = self._create_eval_run(client, run_id, snapshot)
            assert create_resp.status_code == 200, create_resp.text

            r = client.get(f"/api/rule-versions/evaluations/{run_id}")
            assert r.status_code == 200
            body = r.json()

            assert body["supplier_shortlist"] == []
            assert body["suppliers_excluded"] == []
        finally:
            self._cleanup_run(db, run_id)

    def test_detail_null_snapshot_returns_empty_lists(self, client, db):
        """When output_snapshot is null, response returns empty lists."""
        run_id = _make_run_id()

        try:
            create_resp = self._create_eval_run(client, run_id, output_snapshot=None)
            assert create_resp.status_code == 200, create_resp.text

            r = client.get(f"/api/rule-versions/evaluations/{run_id}")
            assert r.status_code == 200
            body = r.json()

            assert body["supplier_shortlist"] == []
            assert body["suppliers_excluded"] == []
        finally:
            self._cleanup_run(db, run_id)

    def test_detail_malformed_excluded_entry_handled(self, client, db):
        """Non-dict entries in suppliers_excluded are replaced with safe defaults."""
        run_id = _make_run_id()
        snapshot = _make_output_snapshot(
            suppliers_excluded=["not-a-dict", 42],
        )

        try:
            create_resp = self._create_eval_run(client, run_id, snapshot)
            assert create_resp.status_code == 200, create_resp.text

            r = client.get(f"/api/rule-versions/evaluations/{run_id}")
            assert r.status_code == 200
            body = r.json()

            assert len(body["suppliers_excluded"]) == 2
            for entry in body["suppliers_excluded"]:
                assert isinstance(entry, dict)
                assert "supplier_id" in entry
                assert "supplier_name" in entry
                assert "reason" in entry
        finally:
            self._cleanup_run(db, run_id)

    def test_detail_not_found(self, client):
        """Nonexistent run_id returns 404."""
        r = client.get(f"/api/rule-versions/evaluations/{_make_run_id()}")
        assert r.status_code == 404

    def test_detail_preserves_arbitrary_shortlist_fields(self, client, db):
        """Shortlist dicts can have any shape — they pass through unmodified."""
        run_id = _make_run_id()
        shortlist = [
            {
                "supplier_id": "SUP-0001",
                "supplier_name": "Dell Technologies",
                "rank": 1,
                "total_price": 9500.0,
                "quality_score": 92,
                "custom_field": "preserved",
            },
        ]
        snapshot = _make_output_snapshot(supplier_shortlist=shortlist)

        try:
            create_resp = self._create_eval_run(client, run_id, snapshot)
            assert create_resp.status_code == 200, create_resp.text

            r = client.get(f"/api/rule-versions/evaluations/{run_id}")
            assert r.status_code == 200
            body = r.json()

            assert len(body["supplier_shortlist"]) == 1
            item = body["supplier_shortlist"][0]
            assert item["supplier_id"] == "SUP-0001"
            assert item["custom_field"] == "preserved"
            assert item["quality_score"] == 92
        finally:
            self._cleanup_run(db, run_id)
