# Phase 14b — Task 10: n8n Integration Contract Doc

**Date:** 2026-05-05
**Branch:** `dev/phase14b-n8n-decouple`
**File created:** `docs/n8n-integration.md`
**Status:** Complete

---

## What We Did

Created `docs/n8n-integration.md` — a formal interface contract between the FastAPI backend and any n8n instance. This document is the single source of truth for how the two systems talk to each other.

## What the Doc Covers

| Section | Content |
|---------|---------|
| 1. Environment requirements | Which n8n hosting tiers are supported (n8n.cloud Starter is NOT) |
| 2. Required env vars | Full table of vars needed on both FastAPI side and n8n side |
| 3. Outbound: backend → n8n | Webhook trigger spec, exact JSON payload shape for OPS push, response handling |
| 4. Inbound: n8n → backend ingest | Endpoint list, required `X-Ingest-Secret` header, body shape reference |
| 5. Push callback | Spec for the callback n8n must make after OPS returns the real `ops_product_id` |
| 6. Self-host setup checklist | Step-by-step for a fresh n8n install |
| 7. Existing-install migration | How to export/import workflows and credentials when moving between n8n hosts |

## Why This Doc Exists

Without it, the "contract" between FastAPI and n8n only existed in the code and in people's heads. Any developer setting up a new environment had to reverse-engineer the workflow JSONs and the service.py to figure out what env vars to set and what payload shapes to expect. This doc makes onboarding and environment setup self-service.

## Key Decision Documented

The `ops_auth.client_secret` is sent in the OPS push request body. The doc explicitly states this requires the webhook URL to be on a private network — public-internet n8n hosts must terminate TLS. This is a security requirement that was previously undocumented.
