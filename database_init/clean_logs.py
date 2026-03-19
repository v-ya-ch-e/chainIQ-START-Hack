"""
Clean pipeline logging and audit log tables.

TRUNCATEs only pipeline_runs, pipeline_log_entries, and audit_logs.
Optionally also clears rule_change_logs (off by default).

Does NOT touch reference data, requests, policies, evaluation data,
pipeline_results, rule_definitions, rule_versions, or any other tables.

Usage:
    source .venv/bin/activate
    python clean_logs.py                          # interactive confirmation
    python clean_logs.py --yes                    # skip confirmation
    python clean_logs.py --dry-run                # preview only
    python clean_logs.py --include-rule-change-logs  # also clear rule change history
"""

import argparse
import os
import sys

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

BASE_TABLES = [
    "pipeline_log_entries",
    "pipeline_runs",
    "audit_logs",
]

OPTIONAL_TABLES = [
    "rule_change_logs",
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


def build_table_list(include_rule_change_logs: bool) -> list[str]:
    tables = list(BASE_TABLES)
    if include_rule_change_logs:
        tables.extend(OPTIONAL_TABLES)
    return tables


def run_clean(
    dry_run: bool = False,
    include_rule_change_logs: bool = False,
    auto_yes: bool = False,
) -> dict:
    """Clean log tables. Returns dict with results for testability."""
    tables = build_table_list(include_rule_change_logs)

    conn = get_connection()
    cursor = conn.cursor()

    before_counts = get_row_counts(cursor, tables)

    print("=== Clean Logs ===\n")
    print("Tables to TRUNCATE:")
    total_rows = 0
    for table in tables:
        count = before_counts[table]
        status = f"{count:>8d} rows" if count >= 0 else "  (missing)"
        print(f"  {table:40s} {status}")
        if count > 0:
            total_rows += count

    if not include_rule_change_logs:
        print(f"\nNote: rule_change_logs preserved (use --include-rule-change-logs to clear)")

    print(f"\nTotal rows to delete: {total_rows}")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        cursor.close()
        conn.close()
        return {"dry_run": True, "tables": tables, "total_rows": total_rows}

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
    for table in tables:
        if before_counts[table] < 0:
            print(f"  SKIP {table} (table does not exist)")
            continue
        cursor.execute(f"TRUNCATE TABLE `{table}`")
        truncated.append(table)
        print(f"  TRUNCATED {table}")

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()

    after_counts = get_row_counts(cursor, tables)

    print("\n=== Summary ===")
    for table in tables:
        before = before_counts[table]
        after = after_counts[table]
        if before >= 0:
            print(f"  {table:40s} {before:>8d} → {after:>8d}")

    cursor.close()
    conn.close()
    print("\nDone.")
    return {"truncated": truncated, "total_rows": total_rows}


def main():
    parser = argparse.ArgumentParser(
        description="Clean pipeline logging and audit log tables"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be cleaned without making changes",
    )
    parser.add_argument(
        "--include-rule-change-logs", action="store_true",
        help="Also clear rule_change_logs (preserved by default)",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip interactive confirmation prompt",
    )
    args = parser.parse_args()
    run_clean(
        dry_run=args.dry_run,
        include_rule_change_logs=args.include_rule_change_logs,
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
