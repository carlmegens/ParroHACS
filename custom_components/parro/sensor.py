"""Compact counters and the last successful summary synchronization."""

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ParroCoordinator
from .entity import ParroEntity

SENSORS = (
    SensorEntityDescription(key="children_count", translation_key="children_count"),
    SensorEntityDescription(key="groups_count", translation_key="groups_count"),
    SensorEntityDescription(key="unread_announcements", translation_key="unread_announcements"),
    SensorEntityDescription(key="unread_chatrooms", translation_key="unread_chatrooms"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ParroCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the account's fixed, content-free sensors."""
    async_add_entities(
        [ParroCountSensor(entry.runtime_data, entry, description) for description in SENSORS]
        + [ParroLastSuccessSensor(entry.runtime_data, entry)]
    )


class ParroCountSensor(ParroEntity, SensorEntity):
    """Represent an available count; missing data remains unknown."""

    def __init__(
        self,
        coordinator: ParroCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description
        source = {
            "unread_announcements": "announcements",
            "unread_chatrooms": "messages",
        }.get(description.key)
        if source:
            # HA's existing more-info hook receives only routing metadata. The
            # component obtains private content through the authenticated API.
            self._attr_extra_state_attributes = {
                "custom_ui_more_info": "more-info-parro",
                "parro_config_entry_id": entry.entry_id,
                "parro_source": source,
            }

    @property
    def native_value(self) -> int | None:
        """Return only a count, never raw response data."""
        value = (self.coordinator.data or {}).get(self.entity_description.key)
        return value if type(value) is int and value >= 0 else None


class ParroLastSuccessSensor(ParroEntity, SensorEntity):
    """Keep the previous successful timestamp visible during an outage."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_available = True

    def __init__(self, coordinator: ParroCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "last_success")

    @property
    def available(self) -> bool:
        """A failed later poll does not invalidate the historical timestamp."""
        return True

    @property
    def native_value(self) -> datetime | None:
        """Return the last successful summary poll."""
        return self.coordinator.last_success
