#!/usr/bin/env node

/**
 * Investigates duplicate-looking validation/escalation issue patterns
 * across all requests by scanning audit logs per request.
 *
 * Usage:
 *   node scripts/investigate-case-issue-collisions.mjs --base-url http://localhost:8000
 */

const DEFAULT_BASE_URL = "http://localhost:8000"
const REQUEST_PAGE_SIZE = 200
const AUDIT_PAGE_SIZE = 500

function parseArgs(argv) {
  const args = { baseUrl: DEFAULT_BASE_URL }
  for (let idx = 0; idx < argv.length; idx += 1) {
    const token = argv[idx]
    if (token === "--base-url" && argv[idx + 1]) {
      args.baseUrl = argv[idx + 1]
      idx += 1
    }
  }
  return args
}

async function fetchJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`${response.status} ${response.statusText} for ${url}: ${text}`)
  }
  return response.json()
}

async function fetchAllRequests(baseUrl) {
  const items = []
  let skip = 0
  let total = 0
  do {
    const data = await fetchJson(
      `${baseUrl}/api/requests?skip=${skip}&limit=${REQUEST_PAGE_SIZE}`,
    )
    items.push(...(Array.isArray(data.items) ? data.items : []))
    total = Number(data.total ?? 0)
    const pageLimit = Number(data.limit ?? REQUEST_PAGE_SIZE)
    skip += pageLimit
  } while (skip < total)
  return items
}

async function fetchAllAuditByRequest(baseUrl, requestId) {
  const items = []
  let skip = 0
  let total = 0
  do {
    const data = await fetchJson(
      `${baseUrl}/api/logs/audit/by-request/${encodeURIComponent(requestId)}?skip=${skip}&limit=${AUDIT_PAGE_SIZE}`,
    )
    items.push(...(Array.isArray(data.items) ? data.items : []))
    total = Number(data.total ?? 0)
    skip += AUDIT_PAGE_SIZE
  } while (skip < total)
  return items
}

function asRecord(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value
}

function countDuplicates(keys) {
  const map = new Map()
  for (const key of keys) {
    map.set(key, (map.get(key) ?? 0) + 1)
  }
  const duplicates = [...map.entries()].filter(([, count]) => count > 1)
  duplicates.sort((a, b) => b[1] - a[1])
  return duplicates
}

function summarizeRequest(requestId, auditItems) {
  const validationItems = auditItems.filter((entry) => entry.category === "validation")
  const escalationItems = auditItems.filter((entry) => entry.category === "escalation")

  const validationTypeKeys = validationItems.map((entry) => {
    const details = asRecord(entry.details)
    return String(details?.issue_type ?? "unknown")
  })

  const validationSignatureKeys = validationItems.map((entry) => {
    const details = asRecord(entry.details)
    const issueType = String(details?.issue_type ?? "unknown")
    const field = String(details?.field ?? "unknown")
    const message = String(entry.message ?? "")
    return `${issueType}::${field}::${message}`
  })

  const escalationSignatureKeys = escalationItems.map((entry) => {
    const details = asRecord(entry.details)
    const target = String(details?.escalate_to ?? "unknown")
    const blocking = String(details?.blocking ?? "unknown")
    const message = String(entry.message ?? "")
    return `${target}::${blocking}::${message}`
  })

  const duplicateValidationTypes = countDuplicates(validationTypeKeys)
  const duplicateValidationSignatures = countDuplicates(validationSignatureKeys)
  const duplicateEscalationSignatures = countDuplicates(escalationSignatureKeys)

  return {
    requestId,
    auditCount: auditItems.length,
    validationCount: validationItems.length,
    escalationCount: escalationItems.length,
    duplicateValidationTypes,
    duplicateValidationSignatures,
    duplicateEscalationSignatures,
    hasValidationTypeCollisions: duplicateValidationTypes.length > 0,
    hasExactValidationCollisions: duplicateValidationSignatures.length > 0,
    hasExactEscalationCollisions: duplicateEscalationSignatures.length > 0,
  }
}

async function main() {
  const { baseUrl } = parseArgs(process.argv.slice(2))
  const normalizedBase = baseUrl.replace(/\/$/, "")
  console.log(`Investigating audit issue collisions via ${normalizedBase}`)

  const requests = await fetchAllRequests(normalizedBase)
  console.log(`Loaded ${requests.length} requests`)

  const summaries = []
  for (let idx = 0; idx < requests.length; idx += 1) {
    const requestId = requests[idx]?.request_id
    if (!requestId) continue
    const auditItems = await fetchAllAuditByRequest(normalizedBase, requestId)
    summaries.push(summarizeRequest(requestId, auditItems))
    if ((idx + 1) % 25 === 0) {
      console.log(`Processed ${idx + 1}/${requests.length} requests`)
    }
  }

  const withValidationTypeCollisions = summaries.filter(
    (entry) => entry.hasValidationTypeCollisions,
  )
  const withExactValidationCollisions = summaries.filter(
    (entry) => entry.hasExactValidationCollisions,
  )
  const withExactEscalationCollisions = summaries.filter(
    (entry) => entry.hasExactEscalationCollisions,
  )

  const report = {
    scannedRequests: summaries.length,
    requestsWithValidationTypeCollisions: withValidationTypeCollisions.length,
    requestsWithExactValidationCollisions: withExactValidationCollisions.length,
    requestsWithExactEscalationCollisions: withExactEscalationCollisions.length,
    topValidationTypeCollisionCases: withValidationTypeCollisions
      .sort(
        (a, b) =>
          (b.duplicateValidationTypes[0]?.[1] ?? 0) -
          (a.duplicateValidationTypes[0]?.[1] ?? 0),
      )
      .slice(0, 15),
    topExactValidationCollisionCases: withExactValidationCollisions
      .sort(
        (a, b) =>
          (b.duplicateValidationSignatures[0]?.[1] ?? 0) -
          (a.duplicateValidationSignatures[0]?.[1] ?? 0),
      )
      .slice(0, 15),
    topExactEscalationCollisionCases: withExactEscalationCollisions
      .sort(
        (a, b) =>
          (b.duplicateEscalationSignatures[0]?.[1] ?? 0) -
          (a.duplicateEscalationSignatures[0]?.[1] ?? 0),
      )
      .slice(0, 15),
  }

  console.log(JSON.stringify(report, null, 2))
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
