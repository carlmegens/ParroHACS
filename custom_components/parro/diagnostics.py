"""Diagnostics contain an explicit allowlist of operational metadata only."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
from .coordinator import ParroCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[ParroCoordinator]
) -> dict[str, Any]:
    """Never serialize the entry, tokens, API responses, or exception text."""
    coordinator = getattr(entry, "runtime_data", None)
    return {
        "entry_state": entry.state.value,
        "poll_interval_minutes": entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        "last_update_success": coordinator.last_update_success if coordinator else None,
        "last_success": (
            coordinator.last_success.isoformat()
            if coordinator and coordinator.last_success is not None
            else None
        ),
    }
