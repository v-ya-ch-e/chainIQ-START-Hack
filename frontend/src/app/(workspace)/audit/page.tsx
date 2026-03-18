import { AuditPage } from "@/components/audit/audit-page"
import { getAuditFeed, getAuditOverview } from "@/lib/data/cases"

export default function Page() {
  const data = getAuditOverview()
  const feed = getAuditFeed()

  return <AuditPage summary={data.summary} feed={feed} />
}
