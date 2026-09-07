"""Keep only compact account counters in the coordinator."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ParroApi, ParroAuthError, ParroConnectionError, ParroError
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
        self.last_success = None

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self.feed.async_close()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.async_fetch_summary()
        except ParroAuthError as err:
            raise ConfigEntryAuthFailed("Parro sign-in has expired") from err
        except ParroConnectionError as err:
            raise UpdateFailed("Unable to reach Parro") from err
        except ParroError as err:
            raise UpdateFailed("Parro returned an unsupported response") from err
        self.last_success = dt_util.utcnow()
        return data
