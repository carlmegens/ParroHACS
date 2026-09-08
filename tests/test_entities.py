"""Validate compact entities, missing counters, recovery, and diagnostic privacy."""

from unittest.mock import patch

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.parro.api import ParroConnectionError
from custom_components.parro.diagnostics import async_get_config_entry_diagnostics


@pytest.fixture
async def entity_states(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    with patch("custom_components.parro.ParroApi", return_value=mock_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    registry = er.async_get(hass)

    def get(key):
        domain = "binary_sensor" if key == "connectivity" else "sensor"
        entity_id = registry.async_get_entity_id(domain, "parro", f"{config_entry.entry_id}_{key}")
        assert entity_id is not None
        return hass.states.get(entity_id)

    return get


async def test_compact_states_and_generic_names(hass, config_entry, mock_api, entity_states):
    assert len(hass.states.async_all()) == 6
    for key, expected in (
        ("children_count", "2"),
        ("groups_count", "3"),
        ("unread_announcements", "4"),
        ("unread_chatrooms", "1"),
        ("connectivity", "on"),
    ):
        assert entity_states(key).state == expected
    assert (
        entity_states("last_success").state
        == config_entry.runtime_data.last_success.replace(microsecond=0).isoformat()
    )
    for state in hass.states.async_all():
        assert config_entry.title not in str(state.as_dict())
        assert "synthetic-access" not in str(state.as_dict())
        assert "acct-1" not in str(state.as_dict())
    mock_api.async_get_announcements.assert_not_awaited()
    mock_api.async_get_chatrooms.assert_not_awaited()
    mock_api.async_get_messages.assert_not_awaited()
    mock_api.async_get_calendar_urls.assert_not_awaited()


async def test_only_existing_unread_counters_have_public_popup_routing(config_entry, entity_states):
    for key, source in (
        ("unread_announcements", "announcements"),
        ("unread_chatrooms", "messages"),
    ):
        attributes = dict(entity_states(key).attributes)
        attributes.pop("friendly_name")
        assert attributes == {
            "custom_ui_more_info": "more-info-parro",
            "parro_config_entry_id": config_entry.entry_id,
            "parro_source": source,
        }
    for key in ("children_count", "groups_count", "last_success", "connectivity"):
        attributes = entity_states(key).attributes
        assert "custom_ui_more_info" not in attributes
        assert not any(key.startswith("parro_") for key in attributes)


async def test_device_links_to_its_internal_account_without_private_values(
    hass, config_entry, entity_states
):
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.configuration_url == f"homeassistant://parro/{config_entry.entry_id}"
    assert device.name == "Parro"
    assert "acct-1" not in device.configuration_url
    assert "synthetic-access" not in device.configuration_url


async def test_missing_values_are_unknown_and_zero_remains_zero(
    config_entry, mock_api, entity_states
):
    mock_api.async_fetch_summary.return_value = {
        "children_count": 0,
        "unread_announcements": None,
        "unread_chatrooms": 0,
        "private_contents": "PRIVATE-SCHOOL-CONTENT",
    }
    await config_entry.runtime_data.async_refresh()
    assert entity_states("children_count").state == "0"
    assert entity_states("groups_count").state == "unknown"
    assert entity_states("unread_announcements").state == "unknown"
    assert entity_states("unread_chatrooms").state == "0"
    assert "PRIVATE-SCHOOL-CONTENT" not in str(entity_states("children_count").as_dict())


async def test_outage_is_visible_and_recovery_updates_entities(
    config_entry, mock_api, entity_states
):
    last_success = entity_states("last_success").state
    mock_api.async_fetch_summary.side_effect = ParroConnectionError("synthetic network failure")
    await config_entry.runtime_data.async_refresh()
    assert entity_states("connectivity").state == "off"
    assert entity_states("children_count").state == "unavailable"
    assert entity_states("last_success").state == last_success
    mock_api.async_fetch_summary.side_effect = None
    mock_api.async_fetch_summary.return_value["children_count"] = 3
    await config_entry.runtime_data.async_refresh()
    assert entity_states("connectivity").state == "on"
    assert entity_states("children_count").state == "3"


async def test_diagnostics_are_an_operational_allowlist(hass, config_entry, entity_states):
    config_entry.runtime_data.data["unexpected_private_key"] = "PRIVATE-CONTENT"
    result = await async_get_config_entry_diagnostics(hass, config_entry)
    assert set(result) == {
        "entry_state",
        "poll_interval_minutes",
        "last_update_success",
        "last_success",
    }
    assert result["entry_state"] == "loaded"
    assert result["poll_interval_minutes"] == 30
    assert result["last_update_success"] is True
    serialized = str(result)
    for value in (
        "PRIVATE-CONTENT",
        "acct-1",
        "synthetic-access",
        "synthetic-refresh",
        config_entry.title,
    ):
        assert value not in serialized


async def test_diagnostics_when_account_not_loaded(hass, config_entry):
    result = await async_get_config_entry_diagnostics(hass, config_entry)
    assert result["entry_state"] == "not_loaded"
    assert result["last_update_success"] is None
    assert result["last_success"] is None
