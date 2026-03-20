import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.main import app
    IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - environment dependent
    TestClient = None  # type: ignore[assignment]
    get_db = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]
    IMPORT_ERROR = exc


class _FakeQuery:
    def __init__(self, exists: bool):
        self._exists = exists

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return ("REQ-TEST",) if self._exists else None


class _FakeDb:
    def __init__(self, exists: bool):
        self._exists = exists

    def query(self, *args, **kwargs):
        return _FakeQuery(self._exists)


def _override_db_factory(exists: bool):
    def _override():
        yield _FakeDb(exists)

    return _override


class EscalationRouterTests(unittest.TestCase):
    def setUp(self):
        if IMPORT_ERROR is not None:
            self.skipTest(f"Backend dependencies unavailable: {IMPORT_ERROR}")
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch("app.routers.escalations.evaluate_escalation_queue")
    def test_queue_endpoint_returns_rows(self, mock_evaluate):
        app.dependency_overrides[get_db] = _override_db_factory(True)
        mock_evaluate.return_value = [
            {
                "escalation_id": "REQ-TEST-ER-001",
                "request_id": "REQ-TEST",
                "title": "Missing budget",
                "category": "IT / Laptops",
                "business_unit": "IT",
                "country": "DE",
                "rule_id": "ER-001",
                "rule_label": "missing_required_information",
                "trigger": "Missing budget.",
                "escalate_to": "Requester Clarification",
                "blocking": True,
                "status": "open",
                "created_at": "2026-03-19T10:00:00",
                "last_updated": "2026-03-19T10:00:00",
                "recommendation_status": "cannot_proceed",
            }
        ]

        response = self.client.get("/api/escalations/queue")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["rule_id"], "ER-001")

    @patch("app.routers.escalations.evaluate_escalation_queue")
    def test_by_request_endpoint_returns_rows(self, mock_evaluate):
        app.dependency_overrides[get_db] = _override_db_factory(True)
        mock_evaluate.return_value = []

        response = self.client.get("/api/escalations/by-request/REQ-TEST")
        self.assertEqual(response.status_code, 200)

    def test_by_request_endpoint_returns_404_when_missing(self):
        app.dependency_overrides[get_db] = _override_db_factory(False)

        response = self.client.get("/api/escalations/by-request/REQ-MISSING")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
