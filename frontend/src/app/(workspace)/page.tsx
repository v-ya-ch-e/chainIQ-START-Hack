import { OverviewPage } from "@/components/overview/overview-page"
import { getDashboardPageData } from "@/lib/data/cases"

export const dynamic = "force-dynamic"

export default async function Page() {
  const { metrics, cases, dataState, insights } = await getDashboardPageData()

  return (
    <OverviewPage
      metrics={metrics}
      cases={cases}
      dataState={dataState}
      insights={insights}
    />
  )
}
