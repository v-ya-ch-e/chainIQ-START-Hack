import { AuditPage } from "@/components/audit/audit-page"
import { getAuditPageData } from "@/lib/data/cases"

export default async function Page() {
  const data = await getAuditPageData()

  return <AuditPage summary={data.summary} feed={data.feed} feedMeta={data.feedMeta} />
}
