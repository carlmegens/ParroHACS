"""Expose polling failures as a connectivity state."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ParroCoordinator
from .entity import ParroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ParroCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the connectivity entity."""
    async_add_entities([ParroConnectivitySensor(entry.runtime_data, entry)])


class ParroConnectivitySensor(ParroEntity, BinarySensorEntity):
    """Remain available so a failed request is shown as disconnected."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ParroCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "connectivity")

    @property
    def available(self) -> bool:
        """The connection status itself is always observable."""
        return True

    @property
    def is_on(self) -> bool:
        """A successful summary poll restores the connection state."""
        return self.coordinator.last_update_success
