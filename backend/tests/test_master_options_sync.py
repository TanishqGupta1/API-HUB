"""T23 follow-up: /api/master-options/sync is gone — its n8n workflow was deleted.

Replacement: POST /api/integrations/v1/master-options/ingest (gateway-authed).
This module just keeps the static guard from T1 that master_options never
imports from modules.n8n_proxy.
"""
from __future__ import annotations

import inspect


def test_master_options_routes_does_not_import_n8n_proxy():
    """Static guard: the routes module must not pull anything from n8n_proxy."""
    from modules.master_options import routes

    src = inspect.getsource(routes)
    assert "modules.n8n_proxy" not in src, (
        "master_options/routes.py must not import from n8n_proxy"
    )


def test_legacy_sync_route_is_removed():
    """Regression guard: trigger_sync + _trigger_n8n_workflow should not return.

    The /sync route was an n8n-trigger for a workflow that no longer exists
    (ops-master-options-pull.json, deleted in T23). Anyone needing to seed
    master options should call POST /api/integrations/v1/master-options/ingest.
    """
    from modules.master_options import routes

    assert not hasattr(routes, "trigger_sync"), "trigger_sync was removed in T23"
    assert not hasattr(routes, "_trigger_n8n_workflow"), "_trigger_n8n_workflow was removed in T23"
