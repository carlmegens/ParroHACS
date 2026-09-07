"""Exercise user/account/reauth/options flows through Home Assistant's flow manager."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.parro.api import (
    LoginResult,
    ParroAccountSelectionRequired,
    ParroAuthError,
    ParroConnectionError,
    ParroError,
)

CREDENTIALS = {CONF_USERNAME: " parent@example.invalid ", CONF_PASSWORD: "synthetic-password"}
TOKENS = {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"}


async def start(hass):
    return await hass.config_entries.flow.async_init("parro", context={"source": "user"})


async def test_single_account_stores_tokens_not_password(hass):
    result = await start(hass)
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    with (
        patch(
            "custom_components.parro.config_flow.async_login",
            return_value=LoginResult(tokens=TOKENS, account_id="acct-1", title="Parro test"),
        ) as login,
        patch("custom_components.parro.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
        await hass.async_block_till_done()
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {"account_id": "acct-1", "tokens": TOKENS}
    assert result["result"].unique_id == "acct-1"
    login.assert_awaited_once_with(
        hass, "parent@example.invalid", "synthetic-password", account_id=None
    )


async def test_multiple_accounts_requires_choice_before_entry(hass):
    result = await start(hass)
    login = AsyncMock(
        side_effect=[
            ParroAccountSelectionRequired(
                accounts=[
                    {"id": "choice-a", "name": "Identity A"},
                    {"id": "choice-b", "name": "Identity B"},
                ]
            ),
            LoginResult(tokens=TOKENS, account_id="real-account-b", title="Parro"),
        ]
    )
    with (
        patch("custom_components.parro.config_flow.async_login", login),
        patch("custom_components.parro.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
        assert result["step_id"] == "account"
        assert not hass.config_entries.async_entries("parro")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"account_id": "choice-b"}
        )
        await hass.async_block_till_done()
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "real-account-b"
    assert login.call_args.kwargs["account_id"] == "choice-b"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ParroAuthError("private upstream body"), "invalid_auth"),
        (ParroConnectionError("private upstream URL"), "cannot_connect"),
        (ParroError("private unexpected payload"), "unsupported_response"),
    ],
)
async def test_auth_failure_safe_error_and_retry(hass, error, reason):
    result = await start(hass)
    with patch("custom_components.parro.config_flow.async_login", side_effect=error):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": reason}
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert flow._credentials == {}
    assert flow._accounts == []
    assert "private" not in str(result)


async def test_duplicate_uses_account_id_not_email(hass, config_entry):
    config_entry.add_to_hass(hass)
    result = await start(hass)
    with patch(
        "custom_components.parro.config_flow.async_login",
        return_value=LoginResult(
            tokens=TOKENS, account_id="acct-1", title="Different display name"
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries("parro")) == 1


@pytest.mark.parametrize("account_id", ["acct-1", "other-account"])
async def test_reauth_validates_real_account(hass, config_entry, account_id):
    config_entry.add_to_hass(hass)
    old_data = dict(config_entry.data)
    result = await hass.config_entries.flow.async_init(
        "parro",
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": config_entry.entry_id},
        data=dict(config_entry.data),
    )
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "user"
    with (
        patch(
            "custom_components.parro.config_flow.async_login",
            return_value=LoginResult(tokens=TOKENS, account_id=account_id, title="Parro"),
        ),
        patch.object(hass.config_entries, "async_reload", return_value=True) as reload,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
        await hass.async_block_till_done()
    if account_id == "acct-1":
        assert result["reason"] == "reauth_successful"
        assert config_entry.data["tokens"] == TOKENS
        reload.assert_awaited_once()
    else:
        assert result["reason"] == "unique_id_mismatch"
        assert config_entry.data == old_data
        reload.assert_not_called()


@pytest.mark.parametrize("interval", [15, 30, 240])
async def test_poll_options(hass, config_entry, interval):
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"poll_interval": interval}
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert config_entry.options["poll_interval"] == interval


@pytest.mark.parametrize("interval", [0, 14, 241, "invalid"])
async def test_poll_options_reject_outside_bounds(hass, config_entry, interval):
    import voluptuous as vol

    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    with pytest.raises(vol.Invalid):
        result["data_schema"]({"poll_interval": interval})
