"""Register the bundled device popup, account panel and optional dashboard card."""

import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import CARD_PATH, CARD_VERSION

_LOGGER = logging.getLogger(__name__)
CARD_URL = f"{CARD_PATH}?v={CARD_VERSION}"


def _is_own_url(value: str) -> bool:
    """Match only this integration's local JavaScript path."""
    url = urlsplit(value)
    return not url.scheme and not url.netloc and url.path == CARD_PATH


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
            if _is_own_url(item.get("url", "")):
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


async def async_register_interfaces(hass: HomeAssistant) -> None:
    """Load device dialogs without visiting a dashboard and keep options intact."""
    # after_dependencies orders us after the frontend when it is configured.
    # Headless HA installations still get sensors and the authenticated API.
    modules = hass.data.get(frontend.DATA_EXTRA_MODULE_URL)
    if modules is not None:
        try:
            for url in modules.urls:
                if _is_own_url(url) and url != CARD_URL:
                    frontend.remove_extra_js_url(hass, url)
            if CARD_URL not in modules.urls:
                frontend.add_extra_js_url(hass, CARD_URL)

            existing = hass.data.get(frontend.DATA_PANELS, {}).get("parro")
            if existing is not None:
                config = (existing.config or {}).get("_panel_custom", {})
                if (
                    existing.component_name != "custom"
                    or config.get("name") != "parro-panel"
                    or not _is_own_url(config.get("module_url", ""))
                ):
                    _LOGGER.warning("Parro account panel path is already in use")
                    await async_register_resource(hass)
                    return
                if config.get("module_url") != CARD_URL:
                    frontend.async_remove_panel(hass, "parro")
                    existing = None
            if existing is None:
                await panel_custom.async_register_panel(
                    hass,
                    frontend_url_path="parro",
                    webcomponent_name="parro-panel",
                    module_url=CARD_URL,
                )
        except Exception:
            # Never log exception text that may contain unrelated panel data.
            _LOGGER.warning("Parro device interface could not be registered")
    await async_register_resource(hass)


async def async_setup_frontend(hass: HomeAssistant) -> None:
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_PATH, str(Path(__file__).parent / "frontend" / "parro-card.js"), False
            )
        ]
    )
    await async_register_interfaces(hass)
    async_at_started(hass, async_register_interfaces)
