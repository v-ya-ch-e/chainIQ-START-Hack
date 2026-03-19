#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:3000}"
PAGE_PATH="${2:-/inbox}"

BASE_URL="${BASE_URL%/}"

echo "Smoke-checking Next static assets for ${BASE_URL}${PAGE_PATH}"

HTML_CONTENT="$(curl -fsSL "${BASE_URL}${PAGE_PATH}")"
mapfile -t ASSETS < <(
  printf "%s" "${HTML_CONTENT}" \
    | rg -o '/_next/static/chunks/[A-Za-z0-9._~\-]+\.(js|css)' \
    | sort -u
)

if [[ "${#ASSETS[@]}" -eq 0 ]]; then
  echo "No static chunk assets were detected in the page markup." >&2
  exit 1
fi

FAILURES=0
for ASSET in "${ASSETS[@]}"; do
  STATUS_CODE="$(curl -sS -o /dev/null -w "%{http_code}" "${BASE_URL}${ASSET}")"
  if [[ "${STATUS_CODE}" != "200" ]]; then
    echo "FAIL ${ASSET} -> ${STATUS_CODE}"
    FAILURES=$((FAILURES + 1))
  else
    echo "OK   ${ASSET}"
  fi
done

if [[ "${FAILURES}" -gt 0 ]]; then
  echo "Asset smoke check failed with ${FAILURES} missing asset(s)." >&2
  exit 1
fi

echo "Asset smoke check passed (${#ASSETS[@]} assets)."
