import { anthropic } from "@ai-sdk/anthropic"
import { streamText } from "ai"

export const maxDuration = 60

export async function POST(req: Request) {
  const { messages, formState } = await req.json()

  const systemPrompt = `You are an AI intake assistant for a procurement system. 
Your primary goal is to help the user complete their purchase request by asking questions for missing REQUIRED fields.

Here is the current state of the extracted request fields (some may be empty strings or null):
${JSON.stringify(formState, null, 2)}

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

  const result = streamText({
    model: anthropic("claude-3-7-sonnet-20250219"),
    messages,
    system: systemPrompt,
  })

  return result.toTextStreamResponse()
}
