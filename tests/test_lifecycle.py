"""Setup, token persistence, polling, error recovery, and unload in real HA."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState

from custom_components.parro.api import ParroAuthError, ParroConnectionError, ParroError


async def test_setup_persist_tokens_apply_options_and_unload(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    with patch("custom_components.parro.ParroApi", return_value=mock_api) as api_class:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.update_interval == timedelta(minutes=30)
    assert len(hass.states.async_all()) == 6

    save_tokens = api_class.call_args.args[3]
    tokens = {"access_token": "rotated-access", "refresh_token": "rotated-refresh"}
    with patch.object(hass.config_entries, "async_reload") as reload:
        save_tokens(tokens)
        await hass.async_block_till_done()
        assert config_entry.data["tokens"] == tokens
        reload.assert_not_called()
        mock_api.async_fetch_summary.assert_awaited_once()
        hass.config_entries.async_update_entry(config_entry, options={"poll_interval": 15})
        await hass.async_block_till_done()
        assert config_entry.runtime_data.update_interval == timedelta(minutes=15)
        reload.assert_not_called()
        assert mock_api.async_fetch_summary.await_count == 2
        save_tokens(tokens)
        await hass.async_block_till_done()
        assert mock_api.async_fetch_summary.await_count == 2

    coordinator = config_entry.runtime_data
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_api.async_close.assert_awaited_once()
    assert coordinator._shutdown_requested
    assert coordinator.feed._closed
    assert all(s.state == "unavailable" for s in hass.states.async_all())
    assert hass.services.has_service("parro", "get_announcements")


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (ParroAuthError("synthetic auth error"), ConfigEntryState.SETUP_ERROR),
        (ParroConnectionError("synthetic connection error"), ConfigEntryState.SETUP_RETRY),
        (ParroError("synthetic malformed response"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_first_refresh_failure_closes_client(hass, config_entry, mock_api, error, state):
    config_entry.add_to_hass(hass)
    mock_api.async_fetch_summary.side_effect = error
    with patch("custom_components.parro.ParroApi", return_value=mock_api):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is state
    mock_api.async_close.assert_awaited_once()
    if isinstance(error, ParroAuthError):
        flows = hass.config_entries.flow.async_progress()
        assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_poll_failure_preserves_timestamp_then_recovers(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    with patch("custom_components.parro.ParroApi", return_value=mock_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    first_success = coordinator.last_success
    mock_api.async_fetch_summary.side_effect = ParroConnectionError("network")
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.last_success == first_success
    mock_api.async_fetch_summary.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.last_success >= first_success


async def test_homeassistant_stop_closes_owned_http_client(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    with patch("custom_components.parro.ParroApi", return_value=mock_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    await hass.async_stop()
    mock_api.async_close.assert_awaited_once()
    assert config_entry.runtime_data._shutdown_requested
    assert config_entry.runtime_data.feed._closed
