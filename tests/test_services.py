"""Exercise action schemas, account isolation, responses, and failures in HA."""

from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.parro.api import ParroAuthError, ParroConnectionError, ParroError
from custom_components.parro.services import SERVICES


@pytest.fixture
async def loaded_account(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    with patch("custom_components.parro.ParroApi", return_value=mock_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry


async def test_actions_registered_without_account(hass):
    assert await async_setup_component(hass, "parro", {})
    for name in SERVICES:
        assert hass.services.has_service("parro", name)
        assert hass.services.supports_response("parro", name) is SupportsResponse.ONLY


@pytest.mark.parametrize("name", SERVICES)
async def test_bounded_response_and_explicit_account(hass, loaded_account, mock_api, name):
    method = getattr(mock_api, f"async_{name}")
    method.return_value = ["private-value-1", "private-value-2", "private-value-3"]
    data = {"config_entry_id": loaded_account.entry_id, "limit": 2}
    if name == "get_messages":
        data["chatroom_id"] = "123"
    response = await hass.services.async_call(
        "parro", name, data, blocking=True, return_response=True
    )
    assert response == {"items": ["private-value-1", "private-value-2"], "returned": 2, "limit": 2}
    if name == "get_messages":
        method.assert_awaited_once_with(chatroom_id="123", limit=2)
    else:
        method.assert_awaited_once_with(limit=2)
    assert all("private-value" not in str(s.as_dict()) for s in hass.states.async_all())


async def test_default_limit_and_explicit_response_required(hass, loaded_account, mock_api):
    data = {"config_entry_id": loaded_account.entry_id}
    result = await hass.services.async_call(
        "parro", "get_announcements", data, blocking=True, return_response=True
    )
    assert result == {"items": [], "returned": 0, "limit": 20}
    mock_api.async_get_announcements.assert_awaited_once_with(limit=20)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("parro", "get_announcements", data, blocking=True)


@pytest.mark.parametrize("limit", [0, 51, -1, True, False, 1.5, "20", None])
async def test_invalid_limit_rejected_before_api(hass, loaded_account, mock_api, limit):
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "parro",
            "get_announcements",
            {"config_entry_id": loaded_account.entry_id, "limit": limit},
            blocking=True,
            return_response=True,
        )
    mock_api.async_get_announcements.assert_not_awaited()


@pytest.mark.parametrize(
    "chatroom_id",
    [
        "",
        "../room",
        "room/path",
        "room?limit=1000",
        "https://other.invalid",
        "9" * 21,
        "0",
        0,
        -1,
        True,
        1.5,
        "room-123",
        "room\n",
    ],
)
async def test_invalid_conversation_id_rejected(hass, loaded_account, mock_api, chatroom_id):
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "parro",
            "get_messages",
            {"config_entry_id": loaded_account.entry_id, "chatroom_id": chatroom_id},
            blocking=True,
            return_response=True,
        )
    mock_api.async_get_messages.assert_not_awaited()


async def test_required_account_and_conversation_id(hass, loaded_account, mock_api):
    for name, data in [
        ("get_announcements", {}),
        ("get_messages", {"config_entry_id": loaded_account.entry_id}),
    ]:
        with pytest.raises(vol.Invalid):
            await hass.services.async_call("parro", name, data, blocking=True, return_response=True)
    mock_api.async_get_announcements.assert_not_awaited()
    mock_api.async_get_messages.assert_not_awaited()


async def test_reject_missing_other_domain_and_unloaded_accounts(hass, loaded_account, mock_api):
    wrong_domain = MockConfigEntry(domain="unrelated", state=ConfigEntryState.LOADED)
    wrong_domain.add_to_hass(hass)
    unloaded = MockConfigEntry(domain="parro", state=ConfigEntryState.NOT_LOADED)
    unloaded.add_to_hass(hass)
    for entry_id in ("missing", wrong_domain.entry_id, unloaded.entry_id):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                "parro",
                "get_announcements",
                {"config_entry_id": entry_id},
                blocking=True,
                return_response=True,
            )
    mock_api.async_get_announcements.assert_not_awaited()


async def test_only_admin_or_automation_can_read(
    hass,
    loaded_account,
    mock_api,
    hass_admin_user,
    hass_read_only_user,
):
    data = {"config_entry_id": loaded_account.entry_id}
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "parro",
            "get_announcements",
            data,
            blocking=True,
            return_response=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    mock_api.async_get_announcements.assert_not_awaited()
    await hass.services.async_call(
        "parro",
        "get_announcements",
        data,
        blocking=True,
        return_response=True,
        context=Context(user_id=hass_admin_user.id),
    )
    mock_api.async_get_announcements.assert_awaited_once()


@pytest.mark.parametrize("error", [ParroAuthError, ParroConnectionError, ParroError])
async def test_safe_errors_and_reauth(hass, loaded_account, mock_api, error, caplog):
    mock_api.async_get_announcements.side_effect = error("SECRET-TOKEN-AND-SCHOOL-CONTENT")
    old_success = loaded_account.runtime_data.last_success
    with patch.object(loaded_account, "async_start_reauth") as reauth:
        with pytest.raises(HomeAssistantError) as exc:
            await hass.services.async_call(
                "parro",
                "get_announcements",
                {"config_entry_id": loaded_account.entry_id},
                blocking=True,
                return_response=True,
            )
        if error is ParroAuthError:
            reauth.assert_called_once_with(hass)
        else:
            reauth.assert_not_called()
    assert "SECRET-TOKEN" not in str(exc.value)
    assert "SECRET-TOKEN" not in caplog.text
    assert not loaded_account.runtime_data.last_update_success
    assert loaded_account.runtime_data.last_success == old_success
