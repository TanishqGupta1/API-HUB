<!-- GRAPHX-CANONICAL-AUTHORITY -->
# ⚠️ Canonical source of truth: GraphXCPI/graphx-docs

**Build, design, and architecture decisions for GraphX live in `GraphXCPI/graphx-docs` (`product-scoping/`), NOT in this repo.** Docs inside this repo are **legacy / reference only** — valuable for historical logic and understanding, but **not authoritative**. On any conflict, **graphx-docs wins.** Read the precedence rule first: **`graphx-docs/product-scoping/_CANONICAL-AUTHORITY.md`**.

**This repo is governed by:** `atomic-specs/connect.md`.

Extracted connector fabric (ex-API-HUB). The Automate canvas + connector contracts are specced in `connect.md`.

> Do not make or defend an architecture decision from a doc in this repo. Escalate to the spec, not to local docs.
<!-- /GRAPHX-CANONICAL-AUTHORITY -->

<!-- GRAPHX-DOCS-FRESHNESS -->
## ⚠️ Docs must stay current — verify against CODE, not docs

**A stale doc is a DEFECT, not a reference.** Before asserting anything is built / unbuilt / done / migrated / blocked, **verify against the actual code** — `git ls-remote` for branches, the schema, the migrations, the tests — **never from a doc.** **Any change that alters build state, architecture, status, or a count MUST update the doc that describes it, in the same commit.** Reconciliation / status / audit docs are DATED + PROVISIONAL (carry date + commit SHA + repo) and are **STALE until re-verified**. Fix stale docs on sight with a dated note — `CORRECTED (YYYY-MM-DD): … verified against <repo>@<sha>`. Every count/status must be reproducible from the code. Full rule: `graphx-docs/_CANONICAL-AUTHORITY.md` -> "Docs must stay current."

> **The code is truth; docs must chase it; a stale doc is a bug you fix, not a source you trust.**
<!-- /GRAPHX-DOCS-FRESHNESS -->
