import asyncio, sys, json
from types import SimpleNamespace
sys.path.insert(0, '/app')

async def main():
    from database import async_session
    from modules.ops_push.gateway import prepare_push_intent, execute_push
    from modules.integrations.schemas import (
        PushRequest, PushRequestSource, PushRequestTarget, PushRequestProductRef
    )
    from modules.push_log.models import ProductPushLog
    import uuid

    customer_id = uuid.UUID("a2b91bac-10a0-4c0a-b284-cbac991250bf")
    product_id  = uuid.UUID("22f47b56-60ce-420e-8d08-350c823a38e6")

    req = PushRequest(
        source=PushRequestSource(supplier_slug="sanmar"),
        target=PushRequestTarget(customer_id=customer_id),
        product_ref=PushRequestProductRef(product_id=product_id),
        dry_run=False,
    )

    key = SimpleNamespace(
        id="dev-push-key",
        name="Dev push key",
        allowed_customer_ids=None,
        allowed_supplier_slugs=None,
        is_active=True,
    )

    async with async_session() as db:
        accepted = await prepare_push_intent(req, key, db)

    print(f"Status after prepare: {accepted.status}")
    print(f"Push log ID: {accepted.push_log_id}")

    print("Executing push against OPS staging...")
    await execute_push(accepted.push_log_id)

    async with async_session() as db:
        log = await db.get(ProductPushLog, accepted.push_log_id)

    print(f"\nFinal status: {log.status}")
    print(f"OPS product id: {log.ops_product_id}")

    steps = log.step_results or []
    if isinstance(steps, str):
        steps = json.loads(steps)

    ok_count   = sum(1 for s in steps if s.get("status") == "ok")
    fail_count = sum(1 for s in steps if s.get("status") not in ("ok", None))
    print(f"Steps: {len(steps)} total, {ok_count} ok, {fail_count} failed/warning")

    # Show any non-ok steps
    for s in steps:
        if s.get("status") != "ok":
            print(f"  NON-OK step {s.get('step')}: {s.get('mutation')} → {s.get('status')} | {s.get('error') or s.get('ops_error')}")

    # setAssignOptions summary
    ao = [s for s in steps if s.get("mutation") == "setAssignOptions"]
    print(f"\nsetAssignOptions: {len(ao)} steps")
    for s in ao:
        oids = s.get("ops_ids", {})
        print(f"  step {s['step']} master_option:{s['source_key'].split(':')[1]} → "
              f"status={s['status']} product_option_id={oids.get('product_option_id')}")

asyncio.run(main())
