import { createAnthropic } from "@ai-sdk/anthropic"
import { streamText, type ModelMessage } from "ai"
import { NextResponse } from "next/server"

export const maxDuration = 60

const DEFAULT_ANTHROPIC_MODEL = "claude-3-7-sonnet-20250219"

type IntakeChatRequestBody = {
  messages: ModelMessage[]
  formState?: Record<string, unknown>
}

function badRequest(message: string, detail: string) {
  return NextResponse.json(
    {
      code: "INVALID_REQUEST",
      message,
      detail,
    },
    { status: 400 },
  )
}

function upstreamError(error: unknown, detailOverride?: string) {
  const detail =
    detailOverride ??
    (error instanceof Error && error.message.trim().length > 0
      ? error.message
      : "Unknown Anthropic provider error.")

  return NextResponse.json(
    {
      code: "ANTHROPIC_UPSTREAM_ERROR",
      message: "Failed to generate intake chat response via Anthropic.",
      detail,
      retryable: true,
    },
    { status: 502 },
  )
}

function parseRequestBody(payload: unknown): IntakeChatRequestBody | null {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return null
  }

  const body = payload as Record<string, unknown>
  const messages = body.messages
  const formState = body.formState

  if (!Array.isArray(messages) || messages.length === 0) {
    return null
  }

  const messagesValid = messages.every((message) => {
    if (!message || typeof message !== "object" || Array.isArray(message)) {
      return false
    }
    const candidate = message as Record<string, unknown>
    return (
      (candidate.role === "system" ||
        candidate.role === "user" ||
        candidate.role === "assistant" ||
        candidate.role === "tool") &&
      "content" in candidate
    )
  })

  if (!messagesValid) {
    return null
  }

  if (
    formState !== undefined &&
    (formState === null || typeof formState !== "object" || Array.isArray(formState))
  ) {
    return null
  }

  return {
    messages: messages as ModelMessage[],
    formState: (formState as Record<string, unknown> | undefined) ?? {},
  }
}

export async function POST(req: Request) {
  let rawPayload: unknown
  try {
    rawPayload = await req.json()
  } catch {
    return badRequest("Malformed JSON request body.", "Request body must be valid JSON.")
  }

  const parsed = parseRequestBody(rawPayload)
  if (!parsed) {
    return badRequest(
      "Invalid request payload.",
      "Expected payload with non-empty 'messages' array and optional object 'formState'.",
    )
  }

  const anthropicApiKey = (process.env.ANTHROPIC_API_KEY ?? "").trim()
  if (!anthropicApiKey) {
    return NextResponse.json(
      {
        code: "ANTHROPIC_NOT_CONFIGURED",
        message: "Anthropic API key is not configured for intake chat.",
        hint: "Set ANTHROPIC_API_KEY in frontend runtime environment.",
      },
      { status: 503 },
    )
  }

  const anthropicModel =
    (process.env.ANTHROPIC_MODEL ?? "").trim() || DEFAULT_ANTHROPIC_MODEL
  const anthropicProvider = createAnthropic({ apiKey: anthropicApiKey })

  const systemPrompt = `You are an AI intake assistant for a procurement system. 
Your primary goal is to help the user complete their purchase request by asking questions for missing REQUIRED fields.

Here is the current state of the extracted request fields (some may be empty strings or null):
${JSON.stringify(parsed.formState ?? {}, null, 2)}

Review the state. If key fields like 'budget_amount', 'quantity', 'required_by_date', 'business_unit', or 'country' are missing or unclear, ask the user to clarify them. 
You should be helpful and conversational. Do not overwhelm the user with all missing fields at once; ask 1-2 logical questions at a time.

CRITICAL REQUIREMENT:
Whenever you gather new information that updates the request, you MUST include a JSON block in your response containing the updated fields.
The JSON must be wrapped in \`\`\`json and \`\`\` tags.
The JSON should be a flat object containing ONLY the keys you want to update from the RequestFormState that exist in the provided state schema.

For example:
"Got it, I'll update the budget and quantity."
\`\`\`json
{
  "budget_amount": "50000",
  "quantity": "50"
}
\`\`\`
`

  try {
    const result = streamText({
      model: anthropicProvider(anthropicModel),
      messages: parsed.messages,
      system: systemPrompt,
    })

    const streamIterator = result.textStream[Symbol.asyncIterator]()
    let firstChunk: string | null = null

    try {
      const firstResult = await streamIterator.next()
      if (firstResult.done) {
        return upstreamError(
          null,
          "Anthropic returned an empty response stream before any text chunk.",
        )
      }
      firstChunk = firstResult.value
    } catch (error) {
      return upstreamError(error)
    }

    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      async pull(controller) {
        try {
          if (firstChunk !== null) {
            controller.enqueue(encoder.encode(firstChunk))
            firstChunk = null
            return
          }

          const nextResult = await streamIterator.next()
          if (nextResult.done) {
            controller.close()
            return
          }
          controller.enqueue(encoder.encode(nextResult.value))
        } catch (error) {
          controller.error(error)
        }
      },
    })

    return new Response(stream, {
      status: 200,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
      },
    })
  } catch (error) {
    return upstreamError(error)
  }
}
