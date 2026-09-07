"""Unofficial, read-only Parro integration."""

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .api import ParroApi
from .const import CONF_ACCOUNT_ID, CONF_POLL_INTERVAL, CONF_TOKENS, DEFAULT_POLL_INTERVAL
from .coordinator import ParroCoordinator
from .dashboard import async_register_dashboard
from .frontend import async_setup_frontend
from .services import async_register_services

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
type ParroConfigEntry = ConfigEntry[ParroCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_register_services(hass)
    async_register_dashboard(hass)
    await async_setup_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ParroConfigEntry) -> bool:
    @callback
    def save_tokens(tokens: dict[str, Any]) -> None:
        if tokens != entry.data.get(CONF_TOKENS):
            hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_TOKENS: tokens})

    api = ParroApi(hass, entry.data[CONF_TOKENS], entry.data[CONF_ACCOUNT_ID], save_tokens)
    coordinator = ParroCoordinator(hass, entry, api)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_shutdown()
        await api.async_close()
        raise

    async def async_stop(_event: Event) -> None:
        await coordinator.async_shutdown()
        await api.async_close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ParroConfigEntry) -> None:
    """Apply changed polling options; persisting tokens must never reload the entry."""
    coordinator = entry.runtime_data
    interval = timedelta(minutes=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
    if interval != coordinator.update_interval:
        coordinator.update_interval = interval
        await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ParroConfigEntry) -> bool:
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        await entry.runtime_data.api.async_close()
    return unloaded
