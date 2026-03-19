"""Tests for app.utils module."""

from app.utils import (
    coerce_budget,
    coerce_quantity,
    compute_days_until_required,
    country_to_region,
    normalize_delivery_countries,
    normalize_scenario_tags,
    primary_delivery_country,
    truncate_error,
    truncate_for_log,
)


class TestCoerceBudget:
    def test_none(self):
        assert coerce_budget(None) is None

    def test_float(self):
        assert coerce_budget(25199.55) == 25199.55

    def test_string(self):
        assert coerce_budget("25199.55") == 25199.55

    def test_int(self):
        assert coerce_budget(25000) == 25000.0

    def test_invalid_string(self):
        assert coerce_budget("not_a_number") is None

    def test_empty_string(self):
        assert coerce_budget("") is None


class TestCoerceQuantity:
    def test_none(self):
        assert coerce_quantity(None) is None

    def test_int(self):
        assert coerce_quantity(240) == 240

    def test_float(self):
        assert coerce_quantity(240.0) == 240

    def test_string(self):
        assert coerce_quantity("240") == 240

    def test_float_string(self):
        assert coerce_quantity("240.0") == 240

    def test_invalid(self):
        assert coerce_quantity("abc") is None


class TestCountryToRegion:
    def test_eu_countries(self):
        for code in ["DE", "FR", "NL", "BE", "AT", "IT", "ES", "PL", "UK"]:
            assert country_to_region(code) == "EU"

    def test_switzerland(self):
        assert country_to_region("CH") == "CH"

    def test_americas(self):
        for code in ["US", "CA", "BR", "MX"]:
            assert country_to_region(code) == "Americas"

    def test_apac(self):
        for code in ["SG", "AU", "IN", "JP"]:
            assert country_to_region(code) == "APAC"

    def test_mea(self):
        for code in ["UAE", "ZA"]:
            assert country_to_region(code) == "MEA"

    def test_unknown_defaults_to_eu(self):
        assert country_to_region("XX") == "EU"


class TestNormalizeDeliveryCountries:
    def test_empty(self):
        assert normalize_delivery_countries([]) == []

    def test_none(self):
        assert normalize_delivery_countries(None) == []

    def test_string_list(self):
        assert normalize_delivery_countries(["DE", "FR"]) == ["DE", "FR"]

    def test_dict_list(self):
        result = normalize_delivery_countries([
            {"country_code": "DE"},
            {"country_code": "FR"},
        ])
        assert result == ["DE", "FR"]

    def test_dict_list_missing_key(self):
        result = normalize_delivery_countries([{"other": "val"}])
        assert result == []


class TestNormalizeScenarioTags:
    def test_string_list(self):
        assert normalize_scenario_tags(["standard"]) == ["standard"]

    def test_dict_list(self):
        assert normalize_scenario_tags([{"tag": "contradictory"}]) == ["contradictory"]

    def test_empty(self):
        assert normalize_scenario_tags([]) == []

    def test_none(self):
        assert normalize_scenario_tags(None) == []


class TestPrimaryDeliveryCountry:
    def test_with_countries(self):
        assert primary_delivery_country({"delivery_countries": ["FR"]}) == "FR"

    def test_with_dict_countries(self):
        assert primary_delivery_country(
            {"delivery_countries": [{"country_code": "FR"}]}
        ) == "FR"

    def test_fallback_to_country(self):
        assert primary_delivery_country(
            {"delivery_countries": [], "country": "CH"}
        ) == "CH"

    def test_fallback_to_de(self):
        assert primary_delivery_country({"delivery_countries": []}) == "DE"


class TestComputeDaysUntilRequired:
    def test_with_dates(self):
        result = compute_days_until_required("2026-03-20", "2026-03-14T17:55:00")
        assert result == 6

    def test_no_required_date(self):
        assert compute_days_until_required(None, "2026-03-14") is None

    def test_no_created_at_uses_today(self):
        result = compute_days_until_required("2030-01-01", None)
        assert result is not None
        assert result > 0

    def test_date_in_past(self):
        result = compute_days_until_required("2020-01-01", "2026-03-14")
        assert result is not None
        assert result < 0

    def test_invalid_date(self):
        assert compute_days_until_required("not-a-date", "2026-03-14") is None

    def test_iso_datetime_with_z(self):
        result = compute_days_until_required("2026-03-20", "2026-03-14T17:55:00Z")
        assert result == 6


class TestTruncateForLog:
    def test_short_string(self):
        assert truncate_for_log("hello") == "hello"

    def test_long_string(self):
        long_str = "x" * 600
        result = truncate_for_log(long_str)
        assert len(result) == 500

    def test_dict(self):
        result = truncate_for_log({"key": "value"})
        assert result == {"key": "value"}

    def test_short_list(self):
        result = truncate_for_log([1, 2, 3])
        assert result == [1, 2, 3]

    def test_long_list(self):
        result = truncate_for_log(list(range(20)))
        assert result["_type"] == "list"
        assert result["_length"] == 20
        assert len(result["_sample"]) == 3

    def test_nested_depth(self):
        deep = {"a": {"b": {"c": {"d": {"e": "val"}}}}}
        result = truncate_for_log(deep)
        assert result["a"]["b"]["c"]["d"] == "<truncated>"

    def test_none(self):
        assert truncate_for_log(None) is None


class TestTruncateError:
    def test_short(self):
        assert truncate_error("error") == "error"

    def test_long(self):
        long_err = "x" * 3000
        assert len(truncate_error(long_err)) == 2000
