# Plain English Task Explanation
## SanMar → API-HUB → OPS Milestone

**For:** Manager + Tech Lead presentation  
**Date:** 2026-05-15  
**Author:** Vidhi

---

## How to read this document

For each task, I explain:
- What the problem is in plain words
- Where it lives right now in the codebase
- Why it needs to be fixed
- What changes in the frontend (the UI the admin sees)
- What changes in the backend (the server-side code)
- How this can be extended later

---

---

## Task 1 — Stop Supplier Passwords From Being Sent to the Browser

### What is the problem?

Right now, when the admin opens the Suppliers page, the backend sends everything it knows about a supplier to the frontend — including the username and password that were typed in when the supplier was added.

This means every time you load the Suppliers list, the SanMar password is travelling over the network and sitting in browser memory. If someone inspects the browser's network tab, they can read it. If someone gets access to a browser session, they can read it.

### Where does this live in the codebase?

**Backend file:** `backend/modules/suppliers/schemas.py`

There is a class called `SupplierRead`. This class defines what the backend sends back when someone asks "give me the list of suppliers." On line 28, there is a field called `auth_config: dict`. This field contains the supplier credentials — the username, password, and API keys that the admin typed in.

The credentials are stored encrypted in the database (which is correct). But the moment the backend sends the API response, it decrypts them and includes them in full. So the database protection is undone at the response layer.

### Why is this necessary to fix?

The whole point of encrypting credentials in the database is to protect them. That protection becomes meaningless if we then send the decrypted credentials to any browser that loads the page.

Beyond security, it is also standard practice: an API that manages accounts should never return passwords or keys in a list response. Even internal admin tools follow this rule.

### What changes in the backend?

Remove `auth_config` from `SupplierRead`. The response will still include everything the UI needs to display: supplier name, protocol type, status, product count, and so on. We just stop including the credentials.

Add one small new endpoint: something like `GET /api/suppliers/{id}/credentials-status` that returns only `{ "has_credentials": true/false }`. This gives the frontend a way to show "credentials configured ✓" without sending the actual credentials.

### What changes in the frontend?

The Suppliers list page (`frontend/src/app/(admin)/suppliers/page.tsx`) currently reads the `auth_config` field from the API response. Once it is removed from the response, we update the frontend to call the new small `credentials-status` endpoint instead. The page will still show whether credentials are set up — it just won't have the actual values in memory.

### How can this be changed later?

If in the future you need to allow an admin to edit credentials (not just see whether they exist), you would add a separate protected endpoint like `PUT /api/suppliers/{id}/credentials` that accepts new credentials. This follows the same pattern that banks use: you can change a password but you can never see the old one.

---

---

## Task 2 — Turn Off Mock Mode in the Push Pipeline

### What is the problem?

The push page — the page where an admin reviews a product and clicks "Push to OPS" — is currently running in **mock mode**. This means when you click "Push to OPS," no real data is sent to OPS. Instead, the code returns fake fixture data that was hardcoded by a developer.

The page looks like it is working. You see a preflight check, a product payload preview, a confirmation dialog. But it is all simulated. No product actually goes to OPS.

### Where does this live in the codebase?

**Frontend file:** `frontend/src/lib/use-push-preview.ts` (line 58)

```
process.env.NEXT_PUBLIC_PHASE8_LIVE === "true"
```

There is one environment variable called `NEXT_PUBLIC_PHASE8_LIVE`. If it is not set to `"true"`, the entire push flow uses fake fixture data instead of calling the real backend.

**Frontend file:** `frontend/src/lib/push-fixtures.ts`

This file contains the hardcoded fake responses — the simulated preflight results, the simulated OPS product ID, and so on.

**Push page file:** `frontend/src/app/(admin)/products/[id]/push/page.tsx`

The push page even shows a small "mock mode" badge in the UI so developers know it is not live.

### Why is this necessary to fix?

The milestone is to make SanMar → OPS work for real. Right now nothing real is happening. Until mock mode is turned off and the real backend is called, we cannot know if the push pipeline actually works.

This is the most important task in the whole milestone. Everything else is preparation — this is the actual connection.

### What changes in the frontend?

Set `NEXT_PUBLIC_PHASE8_LIVE=true` in the frontend environment file (`frontend/.env.local`). That single change switches the push page from fake mode to real mode.

After that, the push page will call the real backend endpoint `POST /api/integrations/v1/push-requests` instead of returning fixture data. The preflight check, payload preview, and push result will all come from the live backend.

The "mock mode" badge on the push page will disappear.

### What changes in the backend?

No backend code needs to change for this specific task. The backend Integration Gateway endpoint (`POST /api/integrations/v1/push-requests`) already exists. The payload builder already exists. The OPS client already exists.

The task is to turn on the connection, watch what happens, and fix whatever breaks.

### How can this be changed later?

Once the pipeline is stable, the mock mode code can be fully removed. Right now it exists as a safety net for development. Once live push is proven to work reliably, the fixture file and the `IS_MOCK_MODE` variable can be deleted from the codebase.

---

---

## Task 3 — Verify the Full Push Pipeline Works End-to-End

### What is the problem?

Once mock mode is turned off (Task 2), we need to trace the entire journey of a push from start to finish and confirm every step works correctly with real data.

The push pipeline has several steps that must happen in a specific order:

1. Backend receives the push request
2. Preflight check runs (does the product have all required fields?)
3. Payload builder assembles the mutation plan (what to send to OPS and in what order)
4. OPS client calls OPS GraphQL: create the product → get back an OPS product ID
5. OPS client uses that product ID to create sizes and prices
6. OPS client creates inventory entries
7. Backend saves the result to the push log
8. Frontend shows success with the OPS product ID

The concern is step 4 to step 5: OPS returns a product ID after creating the product, and that ID must be fed into the next calls (create sizes, create prices). If this handoff is not working correctly, sizes and prices will not be created.

### Where does this live in the codebase?

**Backend file:** `backend/modules/ops_push/payload_builder.py`

This file builds the mutation plan. Each step in the plan references the previous step's result using placeholders. For example, step 2 (create size) says "use the product ID from step 1." The OPS client is supposed to replace those placeholders with real IDs as it goes.

**Backend file:** `backend/modules/ops_client/` 

This is the module that actually calls the OPS GraphQL API. It is responsible for executing each mutation step, reading the response, and passing IDs to the next step.

**Backend file:** `backend/modules/integrations/routes.py`

This is the entry point. When the frontend calls `POST /api/integrations/v1/push-requests`, this route receives it and kicks off the pipeline.

### Why is this necessary?

Individual pieces of the pipeline were built and tested in isolation. But they have not been run together against a real OPS instance with real SanMar data. Edge cases only show up in real runs — for example, OPS might require a category to exist before a product can be created, or size names might need to match an OPS lookup table exactly.

### What changes in the backend?

Likely small fixes discovered during the real run. Examples of things that often break in this step:

- OPS requires `category_id` (a number) but we are sending `category_name` (a string). May need a lookup step.
- OPS rejects a field that is null when it expects an empty string.
- Token refresh fails on the first call because the token expired.

We trace the logs, find each break, fix it.

### What changes in the frontend?

The push status page (`/push-log/[id]`) already exists. After the live push completes, the frontend should redirect to the push log and show: whether it succeeded, the OPS product ID if it worked, or the exact step that failed and why.

If the push log page is not showing enough detail, we add more fields to it.

### How can this be changed later?

Once the pipeline works for one product (PC61), adding new product types or new field mappings only means updating the payload builder. The pipeline structure itself (preflight → build → execute → log) does not need to change.

---

---

## Task 4 — Verify the Product Preview Shows Complete Data

### What is the problem?

Before pushing a product to OPS, the admin should see exactly what data API-HUB has for that product. If something is missing — for example, no images, or some sizes have no price — the admin should see that clearly before clicking Push, not discover it after a failed push.

There are two product-related pages that currently exist:

1. **Product detail page** (`/products/[id]`) — shows the product, its images, its variants, and a "Push to OPS" button. This is the view-what-we-have page.
2. **Push preview page** (`/products/[id]/push`) — shows the preflight check and the mutation plan. This is the confirm-before-push page. Currently in mock mode.

The question is: does the product detail page show all the information the admin needs to make a good decision before pushing?

### Where does this live in the codebase?

**Frontend file:** `frontend/src/app/(admin)/products/[id]/page.tsx`

This page calls `GET /api/catalog/products/{id}` to load the product, then displays images (tabbed by front/back/swatch/detail), supplier info, and a push history section.

**Backend file:** `backend/modules/catalog/routes.py`

This route returns the product data. We need to verify it includes: variant list with size/color/SKU, pricing for each variant, inventory for each variant, images, and a list of any fields that are empty or missing.

### Why is this necessary?

If the admin pushes a product with missing prices or no images, OPS may reject it or create an incomplete listing. The preview is a quality gate — catch problems before they reach OPS, not after.

### What changes in the backend?

Add a check: when the product detail endpoint returns data, also return a `missing_fields` list. For example: "3 variants have no price", "no front image found", "description is empty." This is a simple calculation — scan the variants and flag anything null or empty.

### What changes in the frontend?

Add a warning section on the product detail page that shows the missing fields list. If everything is fine, show nothing (or a green checkmark). If fields are missing, show a yellow warning banner before the Push button so the admin sees it clearly.

### How can this be changed later?

The missing fields check can become more sophisticated over time. For example, different OPS storefronts may have different requirements. The check could be made configurable per customer — "this storefront requires a minimum of 3 images."

---

---

## Task 5 — Verify the Mapping Page Saves and Loads Correctly

### What is the problem?

The mappings page (`/mappings/[supplierId]`) is where an admin tells API-HUB how to translate SanMar data into OPS data. For example: "SanMar size 'M' should map to OPS size option ID 42."

There are two kinds of mappings in this system and they must not be confused:

- **Field mappings** — stored on the supplier record itself (in `suppliers.field_mappings`). These are general rules like "use SanMar's `productName` field for OPS's `products_title` field."
- **Push mappings** — stored in the separate `push_mappings` table. These are per-product, per-customer specific mappings that link supplier variants (color/size combinations) to OPS master option IDs.

The lead flagged that mapping save has bugs and that supplier variant options are being mixed with OPS master options. This needs to be verified and cleaned up.

### Where does this live in the codebase?

**Frontend mappings page:** `frontend/src/app/(admin)/mappings/[supplierId]/page.tsx`

When saving, this page calls:
```
PUT /api/suppliers/{supplierId}/mappings
Body: { "mapping": { ...supplierSpecificFields } }
```

This saves only field mappings (the supplier-level config). Push mappings (the variant-to-OPS-option table) are separate.

**Backend push mappings:** `backend/modules/push_mappings/routes.py` and `schemas.py`

The `PushMappingUpsert` schema defines the save payload for push mappings. It includes `source_master_option_id` and `target_ops_option_id` — these are the OPS master option IDs. These must come from the OPS master options table, not from the supplier's size/color values directly.

### Why is this necessary?

If the mapping payload is structured wrong when saving, the backend either rejects it with an error or silently stores garbage data. Then when a push happens, the payload builder reads those mappings and sends wrong option IDs to OPS. OPS rejects the product or creates it with wrong attributes.

### What changes in the backend?

Confirm the `PUT /api/suppliers/{id}/mappings` endpoint exists and accepts the shape the frontend is sending. Confirm the push mappings `POST /api/push-mappings` endpoint correctly links `source_master_option_id` to the OPS master options table and not to raw supplier size strings.

### What changes in the frontend?

The mappings page has three panels: `SanMarMappingPanel`, `OpsMappingPanel`, and `FourOverMappingPanel`. Verify that the SanMar panel is only sending SanMar-to-canonical mappings (field names), and the OPS mapping panel is only sending canonical-to-OPS option ID mappings. If the two are mixed in one save payload, separate them into their correct endpoints.

### How can this be changed later?

Once SanMar mapping works, other suppliers (S&S, 4Over) can reuse the same mapping infrastructure. Their panels already exist in the frontend (`FourOverMappingPanel`). They just need their respective backend endpoints to match the same pattern.

---

---

## Task 6 — Make Sure the Push Log Shows Clear Results

### What is the problem?

After a product is pushed to OPS, the admin needs to see one of two things clearly:

**Success:** "Product pushed. OPS product ID is 4821. Created at 2:34 PM."

**Failure:** "Push failed at step 2 (setProductSize). OPS returned: size name 'XS' does not match any known size. 3 out of 5 sizes were created before the error."

Right now the push log table and detail page exist. But because the push pipeline has been running in mock mode, we do not know if the real push results are displayed correctly.

### Where does this live in the codebase?

**Frontend:** `frontend/src/app/(admin)/push-log/page.tsx` (list) and `frontend/src/app/(admin)/push-log/[id]/page.tsx` (detail)

**Backend:** `backend/modules/push_log/routes.py` and `models.py`

The push log model stores: status, step results (as JSON), error message, and timestamps. The detail page should read all of these and show them clearly.

### Why is this necessary?

Without a clear push status, the admin has no way to know if a product made it to OPS. They cannot confirm success. They cannot diagnose a failure. The push log is the paper trail for every push — it needs to be readable.

### What changes in the backend?

Confirm that after a live push, the push log record is updated with: final status (success/failed), the OPS product ID returned by OPS, the step-by-step results, and any error message. If the worker is not writing these fields correctly, add the missing writes.

### What changes in the frontend?

Confirm the push log detail page displays: overall status badge, OPS product ID (with a link if possible), per-step breakdown, and error detail. If fields are missing from the display, add them. The page file already exists — this is mostly verification and filling in any gaps.

### How can this be changed later?

In the future, the push log can power a dashboard that shows aggregate statistics — how many products pushed today, success rate per supplier, average push duration. The data is already being collected; it just needs a visualization layer added later.

---

---

## Summary: What Each Change Is and Why

| Task | What we change | Where | Why it is necessary |
|------|---------------|-------|---------------------|
| T1 | Remove supplier password from API response | Backend schema, Frontend supplier list | Credential security — passwords must not travel to the browser |
| T2 | Turn off mock mode in push page | Frontend environment variable | The push currently does nothing real — this turns it on |
| T3 | Trace and fix live push pipeline | Backend integration gateway, OPS client | End-to-end connection has never been tested with real data |
| T4 | Add missing fields warning to product preview | Backend catalog endpoint, Frontend product page | Admin needs to catch bad data before it reaches OPS |
| T5 | Fix mapping save payload and verify separation | Backend push-mappings, Frontend mapping panels | Wrong mappings produce wrong pushes silently |
| T6 | Verify push log shows complete results | Backend push log writer, Frontend push log page | Admin needs clear success/failure feedback after every push |

---

## What is NOT changing

- The SanMar SOAP import is real and working. We are not rewriting it.
- The OPS push payload builder already handles all required fields (products_title, product_size_id, size_id, attribute_id). We are not rebuilding it.
- The Integration Gateway endpoint already exists. We are not replacing it.
- Customer credential storage is already secure. We are not touching it.

The work above is connecting, verifying, and fixing the pieces that already exist — not rebuilding from scratch.
