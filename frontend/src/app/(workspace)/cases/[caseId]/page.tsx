import { notFound } from "next/navigation"

import { CaseWorkspace } from "@/components/case-detail/case-workspace"
import { getCaseDetail } from "@/lib/data/cases"

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ caseId: string }>
  searchParams: Promise<{ tab?: string; created?: string }>
}) {
  const { caseId } = await params
  const { tab, created } = await searchParams
  const data = await getCaseDetail(caseId)

  if (!data) {
    notFound()
  }

  const initialTab =
    tab === "overview" || tab === "suppliers" || tab === "escalations" || tab === "audit"
      ? tab
      : undefined

  return (
    <CaseWorkspace
      key={`${data.id}-${initialTab ?? "overview"}`}
      data={data}
      initialTab={initialTab}
      createdFromIntake={created === "1"}
    />
  )
}
