"""Sensor platform for Synsynk Solar Inverter."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SENSOR_DESCRIPTIONS, SynsynkSensorEntityDescription
from .coordinator import SynsynkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SynsynkCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SynsynkSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SynsynkSensor(SensorEntity):
    """A sensor sourced from the Synsynk solar status file."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SynsynkCoordinator,
        entry: ConfigEntry,
        description: SynsynkSensorEntityDescription,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self.entity_description: SynsynkSensorEntityDescription = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._unsubscribe: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        self._unsubscribe = self._coordinator.async_add_listener(
            self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()

    @property
    def available(self) -> bool:
        return self.entity_description.json_key in self._coordinator.data.get(
            self.entity_description.category, {}
        )

    @property
    def native_value(self) -> float | str | None:
        return self._coordinator.data.get(self.entity_description.category, {}).get(
            self.entity_description.json_key
        )

    @property
    def device_info(self) -> DeviceInfo:
        inverter_id = self._coordinator.data.get("Inverter", {}).get("Inverter ID")
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Synsynk Solar Inverter",
            manufacturer="Synsynk",
            model=inverter_id,
        )
