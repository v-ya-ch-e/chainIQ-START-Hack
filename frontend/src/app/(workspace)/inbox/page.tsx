import { InboxPage } from "@/components/inbox/inbox-page"
import { getCaseList } from "@/lib/data/cases"

export default async function Page() {
  const cases = await getCaseList()
  return <InboxPage cases={cases} />
}
