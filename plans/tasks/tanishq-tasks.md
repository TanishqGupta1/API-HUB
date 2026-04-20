# Tanishq — Sprint Tasks

**Sprint:** Storefront UI redesign
**Spec:** `docs/superpowers/specs/2026-04-20-storefront-ui-redesign-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-20-storefront-ui-redesign.md`
**Role:** PM / reviewer — no coding tasks.

---

## Overview

All 20 implementation tasks run in parallel across Sinchana, Vidhi, and Urvashi. Each person owns a disjoint set of files (see their task files). No serial dependencies — if an import is missing, the author stubs it locally and removes the stub after the dependency lands.

Your job is to keep this parallelism running smoothly.

## Responsibilities

1. **Review every incoming PR** against the spec and the corresponding Plan Task. Acceptance criteria live in each person's task file.
2. **Enforce file ownership.** If a PR from Person A touches a file that Person B owns, flag it and request revision. Prevents merge conflicts before they happen.
3. **Enforce stub policy.** PRs may ship with local stubs for unmerged dependencies — that's allowed. Require the PR author to delete the stub and swap to the real import in a follow-up commit once the dependency lands on `main`.
4. **Collect OPS credentials** from Christian so VG OPS supplier can be flipped `is_active=true` in staging.
5. **Track sprint** via the checklist below.
6. **Scope keeper.** Everything in "Out of scope" in the spec stays out. Push back on scope creep.

## Sprint sign-off checklist

Track merges here:

- [ ] Urvashi 1 — schema fields (`ProductListRead` + `ProductRead`)
- [ ] Urvashi 2 — aggregate query in `list_products`
- [ ] Urvashi 3 — route group migration (admin pages into `(admin)/`)
- [ ] Vidhi 5 — storefront layout skeleton
- [ ] Vidhi 7 — TopBar + SearchContext
- [ ] Vidhi 9 — StorefrontShell real composition
- [ ] Vidhi 14 — PDPLayout
- [ ] Vidhi 15 — ImageGallery keyboard nav
- [ ] Vidhi 16 — DescriptionHtml
- [ ] Vidhi 17 — RelatedProducts
- [ ] Vidhi 18 — PDP page rewrite
- [ ] Sinchana 8 — LeftRail
- [ ] Sinchana 10 — MobileFilterSheet
- [ ] Sinchana 11 — `/storefront/vg/page.tsx` rewrite
- [ ] Sinchana 12 — FilterChipBar
- [ ] Sinchana 13 — ProductCard upgrades + `types.ts`
- [ ] Sinchana 19 — category page rewrite
- [ ] Sinchana 20 — dead code + Lighthouse + .gitignore
- [ ] Sinchana 8 (housekeeping) — inline style sweep

## Out of sprint scope

- OPS push workflow (setProduct mutation + n8n workflow) — separate sprint.
- Cart / quote flow — separate sprint.
- Real lightbox modal — separate sprint.
- Medusa integration — dropped indefinitely (per earlier brainstorm).

## Review cadence

- Triage open PRs every morning.
- First-pass review within 6 hours of review-request.
- Merge within 12 hours of green CI + no open blockers.
- Escalate to Christian same day on creds / API shape blockers.
