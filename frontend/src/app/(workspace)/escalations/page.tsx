import { EscalationsPage } from "@/components/escalations/escalations-page"
import { getEscalationQueue } from "@/lib/data/cases"

export default function Page() {
  return <EscalationsPage items={getEscalationQueue()} />
}
