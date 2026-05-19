# Timesheet — 2026-05-19

**Developer:** Vidhi
**Branch:** `Vidhi`
**Status:** Uncommitted (local fixes, ready for review)

---

## Tasks Completed

### Task 1: Fix Login — Admin Password Reset + Remember Me

**Problem:** Admin could not log in. The password was auto-generated on first startup and was unknown. Also, users had to log in every session with no way to stay signed in.

**Fix:**
- Reset admin password directly in the DB using a bcrypt hash of `admin123`
- Added `remember_me: bool` field to `LoginRequest` schema
- Added `REMEMBER_TOKEN_EXPIRE_MINUTES = 1080` (18 hours) to security config
- Updated login route to use 18-hour expiry when `remember_me=true`
- Added "Keep me signed in for 18 hours" checkbox to the login page (checked by default)

**Files changed:** `backend/modules/auth/schemas.py`, `backend/modules/auth/security.py`, `backend/modules/auth/routes.py`, `frontend/src/app/(auth)/login/page.tsx`

**Status:** ✅ Done

---

### Task 2: Fix Master Options Catalog Page — 405 Error on Sync

**Problem:** `POST /api/master-options/sync` was returning **405 Method Not Allowed**. The route had been removed in a previous session. FastAPI was matching the word "sync" as a UUID path parameter for `GET /{master_option_id}`, which failed.

**Fix:**
- Added back `POST /api/master-options/sync` route — placed before the `GET /{master_option_id}` route to avoid routing conflict
- Route finds the first active customer with OPS credentials, calls OPS GraphQL `getMasterOptions`, upserts results into DB
- Added proper error handling: if OPS is unreachable (e.g. placeholder URL), returns 502 with a readable message instead of crashing with 500
- Changed `log.error()` → `log.warn()` in the frontend catch block to stop Next.js dev overlay from triggering on expected sync failures

**Files changed:** `backend/modules/master_options/routes.py`, `frontend/src/app/(admin)/products/configure/page.tsx`

**Status:** ✅ Done

---

### Task 3: Fix Demo Push URL — UUID Validation Error

**Problem:** Navigating to `/products/demo/push?customer_id=demo` showed a "Preflight blocked" error with raw UUID parsing errors from Pydantic. The URL uses `"demo"` as placeholder IDs, but with `NEXT_PUBLIC_PHASE8_LIVE=true`, the hook was calling the real backend which rejected `"demo"` as an invalid UUID.

**Fix:** In `use-push-preview.ts`, added a UUID check before making any API call. If either `customerId` or `productId` is not a valid UUID, the hook falls back to fixture/mock data regardless of the live mode env var. Real product pages with actual UUIDs continue to call the live backend normally.

**Files changed:** `frontend/src/lib/use-push-preview.ts`

**Status:** ✅ Done

---

### Task 4: Fix Publish Button — Raw JSON Error Shown on Product Page

**Problem:** Clicking "Publish to OPS" on a product page was showing raw JSON preflight error output directly on the product detail page — ugly and unreadable.

**Root cause:** `PublishButton` was calling the push API directly and displaying `err.message`, which is `JSON.stringify()` of the full preflight envelope when a 422 is returned.

**Fix:** Changed `PublishButton` to navigate to `/products/[id]/push?customer_id=xxx` instead of calling the API directly. The dedicated push page already has proper preflight error rendering.

**Files changed:** `frontend/src/components/products/publish-button.tsx`

**Status:** ✅ Done

---

### Task 5: Fix Push Page — Preflight Error Showed Blank Page

**Problem:** When preflight fails, the push page was returning a bare `ErrorCard` component with no header, no back button, no context — just a red box floating on a blank page.

**Fix:**
- Removed the early return that replaced the whole page with `ErrorCard`
- Inline the error into the full page layout — header + back link always show
- Hid `PreviewPanel` and `DryRunControls` when there is a preflight error (nothing to show)

**Files changed:** `frontend/src/app/(admin)/products/[id]/push/page.tsx`

**Status:** ✅ Done

---

### Task 6: Fix Publish Button — Wrong Customer Selected

**Problem:** "Publish to OPS" was defaulting to the first active customer in the DB — which was a test fixture customer ("Test Customer") with no markup rules. "Visual Graphics" was selected in the top bar but ignored.

**Fix:** Updated `PublishButton` to use `useSelectedCustomer()` context (the globally selected customer shown in the top bar) as the default. Falls back to first active if nothing is selected globally.

**Files changed:** `frontend/src/components/products/publish-button.tsx`

**Status:** ✅ Done

---

### Task 7: Seed Product Images for Demo Products

**Problem:** PC450 and ST350 products had 0 images in the database. Preflight check 5 (`image_urls_reachable`) was blocking the push with "no images attached to product".

**Fix:** Inserted real SanMar CDN front image URLs directly into the `product_images` table for both products so the demo push flow can proceed past the images check.

**Status:** ✅ Done (dev data only)

---

## Summary

| Item | Detail |
|------|--------|
| Tasks completed | 7 |
| Bugs fixed | 5 |
| Files modified | 7 |
| Backend tests | Not re-run today |
| Commits | 0 (all local, uncommitted) |
| End state | PC450 × Visual Graphics push page loads, preflight passes, SEND DRY-RUN button visible |
