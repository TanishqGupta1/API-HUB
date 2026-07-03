"""
One-shot setup for K420 demo push.
Run ONCE before live_push_k420.py.

Does four things:
  1. Seeds master options from fixtures/master_options.json into master_options table
  2. Enables demo-relevant master options on K420 ProductOption rows (reference data)
  3. Creates/updates push_mapping + PushMappingOption rows for the 4 master options
     so that MASTER_OPTION_ATTACH mode emits setAssignOptions on the next push
  4. Retires stale partial_failure/failed push logs so step-resumption starts fresh
"""
import asyncio, sys, json
from pathlib import Path
sys.path.insert(0, '/app')

K420_PRODUCT_ID = '22f47b56-60ce-420e-8d08-350c823a38e6'
CUSTOMER_ID     = 'a2b91bac-10a0-4c0a-b284-cbac991250bf'

# OPS staging master option IDs confirmed via productMasterOptions query (2026-06-19)
ENABLE_FOR_K420 = [
    (50,  'print_sides',       'Print Sides',       0),
    (52,  'production_time',   'Production Time',   1),
    (112, 'ink_finish',        'Ink Finish',        2),
    (146, 'ink_type',          'Ink Type',          3),
]  # (ops_master_option_id, option_key, title, sort_order)


async def main():
    from database import async_session
    from sqlalchemy import select, delete
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.orm import selectinload
    from datetime import datetime, timezone
    import uuid

    from modules.customers.models import Customer  # noqa: F401 — registers FK target
    from modules.master_options.models import MasterOption, MasterOptionAttribute
    from modules.catalog.models import ProductOption, ProductOptionAttribute
    from modules.push_mappings.models import PushMapping, PushMappingOption
    from modules.push_log.models import ProductPushLog

    fixtures_path = Path('/app/fixtures/master_options.json')
    data = json.loads(fixtures_path.read_text())
    all_mos = data.get('master_options', [])
    print(f'Fixtures: {len(all_mos)} master options')

    async with async_session() as db:
        # ── 1. Seed master options ──────────────────────────────────────
        seeded = 0
        for item in all_mos:
            mo_id_ops = int(item['master_option_id'])
            stmt = (
                pg_insert(MasterOption)
                .values(
                    ops_master_option_id=mo_id_ops,
                    title=item.get('title', ''),
                    option_key=item.get('option_key'),
                    options_type=item.get('options_type'),
                    pricing_method=str(item.get('pricing_method', '')) or None,
                    status=int(item.get('status', 1)),
                    sort_order=int(item.get('sort_order', 0)),
                    description=item.get('description'),
                    raw_json=item,
                )
                .on_conflict_do_update(
                    index_elements=['ops_master_option_id'],
                    set_={
                        'title': item.get('title', ''),
                        'option_key': item.get('option_key'),
                        'raw_json': item,
                    },
                )
                .returning(MasterOption.id)
            )
            mo_uuid = (await db.execute(stmt)).scalar_one()

            await db.execute(
                delete(MasterOptionAttribute)
                .where(MasterOptionAttribute.master_option_id == mo_uuid)
            )
            for attr in item.get('attributes', []):
                db.add(MasterOptionAttribute(
                    master_option_id=mo_uuid,
                    ops_attribute_id=int(attr['master_attribute_id']),
                    title=attr.get('label') or attr.get('title') or 'Unnamed',
                    sort_order=int(attr.get('sort_order', 0)),
                    default_price=float(attr.get('setup_cost', 0) or 0),
                    raw_json=attr,
                ))
            seeded += 1

        await db.commit()
        print(f'Seeded {seeded} master options into DB')

        # ── 2. Rebuild ProductOption rows for K420 (reference data) ────
        product_id = uuid.UUID(K420_PRODUCT_ID)
        customer_id = uuid.UUID(CUSTOMER_ID)

        for po_row in (await db.execute(
            select(ProductOption).where(ProductOption.product_id == product_id)
        )).scalars().all():
            await db.execute(
                delete(ProductOptionAttribute).where(
                    ProductOptionAttribute.product_option_id == po_row.id
                )
            )
        await db.execute(delete(ProductOption).where(ProductOption.product_id == product_id))
        await db.commit()

        enabled = 0
        for ops_mo_id, option_key, title, sort_i in ENABLE_FOR_K420:
            mo = (await db.execute(
                select(MasterOption)
                .where(MasterOption.ops_master_option_id == ops_mo_id)
                .options(selectinload(MasterOption.attributes))
            )).scalar_one_or_none()
            if not mo:
                print(f'  WARN: ops_master_option_id={ops_mo_id} not found — skipping')
                continue

            po = ProductOption(
                product_id=product_id,
                master_option_id=mo.ops_master_option_id,
                option_key=option_key,
                title=title,
                options_type=mo.options_type,
                sort_order=sort_i,
                required=False,
                status=1,
                enabled=True,
            )
            db.add(po)
            await db.flush()

            seen_attr_ids: set[int] = set()
            seen_titles: set[str] = set()
            for ma in sorted(mo.attributes, key=lambda a: a.sort_order or 0):
                if ma.ops_attribute_id in seen_attr_ids or ma.title in seen_titles:
                    continue
                seen_attr_ids.add(ma.ops_attribute_id)
                seen_titles.add(ma.title)
                db.add(ProductOptionAttribute(
                    product_option_id=po.id,
                    ops_attribute_id=ma.ops_attribute_id,
                    title=ma.title,
                    sort_order=ma.sort_order or 0,
                    status=1,
                    enabled=True,
                    price=0,
                ))

            print(f'  ProductOption: {title!r} (ops_id={ops_mo_id}, attrs={len(seen_titles)})')
            enabled += 1

        await db.commit()
        print(f'Saved {enabled} ProductOption rows for K420')

        # ── 3. push_mapping + PushMappingOption for MASTER_OPTION_ATTACH ─
        #
        # MASTER_OPTION_ATTACH reads push_mapping.options at payload-build time.
        # PushMapping.target_ops_product_id is NOT NULL, so we need an existing
        # OPS product ID. We use the most recent non-zero ops_product_id from
        # push_logs for this product.
        now = datetime.now(timezone.utc)
        customer_row = (await db.execute(
            select(Customer).where(Customer.id == customer_id)
        )).scalar_one()

        last_log = (await db.execute(
            select(ProductPushLog)
            .where(
                ProductPushLog.product_id == product_id,
                ProductPushLog.customer_id == customer_id,
                ProductPushLog.ops_product_id.isnot(None),
                ProductPushLog.dry_run.is_(False),
            )
            .order_by(ProductPushLog.pushed_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if last_log and last_log.ops_product_id:
            ops_product_id = int(last_log.ops_product_id)
            print(f'Using OPS product_id={ops_product_id} from push_log {last_log.id} '
                  f'(status={last_log.status}) for UPDATE mode')
        else:
            print('WARNING: No push_log with OPS product_id found.')
            print('         Run live_push_k420.py first (CREATE push) then re-run this script.')
            print('         Options will not be applied on the first push.')
            ops_product_id = None

        if ops_product_id:
            existing_mapping = (await db.execute(
                select(PushMapping).where(
                    PushMapping.source_product_id == product_id,
                    PushMapping.customer_id == customer_id,
                )
            )).scalar_one_or_none()

            if existing_mapping:
                existing_mapping.target_ops_product_id = ops_product_id
                existing_mapping.updated_at = now
                mapping_id = existing_mapping.id
                print(f'Updated push_mapping {mapping_id} → ops_product_id={ops_product_id}')
            else:
                new_mapping = PushMapping(
                    source_system='sanmar',
                    source_product_id=product_id,
                    source_supplier_sku='K420',
                    customer_id=customer_id,
                    target_ops_base_url=customer_row.ops_base_url,
                    target_ops_product_id=ops_product_id,
                    pushed_at=now,
                    updated_at=now,
                    status='active',
                )
                db.add(new_mapping)
                await db.flush()
                mapping_id = new_mapping.id
                print(f'Created push_mapping {mapping_id} → ops_product_id={ops_product_id}')

            # Replace all PushMappingOption rows for this mapping
            await db.execute(
                delete(PushMappingOption).where(
                    PushMappingOption.push_mapping_id == mapping_id
                )
            )
            for ops_mo_id, option_key, title, sort_i in ENABLE_FOR_K420:
                db.add(PushMappingOption(
                    push_mapping_id=mapping_id,
                    source_master_option_id=ops_mo_id,
                    source_option_key=option_key,
                    target_ops_option_id=ops_mo_id,
                    title=title,
                    sort_order=sort_i,
                    created_at=now,
                ))
            await db.commit()
            print(f'Created {len(ENABLE_FOR_K420)} PushMappingOption rows '
                  f'(ops_ids={[x[0] for x in ENABLE_FOR_K420]})')
        else:
            # No OPS product yet — delete any stale mapping so push runs in CREATE mode
            await db.execute(
                delete(PushMapping).where(
                    PushMapping.source_product_id == product_id,
                    PushMapping.customer_id == customer_id,
                )
            )
            await db.commit()
            print('Deleted stale push_mapping → next push will be CREATE mode')

        # ── 4. Retire stale partial_failure/failed push logs ────────────
        old_logs = (await db.execute(
            select(ProductPushLog).where(
                ProductPushLog.product_id == product_id,
                ProductPushLog.customer_id == customer_id,
                ProductPushLog.status.in_(('partial_failure', 'failed')),
                ProductPushLog.dry_run.is_(False),
            )
        )).scalars().all()
        for log in old_logs:
            log.status = 'superseded'
        await db.commit()
        print(f'Retired {len(old_logs)} partial_failure/failed push log(s) → step-resumption clean')

        print('\nSetup complete. Ready to run live_push_k420.py')


asyncio.run(main())
