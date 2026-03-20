import { notFound } from "next/navigation"

import { CaseWorkspace } from "@/components/case-detail/case-workspace"
import { getCaseDetailByRunId } from "@/lib/data/cases"

export default async function Page({
  params,
}: {
  params: Promise<{ runId: string }>
}) {
  const { runId } = await params
  const result = await getCaseDetailByRunId(runId)

  if (!result) {
    notFound()
  }

  const { caseDetail } = result

  return (
    <CaseWorkspace
      key={`eval-${runId}`}
      data={caseDetail}
      initialTab="audit"
      initialRunId={runId}
      showReturnToLatest
    />
  )
}
