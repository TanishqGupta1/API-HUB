# Tanishq — Sprint Tasks

**Sprint:** Storefront UI redesign
**Spec:** `docs/superpowers/specs/2026-04-20-storefront-ui-redesign-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-04-20-storefront-ui-redesign.md`
**Load:** **no coding tasks** — PM role.

---

## Responsibilities

1. **Review all team PRs** against the spec and plan. Use `docs/code_review_all_tasks.md` standards + the plan's acceptance criteria per task. Require TDD on backend tasks.
2. **Unblock dependencies:**
   - Urvashi Tasks 1–3 land first → unlocks Sinchana 13 and Vidhi 18.
   - Urvashi Task 4 (route migration) lands → unlocks Vidhi 5/9 and Sinchana 11/19.
   - Vidhi Task 7 (TopBar + SearchContext) lands → unlocks Sinchana 11/19.
3. **Track sprint status** in this file once started. Update the checkbox per task as PRs merge.
4. **Collect OPS credentials** from Christian so VG OPS supplier can be flipped `is_active=true` in staging.
5. **Confirm follow-ups that fall outside this sprint:**
   - OPS push workflow (setProduct mutation + n8n workflow) — separate sprint.
   - Cart / quote flow — separate sprint.
   - Real lightbox modal — separate sprint.
   - Medusa integration (dropped indefinitely per earlier brainstorm).

---

## Sprint sign-off checklist

Mark when each phase ships:

- [ ] Phase 1 backend (Urvashi 1–3)
- [ ] Phase 2 route migration (Urvashi 4 + Vidhi 5)
- [ ] Phase 3 shell (Vidhi 7/9 + Sinchana 8/10)
- [ ] Phase 4 grid (Sinchana 11/12/13)
- [ ] Phase 5 PDP (Vidhi 14–18)
- [ ] Phase 6 polish (Sinchana 19/20)

## Review cadence

- Daily triage of open PRs (morning).
- Comment within 6 hours of any PR review request.
- Merge within 12 hours of green CI + no open blockers.
- Escalate blockers to Christian same day.
