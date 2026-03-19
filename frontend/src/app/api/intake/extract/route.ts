import { NextResponse } from "next/server"

type IntakeRequestBody = {
  source_type?: string
  source_text?: string
  note?: string | null
  request_channel?: string | null
  file_names?: string[]
}

function plusDaysIso(days: number) {
  const value = new Date()
  value.setDate(value.getDate() + days)
  return value.toISOString().slice(0, 10)
}

function extractCurrency(text: string): string | null {
  const upper = text.toUpperCase()
  for (const token of ["CHF", "EUR", "USD"]) {
    if (upper.includes(token)) return token
  }
  return null
}

function extractBudget(text: string): number | null {
  const match = text.match(
    /(?:budget|up to|max(?:imum)?|cap)\s*[:\-]?\s*(?:CHF|EUR|USD)?\s*([0-9][0-9,.]*)/i,
  )
  if (!match?.[1]) return null
  const parsed = Number(match[1].replaceAll(",", ""))
  return Number.isFinite(parsed) ? parsed : null
}

function extractQuantity(text: string): number | null {
  const match = text.match(/(?:qty|quantity|need|needs|for)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)/i)
  if (!match?.[1]) return null
  const parsed = Number(match[1])
  return Number.isFinite(parsed) ? parsed : null
}

function extractRequiredByDate(text: string): string | null {
  const iso = text.match(/\b(20\d{2}-\d{2}-\d{2})\b/)
  if (iso?.[1]) return iso[1]

  const slash = text.match(/\b(\d{2})\/(\d{2})\/(20\d{2})\b/)
  if (slash) {
    const [, day, month, year] = slash
    return `${year}-${month}-${day}`
  }
  return null
}

function extractCountry(text: string): string | null {
  const upper = text.toUpperCase()
  for (const code of ["CH", "DE", "FR", "US", "UK", "ES", "IT", "PT", "JP"]) {
    if (new RegExp(`\\b${code}\\b`).test(upper)) return code
  }
  return null
}

function inferLanguage(text: string) {
  if (/[äöüß]/i.test(text)) return "de"
  if (/[éèàç]/i.test(text)) return "fr"
  if (/\b(hola|gracias|solicitud)\b/i.test(text)) return "es"
  return "en"
}

function extractionStrength(missingRequiredCount: number, confidentFieldsCount: number) {
  if (missingRequiredCount === 0 && confidentFieldsCount >= 8) return "strong"
  if (confidentFieldsCount >= 4) return "partial"
  return "low"
}

export async function POST(request: Request) {
  const body = (await request.json()) as IntakeRequestBody
  const sourceText = (body.source_text ?? "").trim()
  const lines = sourceText
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
  const title = (lines[0] ?? "New sourcing case").slice(0, 120)

  const country = extractCountry(sourceText) ?? "CH"
  const draft = {
    title,
    requestText: sourceText,
    requestChannel: body.request_channel ?? "portal",
    requestLanguage: inferLanguage(sourceText),
    businessUnit: "General",
    country,
    site: "HQ",
    requesterId: "UNKNOWN",
    requesterRole: "Not specified",
    submittedForId: "SELF",
    categoryId: null,
    quantity: extractQuantity(sourceText),
    unitOfMeasure: "unit",
    currency: extractCurrency(sourceText) ?? "CHF",
    budgetAmount: extractBudget(sourceText),
    requiredByDate: extractRequiredByDate(sourceText) ?? plusDaysIso(14),
    deliveryCountries: [country],
    preferredSupplierMentioned: null,
    incumbentSupplier: null,
    contractTypeRequested: "one_time",
    dataResidencyConstraint: /data[- ]residency|local data/i.test(sourceText),
    esgRequirement: /\b(esg|sustainab)/i.test(sourceText),
    requesterInstruction: body.note ?? null,
    scenarioTags: ["standard"],
    status: "new",
  }

  const fieldStatus: Record<
    string,
    { status: "confident" | "inferred" | "missing" | "needs_review"; confidence: number; reason: string }
  > = {}

  const setStatus = (
    field: string,
    value: unknown,
    inferred = false,
  ) => {
    if (
      value === null ||
      value === undefined ||
      value === "" ||
      (Array.isArray(value) && value.length === 0)
    ) {
      fieldStatus[field] = {
        status: "missing",
        confidence: 0,
        reason: "Value not found in source input.",
      }
      return
    }

    fieldStatus[field] = {
      status: inferred ? "inferred" : "confident",
      confidence: inferred ? 0.65 : 0.9,
      reason: inferred ? "Derived from request content." : "Directly extracted.",
    }
  }

  setStatus("title", draft.title)
  setStatus("requestText", draft.requestText)
  setStatus("requestChannel", draft.requestChannel, !body.request_channel)
  setStatus("requestLanguage", draft.requestLanguage, true)
  setStatus("businessUnit", draft.businessUnit, true)
  setStatus("country", draft.country, true)
  setStatus("site", draft.site, true)
  setStatus("requesterId", draft.requesterId, true)
  setStatus("requesterRole", draft.requesterRole, true)
  setStatus("submittedForId", draft.submittedForId, true)
  setStatus("categoryId", draft.categoryId)
  setStatus("quantity", draft.quantity, true)
  setStatus("unitOfMeasure", draft.unitOfMeasure, true)
  setStatus("currency", draft.currency, true)
  setStatus("budgetAmount", draft.budgetAmount, true)
  setStatus("requiredByDate", draft.requiredByDate, true)
  setStatus("deliveryCountries", draft.deliveryCountries, true)
  setStatus("contractTypeRequested", draft.contractTypeRequested, true)

  const required = [
    "title",
    "requestText",
    "requestChannel",
    "requestLanguage",
    "businessUnit",
    "country",
    "site",
    "requesterId",
    "submittedForId",
    "categoryId",
    "unitOfMeasure",
    "currency",
    "requiredByDate",
    "contractTypeRequested",
  ]

  const missing_required = required.filter((field) => fieldStatus[field]?.status === "missing")

  const warnings: Array<{ code: string; severity: "high" | "medium"; message: string }> = []
  if (missing_required.includes("categoryId")) {
    warnings.push({
      code: "CATEGORY_MISSING",
      severity: "high",
      message: "Category could not be extracted. Please select it manually.",
    })
  }
  if (draft.budgetAmount === null) {
    warnings.push({
      code: "BUDGET_UNCLEAR",
      severity: "medium",
      message: "Budget amount was not confidently extracted from source text.",
    })
  }
  if (sourceText === "" && body.source_type !== "manual") {
    warnings.push({
      code: "EMPTY_SOURCE",
      severity: "high",
      message: "Input content is empty. Please provide source text or complete manually.",
    })
  }

  const confidentFieldsCount = Object.values(fieldStatus).filter((entry) =>
    entry.status === "confident" || entry.status === "inferred",
  ).length

  return NextResponse.json({
    draft,
    field_status: fieldStatus,
    missing_required,
    warnings,
    extraction_strength: extractionStrength(missing_required.length, confidentFieldsCount),
  })
}
