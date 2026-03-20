export type BackendKind = "org" | "logical"

export type QueryPrimitive = string | number | boolean | null | undefined
export type QueryValue = QueryPrimitive | QueryPrimitive[]
export type QueryParams = Record<string, QueryValue>

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export interface BlobResponse {
  blob: Blob
  contentType: string | null
  contentDisposition: string | null
}

export class ApiError extends Error {
  status: number
  path: string
  detail: unknown

  constructor(path: string, status: number, message: string, detail: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.path = path
    this.detail = detail
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function isServerSide() {
  return typeof window === "undefined"
}

function deriveLogicalUrlFromOrg(orgUrl: string): string {
  try {
    const parsed = new URL(orgUrl)
    if (parsed.port === "8000") {
      parsed.port = "8080"
      return parsed.toString().replace(/\/$/, "")
    }
    return `${parsed.protocol}//${parsed.hostname}:8080`
  } catch {
    return orgUrl.replace(":8000", ":8080")
  }
}

function getBaseUrl(kind: BackendKind): string {
  if (!isServerSide()) {
    return ""
  }

  const orgUrl = process.env.BACKEND_INTERNAL_URL
  if (!orgUrl) {
    throw new Error("BACKEND_INTERNAL_URL is required for backend requests.")
  }

  if (kind === "org") {
    return orgUrl.replace(/\/$/, "")
  }

  const logicalUrl = process.env.LOGICAL_BACKEND_INTERNAL_URL
  return (logicalUrl || deriveLogicalUrlFromOrg(orgUrl)).replace(/\/$/, "")
}

export function buildQuery(params?: QueryParams): string {
  if (!params) return ""

  const search = new URLSearchParams()
  for (const [key, rawValue] of Object.entries(params)) {
    if (rawValue === undefined || rawValue === null || rawValue === "") continue

    if (Array.isArray(rawValue)) {
      for (const entry of rawValue) {
        if (entry === undefined || entry === null || entry === "") continue
        search.append(key, String(entry))
      }
      continue
    }

    search.append(key, String(rawValue))
  }

  const query = search.toString()
  return query ? `?${query}` : ""
}

function toErrorMessage(status: number, path: string, detail: unknown): string {
  if (typeof detail === "string" && detail.trim()) {
    return `Request failed (${status}) for ${path}: ${detail}`
  }

  if (detail && typeof detail === "object") {
    const asRecord = detail as Record<string, unknown>
    if (typeof asRecord.detail === "string" && asRecord.detail.trim()) {
      return `Request failed (${status}) for ${path}: ${asRecord.detail}`
    }

    if (Array.isArray(asRecord.detail)) {
      const first = asRecord.detail[0]
      if (first && typeof first === "object" && "msg" in first) {
        const msg = (first as { msg?: unknown }).msg
        if (typeof msg === "string" && msg.trim()) {
          return `Request failed (${status}) for ${path}: ${msg}`
        }
      }
    }
  }

  return `Request failed (${status}) for ${path}`
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? ""

  if (!contentType.includes("application/json")) {
    const text = await response.text()
    return text.length > 0 ? text : null
  }

  try {
    return await response.json()
  } catch {
    return null
  }
}

function shouldRetry(error: unknown): boolean {
  if (!(error instanceof ApiError)) {
    return true
  }

  return error.status >= 500
}

export async function requestJson<T>(
  kind: BackendKind,
  path: string,
  init?: RequestInit,
  options?: { retries?: number; retryDelayMs?: number },
): Promise<T> {
  const retries = options?.retries ?? 1
  const retryDelayMs = options?.retryDelayMs ?? 250
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  const url = `${getBaseUrl(kind)}${normalizedPath}`

  let attempt = 0
  for (;;) {
    try {
      const response = await fetch(url, {
        cache: "no-store",
        ...init,
      })

      const payload = await parseResponseBody(response)

      if (!response.ok) {
        throw new ApiError(
          normalizedPath,
          response.status,
          toErrorMessage(response.status, normalizedPath, payload),
          payload,
        )
      }

      return payload as T
    } catch (error) {
      // #region agent log
      if (normalizedPath.includes("/pipeline/runs")) {
        console.log(`[DEBUG-105a7f] requestJson CATCH: attempt=${attempt}, error=${error instanceof Error ? error.message : String(error)}`);
      }
      // #endregion
      if (attempt >= retries || !shouldRetry(error)) {
        throw error
      }

      attempt += 1
      await sleep(retryDelayMs * attempt)
    }
  }
}

export async function requestNoContent(
  kind: BackendKind,
  path: string,
  init?: RequestInit,
  options?: { retries?: number; retryDelayMs?: number },
): Promise<void> {
  await requestJson<unknown>(kind, path, init, options)
}

export async function requestBlob(
  kind: BackendKind,
  path: string,
  init?: RequestInit,
  options?: { retries?: number; retryDelayMs?: number },
): Promise<BlobResponse> {
  const retries = options?.retries ?? 1
  const retryDelayMs = options?.retryDelayMs ?? 250
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  const url = `${getBaseUrl(kind)}${normalizedPath}`

  let attempt = 0
  for (;;) {
    try {
      const response = await fetch(url, {
        cache: "no-store",
        ...init,
      })

      if (!response.ok) {
        const payload = await parseResponseBody(response)
        throw new ApiError(
          normalizedPath,
          response.status,
          toErrorMessage(response.status, normalizedPath, payload),
          payload,
        )
      }

      return {
        blob: await response.blob(),
        contentType: response.headers.get("content-type"),
        contentDisposition: response.headers.get("content-disposition"),
      }
    } catch (error) {
      if (attempt >= retries || !shouldRetry(error)) {
        throw error
      }

      attempt += 1
      await sleep(retryDelayMs * attempt)
    }
  }
}

export async function fetchAllPages<T>(
  fetchPage: (skip: number, limit: number) => Promise<PaginatedResponse<T>>,
  limit = 200,
): Promise<T[]> {
  const items: T[] = []
  let skip = 0
  let total = 0

  do {
    const page = await fetchPage(skip, limit)
    items.push(...page.items)
    total = page.total
    skip += page.limit
  } while (skip < total)

  return items
}
