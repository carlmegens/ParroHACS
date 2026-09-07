"""Bounded, on-demand read actions for Parro."""

from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import ParroAuthError, ParroConnectionError, ParroError
from .const import DEFAULT_LIMIT, DOMAIN, MAX_LIMIT

SERVICES = ("get_announcements", "get_chatrooms", "get_messages", "get_calendar_urls")


def _limit(value: Any) -> int:
    """Require a genuine integer, excluding booleans and silent truncation."""
    if type(value) is not int or not 1 <= value <= MAX_LIMIT:
        raise vol.Invalid(f"limit must be an integer between 1 and {MAX_LIMIT}")
    return value


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register response-only actions even before an account has been loaded."""
    for name in SERVICES:
        schema = {
            vol.Required("config_entry_id"): cv.string,
            vol.Optional("limit", default=DEFAULT_LIMIT): _limit,
        }
        if name == "get_messages":
            schema[vol.Required("chatroom_id")] = vol.All(
                cv.string,
                vol.Match(r"\A[0-9]{1,20}\Z"),
                vol.Coerce(int),
                vol.Range(min=1),
                vol.Coerce(str),
            )
        # These actions expose private school content without an entity target.
        # Use HA's administrator check; trusted automations remain supported.
        async_register_admin_service(
            hass,
            DOMAIN,
            name,
            partial(_async_read, hass, name),
            schema=vol.Schema(schema),
            supports_response=SupportsResponse.ONLY,
        )


async def _async_read(hass: HomeAssistant, name: str, call: ServiceCall) -> dict[str, Any]:
    """Route only a validated, loaded Parro account to its adapter."""
    entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="account_not_loaded"
        )
    coordinator = entry.runtime_data
    limit = call.data["limit"]
    try:
        method = getattr(coordinator.api, f"async_{name}")
        if name == "get_messages":
            items = await method(chatroom_id=call.data["chatroom_id"], limit=limit)
        else:
            items = await method(limit=limit)
    except ParroAuthError:
        coordinator.async_set_update_error(ConfigEntryAuthFailed("Parro sign-in has expired"))
        entry.async_start_reauth(hass)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="authentication_expired"
        ) from None
    except ParroConnectionError:
        coordinator.async_set_update_error(UpdateFailed("Unable to reach Parro"))
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from None
    except ParroError:
        coordinator.async_set_update_error(UpdateFailed("Parro returned an unsupported response"))
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="unsupported_response"
        ) from None
    # The adapter bounds upstream requests too. Keep the response contract bounded
    # even if a server ignores its page-size parameter.
    items = items[:limit]
    return {"items": items, "returned": len(items), "limit": limit}
