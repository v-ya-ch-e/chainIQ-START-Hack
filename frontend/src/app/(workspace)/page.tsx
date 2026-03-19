import { OverviewPage } from "@/components/overview/overview-page"
import { getCaseList, getDashboardMetrics } from "@/lib/data/cases"

export default async function Page() {
  const [metrics, cases] = await Promise.all([
    getDashboardMetrics(),
    getCaseList(),
  ])

  return (
    <OverviewPage metrics={metrics} cases={cases} />
  )
}
