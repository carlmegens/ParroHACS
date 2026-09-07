"""Bundled card resource registration and static delivery in Home Assistant."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE, MODE_YAML
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.setup import async_setup_component

from custom_components.parro.frontend import (
    CARD_PATH,
    CARD_URL,
    async_register_resource,
    async_setup_frontend,
)


@pytest.fixture
def resources(hass):
    """Use HA's actual validated resource collection with empty synthetic storage."""
    collection = ResourceStorageCollection(
        hass, SimpleNamespace(async_load=AsyncMock(return_value={}))
    )
    hass.data[LOVELACE_DATA] = SimpleNamespace(resource_mode=MODE_STORAGE, resources=collection)
    return collection


async def test_register_card_preserves_unrelated_resources_and_is_idempotent(hass, resources):
    other = await resources.async_create_item(
        {"url": "/local/unrelated-card.js", "res_type": "module"}
    )
    external = await resources.async_create_item(
        {"url": f"https://example.invalid{CARD_PATH}?v=old", "res_type": "css"}
    )
    snapshot = {item["id"]: dict(item) for item in (other, external)}
    await async_register_resource(hass)
    actual = {item["id"]: item for item in resources.async_items()}
    assert len(actual) == 3
    assert actual[other["id"]] == snapshot[other["id"]]
    assert actual[external["id"]] == snapshot[external["id"]]
    own = [item for item in actual.values() if item["url"] == CARD_URL]
    assert len(own) == 1
    assert own[0]["type"] == "module"
    with (
        patch.object(resources, "async_create_item", wraps=resources.async_create_item) as create,
        patch.object(resources, "async_update_item", wraps=resources.async_update_item) as update,
    ):
        await async_register_resource(hass)
    create.assert_not_called()
    update.assert_not_called()
    assert {item["id"]: item for item in resources.async_items()} == actual


@pytest.mark.parametrize("old_type", ["module", "css"])
async def test_register_card_updates_only_own_resource_in_place(hass, resources, old_type):
    own = await resources.async_create_item({"url": f"{CARD_PATH}?v=old", "res_type": old_type})
    other = await resources.async_create_item(
        {"url": "/local/unrelated-card.js", "res_type": "module"}
    )
    await async_register_resource(hass)
    actual = {item["id"]: item for item in resources.async_items()}
    assert len(actual) == 2
    assert actual[own["id"]] == {"id": own["id"], "url": CARD_URL, "type": "module"}
    assert actual[other["id"]] == other


async def test_register_card_leaves_yaml_resources_to_user(hass):
    collection = SimpleNamespace(
        async_get_info=AsyncMock(), async_create_item=AsyncMock(), async_update_item=AsyncMock()
    )
    hass.data[LOVELACE_DATA] = SimpleNamespace(resource_mode=MODE_YAML, resources=collection)
    await async_register_resource(hass)
    collection.async_get_info.assert_not_called()
    collection.async_create_item.assert_not_called()
    collection.async_update_item.assert_not_called()


async def test_register_card_tolerates_missing_lovelace(hass):
    hass.data.pop(LOVELACE_DATA, None)
    await async_register_resource(hass)


async def test_resource_failure_is_safe_and_does_not_break_account_setup(hass, caplog):
    collection = SimpleNamespace(
        async_get_info=AsyncMock(side_effect=RuntimeError("SYNTHETIC-PRIVATE-STORAGE-CONTENT"))
    )
    hass.data[LOVELACE_DATA] = SimpleNamespace(resource_mode=MODE_STORAGE, resources=collection)
    await async_register_resource(hass)
    assert "Parro card resource could not be registered" in caplog.text
    assert "SYNTHETIC-PRIVATE-STORAGE-CONTENT" not in caplog.text


async def test_setup_serves_only_bundled_javascript_without_school_data(
    hass, hass_client_no_auth, config_entry
):
    assert await async_setup_component(hass, "http", {"http": {}})
    config_entry.add_to_hass(hass)
    hass.states.async_set("sensor.parro_synthetic_private", "SYNTHETIC-PRIVATE-SCHOOL-CONTENT")
    with patch("custom_components.parro.frontend.async_at_started") as at_started:
        await async_setup_frontend(hass)
    at_started.assert_called_once_with(hass, async_register_resource)
    client = await hass_client_no_auth()
    response = await client.get(CARD_URL)
    assert response.status == 200
    body = await response.read()
    expected = (
        Path(__file__).resolve().parents[1] / "custom_components/parro/frontend/parro-card.js"
    ).read_bytes()
    assert body == expected
    assert "javascript" in response.headers["Content-Type"]
    for private in (b"synthetic-access", b"synthetic-refresh", b"SYNTHETIC-PRIVATE-SCHOOL-CONTENT"):
        assert private not in body
    # The static path must not expose adjacent integration source or config data.
    for path in ("/parro_static/manifest.json", "/parro_static/api.py", "/parro_static/"):
        assert (await client.get(path)).status == 404
