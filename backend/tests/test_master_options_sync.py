"""T1 regression: /api/master-options/sync uses a local n8n helper, not n8n_proxy."""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_trigger_sync_uses_local_helper(monkeypatch):
    """The /sync handler dispatches through a helper defined in master_options
    itself, not via `modules.n8n_proxy`. Calls the handler directly to bypass
    router-level JWT auth, which is independent of this refactor.
    """
    monkeypatch.setenv("N8N_API_BASE_URL", "http://n8n:5678")
    monkeypatch.setenv("N8N_API_KEY", "test-key")
    monkeypatch.setenv("MASTER_OPTIONS_SYNC_WORKFLOW_ID", "wf-123")

    from modules.master_options import routes

    target = "modules.master_options.routes._trigger_n8n_workflow"
    with patch(target, new_callable=AsyncMock) as mock_trigger:
        mock_trigger.return_value = {"triggered": True, "url": "http://x", "response": {}}
        result = await routes.trigger_sync()

    mock_trigger.assert_awaited_once()
    args, kwargs = mock_trigger.call_args
    workflow_id = args[0] if args else kwargs.get("workflow_id")
    assert workflow_id == "wf-123"
    assert result == {"triggered": True, "url": "http://x", "response": {}}


def test_master_options_routes_does_not_import_n8n_proxy():
    """Static guard: the routes module must not pull anything from n8n_proxy.

    Preempts M4 deletion of `modules/n8n_proxy/` — if this assertion ever
    starts failing again, the import sneaked back in and M4 will break.
    """
    from modules.master_options import routes

    src = inspect.getsource(routes)
    assert "modules.n8n_proxy" not in src, (
        "master_options/routes.py must not import from n8n_proxy — M4 deletes it"
    )
