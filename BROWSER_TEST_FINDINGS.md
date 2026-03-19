# Browser Test Findings — 19 Mar 2026

Systematic browser testing across all four pages (Overview, Inbox, Escalations, Audit) at desktop (1440px), tablet (768px), and mobile (375px) viewports.

---

## Frontend Issues (Fixed)

### 1. Win Rate Display: 10000.0% (FIXED)

**Location:** `frontend/src/lib/data/cases.ts` line 773

**Root cause:** The backend `GET /api/analytics/supplier-win-rates` returns `win_rate` as a percentage (0–100) via `round(wins / total * 100, 2)` in `backend/organisational_layer/app/routers/analytics.py:731`. The frontend then multiplied by 100 again: `(Number(topWinRate.win_rate) * 100).toFixed(1)%`, producing `100.0 * 100 = 10000.0%`.

**Fix:** Removed the `* 100` multiplication. Now displays correctly as `100.0%`.

### 2. React Hydration Error #418 (FIXED)

**Affected pages:** Audit, Escalations

**Root cause:** `Intl.DateTimeFormat` with locale `en-GB` and `timeZone: "UTC"` can produce subtly different text between Node.js server and browser client due to ICU data differences. Timestamp text rendered by `formatDateTime()` mismatched between SSR and hydration.

**Fix:** Added `suppressHydrationWarning` to all elements rendering `formatDateTime()` output on Audit and Escalations pages. This matches the pattern already used on the Overview page.

### 3. `useIsMobile` Hydration Mismatch (FIXED)

**Location:** `frontend/src/hooks/use-mobile.ts`

**Root cause:** `useState<boolean | undefined>(undefined)` produced `!!undefined = false` during SSR. On mobile viewports, after the `useEffect` fired, `isMobile` switched to `true`, causing the `Sidebar` component to swap from a `div` to a `Sheet` — a structural DOM change that React flagged as a hydration error.

**Fix:** Changed initial state from `undefined` to `false` explicitly, and return `isMobile` directly instead of `!!isMobile`. Both server and client now start with `false`, and the `useEffect` updates to the real value post-hydration. CSS `hidden md:block` handles the visual hiding on mobile during the brief pre-effect window.

### 4. Audit Page Tab Switching Bug (FIXED)

**Symptom:** Clicking "Full Log" tab briefly activates then snaps back to "Actionable."

**Root cause:** Consequence of React hydration error #418 — React tore down and rebuilt the component tree, resetting `defaultValue="actionable"` on the `Tabs` component.

**Fix:** Resolved by fixing the underlying hydration errors (items 2 and 3 above).

---

## Frontend Data-Fetching Issues (Fixed)

### 7. Audit Feed Pagination (FIXED)

**Location:** `frontend/src/lib/data/cases.ts`

**Root cause:** Frontend hardcoded `AUDIT_FEED_LIMIT = 500` and made a single API call. Backend supports `skip`/`limit` pagination.

**Fix:** Added `fetchAllAuditPages()` that paginates through all pages. Feed now shows all entries (849 vs 500 previously).

### 8. Audit By Request Deduplication (FIXED)

**Location:** `frontend/src/components/audit/audit-page.tsx`, `frontend/src/lib/data/cases.ts`

**Root cause:** Re-running the pipeline creates new audit entries, but the "By Request" tab showed ALL entries from ALL runs.

**Fix:** "By Request" tab now filters to the latest `run_id` per request. Added run filter dropdown to let users trace any specific run.

### 9. LCP Logo Image Warning (FIXED)

**Location:** `frontend/src/components/app-shell/workspace-shell.tsx`

**Root cause:** The sidebar logo `/chainiq_logo.svg` was detected as LCP but lacked `priority` prop, causing a performance warning on every page.

**Fix:** Added `priority` prop to both logo `Image` components (expanded and icon-only sidebar states).

### 10. Date Timezone Parsing Bug (FIXED)

**Location:** `frontend/src/lib/data/formatters.ts`

**Root cause:** MySQL `DATETIME` fields come without timezone suffix (e.g., `"2026-03-14T17:55:00"`). JavaScript `new Date()` parses these as local time, but `Intl.DateTimeFormat` formats with `timeZone: "UTC"`. Server (UTC Docker) and client (user's timezone) show different times for the same date.

**Fix:** Added `parseAsUtc()` helper that appends "Z" to timezone-less date strings. Updated `formatDate`, `formatDateTime`, and `formatDateDdMmYyyy` to use it. Also fixed `formatDateDdMmYyyy` to use `getUTCDate/Month/FullYear` instead of local timezone methods.

---

## Responsive Design Issues (Not Yet Fixed — Low Priority)

### R1. Mobile Sidebar Doesn't Collapse

**Viewport:** 375×812px

**Observation:** The sidebar's CSS `hidden md:block` hides the desktop sidebar div on mobile, but the sidebar gap div and the overall layout still reserve space. After `useIsMobile` effect fires, the sidebar switches to Sheet mode. The transition is correct but there's a brief flash of layout shift.

**Impact:** Minor — the CSS handles the visual correctly; the layout shift is sub-100ms.

### R2. Table Overflow on Mobile (Inbox, Escalations)

**Viewport:** 375×812px

**Observation:** The Inbox and Escalations pages use `<Table>` components with many columns. On mobile, the tables overflow horizontally. The wrapper has `overflow-x-auto` so horizontal scrolling works, but there's no visual indicator (scroll hint).

**Recommendation:** Consider a card-based layout for mobile, or add a scroll shadow/indicator.

---

## Console Errors Summary


| Page        | Error                                      | Status    |
| ----------- | ------------------------------------------ | --------- |
| Audit       | React Error #418 (hydration text mismatch) | **Fixed** |
| Escalations | React Error #418 (hydration text mismatch) | **Fixed** |
| Overview    | None                                       | Clean     |
| Inbox       | None                                       | Clean     |


---

## What Works Well

- All CRUD workflows functional (navigate, filter, search, case detail, re-run pipeline)
- Data consistency between Overview metrics and Inbox/Escalation counts
- Audit trail grouped by request with expandable accordions
- Escalation review modal with full context (rule, audit, pipeline status)
- Case detail view with 4 tabs (Overview, Suppliers, Escalations, Audit Trace)
- Re-run pipeline button with proper loading state
- Search functionality across all pages
- Desktop layout is clean and well-organized

