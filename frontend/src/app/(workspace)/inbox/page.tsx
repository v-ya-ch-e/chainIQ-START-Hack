import { InboxPage } from "@/components/inbox/inbox-page"
import { getCaseList } from "@/lib/data/cases"

export default function Page() {
  return <InboxPage cases={getCaseList()} />
}
