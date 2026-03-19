import { notFound } from "next/navigation"

import { CaseWorkspace } from "@/components/case-detail/case-workspace"
import { getCaseDetail } from "@/lib/data/cases"

export default async function Page({
  params,
}: {
  params: Promise<{ caseId: string }>
}) {
  const { caseId } = await params
  const data = await getCaseDetail(caseId)

  if (!data) {
    notFound()
  }

  return <CaseWorkspace data={data} />
}
