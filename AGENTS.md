<!-- GRAPHX-GOVERNANCE-VERSION: 2026.07.12 -->
# GraphX Connect Service Contract

This repository is the approved heterogeneous FastAPI/connector service authority for GraphX
Connect. Product decisions live in `GraphXCPI/graphx-docs/atomic-specs/connect.md`. The canonical
Platform Connect floor and integration target live in `GraphXCPI/graphx-platform`; this service is
not yet proven wired to that floor. Local API-HUB, n8n, deployment, and status documents are
implementation evidence, not current product or production authority.

- Verify behavior against code, tests, current branch, and live state before trusting dated plans.
- Do not start Compose, n8n, databases, migrations, seeds, live supplier/OPS calls, or deployment
  scripts merely because local docs contain commands.
- Credentials and tenant identity must remain scoped and server-derived. Never print or commit
  secrets, live payloads, or customer data.
- `VisualGraphxLLC` references are provenance only; never push or repair old-org sources.
- Query Knowledge Vault and CodeGraph before non-trivial work. Use a clean GraphXCPI anchor plus a
  repo-scoped worktree and a small PR from the correct default branch.
- Auth/data/migration/infra/live-integration changes require Claude + Gemini review, green
  repository-specific checks, rollback evidence, and explicit human approval.
- No default-branch work, force push, merge, broad sync, Docker mutation, or repo disposal without
  explicit authority. Docker paths are runtime-only.

Read `README.md`, `CLAUDE.md`, and `RESTART.md`. Update current status in the same reviewed change.
