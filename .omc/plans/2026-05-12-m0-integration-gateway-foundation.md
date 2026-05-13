# M0 — Integration Gateway Foundation (Implementation Plan)

**Status:** Draft Rev 0 — Planner initial pass; pending Architect + Critic review
**Spec:** [`docs/superpowers/specs/2026-05-11-integration-gateway-design.md`](../../docs/superpowers/specs/2026-05-11-integration-gateway-design.md) (Rev 3)
**Phase:** M0 (additive foundation only — safe even if M1-M5 change)
**Owner:** Tanishq
**Branch target:** `feat/m0-gateway-foundation` off `main`

---

## RALPLAN-DR Summary (Short Mode)

### Principles
1. **Additive-only DB changes** — no destructive migrations; everything `NULL`able or defaulted so legacy ingest keeps working
2. **Round-trip fidelity** — `ProductIngest → persist (snapshot=True) → DB → rehydrate → ProductIngest` MUST be lossless
3. **Backward-compat default** — `persist_product()` default behavior unchanged; snapshot mode opt-in only
4. **Contract tests before implementation** — failing tests written first, then code (TDD per superpowers)
5. **Single source of truth** — Rev 3 spec drives field names, types, widths; no inventing new contracts

### Decision Drivers (Top 3)
1. **Unblock M1 without blocking team review of M1-M5** — M0 must land independent of spec body approval
2. **Zero regression for existing supplier ingest** — `POST /api/ingest/{supplier_id}/products` must behave identically pre/post M0
3. **Migration must be reversible** — every `ADD COLUMN` has a matching `DROP COLUMN` in `downgrade()`; no PG enum migrations (per project CLAUDE.md)

### Viable Options

#### Option A — One big Alembic migration + persistence flag (Recommended)
- Single Alembic revision: all `product_push_log` fields, `integration_keys` table, `ProductVariant.sort_order`, `Product*` round-trip fields
- Persistence: add `snapshot: bool = False` param + delete-missing-children logic when True
- Tests: 1 fixture-driven round-trip test + 1 idempotency-replay contract test

**Pros:** Single deploy unit; reviewable in one PR; rollback = one `alembic downgrade -1`
**Cons:** Larger PR (~600 LOC); reviewer fatigue risk

#### Option B — Split into 3 migrations (push_log, integration_keys, catalog round-trip)
- Three sequential Alembic revs; three smaller PRs
- Same code-side scope

**Pros:** Smaller per-PR diff; each rev independently rollbackable
**Cons:** Three deploy steps; merge ordering hazard; team review burden 3× not 1×; integration_keys table is useless until push_log has key_id

**Invalidation rationale for B:** PR #105 spec review is the bottleneck, not migration size. Three PRs triple the review surface area without proportional risk reduction. Stick with A.

---

## Scope

### In Scope
1. Alembic migration `0002_integration_gateway_foundation.py` (additive only)
2. `backend/modules/catalog/schemas.py` — add `VariantIngest.sort_order`, `ProductIngest` round-trip fields
3. `backend/modules/catalog/models.py` — add `ProductVariant.sort_order` column + any missing round-trip columns
4. `backend/modules/catalog/persistence.py` — `persist_product(..., snapshot: bool = False)` + delete-missing-children logic
5. `backend/modules/push_log/models.py` — add 15 fields per Rev 3 spec lines 904-929
6. `backend/modules/push_log/schemas.py` — Pydantic mirror for new fields (read-side)
7. Contract tests:
   - `backend/tests/test_m0_round_trip.py` (ProductIngest snapshot fidelity)
   - `backend/tests/test_m0_idempotency_ledger.py` (unique constraint on `(key_id, idempotency_key)`)

### Out of Scope
- M1 OPS push execution (gateway endpoints, worker)
- M2 cutover dispatcher, GATEWAY_ENABLED_CUSTOMERS flag
- M3-M5 (n8n deletion, etc.)
- Any frontend changes
- `integration_keys` admin UI (M2 territory)

---

## Implementation Steps

### Step 1 — Schema additions (`backend/modules/catalog/schemas.py`)

Add to `VariantIngest` (line 172-180):
```python
class VariantIngest(BaseModel):
    part_id: str
    color: Optional[str] = None
    size: Optional[str] = None
    sku: Optional[str] = None
    base_price: Optional[Decimal] = None
    inventory: Optional[int] = None
    warehouse: Optional[str] = None
    sort_order: int = 0  # NEW — preserves supplier size ordering for OPS
    prices: list["VariantPriceIngest"] = Field(default_factory=list)
```

Audit `ProductIngest` for round-trip gaps (Rev 3 spec line 725-726 lists `category_external_id`, `category_name`, `raw_payload`, `part_id`, `sort_order`, size metadata, print metadata). For each gap, either confirm field exists or add it.

**File:** `backend/modules/catalog/schemas.py:172-180`
**Expected diff:** ~5 lines

### Step 2 — Model additions (`backend/modules/catalog/models.py`)

Add `ProductVariant.sort_order` column (currently absent per Rev 3 P2.5 audit):
```python
sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
```

Audit `ProductVariant`, `ProductSize`, `ProductImage`, `ApparelDetails`, `PrintDetails` against `ProductIngest` schema for round-trip gaps. Add missing columns nullable with sensible defaults.

**File:** `backend/modules/catalog/models.py:79-95` + neighbors
**Expected diff:** ~10-20 lines

### Step 3 — Push log model (`backend/modules/push_log/models.py`)

Per Rev 3 spec lines 904-929, add to `ProductPushLog`:
```python
request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, server_default=text("gen_random_uuid()"))
key_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("integration_keys.id", ondelete="SET NULL"), nullable=True)
idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
supplier_slug: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
supplier_sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
callback_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
callback_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="'not_requested'")
callback_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
callback_next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
step_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
cleanup_targets: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
retry_of: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
worker_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

Widen `status` from current type to `VARCHAR(32)`.

**File:** `backend/modules/push_log/models.py:11-22`
**Expected diff:** ~25 lines

### Step 4 — Integration keys table (new file)

Create `backend/modules/integrations/models.py` (module may not exist yet):
```python
class IntegrationKey(Base):
    __tablename__ = "integration_keys"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    primary_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    secondary_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    allowed_callback_hosts: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**File:** `backend/modules/integrations/models.py` (NEW)
**Expected diff:** ~25 lines

### Step 5 — Persistence snapshot mode (`backend/modules/catalog/persistence.py`)

Modify `persist_product()` signature at line 31:
```python
async def persist_product(
    db: AsyncSession,
    supplier_id: UUID,
    item: ProductIngest,
    category_id: UUID | None = None,
    snapshot: bool = False,  # NEW
) -> UUID:
```

After UPSERTing the product spine (existing logic), insert snapshot block:
```python
if snapshot:
    # Delete variants not present in payload
    new_part_ids = [v.part_id for v in item.variants]
    if new_part_ids:
        await db.execute(
            delete(ProductVariant)
            .where(ProductVariant.product_id == product_id)
            .where(ProductVariant.part_id.notin_(new_part_ids))
        )
    else:
        await db.execute(
            delete(ProductVariant).where(ProductVariant.product_id == product_id)
        )

    # Delete images not present
    new_urls = [img.url for img in item.images]
    if new_urls:
        await db.execute(
            delete(ProductImage)
            .where(ProductImage.product_id == product_id)
            .where(ProductImage.url.notin_(new_urls))
        )

    # Sizes already use delete-and-reinsert (persistence.py:114)
    # Options: delete by option_key not in payload
```

Persist `sort_order` in variant UPSERT block at `persistence.py:126-149`.

**File:** `backend/modules/catalog/persistence.py:31-188`
**Expected diff:** ~40 lines

### Step 6 — Alembic migration

Create `backend/alembic/versions/0002_integration_gateway_foundation.py`:
- All `ADD COLUMN` statements with `IF NOT EXISTS` where appropriate
- `CREATE TABLE integration_keys`
- Constraint additions: `fk_product_push_log_key_id`, `ux_push_log_idem_key`
- Index additions: `ix_push_log_payload_hash`, `uq_push_log_in_flight` (partial)
- `downgrade()` mirrors every change

**File:** `backend/alembic/versions/0002_integration_gateway_foundation.py` (NEW)
**Expected diff:** ~120 lines

### Step 7 — Round-trip contract test

`backend/tests/test_m0_round_trip.py`:
```python
@pytest.mark.asyncio
async def test_snapshot_round_trip_no_loss(db_session, supplier_factory):
    original = ProductIngest(
        supplier_sku="PC61",
        product_name="Test Product",
        brand="Port Authority",
        category_external_id="cat-123",
        category_name="Apparel",
        raw_payload={"source": "test"},
        variants=[
            VariantIngest(part_id="PC61-RED-S", color="Red", size="S", sku="PC61-RED-S", sort_order=0),
            VariantIngest(part_id="PC61-RED-M", color="Red", size="M", sku="PC61-RED-M", sort_order=1),
        ],
        # ... full payload
    )
    pid = await persist_product(db_session, supplier.id, original, snapshot=True)
    rehydrated = await load_product_ingest_from_db(db_session, pid)
    assert rehydrated == original  # field-by-field equality
```

Also assert: omitting a variant on second `persist_product(snapshot=True)` call deletes it; `snapshot=False` (default) keeps it.

**File:** `backend/tests/test_m0_round_trip.py` (NEW)
**Expected diff:** ~80 lines

### Step 8 — Idempotency ledger contract test

`backend/tests/test_m0_idempotency_ledger.py`:
```python
@pytest.mark.asyncio
async def test_unique_constraint_blocks_duplicate_key(db_session, integration_key):
    await db_session.execute(insert(ProductPushLog).values(
        key_id=integration_key.id, idempotency_key="abc", payload_hash="h1", ...
    ))
    await db_session.commit()
    with pytest.raises(IntegrityError):
        await db_session.execute(insert(ProductPushLog).values(
            key_id=integration_key.id, idempotency_key="abc", payload_hash="h2", ...
        ))
        await db_session.commit()
```

Also assert: same `idempotency_key` under different `key_id` is allowed (per Rev 3 line 605).

**File:** `backend/tests/test_m0_idempotency_ledger.py` (NEW)
**Expected diff:** ~50 lines

---

## Acceptance Criteria (Testable)

1. ✅ `alembic upgrade head` from `0001_baseline` runs clean on fresh Postgres
2. ✅ `alembic downgrade -1` restores schema to `0001` state without data loss for existing rows
3. ✅ `pytest backend/tests/test_m0_round_trip.py -v` passes — snapshot round-trip lossless
4. ✅ `pytest backend/tests/test_m0_idempotency_ledger.py -v` passes — unique constraint enforced
5. ✅ `pytest backend/tests/test_ingest_routes.py -v` passes unchanged — legacy ingest semantics preserved
6. ✅ `POST /api/ingest/{supplier_id}/products` with partial payload (missing variants) does NOT delete variants (default `snapshot=False`)
7. ✅ `persist_product(..., snapshot=True)` with partial payload deletes missing variants/images
8. ✅ `VariantIngest.sort_order` round-trips through DB (write → read → equal)
9. ✅ All new columns nullable or defaulted — no NOT NULL violations on existing rows
10. ✅ Existing `vg-ops-push-001` n8n workflow still resolves push payloads (regression check via curl)

---

## Risks + Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Snapshot delete cascades to FK-protected children | Medium | High | Use explicit DELETE statements with `WHERE NOT IN` instead of relying on cascade; test with FK violation case |
| `sort_order` field collision with existing supplier ingest paths | Low | Medium | Default `0`; existing code paths that don't set it still work |
| Alembic migration timing on prod (long lock) | Medium | High | All `ADD COLUMN` use `nullable=True` or `server_default` (no table rewrite); index creation uses `CREATE INDEX CONCURRENTLY` outside transaction |
| Round-trip test reveals deeper schema gaps | Medium | Medium | Fail fast in M0 rather than M1; budget +1 day for schema additions |
| `integration_keys.id` format (UUID vs prefix-shortid) not specified in Rev 3 | High | Low | Pick `VARCHAR(64)` accommodating both `ig_abc123...` shortid and UUID; settle in M2 admin UI work |
| Sinchana / Vidhi / Urvashi block on PR review | Medium | Medium | Land M0 as separate PR before team review of M1-M5; M0 is reversible |

---

## Verification Steps

1. `cd backend && source .venv/bin/activate`
2. `docker compose up -d postgres`
3. `alembic upgrade head` — confirms migration applies
4. `alembic downgrade base && alembic upgrade head` — confirms idempotency
5. `pytest backend/tests/ -v -k m0` — runs new contract tests
6. `pytest backend/tests/ -v` — full suite passes (no regression)
7. `python seed_demo.py` — confirms demo seed still works
8. `curl -X POST http://localhost:8000/api/ingest/{seed_supplier_id}/products -d @sample_partial.json` — confirm partial ingest preserved
9. Manual SQL audit: `SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'product_push_log';` — every new column nullable or defaulted
10. `git diff --stat main...HEAD` — confirm scope (~300-400 LOC + tests)

---

## Open Questions (resolve before Architect review)

1. Does `customers` table exist yet for `integration_keys.customer_id` FK? If not, defer FK and reference as plain UUID with audit comment.
2. Is JSONB the right type for `step_results` / `cleanup_targets` or should it be `JSON`? Postgres-native = JSONB; chosen.
3. Should `ProductSize.sort_order` also be added now or wait for M1? Spec only mentions `VariantIngest.sort_order`. Defer.

---

## Estimated Effort

- Step 1-2 (schema/model): 0.5 day
- Step 3-4 (push_log + integration_keys): 0.5 day
- Step 5 (persistence snapshot): 1 day
- Step 6 (migration): 0.5 day
- Step 7-8 (tests): 1 day
- Verification + review iteration: 0.5 day
- **Total: 4 days** (single dev, no blockers)

---

## Status: pending approval
