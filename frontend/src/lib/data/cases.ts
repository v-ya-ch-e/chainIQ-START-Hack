import {
  caseDetails,
  caseListItems,
  dashboardMetrics,
  escalationQueue,
} from "@/lib/data/demo-fixtures"

export function getDashboardMetrics() {
  return dashboardMetrics
}

export function getCaseList() {
  return caseListItems
}

export function getCaseDetail(caseId: string) {
  return caseDetails.find((entry) => entry.id === caseId) ?? null
}

export function getEscalationQueue() {
  return escalationQueue
}

export function getAuditFeed() {
  return caseDetails
    .flatMap((entry) =>
      entry.auditTrail.timeline.map((event) => ({
        ...event,
        caseId: entry.id,
        caseTitle: entry.title,
      })),
    )
    .sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    )
}

export function getAuditOverview() {
  const totalPoliciesChecked = caseDetails.reduce(
    (sum, entry) => sum + entry.auditTrail.policiesChecked.length,
    0
  )
  const totalSuppliersEvaluated = caseDetails.reduce(
    (sum, entry) => sum + entry.auditTrail.supplierIdsEvaluated.length,
    0
  )

  return {
    cases: caseDetails,
    summary: [
      {
        label: "Cases With Audit Trace",
        value: caseDetails.length.toString(),
        helper: "Detailed decision packets available in the demo",
      },
      {
        label: "Policies Checked",
        value: totalPoliciesChecked.toString(),
        helper: "Total explicit rule references shown across detailed cases",
      },
      {
        label: "Suppliers Evaluated",
        value: totalSuppliersEvaluated.toString(),
        helper: "Supplier rows included in reasoning and comparison evidence",
      },
      {
        label: "Historical Consults",
        value: caseDetails.filter((entry) => entry.auditTrail.historicalAwardsConsulted).length.toString(),
        helper: "Cases enriched with precedent context",
      },
    ],
  }
}
