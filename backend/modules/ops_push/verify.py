"""OPS push read-back verifier — Bucket B7.

ADDITIVE / NO-CONFLICT: this is a brand-new module. It does NOT touch
payload_builder.py / mutations.py / gateway.py (the files the OPS-schema PR
rewrites), so it merges cleanly alongside that PR. After the PR lands, wire
`verify_pushed_product()` into the gateway's push-finalize step so the push
status reflects what ACTUALLY persisted in OPS, not the mutation acks.

It is also runnable standalone to inspect an existing product:
    python -m modules.ops_push.verify 540
"""
from __future__ import annotations

from typing import Any

from modules.ops_client.client import OpsGraphQLClient

# Introspection used to self-adapt to OPS's (fiddly, wrapper-nested) read schema
# instead of hard-coding field names that drift between deployments.
_QUERY_FIELDS = (
    "query { __schema { queryType { fields { name "
    "type { kind name ofType { kind name ofType { kind name } } } } } } }"
)
_TYPE_FIELDS = (
    "query T($n: String!) { __type(name: $n) { kind fields { name "
    "type { kind name ofType { kind name ofType { kind name } } } } } }"
)


def _base(t: dict | None) -> tuple[str | None, str | None]:
    while t and not t.get("name"):
        t = t.get("ofType")
    return (t.get("kind"), t.get("name")) if t else (None, None)


async def _records_shape(ops: OpsGraphQLClient, query_field: str) -> tuple[list[str], list[str]]:
    """Return (path, scalar_fields): the chain of wrapper object-field names from
    the query's return type down to the record type, plus that record's scalars."""
    qf = await ops.execute(_QUERY_FIELDS, variables={})
    fields = (((qf.data or {}).get("__schema") or {}).get("queryType") or {}).get("fields") or []
    f = next((x for x in fields if x["name"] == query_field), None)
    if not f:
        return [], []
    _, cur = _base(f["type"])
    path: list[str] = []
    scalars: list[str] = []
    for _ in range(4):  # descend through wrappers to the leaf record type
        if not cur:
            break
        t = await ops.execute(_TYPE_FIELDS, variables={"n": cur})
        tflds = (((t.data or {}).get("__type") or {}).get("fields")) or []
        obj = next((x for x in tflds if _base(x["type"])[0] == "OBJECT"), None)
        if obj:
            path.append(obj["name"])
            _, cur = _base(obj["type"])
            continue
        scalars = [x["name"] for x in tflds if _base(x["type"])[0] in ("SCALAR", "ENUM")]
        break
    return path, scalars


async def _fetch(ops: OpsGraphQLClient, query_field: str, args: str) -> list[dict[str, Any]]:
    """Run a list-returning OPS query and return the record rows (best-effort)."""
    path, scalars = await _records_shape(ops, query_field)
    if not scalars:
        return []
    sel = "{ " + " ".join(scalars) + " }"
    for fld in reversed(path):
        sel = "{ " + fld + " " + sel + " }"
    res = await ops.execute(f"query {{ {query_field}({args}) {sel} }}", variables={})
    if not res.ok:
        return []
    node: Any = (res.data or {}).get(query_field)
    for fld in path:
        if isinstance(node, dict):
            node = node.get(fld)
    return node if isinstance(node, list) else ([] if node is None else [node])


async def verify_pushed_product(ops: OpsGraphQLClient, products_id: int) -> dict[str, Any]:
    """Read back a pushed product's ACTUAL persisted state from OPS.

    Returns a report dict: existence, size/variant count, stock rows, image rows.
    Use the booleans to decide the real push outcome (B7).
    """
    products = await _fetch(ops, "products", f"products_id: {products_id}")
    sizes = await _fetch(ops, "productSize", f"products_id: {products_id}")
    stocks = await _fetch(ops, "productStocks", f"product_id: {products_id}")
    images = await _fetch(ops, "productsImageGallery", f"products_id: {products_id}")

    # Price read-back (sample): the push prices per size, and OPS exposes prices
    # keyed by size/attribute (not by product_id), so we sample this product's
    # size_ids and check whether price rows actually exist for them.
    size_ids = [s.get("size_id") for s in sizes if s.get("size_id") is not None]
    sample_ids = size_ids[:8]
    priced = 0
    price_sample: list[dict[str, Any]] = []
    for sid in sample_ids:
        rows = await _fetch(ops, "productsAttributePrice", f"size_id: {sid}")
        if rows:
            priced += 1
            if not price_sample:
                price_sample = rows[:1]

    exists = any(int(p.get("product_id") or 0) == products_id for p in products) or bool(products)
    return {
        "products_id": products_id,
        "exists": exists,
        "name": (products[0].get("product_name") if products else None),
        "size_count": len(sizes),
        "stock_rows": len(stocks),
        "image_count": len(images),
        "price_check": {"sizes_sampled": len(sample_ids), "with_price_rows": priced},
        "_samples": {
            "product": products[:1],
            "size": sizes[:2],
            "stock": stocks[:2],
            "image": images[:2],
            "price": price_sample,
        },
    }


if __name__ == "__main__":
    import asyncio
    import json
    import sys

    from sqlalchemy import select

    from database import async_session
    from modules.customers.models import Customer
    from modules.ops_client.client import OpsAuth

    async def _run() -> None:
        pid = int(sys.argv[1]) if len(sys.argv) > 1 else 540
        async with async_session() as db:
            rows = (await db.execute(select(Customer))).scalars().all()
            cust = next(
                (c for c in rows
                 if c.ops_base_url and "visualgraphx" in c.ops_base_url
                 and c.ops_token_url and c.ops_client_id
                 and (c.ops_auth_config or {}).get("client_secret")),
                None,
            )
            sec = (cust.ops_auth_config or {}).get("client_secret")
            auth = OpsAuth(base_url=cust.ops_base_url, token_url=cust.ops_token_url,
                           client_id=cust.ops_client_id, client_secret=sec)
            async with OpsGraphQLClient(auth) as ops:
                report = await verify_pushed_product(ops, pid)
        print(json.dumps(report, indent=2, default=str)[:3000])

    asyncio.run(_run())
