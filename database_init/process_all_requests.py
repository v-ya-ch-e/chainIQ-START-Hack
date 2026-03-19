"""
Process all purchase requests through the procurement pipeline.

Fetches request IDs from the Organisational Layer API, then calls the
Logical Layer pipeline endpoint for each request with configurable
concurrency and progress tracking.

Usage:
    source .venv/bin/activate
    python process_all_requests.py                        # process all 'new' requests
    python process_all_requests.py --status all           # process ALL requests regardless of status
    python process_all_requests.py --concurrency 5        # 5 concurrent requests
    python process_all_requests.py --dry-run              # list request IDs without processing
"""

import argparse
import asyncio
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ORG_URL = os.getenv("ORGANISATIONAL_LAYER_URL", "http://localhost:8000")
DEFAULT_LOGICAL_URL = os.getenv("LOGICAL_LAYER_URL", "http://localhost:8080")


async def fetch_request_ids(
    client: httpx.AsyncClient,
    org_url: str,
    status_filter: str | None,
) -> list[str]:
    """Fetch all request IDs from the Organisational Layer, paginated."""
    ids: list[str] = []
    skip = 0
    limit = 200

    while True:
        params: dict = {"skip": skip, "limit": limit}
        if status_filter and status_filter != "all":
            params["status"] = status_filter

        resp = await client.get(f"{org_url}/api/requests", params=params)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        for item in items:
            ids.append(item["request_id"])

        total = data.get("total", 0)
        skip += limit
        if skip >= total:
            break

    return ids


async def process_single(
    client: httpx.AsyncClient,
    logical_url: str,
    request_id: str,
    timeout: float,
) -> dict:
    """Process one request through the pipeline. Returns result dict."""
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{logical_url}/api/pipeline/process",
            json={"request_id": request_id},
            timeout=timeout,
        )
        elapsed = time.monotonic() - start

        if resp.status_code == 200:
            data = resp.json()
            status = data.get("recommendation", {}).get("status", "unknown")
            return {
                "request_id": request_id,
                "success": True,
                "status": status,
                "elapsed_s": round(elapsed, 1),
            }
        else:
            return {
                "request_id": request_id,
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "elapsed_s": round(elapsed, 1),
            }
    except httpx.TimeoutException:
        elapsed = time.monotonic() - start
        return {
            "request_id": request_id,
            "success": False,
            "error": f"Timeout after {round(elapsed, 1)}s",
            "elapsed_s": round(elapsed, 1),
        }
    except Exception as exc:
        elapsed = time.monotonic() - start
        return {
            "request_id": request_id,
            "success": False,
            "error": str(exc)[:200],
            "elapsed_s": round(elapsed, 1),
        }


async def run_processing(
    org_url: str = DEFAULT_ORG_URL,
    logical_url: str = DEFAULT_LOGICAL_URL,
    status_filter: str | None = "new",
    concurrency: int = 3,
    timeout: float = 120.0,
    dry_run: bool = False,
) -> dict:
    """Process all matching requests. Returns summary dict for testability."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        print("=== Process All Requests ===\n")
        print(f"Org Layer:     {org_url}")
        print(f"Logical Layer: {logical_url}")
        print(f"Status filter: {status_filter or 'all'}")
        print(f"Concurrency:   {concurrency}")
        print(f"Timeout:       {timeout}s per request")

        print("\nFetching request IDs...")
        request_ids = await fetch_request_ids(client, org_url, status_filter)
        print(f"Found {len(request_ids)} request(s)")

        if not request_ids:
            print("\nNo requests to process.")
            return {"total": 0, "succeeded": 0, "failed": 0, "request_ids": []}

        if dry_run:
            print(f"\n[DRY RUN] Would process {len(request_ids)} requests:")
            for rid in request_ids:
                print(f"  {rid}")
            return {"dry_run": True, "total": len(request_ids), "request_ids": request_ids}

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout + 10)) as client:
        semaphore = asyncio.Semaphore(concurrency)
        results: list[dict] = []
        succeeded = 0
        failed = 0
        start_time = time.monotonic()

        async def _process_with_semaphore(rid: str, index: int) -> None:
            nonlocal succeeded, failed
            async with semaphore:
                result = await process_single(client, logical_url, rid, timeout)
                results.append(result)
                if result["success"]:
                    succeeded += 1
                    marker = "OK"
                else:
                    failed += 1
                    marker = "FAIL"
                progress = f"[{index + 1}/{len(request_ids)}]"
                print(
                    f"  {progress:>10s} {rid} {marker:>4s}"
                    f"  ({result.get('elapsed_s', 0)}s)"
                    f"  {result.get('status', result.get('error', ''))}"
                )

        print(f"\nProcessing {len(request_ids)} requests...\n")
        tasks = [
            _process_with_semaphore(rid, i)
            for i, rid in enumerate(request_ids)
        ]
        await asyncio.gather(*tasks)

        total_elapsed = time.monotonic() - start_time

        print(f"\n=== Summary ===")
        print(f"  Total:     {len(request_ids)}")
        print(f"  Succeeded: {succeeded}")
        print(f"  Failed:    {failed}")
        print(f"  Elapsed:   {total_elapsed:.1f}s")
        if len(request_ids) > 0:
            print(f"  Avg:       {total_elapsed / len(request_ids):.1f}s per request")

        if failed > 0:
            print(f"\nFailed requests:")
            for r in results:
                if not r["success"]:
                    print(f"  {r['request_id']}: {r['error']}")

        return {
            "total": len(request_ids),
            "succeeded": succeeded,
            "failed": failed,
            "elapsed_s": round(total_elapsed, 1),
            "results": results,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Process all purchase requests through the procurement pipeline"
    )
    parser.add_argument(
        "--org-url", default=DEFAULT_ORG_URL,
        help=f"Organisational Layer URL (default: {DEFAULT_ORG_URL})",
    )
    parser.add_argument(
        "--logical-url", default=DEFAULT_LOGICAL_URL,
        help=f"Logical Layer URL (default: {DEFAULT_LOGICAL_URL})",
    )
    parser.add_argument(
        "--status", default="new",
        help="Filter requests by status (default: 'new', use 'all' for all statuses)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=3,
        help="Maximum concurrent pipeline requests (default: 3)",
    )
    parser.add_argument(
        "--timeout", type=float, default=120.0,
        help="Timeout per request in seconds (default: 120)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List request IDs without processing them",
    )
    args = parser.parse_args()
    asyncio.run(run_processing(
        org_url=args.org_url,
        logical_url=args.logical_url,
        status_filter=args.status,
        concurrency=args.concurrency,
        timeout=args.timeout,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
