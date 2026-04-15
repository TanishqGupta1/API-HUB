# Task 9 — Next.js Scaffold + Blueprint Layout — Code Review

**PR:** #2 (Sinchana) | **Reviewed:** 2026-04-15 | **Verdict:** Mostly Done — 2 issues to fix before Phase 4

---

## What Was Required (from V0 plan)

1. Next.js scaffold with TypeScript, Tailwind, ESLint, App Router, src directory
2. shadcn/ui components: button, card, input, table, badge, separator, scroll-area
3. globals.css with Blueprint design tokens (Outfit + Fira Code fonts, paper #f2f0ed, blueprint blue #1e4d92, dot-grid)
4. layout.tsx with sidebar (10 nav items)
5. API client at src/lib/api.ts
6. TypeScript types at src/lib/types.ts
7. Dashboard page at src/app/page.tsx (stats cards + recent sync table)

---

## Verification Results

### 1. Next.js Scaffold — PASS

- Next.js v15.2.4 with TypeScript strict mode
- Tailwind CSS v3.4.17 configured
- ESLint with next/core-web-vitals
- App Router (`src/app/`) structure
- `src/` directory with `app/`, `components/`, `lib/`

### 2. shadcn/ui Components — FAIL

**No shadcn/ui components are installed.** The spec requires:

```bash
npx shadcn@latest init -d
npx shadcn@latest add button card input table badge separator scroll-area
```

**What's missing:**
- No `@radix-ui/*` packages in package.json
- No `components/ui/` directory
- UI elements are implemented with raw CSS classes instead

**Why this matters:** All 7 frontend pages (Tasks 10-16) expect shadcn components to be available. Without them, every page developer will need to either install shadcn first or build UI from scratch.

**Fix:** Run the two commands above in the `frontend/` directory.

### 3. globals.css — PASS

All Blueprint design tokens present:
- `--paper: #f2f0ed`
- `--blue: #1e4d92` (mapped as `--blueprint` equivalent)
- Outfit font imported (weights 400, 600, 700, 800)
- Fira Code imported (weights 400, 500, 600)
- Dot-grid background via linear gradients at 32px spacing
- Full color palette: ink variants, blueprint variants, success/error/warning

### 4. layout.tsx + Sidebar — PASS

Blueprint layout with all 10 navigation items:

| # | Label | Route | Section |
|---|-------|-------|---------|
| 1 | Dashboard | `/` | Orchestration |
| 2 | Suppliers | `/suppliers` | Orchestration |
| 3 | Catalog | `/products` | Orchestration |
| 4 | Customers | `/customers` | Management |
| 5 | Markup Rules | `/markup` | Management |
| 6 | Workflows | `/workflows` | Management |
| 7 | Sync Jobs | `/sync` | Management |
| 8 | Field Mapping | `/mappings` | Management |
| 9 | API Registry | `/api-registry` | Actions |
| 10 | Add Supplier | `/suppliers/new` | Actions |

Additional: brand header "API-HUB", version "Blueprint v0.3", engine status indicator, dashed borders on sections.

### 5. API Client (api.ts) — PASS

- Generic `api<T>()` fetch wrapper
- Base URL from `NEXT_PUBLIC_API_URL` env var, falls back to `http://localhost:8000`
- Proper error handling (checks `res.ok`, throws descriptive error)
- Auto-sets `Content-Type: application/json`
- Supports `RequestInit` options merging

### 6. TypeScript Types (types.ts) — PASS

Complete type definitions matching backend schemas:
- `Supplier`, `SupplierCreate`
- `PSCompany`, `PSEndpoint`
- `Product`, `ProductListItem`, `Variant`
- `Customer`
- `SyncJob` (with status and job_type union types)
- `Stats` (suppliers, products, variants, customers)
- `FieldMapping`

### 7. Dashboard Page (page.tsx) — PARTIAL PASS

**Layout and UI: Correct.**
- 4 stat cards (Vendors, SKUs Indexed, Total Variants, System Health)
- Recent Pipeline Activity table with 4 sample rows
- Status badges (Complete, Auth_Error)
- Proper Blueprint styling

**API integration: Missing.**
- Page uses hardcoded sample data, not real API calls
- Does not call `api<Stats>("/api/stats")` from `lib/api.ts`
- Does not use types from `lib/types.ts`

**Fix:** Replace hardcoded stats with a `useEffect` + `api<Stats>("/api/stats")` call. The sample table data can stay as placeholder until sync jobs are running.

### 8. tailwind.config.ts — PASS

Full Blueprint theme extension:
- Font families: Outfit (sans), Fira Code (mono)
- Colors: paper, vellum, ink variants, blueprint variants, success/error/warning

### 9. package.json Dependencies — PARTIAL PASS

Present: next, react, react-dom, @fontsource/outfit, @fontsource/fira-code, class-variance-authority, clsx, lucide-react, tailwind-merge

Missing: All shadcn/ui packages (@radix-ui/*)

---

## Summary

| Requirement | Status |
|-------------|--------|
| Next.js scaffold (TS, Tailwind, ESLint, App Router) | PASS |
| shadcn/ui components installed | **FAIL** |
| globals.css Blueprint design tokens | PASS |
| layout.tsx with 10-item sidebar | PASS |
| api.ts fetch wrapper | PASS |
| types.ts TypeScript types | PASS |
| page.tsx dashboard | PARTIAL — UI correct, API not wired |
| tailwind.config.ts Blueprint theme | PASS |

---

## Action Items

### Must Fix Before Phase 4

| # | Issue | Owner | Fix |
|---|-------|-------|-----|
| 1 | **shadcn/ui not installed** | Sinchana | Run `npx shadcn@latest init -d && npx shadcn@latest add button card input table badge separator scroll-area` in `frontend/` |

### Nice to Fix

| # | Issue | Owner | Fix |
|---|-------|-------|-----|
| 2 | Dashboard uses hardcoded data | Sinchana | Replace stats with `useEffect` + `api<Stats>("/api/stats")` call |
| 3 | `Sidebar.tsx` component exists but layout.tsx implements sidebar inline | — | Low priority — works either way |
