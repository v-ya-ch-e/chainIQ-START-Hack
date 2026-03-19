"""
Clean pipeline processing results and evaluation data.

TRUNCATEs only pipeline_results, evaluation engine tables, and related audit
tables.  Optionally resets all request statuses back to 'new'.

Does NOT touch reference data, requests, policies, rules, rule_definitions,
rule_versions, dynamic_rules, or pipeline logging tables.

Usage:
    source .venv/bin/activate
    python clean_pipeline_data.py              # interactive confirmation
    python clean_pipeline_data.py --yes        # skip confirmation
    python clean_pipeline_data.py --dry-run    # preview only
"""

import argparse
import os
import sys

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

TABLES_TO_TRUNCATE = [
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


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def get_row_counts(cursor, tables: list[str]) -> dict[str, int]:
    counts = {}
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            counts[table] = cursor.fetchone()[0]
        except mysql.connector.Error:
            counts[table] = -1
    return counts


def run_clean(
    dry_run: bool = False,
    skip_status_reset: bool = False,
    auto_yes: bool = False,
) -> dict:
    """Clean pipeline data. Returns dict with results for testability."""
    conn = get_connection()
    cursor = conn.cursor()

    before_counts = get_row_counts(cursor, TABLES_TO_TRUNCATE)

    cursor.execute("SELECT COUNT(*) FROM `requests` WHERE `status` != 'new'")
    non_new_count = cursor.fetchone()[0]

    print("=== Clean Pipeline Data ===\n")
    print("Tables to TRUNCATE:")
    total_rows = 0
    for table in TABLES_TO_TRUNCATE:
        count = before_counts[table]
        status = f"{count:>8d} rows" if count >= 0 else "  (missing)"
        print(f"  {table:40s} {status}")
        if count > 0:
            total_rows += count

    if not skip_status_reset:
        print(f"\nRequest status reset: {non_new_count} requests will be set back to 'new'")
    else:
        print("\nRequest status reset: SKIPPED (--skip-status-reset)")

    print(f"\nTotal rows to delete: {total_rows}")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        cursor.close()
        conn.close()
        return {"dry_run": True, "tables": TABLES_TO_TRUNCATE, "total_rows": total_rows}

    if not auto_yes:
        answer = input("\nProceed? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            cursor.close()
            conn.close()
            return {"aborted": True}

    print("\nTruncating tables...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

    truncated = []
    for table in TABLES_TO_TRUNCATE:
        if before_counts[table] < 0:
            print(f"  SKIP {table} (table does not exist)")
            continue
        cursor.execute(f"TRUNCATE TABLE `{table}`")
        truncated.append(table)
        print(f"  TRUNCATED {table}")

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()

    reset_count = 0
    if not skip_status_reset:
        cursor.execute("UPDATE `requests` SET `status` = 'new' WHERE `status` != 'new'")
        reset_count = cursor.rowcount
        conn.commit()
        print(f"\nReset {reset_count} request(s) to status='new'")

    after_counts = get_row_counts(cursor, TABLES_TO_TRUNCATE)

    print("\n=== Summary ===")
    for table in TABLES_TO_TRUNCATE:
        before = before_counts[table]
        after = after_counts[table]
        if before >= 0:
            print(f"  {table:40s} {before:>8d} → {after:>8d}")

    cursor.close()
    conn.close()
    print("\nDone.")
    return {
        "truncated": truncated,
        "total_rows": total_rows,
        "reset_count": reset_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Clean pipeline processing results and evaluation data"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be cleaned without making changes",
    )
    parser.add_argument(
        "--skip-status-reset", action="store_true",
        help="Do not reset request statuses back to 'new'",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip interactive confirmation prompt",
    )
    args = parser.parse_args()
    run_clean(
        dry_run=args.dry_run,
        skip_status_reset=args.skip_status_reset,
        auto_yes=args.yes,
    )


if __name__ == "__main__":
    try:
        main()
    except mysql.connector.Error as e:
        print(f"\nDatabase error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
