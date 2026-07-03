"""Idempotent re-push cleanup — `_clear_existing_children`.

PR #183 review raised that the child-clear guards might be a silent no-op if
they key on different mutation-name casing than the plan carries. The plan's
`mutation` field is camelCase (see payload_builder: `mutation="setProductSize"`
etc.), and the guards check the same camelCase names — so cleanup *does* fire.

These tests lock that contract in: they assert real delete mutations are issued
(with delete:1) for each planned child type, and that an unplanned child type is
skipped. If anyone reintroduces a casing mismatch, these go red instead of the
cleanup silently doing nothing.
"""
from __future__ import annotations

import pytest

from modules.ops_push.gateway import (
    _EXISTING_GALLERY_Q,
    _EXISTING_OPTIONS_Q,
    _EXISTING_SIZES_Q,
    _clear_existing_children,
    _verify_gallery_persisted,
)

_EXISTENCE_QUERIES = {_EXISTING_OPTIONS_Q, _EXISTING_SIZES_Q, _EXISTING_GALLERY_Q}


class _Resp:
    def __init__(self, ok: bool = True, data: dict | None = None):
        self.ok = ok
        self.data = data or {}


class _FakeRawClient:
    """Records every execute() call and returns canned existence rows.

    `existing` maps child type → list of ids OPS currently has for the product.
    Any query that isn't an existence query is treated as a delete mutation.
    """

    def __init__(self, existing: dict):
        self.existing = existing
        self.calls: list[tuple[str, dict | None]] = []

    async def execute(self, query, variables=None):
        self.calls.append((query, variables))
        if query == _EXISTING_OPTIONS_Q:
            rows = [{"prod_add_opt_id": i} for i in self.existing.get("options", [])]
            return _Resp(data={"productAdditionalOptions": {"productAdditionalOptions": rows}})
        if query == _EXISTING_SIZES_Q:
            rows = [{"size_id": i} for i in self.existing.get("sizes", [])]
            return _Resp(data={"productSize": {"productSize": rows}})
        if query == _EXISTING_GALLERY_Q:
            rows = [{"products_image_gallery_id": i} for i in self.existing.get("gallery", [])]
            return _Resp(data={"productsImageGallery": {"productsImageGallery": rows}})
        # Anything else is a delete mutation.
        return _Resp(ok=True)

    @property
    def delete_calls(self):
        return [(q, v) for (q, v) in self.calls if q not in _EXISTENCE_QUERIES]


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_clear_existing_children_issues_deletes_for_planned_types():
    """camelCase plan → existing options/sizes are actually deleted, not silently
    skipped. Gallery is NOT cleared here (the gallery step owns clear-and-re-add
    inline — see _clear_existing_children), even when the plan re-adds it."""
    client = _FakeRawClient({"options": [11, 22], "sizes": [101], "gallery": [7, 8, 9]})
    plan_mutations = {
        "setProduct",
        "setAdditionalOption",
        "setProductSize",
        "setProductsImageGallery",
    }

    deleted = await _clear_existing_children(client, 555, plan_mutations)

    # Counts: 2 options + 1 size cleared; gallery deliberately left to the
    # inline gallery step, so 0 here.
    assert deleted == {"options": 2, "sizes": 1, "gallery": 0}

    # Deletes were really issued: 2 option deletes + 1 size delete. No gallery
    # delete, and the gallery existence query is never even run.
    assert len(client.delete_calls) == 3
    assert _EXISTING_GALLERY_Q not in [q for q, _ in client.calls]

    # Every option/size delete carries delete:1 against the right product.
    flat_inputs = [
        inp
        for (_q, v) in client.delete_calls
        for inp in (v or {}).get("inputs", [])
    ]
    assert {i["prod_add_opt_id"] for i in flat_inputs if "prod_add_opt_id" in i} == {11, 22}
    assert {i["size_id"] for i in flat_inputs if "size_id" in i} == {101}
    assert all(i["delete"] == 1 for i in flat_inputs)
    assert all(i["products_id"] == 555 for i in flat_inputs)

    # No gallery delete mutation was issued at all.
    assert not [
        v for (_q, v) in client.delete_calls if v and "image_arr" in (v.get("input") or {})
    ]


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_clear_existing_children_skips_unplanned_types():
    """A child type the plan won't re-add is left alone — no existence query, no delete."""
    client = _FakeRawClient({"options": [11], "sizes": [101], "gallery": [7]})
    # Plan only re-adds sizes → options/gallery must be untouched.
    deleted = await _clear_existing_children(client, 555, {"setProductSize"})

    assert deleted == {"options": 0, "sizes": 1, "gallery": 0}
    assert _EXISTING_OPTIONS_Q not in [q for q, _ in client.calls]
    assert _EXISTING_GALLERY_Q not in [q for q, _ in client.calls]
    assert _EXISTING_SIZES_Q in [q for q, _ in client.calls]


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_clear_guards_match_payload_builder_casing():
    """Drift guard: the names the clear guards check must be names the payload
    builder actually emits — otherwise cleanup silently no-ops (the PR #183 risk).
    """
    import inspect

    from modules.ops_push import payload_builder

    guard_src = inspect.getsource(_clear_existing_children)
    builder_src = inspect.getsource(payload_builder)
    # Options/sizes are cleared by _clear_existing_children, so their guards must
    # match the camelCase names the builder emits.
    for name in ("setAdditionalOption", "setProductSize"):
        assert f'"{name}"' in guard_src, f"{name} guard missing from _clear_existing_children"
        assert f'mutation="{name}"' in builder_src, f"{name} not emitted by payload_builder"
    # Gallery is intentionally NOT guarded here (the gallery step clears it
    # inline). The guard pattern checks the quoted mutation name against
    # plan_mutations; that quoted form must be absent for gallery (prose
    # mentions in the docstring don't count).
    assert '"setProductsImageGallery"' not in guard_src, (
        "gallery should not be cleared by _clear_existing_children — the gallery "
        "step owns clear-and-re-add inline"
    )
    assert 'mutation="setProductsImageGallery"' in builder_src


class _GalleryReadbackClient:
    """Returns `count` gallery rows for the existence read-back query."""

    def __init__(self, count: int):
        self.count = count

    async def execute(self, query, variables=None):
        rows = [{"products_image_gallery_id": i} for i in range(self.count)]
        return _Resp(data={"productsImageGallery": {"productsImageGallery": rows}})


def _gallery_step_result(status: str = "ok") -> dict:
    return {"step": 276, "mutation": "setProductsImageGallery", "status": status, "ops_ids": {}}


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_verify_gallery_persisted_flags_zero_rows():
    """OPS acked success but stored 0 rows → note returned, step flipped to warning."""
    steps = [_gallery_step_result()]
    note = await _verify_gallery_persisted(_GalleryReadbackClient(0), 636, expected=77, step_results=steps)

    assert note is not None
    assert "persisted 0/77" in note
    assert steps[0]["status"] == "warning"
    assert steps[0]["error"] == note


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_verify_gallery_persisted_ok_when_rows_match():
    """All expected rows present → no note, step untouched."""
    steps = [_gallery_step_result()]
    note = await _verify_gallery_persisted(_GalleryReadbackClient(77), 636, expected=77, step_results=steps)

    assert note is None
    assert steps[0]["status"] == "ok"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_verify_gallery_persisted_noop_when_no_images_expected():
    """Push sent no images → read-back is skipped entirely."""
    note = await _verify_gallery_persisted(_GalleryReadbackClient(0), 636, expected=0, step_results=[])
    assert note is None
