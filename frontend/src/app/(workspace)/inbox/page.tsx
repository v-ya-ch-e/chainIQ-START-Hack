import { InboxPage } from "@/components/inbox/inbox-page"
import { getCaseListPage } from "@/lib/data/cases"
import type { CaseListItem } from "@/lib/types/case"

const DEFAULT_PAGE_SIZE = 25

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export default async function Page({ searchParams }: PageProps) {
  const params = await searchParams
  const rawPage = Number(params.page) || 1
  const page = Math.max(1, rawPage)
  const pageSize = Math.min(
    100,
    Math.max(10, Number(params.pageSize) || DEFAULT_PAGE_SIZE),
  )
  const statusParam =
    typeof params.status === "string" && params.status !== "all"
      ? params.status
      : undefined

  let cases: CaseListItem[] = []
  let total = 0
  let dataLoadError: string | null = null

  try {
    const result = await getCaseListPage({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      status: statusParam,
    })
    cases = result.items
    total = result.total
  } catch (err) {
    dataLoadError =
      err instanceof Error ? err.message : "Failed to load inbox data."
  }

  return (
    <InboxPage
      cases={cases}
      total={total}
      page={page}
      pageSize={pageSize}
      statusParam={statusParam ?? "all"}
      dataLoadError={dataLoadError}
    />
  )
}
