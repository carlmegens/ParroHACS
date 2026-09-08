"""Set up Parro through Home Assistant, without saving a password."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import (
    ParroAccountSelectionRequired,
    ParroAuthError,
    ParroConnectionError,
    ParroError,
    ParroLoginFlowError,
    async_login,
)
from .const import (
    CONF_ACCOUNT_ID,
    CONF_CHAT_VIEWERS,
    CONF_DASHBOARD_VIEWERS,
    CONF_POLL_INTERVAL,
    CONF_TOKENS,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class ParroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Authenticate and explicitly choose an identity when needed."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, str] = {}
        self._accounts: list[dict[str, str]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._credentials = {
                CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            return await self._async_authenticate()
        return self._login_form(errors)

    def _login_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def _async_authenticate(self, account_id: str | None = None) -> ConfigFlowResult:
        try:
            result = await async_login(
                self.hass,
                self._credentials[CONF_USERNAME],
                self._credentials[CONF_PASSWORD],
                account_id=account_id,
            )
        except ParroAccountSelectionRequired as err:
            self._accounts = err.accounts
            return await self.async_step_account()
        except ParroLoginFlowError as err:
            _LOGGER.warning("Parro sign-in could not finish (%s)", err.reason)
            error = "login_flow_failed"
        except ParroAuthError:
            error = "invalid_auth"
        except ParroConnectionError:
            error = "cannot_connect"
        except ParroError:
            error = "unsupported_response"
        else:
            self._credentials.clear()
            self._accounts.clear()
            await self.async_set_unique_id(result.account_id)
            data = {CONF_ACCOUNT_ID: result.account_id, CONF_TOKENS: result.tokens}
            if self.source == config_entries.SOURCE_REAUTH:
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=data
                )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=result.title or "Parro", data=data)

        self._credentials.clear()
        self._accounts.clear()
        return self._login_form({"base": error})

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._credentials or not self._accounts:
            return self.async_abort(reason="session_expired")
        accounts = {str(item["id"]): item["name"] for item in self._accounts}
        if user_input is not None:
            account_id = user_input[CONF_ACCOUNT_ID]
            if account_id in accounts:
                return await self._async_authenticate(account_id)
        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema({vol.Required(CONF_ACCOUNT_ID): vol.In(accounts)}),
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "ParroOptionsFlow":
        return ParroOptionsFlow()


class ParroOptionsFlow(config_entries.OptionsFlow):
    """Configure polling and explicit read access to the account dashboard."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        users = [
            user
            for user in await self.hass.auth.async_get_users()
            if user.is_active and not user.is_admin and not user.system_generated
        ]
        user_ids = {user.id for user in users}
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            for key in (CONF_DASHBOARD_VIEWERS, CONF_CHAT_VIEWERS):
                viewers = user_input.get(key, [])
                if not isinstance(viewers, list) or any(
                    viewer not in user_ids for viewer in viewers
                ):
                    errors[key] = "invalid_viewers"
                else:
                    data[key] = list(dict.fromkeys(viewers))
            if not errors:
                return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)
                    ),
                    **{
                        vol.Optional(
                            key,
                            default=[
                                viewer
                                for viewer in self.config_entry.options.get(key, [])
                                if viewer in user_ids
                            ],
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    {"value": user.id, "label": user.name or user.id}
                                    for user in users
                                ],
                                multiple=True,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                            )
                        )
                        for key in (CONF_DASHBOARD_VIEWERS, CONF_CHAT_VIEWERS)
                    },
                }
            ),
            errors=errors,
        )
