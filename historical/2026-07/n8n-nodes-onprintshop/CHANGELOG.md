# Changelog — n8n-nodes-onprintshop

## [Unreleased] — ⚠️ BREAKING: batch mutation contract

> **Coordination note for n8n flow owners.** This release changes the GraphQL
> contract of five existing Product mutations to match the **live OnPrintShop
> GraphQL schema** (the previous single-`input` form did not match real OPS and
> would fail against it). The change is correct, but it **breaks any existing
> workflow** still built against the old single-object form. Audit your flows
> before upgrading the node.

### Breaking — five mutations moved from single `input` to batch `inputs`

For each mutation below the request variable changed from a single object
(`$input: XInput!`, passed as `input: $input`) to a **non-null array**
(`$inputs: [XInput!]!`, passed as `inputs: $inputs`), **and** the response
selection set changed.

| Mutation | Old variable | New variable | Old response fields | New response fields |
|---|---|---|---|---|
| `setProduct`         | `input: ProductInput!`         | `inputs: [ProductInput!]!`         | `id, title, status` | `result, message, id` |
| `setProductPrice`    | `input: ProductPriceInput!`    | `inputs: [ProductPriceInput!]!`    | `status, message`   | `result, message, id` |
| `setProductSize`     | `input: ProductSizeInput!`     | `inputs: [ProductSizeInput!]!`     | `status, message`   | `result, message, id` |
| `setProductCategory` | `input: ProductCategoryInput!` | `inputs: [ProductCategoryInput!]!` | `status, message`   | `result, message, id` |
| `setAssignOptions`   | `input: AssignOptionsInput!`   | `inputs: [AssignOptionsInput!]!`   | `status, …`         | `result, message, …`  |

Source: `nodes/OnPrintShop/graphql/mutations.ts`, `nodes/OnPrintShop/execute/product.ts`.

### What breaks

A workflow built against the old node will break in two ways:

1. **Request shape** — it sends `input: { … }` (single). OPS now expects
   `inputs: [ { … } ]` (array). The old shape is rejected.
2. **Response shape** — it reads `.status` / `.title` from the mutation result.
   Those fields are gone; read `.result` (success flag), `.message`, and `.id`.

### Migration for flow owners

For each affected mutation node in your workflow:

- Wrap the input object in an array: `input: {…}` → `inputs: [{…}]`.
- Update any downstream reference to the response: `status` → `result`,
  and use `message` / `id` as needed.
- `setProduct` previously returned `title`; it no longer does — drop references.

### Added (non-breaking)

New batch mutations exposed by the node (additive — no migration needed):
`setAdditionalOption`, `setAdditionalOptionAttributes`,
`setProductsAttributePrice`, `setProductSku`. `setProductsImageGallery` and
`updateProductStock` use a single bulk `input` object (not the `inputs` array).
New queries added in `graphql/queries.ts`.

---

_If you own an n8n workflow that calls any of the five mutations above, reply on
the PR before this merges so we can sequence the node upgrade with your flow
update._
