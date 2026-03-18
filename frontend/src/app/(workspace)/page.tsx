import { OverviewPage } from "@/components/overview/overview-page"
import { getCaseList, getDashboardMetrics } from "@/lib/data/cases"

export default function Page() {
  return (
    <OverviewPage metrics={getDashboardMetrics()} cases={getCaseList()} />
  )
}
