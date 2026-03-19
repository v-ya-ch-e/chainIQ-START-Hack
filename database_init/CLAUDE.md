# **USER INSTRUCTIONS**

> Always work in .venv
> Always update @CLAUDE.md file to keep it updated about the project
> You should keep this block with user instructions as it is. You can write below everything you want

# **SERVICE OVERVIEW**

Data migration service that loads all 6 ChainIQ data files (`data/` folder) into a normalised MySQL schema on AWS RDS.

## How to run

```bash
cd database_init
source .venv/bin/activate
cp .env.example .env   # then fill in your RDS credentials
python migrate.py
```

## Key files

| File | Purpose |
|------|---------|
| `migrate.py` | Main migration script — drops/creates 24 tables, reads all data files, normalises inconsistencies, inserts in FK-safe order, prints summary |
| `migrate_rules.py` | Creates rule_definitions, rule_versions, evaluation_runs, hard_rule_checks, policy_checks, supplier_evaluations, escalations. Seeds rule definitions and versions. Run after migrate.py. Required for from-pipeline evaluation persistence. |
| `migrate_dynamic_rules.py` | Creates dynamic_rules tables and seeds 30+ procurement rules (validate, comply, policy, escalate stages). Run after migrate.py and migrate_rules.py. Idempotent. |
| `clean_pipeline_data.py` | Cleanup script — TRUNCATEs pipeline_results + evaluation engine tables (escalations, hard_rule_checks, policy_checks, supplier_evaluations, evaluation_runs, and related audit logs). Resets request statuses to 'new'. Does NOT touch reference data, rules, or logging tables. Flags: `--dry-run`, `--skip-status-reset`, `--yes` |
| `clean_logs.py` | Cleanup script — TRUNCATEs pipeline_runs, pipeline_log_entries, audit_logs. Optionally clears rule_change_logs with `--include-rule-change-logs`. Does NOT touch evaluation data, pipeline_results, or reference data. Flags: `--dry-run`, `--yes` |
| `process_all_requests.py` | Processes all purchase requests through the pipeline. Fetches request IDs from Org Layer, calls Logical Layer pipeline with configurable concurrency and progress tracking. Flags: `--org-url`, `--logical-url`, `--status`, `--concurrency`, `--timeout`, `--dry-run` |
| `tests/test_clean_scripts.py` | Unit tests for all three scripts (mocked DB + HTTP) |
| `requirements.txt` | Python deps: `mysql-connector-python`, `python-dotenv`, `httpx`, `pytest` |
| `.env.example` | Template for DB connection env vars |
| `.env` | Actual credentials (git-ignored) |

## Cleanup & processing scripts

These scripts target only their specific tables — they never drop or recreate the full database.

```bash
cd database_init
source .venv/bin/activate

# Clean pipeline results + evaluation data (resets request statuses to 'new')
python clean_pipeline_data.py --yes

# Clean only logs (pipeline runs, audit logs)
python clean_logs.py --yes

# Process all 'new' requests through the pipeline (requires running backend)
python process_all_requests.py --concurrency 3

# Process ALL requests regardless of status
python process_all_requests.py --status all --concurrency 5

# Preview what each script would do without making changes
python clean_pipeline_data.py --dry-run
python clean_logs.py --dry-run
python process_all_requests.py --dry-run
```

### Typical reset-and-reprocess workflow

```bash
python clean_pipeline_data.py --yes    # clear old results, reset statuses
python clean_logs.py --yes             # clear old logs
python process_all_requests.py --concurrency 3   # reprocess everything
```

## Running tests

```bash
cd database_init
source .venv/bin/activate
python -m pytest tests/ -v
```

## Database schema (24 tables)

**Reference data:** `categories`, `suppliers`, `supplier_categories`, `supplier_service_regions`, `pricing_tiers`
**Requests:** `requests`, `request_delivery_countries`, `request_scenario_tags`
**Historical:** `historical_awards`
**Policies — thresholds:** `approval_thresholds`, `approval_threshold_managers`, `approval_threshold_deviation_approvers`
**Policies — preferred:** `preferred_suppliers_policy`, `preferred_supplier_region_scopes`
**Policies — restricted:** `restricted_suppliers_policy`, `restricted_supplier_scopes`
**Policies — rules:** `category_rules`, `geography_rules`, `geography_rule_countries`, `geography_rule_applies_to_categories`, `escalation_rules`, `escalation_rule_currencies`
**Pipeline logging:** `pipeline_runs`, `pipeline_log_entries`

## Normalisation details

- `suppliers.csv` (151 rows) is split into `suppliers` (40 unique) + `supplier_categories` (151) + `supplier_service_regions` (semicolon-delimited field split into rows)
- `policies.json` approval_thresholds: USD entries use different key names (`min_value`/`max_value`/`quotes_required`/`approvers`) — normalised to match EUR/CHF schema
- `policies.json` geography_rules: GR-001..004 vs GR-005..008 have different schemas — unified
- `policies.json` escalation_rules: ER-008 uses `escalation_target` instead of `escalate_to` — normalised
- `requests.json` arrays (`delivery_countries`, `scenario_tags`) extracted into junction tables