"""Keep only compact account counters in the coordinator."""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ParroApi, ParroAuthError, ParroConnectionError, ParroError
from .chat_feed import ParroChatFeed
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .feed import ParroFeed

_LOGGER = logging.getLogger(__name__)


class ParroCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """One poll for counters, with an independent in-memory dashboard feed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: ParroApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                minutes=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            ),
        )
        self.api = api
        self.feed = ParroFeed(hass, api)
        self.chat_feed = ParroChatFeed(hass, api)
        self.last_success = None
        self.content_auth_failed = False

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self.feed.async_close()
        await self.chat_feed.async_close()

    async def async_invalidate_auth(self) -> None:
        """Withhold both content sources until reauthentication reloads this entry."""
        self.content_auth_failed = True
        # Closing sets each store's flag before waiting for active reads. Those
        # reads cannot repopulate it, and HTTP/WS post-checks withhold their result.
        await asyncio.gather(self.feed.async_close(), self.chat_feed.async_close())

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.async_fetch_summary()
        except ParroAuthError as err:
            await self.async_invalidate_auth()
            raise ConfigEntryAuthFailed("Parro sign-in has expired") from err
        except ParroConnectionError as err:
            raise UpdateFailed("Unable to reach Parro") from err
        except ParroError as err:
            raise UpdateFailed("Parro returned an unsupported response") from err
        self.last_success = dt_util.utcnow()
        return data
