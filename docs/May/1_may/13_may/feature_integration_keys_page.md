# Feature — Integration Keys Admin Page

**Owner:** Vidhi
**Status:** Done
**Date:** 2026-05-13
**Files:** `frontend/src/app/(admin)/integrations/page.tsx`, `frontend/src/components/SidebarNav.tsx`

---

## What is this?

A new admin page at `/integrations` for managing `X-Orchestrator-Key` API credentials. Operators use this page to create, inspect, and revoke API keys for external orchestrators (n8n, cron jobs, Lambda functions, etc.) that push products to OPS storefronts.

---

## Why is it important?

The Integration Gateway requires every external caller to authenticate with an `X-Orchestrator-Key` header. Before this page existed, there was no way to create or revoke these keys through the UI — they could only be managed via raw curl calls to the admin API.

Without this page:
- No operator could set up n8n to use the gateway without developer help
- A leaked key could not be revoked quickly in an emergency
- There was no visibility into which keys exist, what they're scoped to, or when they were last used

This page makes key management self-service for operators and is a prerequisite for any real orchestrator push to work.

---

## What was built

### Key list

Displays all integration keys with:
- Name and key ID (with copy button)
- Active (green) or Revoked (red) status badge
- Created date and last used date
- Scope badges — which suppliers and customers the key is allowed to access
- Rate limit (requests per minute)

### Create modal

Clicking "Create Key" opens a modal with fields for:
- **Key ID** — human-readable slug (e.g. `n8n-vidhi-staging`). Must be unique.
- **Display Name** — friendly label shown in the list
- **Rate Limit** — max requests per minute (default 60)
- **Allowed Customer IDs** — comma-separated UUIDs. Leave blank = all customers allowed
- **Allowed Supplier Slugs** — comma-separated slugs. Leave blank = all suppliers allowed

### One-time raw key banner

After creating a key, a yellow warning banner appears showing the raw key value with a copy button. The banner makes clear this is the **only time the key is shown** — the backend stores only a SHA-256 hash, never the raw value. Closing the banner removes it permanently.

### Revoke

Active keys have a red "Revoke" button. Clicking it shows a browser confirm dialog, then calls `POST /api/integrations/keys/{id}/revoke`. The key card immediately goes grey and the Revoked badge appears. Revoked keys cannot be reactivated — a new key must be created.

### Sidebar nav

Added **Integration Keys** entry under the Actions section in the sidebar, between Push Log and API Registry.

---

## API endpoints used

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/integrations/keys` | Load all keys on page mount |
| `POST` | `/api/integrations/keys` | Create a new key |
| `POST` | `/api/integrations/keys/{id}/revoke` | Revoke a key |

All three require a valid `vg_admin` session cookie — same auth as the rest of the admin UI.

---

## Security notes

- The raw key is generated server-side with `secrets.token_urlsafe(32)` — never predictable
- Only the SHA-256 hash is stored in the database — even a full DB dump does not expose keys
- The raw key is returned exactly once in the `POST /keys` response and shown once in the UI banner
- Revoking is immediate — the next request with that key returns `403 KEY_REVOKED`
