# GraphX Connect Restart

Verified: 2026-07-12 against `GraphXCPI/graphx-connect@5afa7b82d4430219c6719a75a6f1ae95c83d0929`.

Classification: separate FastAPI/connector service authority. The adjacent frontend, Compose/n8n
topology, and dated API-HUB plans are not proof of the canonical Platform Connect integration or a
current deployment. No live service, Docker state, database, workflow, supplier, or OPS endpoint was
changed by this governance pass.

Next safe action: map the current FastAPI contracts to the Platform Connect floor and identify
which frontend/n8n paths are retained, migrated, or legacy. Prove with code/tests before runtime work.

Do not run live connector calls, seeds, migrations, deployment runbooks, old-org actions, or
credential operations without scoped approval, rollback, and verification.
