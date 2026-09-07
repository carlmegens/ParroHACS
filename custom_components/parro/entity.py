"""Shared entity identity without school or account names."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ParroCoordinator


class ParroEntity(CoordinatorEntity[ParroCoordinator]):
    """One generic device per configured account."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ParroCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Parro",
            manufacturer="Parro",
            model="School account",
            entry_type=DeviceEntryType.SERVICE,
        )
