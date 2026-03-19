import { AuditPage } from "@/components/audit/audit-page"
import { getAuditFeed, getAuditOverview } from "@/lib/data/cases"

export default async function Page() {
  const [data, feed] = await Promise.all([getAuditOverview(), getAuditFeed()])

  return <AuditPage summary={data.summary} feed={feed} />
}
