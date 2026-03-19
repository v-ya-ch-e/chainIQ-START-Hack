import { EscalationsPage } from "@/components/escalations/escalations-page"
import { getEscalationQueue } from "@/lib/data/cases"

export default async function Page() {
  const items = await getEscalationQueue()
  return <EscalationsPage items={items} />
}
