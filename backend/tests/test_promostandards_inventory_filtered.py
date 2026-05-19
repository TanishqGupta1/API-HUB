"""Bug 4 fix verification — getFilteredInventoryLevels routing.

Confirms the PromoStandardsClient routes inventory calls to the correct
SOAP operation:

* When ``part_ids`` is provided → call ``getFilteredInventoryLevels``.
  Required for SanMar v200, which returns empty on the unfiltered
  variant for catalogs with many SKUs.
* When ``part_ids`` is omitted → fall back to ``getInventoryLevels``.
* When the filtered call raises → silent fallback to the unfiltered call.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from modules.promostandards.client import PromoStandardsClient


pytestmark = pytest.mark.no_db


def _make_client_with_mock_service(svc: Any) -> PromoStandardsClient:
    """Build a client that returns ``svc`` from ``_get_service()``.

    No real WSDL fetch, no network. The auth payload helper still runs but
    only with the stub supplier_id/password we hand it.
    """
    client = PromoStandardsClient.__new__(PromoStandardsClient)
    client.auth_config = {"id": "stub-id", "password": "stub-pwd"}
    client.wsdl_url = "http://example.invalid/?wsdl"
    client._get_service = lambda: svc  # type: ignore[method-assign]
    return client


def _empty_inventory_response() -> Any:
    """An inventory response shape with no PartInventory entries.

    Stops _parse_inventory from doing anything meaningful so we can assert
    on the SOAP call without setting up full XML mocks.
    """
    response = MagicMock()
    response.Inventory = None
    response.inventory = None
    return response


def test_filtered_inventory_used_when_part_ids_provided():
    svc = MagicMock()
    svc.getFilteredInventoryLevels.return_value = _empty_inventory_response()

    client = _make_client_with_mock_service(svc)
    asyncio.run(
        client.get_inventory(["PC61"], part_ids=["PC61-NAV-S", "PC61-NAV-M"])
    )

    svc.getFilteredInventoryLevels.assert_called_once()
    kwargs = svc.getFilteredInventoryLevels.call_args.kwargs
    assert kwargs["productId"] == "PC61"
    assert kwargs["partIdArray"] == {"partId": ["PC61-NAV-S", "PC61-NAV-M"]}
    svc.getInventoryLevels.assert_not_called()


def test_unfiltered_inventory_used_when_part_ids_omitted():
    svc = MagicMock()
    svc.getInventoryLevels.return_value = _empty_inventory_response()

    client = _make_client_with_mock_service(svc)
    asyncio.run(client.get_inventory(["PC61"]))

    svc.getInventoryLevels.assert_called_once()
    kwargs = svc.getInventoryLevels.call_args.kwargs
    assert kwargs["productId"] == "PC61"
    svc.getFilteredInventoryLevels.assert_not_called()


def test_filtered_failure_falls_back_to_unfiltered():
    svc = MagicMock()
    svc.getFilteredInventoryLevels.side_effect = RuntimeError("SOAP fault")
    svc.getInventoryLevels.return_value = _empty_inventory_response()

    client = _make_client_with_mock_service(svc)
    asyncio.run(client.get_inventory(["PC61"], part_ids=["PC61-NAV-S"]))

    svc.getFilteredInventoryLevels.assert_called_once()
    svc.getInventoryLevels.assert_called_once()


def test_both_failures_yield_empty_result_without_raising():
    svc = MagicMock()
    svc.getFilteredInventoryLevels.side_effect = RuntimeError("filtered failed")
    svc.getInventoryLevels.side_effect = RuntimeError("unfiltered failed too")

    client = _make_client_with_mock_service(svc)
    result = asyncio.run(
        client.get_inventory(["PC61"], part_ids=["PC61-NAV-S"])
    )

    assert result == []
