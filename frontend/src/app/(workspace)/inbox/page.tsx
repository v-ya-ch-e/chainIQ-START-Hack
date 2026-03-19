import { InboxPage } from "@/components/inbox/inbox-page"
import { getCaseList } from "@/lib/data/cases"

export default async function Page() {
  let cases: Awaited<ReturnType<typeof getCaseList>> = []
  let dataLoadError: string | null = null
  try {
    cases = await getCaseList()
  } catch (err) {
    dataLoadError =
      err instanceof Error ? err.message : "Failed to load inbox data."
  }
  return <InboxPage cases={cases} dataLoadError={dataLoadError} />
}
