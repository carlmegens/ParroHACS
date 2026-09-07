"""Serve the bundled card and register its own dashboard resource."""

import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import CARD_PATH, CARD_VERSION

_LOGGER = logging.getLogger(__name__)
CARD_URL = f"{CARD_PATH}?v={CARD_VERSION}"


async def async_register_resource(hass: HomeAssistant) -> None:
    """Update only this bundled card's resource, through HA's collection API."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None or lovelace.resource_mode != MODE_STORAGE:
        return
    resources = lovelace.resources
    try:
        await resources.async_get_info()
        existing = []
        for item in resources.async_items():
            url = urlsplit(item.get("url", ""))
            if not url.scheme and not url.netloc and url.path == CARD_PATH:
                existing.append(item)
        for item in existing:
            if item.get("url") != CARD_URL or item.get("type") != "module":
                await resources.async_update_item(
                    item["id"], {"url": CARD_URL, "res_type": "module"}
                )
        if not existing:
            await resources.async_create_item({"url": CARD_URL, "res_type": "module"})
    except Exception:
        # A card-resource problem must not break the account connection.
        _LOGGER.warning(
            "Parro card resource could not be registered; add it in dashboard resources"
        )


async def async_setup_frontend(hass: HomeAssistant) -> None:
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_PATH, str(Path(__file__).parent / "frontend" / "parro-card.js"), False
            )
        ]
    )
    async_at_started(hass, async_register_resource)
