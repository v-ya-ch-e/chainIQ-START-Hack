"""
Tests for database cleanup and pipeline processing scripts.

All tests use mocked MySQL connections and mocked HTTP responses —
no live database or services needed.
"""

import asyncio
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_cursor(row_counts: dict[str, int] | None = None):
    """Create a mock cursor that returns row counts for SELECT COUNT(*)."""
    cursor = MagicMock()
    counts = row_counts or {}
    call_index = {"i": 0}
    results = []

    def _execute(sql, *args, **kwargs):
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT COUNT(*)"):
            for table_name, count in counts.items():
                if table_name in sql:
                    results.append(count)
                    return
            results.append(0)

    def _fetchone():
        if results:
            return (results.pop(0),)
        return (0,)

    cursor.execute = MagicMock(side_effect=_execute)
    cursor.fetchone = MagicMock(side_effect=_fetchone)
    cursor.rowcount = 5
    return cursor


def _make_mock_connection(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ===========================================================================
# clean_pipeline_data.py tests
# ===========================================================================


class TestCleanPipelineData:
    """Tests for clean_pipeline_data module."""

    def test_tables_to_truncate_are_correct(self):
        from clean_pipeline_data import TABLES_TO_TRUNCATE

        expected = [
            "escalation_logs",
            "policy_change_logs",
            "evaluation_run_logs",
            "policy_check_logs",
            "escalations",
            "hard_rule_checks",
            "policy_checks",
            "supplier_evaluations",
            "evaluation_runs",
            "pipeline_results",
        ]
        assert TABLES_TO_TRUNCATE == expected

    def test_does_not_include_reference_tables(self):
        from clean_pipeline_data import TABLES_TO_TRUNCATE

        protected = [
            "categories", "suppliers", "supplier_categories",
            "supplier_service_regions", "pricing_tiers",
            "requests", "request_delivery_countries", "request_scenario_tags",
            "historical_awards",
            "approval_thresholds", "preferred_suppliers_policy",
            "restricted_suppliers_policy",
            "rule_definitions", "rule_versions",
            "pipeline_runs", "pipeline_log_entries", "audit_logs",
        ]
        for table in protected:
            assert table not in TABLES_TO_TRUNCATE, f"{table} should not be truncated"

    @patch("clean_pipeline_data.get_connection")
    def test_dry_run_does_not_write(self, mock_get_conn):
        from clean_pipeline_data import run_clean

        cursor = MagicMock()
        cursor.fetchone.return_value = (0,)
        conn = _make_mock_connection(cursor)
        mock_get_conn.return_value = conn

        result = run_clean(dry_run=True)

        assert result["dry_run"] is True
        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        for sql in executed_sqls:
            assert "TRUNCATE" not in sql.upper()
            assert "UPDATE" not in sql.upper()

    @patch("clean_pipeline_data.get_connection")
    def test_truncates_all_tables_with_yes(self, mock_get_conn):
        from clean_pipeline_data import TABLES_TO_TRUNCATE, run_clean

        cursor = MagicMock()
        cursor.fetchone.return_value = (10,)
        cursor.rowcount = 5
        conn = _make_mock_connection(cursor)
        mock_get_conn.return_value = conn

        result = run_clean(dry_run=False, auto_yes=True)

        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        for table in TABLES_TO_TRUNCATE:
            assert any(
                f"TRUNCATE TABLE `{table}`" in sql for sql in executed_sqls
            ), f"Expected TRUNCATE for {table}"

    @patch("clean_pipeline_data.get_connection")
    def test_resets_request_status(self, mock_get_conn):
        from clean_pipeline_data import run_clean

        cursor = MagicMock()
        cursor.fetchone.return_value = (10,)
        cursor.rowcount = 42
        conn = _make_mock_connection(cursor)
        mock_get_conn.return_value = conn

        result = run_clean(dry_run=False, auto_yes=True, skip_status_reset=False)

        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        update_sqls = [s for s in executed_sqls if "UPDATE" in s.upper() and "requests" in s]
        assert len(update_sqls) == 1
        assert "status" in update_sqls[0]
        assert "new" in update_sqls[0]

    @patch("clean_pipeline_data.get_connection")
    def test_skip_status_reset_omits_update(self, mock_get_conn):
        from clean_pipeline_data import run_clean

        cursor = MagicMock()
        cursor.fetchone.return_value = (0,)
        conn = _make_mock_connection(cursor)
        mock_get_conn.return_value = conn

        result = run_clean(dry_run=False, auto_yes=True, skip_status_reset=True)

        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        update_sqls = [s for s in executed_sqls if "UPDATE" in s.upper() and "requests" in s]
        assert len(update_sqls) == 0

    @patch("clean_pipeline_data.get_connection")
    def test_disables_and_restores_fk_checks(self, mock_get_conn):
        from clean_pipeline_data import run_clean

        cursor = MagicMock()
        cursor.fetchone.return_value = (5,)
        cursor.rowcount = 0
        conn = _make_mock_connection(cursor)
        mock_get_conn.return_value = conn

        run_clean(dry_run=False, auto_yes=True)

        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        assert "SET FOREIGN_KEY_CHECKS = 0" in executed_sqls
        assert "SET FOREIGN_KEY_CHECKS = 1" in executed_sqls
        fk_off_idx = executed_sqls.index("SET FOREIGN_KEY_CHECKS = 0")
        fk_on_idx = executed_sqls.index("SET FOREIGN_KEY_CHECKS = 1")
        assert fk_off_idx < fk_on_idx


# ===========================================================================
# clean_logs.py tests
# ===========================================================================


class TestCleanLogs:
    """Tests for clean_logs module."""

    def test_base_tables_are_correct(self):
        from clean_logs import BASE_TABLES

        assert "pipeline_log_entries" in BASE_TABLES
        assert "pipeline_runs" in BASE_TABLES
        assert "audit_logs" in BASE_TABLES
        assert "rule_change_logs" not in BASE_TABLES

    def test_build_table_list_without_rule_change_logs(self):
        from clean_logs import build_table_list

        tables = build_table_list(include_rule_change_logs=False)
        assert "rule_change_logs" not in tables
        assert "pipeline_runs" in tables

    def test_build_table_list_with_rule_change_logs(self):
        from clean_logs import build_table_list

        tables = build_table_list(include_rule_change_logs=True)
        assert "rule_change_logs" in tables
        assert "pipeline_runs" in tables

    def test_does_not_include_evaluation_tables(self):
        from clean_logs import build_table_list

        tables = build_table_list(include_rule_change_logs=True)
        protected = [
            "pipeline_results", "evaluation_runs", "hard_rule_checks",
            "policy_checks", "supplier_evaluations", "escalations",
            "requests", "categories", "suppliers",
        ]
        for t in protected:
            assert t not in tables, f"{t} should not be in log cleanup"

    @patch("clean_logs.get_connection")
    def test_dry_run_does_not_write(self, mock_get_conn):
        from clean_logs import run_clean

        cursor = MagicMock()
        cursor.fetchone.return_value = (0,)
        conn = _make_mock_connection(cursor)
        mock_get_conn.return_value = conn

        result = run_clean(dry_run=True)

        assert result["dry_run"] is True
        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        for sql in executed_sqls:
            assert "TRUNCATE" not in sql.upper()

    @patch("clean_logs.get_connection")
    def test_truncates_base_tables(self, mock_get_conn):
        from clean_logs import BASE_TABLES, run_clean

        cursor = MagicMock()
        cursor.fetchone.return_value = (10,)
        conn = _make_mock_connection(cursor)
        mock_get_conn.return_value = conn

        run_clean(dry_run=False, auto_yes=True, include_rule_change_logs=False)

        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        for table in BASE_TABLES:
            assert any(
                f"TRUNCATE TABLE `{table}`" in sql for sql in executed_sqls
            ), f"Expected TRUNCATE for {table}"
        assert not any("rule_change_logs" in sql and "TRUNCATE" in sql for sql in executed_sqls)

    @patch("clean_logs.get_connection")
    def test_include_rule_change_logs_flag(self, mock_get_conn):
        from clean_logs import run_clean

        cursor = MagicMock()
        cursor.fetchone.return_value = (10,)
        conn = _make_mock_connection(cursor)
        mock_get_conn.return_value = conn

        run_clean(dry_run=False, auto_yes=True, include_rule_change_logs=True)

        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        assert any(
            "TRUNCATE TABLE `rule_change_logs`" in sql for sql in executed_sqls
        )


# ===========================================================================
# process_all_requests.py tests
# ===========================================================================


class TestProcessAllRequests:
    """Tests for process_all_requests module."""

    def test_fetch_request_ids_single_page(self):
        from process_all_requests import fetch_request_ids

        async def _test():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "items": [
                    {"request_id": "REQ-000001"},
                    {"request_id": "REQ-000002"},
                ],
                "total": 2,
                "skip": 0,
                "limit": 200,
            }

            client = MagicMock()
            client.get = _async_return(mock_response)

            ids = await fetch_request_ids(client, "http://test:8000", "new")
            assert ids == ["REQ-000001", "REQ-000002"]

        asyncio.run(_test())

    def test_fetch_request_ids_pagination(self):
        from process_all_requests import fetch_request_ids

        async def _test():
            page1 = MagicMock()
            page1.raise_for_status = MagicMock()
            page1.json.return_value = {
                "items": [{"request_id": f"REQ-{i:06d}"} for i in range(200)],
                "total": 304,
                "skip": 0,
                "limit": 200,
            }

            page2 = MagicMock()
            page2.raise_for_status = MagicMock()
            page2.json.return_value = {
                "items": [{"request_id": f"REQ-{i:06d}"} for i in range(200, 304)],
                "total": 304,
                "skip": 200,
                "limit": 200,
            }

            call_count = {"n": 0}

            async def mock_get(url, params=None):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return page1
                return page2

            client = MagicMock()
            client.get = mock_get

            ids = await fetch_request_ids(client, "http://test:8000", "new")
            assert len(ids) == 304

        asyncio.run(_test())

    def test_fetch_request_ids_status_all(self):
        from process_all_requests import fetch_request_ids

        async def _test():
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "items": [{"request_id": "REQ-000001"}],
                "total": 1,
            }

            captured_params = {}

            async def mock_get(url, params=None):
                captured_params.update(params or {})
                return mock_response

            client = MagicMock()
            client.get = mock_get

            await fetch_request_ids(client, "http://test:8000", "all")
            assert "status" not in captured_params

        asyncio.run(_test())

    def test_process_single_success(self):
        from process_all_requests import process_single

        async def _test():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "recommendation": {"status": "can_proceed"}
            }

            async def mock_post(url, json=None, timeout=None):
                return mock_response

            client = MagicMock()
            client.post = mock_post

            result = await process_single(client, "http://test:8080", "REQ-000001", 60.0)
            assert result["success"] is True
            assert result["status"] == "can_proceed"

        asyncio.run(_test())

    def test_process_single_http_error(self):
        from process_all_requests import process_single

        async def _test():
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            async def mock_post(url, json=None, timeout=None):
                return mock_response

            client = MagicMock()
            client.post = mock_post

            result = await process_single(client, "http://test:8080", "REQ-000001", 60.0)
            assert result["success"] is False
            assert "500" in result["error"]

        asyncio.run(_test())

    def test_process_single_timeout(self):
        from process_all_requests import process_single

        async def _test():
            async def mock_post(url, json=None, timeout=None):
                raise httpx.TimeoutException("timed out")

            client = MagicMock()
            client.post = mock_post

            result = await process_single(client, "http://test:8080", "REQ-000001", 5.0)
            assert result["success"] is False
            assert "Timeout" in result["error"]

        asyncio.run(_test())

    def test_dry_run_does_not_process(self):
        from process_all_requests import run_processing

        async def _test():
            with patch("process_all_requests.httpx.AsyncClient") as MockClient:
                mock_client = MagicMock()

                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.json.return_value = {
                    "items": [
                        {"request_id": "REQ-000001"},
                        {"request_id": "REQ-000002"},
                    ],
                    "total": 2,
                }

                async def mock_get(url, params=None):
                    return mock_response

                mock_client.get = mock_get
                mock_client.post = MagicMock(side_effect=AssertionError("should not call post"))

                mock_cm = MagicMock()
                mock_cm.__aenter__ = _async_return(mock_client)
                mock_cm.__aexit__ = _async_return(None)
                MockClient.return_value = mock_cm

                result = await run_processing(dry_run=True)
                assert result["dry_run"] is True
                assert result["total"] == 2

        asyncio.run(_test())

    def test_run_processing_handles_mixed_results(self):
        from process_all_requests import run_processing

        async def _test():
            with patch("process_all_requests.httpx.AsyncClient") as MockClient:
                mock_client = MagicMock()

                mock_list_response = MagicMock()
                mock_list_response.raise_for_status = MagicMock()
                mock_list_response.json.return_value = {
                    "items": [
                        {"request_id": "REQ-000001"},
                        {"request_id": "REQ-000002"},
                    ],
                    "total": 2,
                }

                ok_response = MagicMock()
                ok_response.status_code = 200
                ok_response.json.return_value = {"recommendation": {"status": "can_proceed"}}

                fail_response = MagicMock()
                fail_response.status_code = 500
                fail_response.text = "Internal Server Error"

                post_calls = {"n": 0}

                async def mock_post(url, json=None, timeout=None):
                    post_calls["n"] += 1
                    if post_calls["n"] == 1:
                        return ok_response
                    return fail_response

                async def mock_get(url, params=None):
                    return mock_list_response

                mock_client.get = mock_get
                mock_client.post = mock_post

                mock_cm = MagicMock()
                mock_cm.__aenter__ = _async_return(mock_client)
                mock_cm.__aexit__ = _async_return(None)
                MockClient.return_value = mock_cm

                result = await run_processing(
                    status_filter="all",
                    concurrency=1,
                    dry_run=False,
                )
                assert result["total"] == 2
                assert result["succeeded"] == 1
                assert result["failed"] == 1

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Async test helpers
# ---------------------------------------------------------------------------


def _async_return(value):
    """Create a coroutine that returns a value (for mocking async calls)."""
    async def _coro(*args, **kwargs):
        return value
    return _coro
