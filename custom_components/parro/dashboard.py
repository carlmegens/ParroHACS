"""Authenticated, per-account dashboard reads without private sensor attributes."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.auth.models import User
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv

from .api import ParroAuthError, ParroConnectionError, ParroError
from .const import (
    CONF_DASHBOARD_VIEWERS,
    DEFAULT_FEED_LIMIT,
    DOMAIN,
    MAX_FEED_LIMIT,
)

_LOGGER = logging.getLogger(__name__)
_PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def _positive_id(value: str) -> str:
    if int(value) <= 0:
        raise vol.Invalid("Invalid group")
    return value


_GROUP = vol.All(cv.string, vol.Match(r"\A[0-9]{1,20}\Z"), _positive_id)


def _limit(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_FEED_LIMIT:
        raise vol.Invalid("Invalid limit")
    return value


class DashboardError(Exception):
    """A finite client-facing error with no upstream text."""

    def __init__(self, code: str, status: int = 502) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@callback
def can_view(entry: ConfigEntry, user: User | None) -> bool:
    """Allow administrators and explicitly selected active viewers of this account."""
    return bool(
        user
        and user.is_active
        and (user.is_admin or user.id in entry.options.get(CONF_DASHBOARD_VIEWERS, []))
    )


async def _entry_for_user(hass: HomeAssistant, entry_id: str, user_id: str) -> ConfigEntry:
    user = await hass.auth.async_get_user(user_id)
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or not can_view(entry, user):
        raise DashboardError("unauthorized", 403)
    if entry.state is not ConfigEntryState.LOADED:
        raise DashboardError("not_loaded", 503)
    return entry


async def _read_feed(
    hass: HomeAssistant, entry_id: str, user_id: str, limit: int, group_id: str | None
) -> dict[str, Any]:
    entry = await _entry_for_user(hass, entry_id, user_id)
    coordinator = entry.runtime_data
    try:
        result = await coordinator.feed.async_get_feed(limit=limit, group_id=group_id)
    except ParroAuthError:
        coordinator.async_set_update_error(ConfigEntryAuthFailed("Parro requires sign-in"))
        entry.async_start_reauth(hass)
        raise DashboardError("authentication_expired", 503) from None
    except ParroConnectionError:
        raise DashboardError("cannot_connect", 503) from None
    except ParroError:
        raise DashboardError("unsupported_response") from None
    except Exception:
        _LOGGER.error("Parro dashboard read failed")
        raise DashboardError("unsupported_response") from None
    # Options, account loading and the user can change while an upstream read waits.
    current = await _entry_for_user(hass, entry_id, user_id)
    if current is not entry or current.runtime_data is not coordinator:
        raise DashboardError("not_loaded", 503)
    return result


@callback
@websocket_api.websocket_command({vol.Required("type"): "parro/accounts"})
@websocket_api.async_response
async def websocket_accounts(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    """Only disclose identities the requesting user may view."""
    user = await hass.auth.async_get_user(connection.user.id)
    connection.send_result(
        msg["id"],
        {
            "accounts": [
                {"config_entry_id": entry.entry_id, "title": entry.title or "Parro"}
                for entry in hass.config_entries.async_entries(DOMAIN)
                if can_view(entry, user)
            ]
        },
    )


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "parro/feed",
        vol.Required("config_entry_id"): cv.string,
        vol.Optional("limit", default=DEFAULT_FEED_LIMIT): _limit,
        vol.Optional("group_id"): _GROUP,
    }
)
@websocket_api.async_response
async def websocket_feed(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    try:
        result = await _read_feed(
            hass, msg["config_entry_id"], connection.user.id, msg["limit"], msg.get("group_id")
        )
    except DashboardError as err:
        connection.send_error(msg["id"], err.code, "Parro could not provide this view")
    else:
        connection.send_result(msg["id"], result)


class ParroFeedView(HomeAssistantView):
    """The same bounded feed for authenticated server-side consumers."""

    url = "/api/parro/{config_entry_id}/feed"
    name = "api:parro:feed"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, config_entry_id: str) -> web.Response:
        try:
            if set(request.query) - {"limit", "group_id"}:
                raise ValueError
            if (
                len(request.query.getall("limit", [])) > 1
                or len(request.query.getall("group_id", [])) > 1
            ):
                raise ValueError
            limit = _limit(int(request.query.get("limit", str(DEFAULT_FEED_LIMIT))))
            group_id = _GROUP(request.query["group_id"]) if "group_id" in request.query else None
        except ValueError, vol.Invalid:
            return self.json({"code": "invalid_request"}, 400, headers=_PRIVATE_HEADERS)
        user = request.get("hass_user")
        if user is None:
            return self.json({"code": "unauthorized"}, 401, headers=_PRIVATE_HEADERS)
        try:
            result = await _read_feed(self.hass, config_entry_id, user.id, limit, group_id)
        except DashboardError as err:
            return self.json({"code": err.code}, err.status, headers=_PRIVATE_HEADERS)
        return self.json(result, headers=_PRIVATE_HEADERS)


class ParroImageView(HomeAssistantView):
    """Proxy opaque image handles; never accept a URL from a caller."""

    url = "/api/parro/{config_entry_id}/image/{media_id}"
    name = "api:parro:image"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, config_entry_id: str, media_id: str) -> web.Response:
        user = request.get("hass_user")
        if user is None:
            return self.json({"code": "unauthorized"}, 401, headers=_PRIVATE_HEADERS)
        try:
            entry = await _entry_for_user(self.hass, config_entry_id, user.id)
            coordinator = entry.runtime_data
            try:
                data, content_type = await coordinator.feed.async_get_image(media_id)
            except ParroConnectionError:
                raise DashboardError("cannot_connect", 503) from None
            except ParroError:
                raise DashboardError("image_unavailable", 404) from None
            except Exception:
                _LOGGER.error("Parro dashboard image could not be loaded")
                raise DashboardError("image_unavailable", 502) from None
            current = await _entry_for_user(self.hass, config_entry_id, user.id)
            if current is not entry or current.runtime_data is not coordinator:
                raise DashboardError("not_loaded", 503)
        except DashboardError as err:
            return self.json({"code": err.code}, err.status, headers=_PRIVATE_HEADERS)
        return web.Response(body=data, content_type=content_type, headers=_PRIVATE_HEADERS)


@callback
def async_register_dashboard(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, websocket_accounts)
    websocket_api.async_register_command(hass, websocket_feed)
    hass.http.register_view(ParroFeedView(hass))
    hass.http.register_view(ParroImageView(hass))
