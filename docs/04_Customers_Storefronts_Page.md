# Task 0.4 — Customers (Storefronts) Page

**Completed by:** Vidhi
**Branch:** `Vidhi`
**Date:** 2026-04-17
**Status:** ✅ Done — tested and committed

---

## In Simple Words (For Everyone)

This page is where you manage your OnPrintShop storefronts. A "storefront" is a live online store powered by OnPrintShop — like "Acme Corp Store" at `acme.onprintshop.com`. 

Before products can be published to any store, the store must first be added here with its connection credentials. Think of it like adding a phone contact before you can call someone.

---

## What the Page Shows

A table of all connected storefronts with:

| Column | What it shows |
|--------|--------------|
| Store Name | The name you gave the storefront (e.g. "Acme Corp Store") |
| OPS URL | The storefront's web address — shown as just the hostname (e.g. `acme.onprintshop.com`) |
| Status | Active (green dot) or Inactive (gray) |
| Products Pushed | How many products have been published to this store |
| Actions | Deactivate / Activate toggle + Delete button |

---

## The Add Storefront Form

Clicking **"+ Add Storefront"** opens an inline form with 5 fields:

| Field | What it is |
|-------|-----------|
| Store Name | A label for you to identify this store |
| OPS GraphQL URL | The API address for this OPS instance (e.g. `https://acme.onprintshop.com/graphql`) |
| OAuth Token URL | Where the system fetches an access token (e.g. `https://acme.onprintshop.com/oauth/token`) |
| Client ID | OAuth2 client identifier — not secret |
| Client Secret | OAuth2 secret — **write-only**, never shown back after saving |

Help text on the form: *"You can find these credentials in your OnPrintShop admin panel under Settings > API."*

### Why is Client Secret write-only?

Once saved, the secret is encrypted in the database using Fernet AES-128 encryption. The API never returns it — not even to an admin. This protects the credential even if someone reads the API responses.

---

## Files Changed

| File | What changed |
|------|-------------|
| `frontend/src/app/customers/page.tsx` | Full rewrite — shadcn/ui components, CRUD operations, form validation, empty state |

---

## API Calls Used

| Method | Endpoint | When |
|--------|---------|------|
| `GET` | `/api/customers` | Page load — fetch all storefronts |
| `POST` | `/api/customers` | Save Storefront button — create new storefront |
| `PATCH` | `/api/customers/{id}` | Deactivate / Activate button — toggle `is_active` |
| `DELETE` | `/api/customers/{id}` | Delete button — remove storefront |

---

## Empty State

When no storefronts exist:
> "No storefronts added. Add your OnPrintShop storefront to start publishing products."

---

## How to Test

Make sure the backend is running:

```bash
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8000

cd frontend && npm run dev
```

Open `http://localhost:3000/customers` and verify:

1. Page loads with table — shows existing storefronts
2. Click **"+ Add Storefront"** — form appears with all 5 fields and help text
3. Submit empty form — all 5 fields show "Required" validation errors
4. Fill in valid data and click **"Save Storefront"** — new row appears in table
5. Click **"Deactivate"** — badge changes from Active to Inactive
6. Click **"Delete"** — row disappears, empty state appears if no storefronts left

---

## Where This Fits in the Pipeline

```
Storefronts Page (Task 0.4)  ◀── YOU ARE HERE
        │
        ▼
Markup Rules Page (already done)
— each storefront gets its own pricing rules
        │
        ▼
OPS Push Workflow (V1c)
— n8n loops over active storefronts and pushes products into each one
```

The storefront list must be populated before the push workflow (V1c) can run — it needs at least one active storefront to push products into.
