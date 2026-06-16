"""Read-only diagnostic: ask the LIVE OPS GraphQL API what it actually accepts
for a customizable PRINT product — product type, design (design studio), and
decoration / additional options.

Why this exists
---------------
Our push code (modules/ops_push/payload_builder.py) was reverse-engineered and
hardcodes product_type="1", sends NO decoration info, and the design mutation
(setProductDesign) is a dormant stub. Before we change any of that, we want the
ground truth: introspect the real OPS schema for the types we'd have to fill in.

This NEVER mutates anything — it only runs GraphQL introspection + the existing
read-only `products` query, using the same credentials a normal push uses.

Usage (from backend/, with the venv active)::

    python inspect_ops_schema.py                      # first active customer
    python inspect_ops_schema.py --customer "Visual Graphx"

If introspection is disabled on the OPS server, the script says so — in that
case we fall back to the manual "configure one product by hand in OPS admin,
then read it back" approach.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from database import async_session
from modules.customers.models import Customer
from modules.ops_client.client import OpsAuth, OpsGraphQLClient


# Introspect a single named type — works for both input types (inputFields)
# and object types (fields). Three levels of ofType unwrapping cover
# [NonNull[List[NonNull[Named]]]] which is the deepest GraphQL nests in practice.
_INTROSPECT_TYPE = """
query IntrospectType($name: String!) {
  __type(name: $name) {
    name
    kind
    description
    inputFields {
      name
      description
      type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
    }
    fields {
      name
      description
      type { kind name ofType { kind name ofType { kind name } } }
    }
  }
}
""".strip()

# Root schema — lists every query + mutation name so we can spot the real
# single-product query and the real design mutation (whatever they're called).
_INTROSPECT_ROOT = """
query Root {
  __schema {
    queryType { fields { name } }
    mutationType { fields { name } }
  }
}
""".strip()

# The types that matter for "apparel as a customizable print product".
_TYPES_OF_INTEREST = [
    "ProductInput",                     # setProduct — has product_type + (maybe) design fields
    "AssignOptionsInput",               # link master options to a product
    "AdditionalOptionInput",            # decoration / extra options (embroidery, print method)
    "AdditionalOptionAttributesInput",  # the choices within an option + their pricing
    "setProductDesign_input",           # design-studio setup (sides / print areas) — likely wrong name
]


def _type_str(t: dict | None) -> str:
    """Flatten a GraphQL type ref into a readable string, e.g. '[ProductInput!]!'."""
    if not t:
        return "?"
    kind, name, of = t.get("kind"), t.get("name"), t.get("ofType")
    if kind == "NON_NULL":
        return _type_str(of) + "!"
    if kind == "LIST":
        return "[" + _type_str(of) + "]"
    return name or "?"


async def _load_customer(db, name: str | None) -> Customer | None:
    stmt = select(Customer)
    stmt = stmt.where(Customer.name == name) if name else stmt.where(Customer.is_active.is_(True))
    return (await db.execute(stmt.limit(1))).scalars().first()


def _print_type(label: str, t: dict | None, err: str | None) -> None:
    if not t:
        print(f"## {label}: NOT FOUND ({err or 'no such type'})\n")
        return
    fields = t.get("inputFields") or t.get("fields") or []
    print(f"## {label}  [{t.get('kind')}] — {len(fields)} fields")
    for f in fields:
        line = f"  - {f['name']}: {_type_str(f['type'])}"
        if f.get("description"):
            line += f"   # {f['description']}"
        print(line)
    print()


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--customer", help="Customer name (default: first active customer)")
    args = ap.parse_args()

    async with async_session() as db:
        customer = await _load_customer(db, args.customer)
        if not customer:
            print("No matching customer. Run with --customer 'NAME'.", file=sys.stderr)
            return 1
        secret = (customer.ops_auth_config or {}).get("client_secret")
        if not secret:
            print(f"Customer '{customer.name}' has no OPS client_secret set.", file=sys.stderr)
            return 1
        auth = OpsAuth(
            base_url=customer.ops_base_url,
            token_url=customer.ops_token_url,
            client_id=customer.ops_client_id,
            client_secret=secret,
        )
        cust_name = customer.name

    print(f"# Live OPS schema inspection (customer: {cust_name})")
    print(f"# endpoint: {auth.base_url}\n")

    async with OpsGraphQLClient(auth) as client:
        # 1) All query + mutation names — find the product/design entry points.
        root = await client.execute(_INTROSPECT_ROOT, variables={})
        if root.ok and root.data:
            qs = sorted(f["name"] for f in root.data["__schema"]["queryType"]["fields"])
            ms = sorted(f["name"] for f in root.data["__schema"]["mutationType"]["fields"])
            print(f"## Queries ({len(qs)})\n" + ", ".join(qs) + "\n")
            print(f"## Mutations ({len(ms)})\n" + ", ".join(ms) + "\n")
            hits = [s for s in qs + ms if any(k in s.lower() for k in ("design", "decorat", "option", "print"))]
            print("## Design / decoration / option related (filtered)\n" + (", ".join(hits) or "(none)") + "\n")
        else:
            print("!! Schema introspection appears DISABLED or failed:")
            print(f"   {root.ops_error_code}: {root.ops_error_message}")
            print("   → Fall back to the manual read-back: configure one product")
            print("     by hand in OPS admin, then read it via the products query.\n")

        # 2) Field-by-field for the types we'd have to fill in.
        for tname in _TYPES_OF_INTEREST:
            res = await client.execute(_INTROSPECT_TYPE, variables={"name": tname})
            t = (res.data or {}).get("__type") if res.ok else None
            _print_type(tname, t, res.ops_error_message if not res.ok else None)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
