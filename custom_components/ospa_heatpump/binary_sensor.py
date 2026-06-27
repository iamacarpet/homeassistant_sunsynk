"""Binary sensor entities for O Spa Heat Pump."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OspaCoordinator


@dataclass(frozen=True, kw_only=True)
class OspaBinarySensorDescription(BinarySensorEntityDescription):
    section: str = ""
    data_key: str = ""


BINARY_SENSOR_DESCRIPTIONS: tuple[OspaBinarySensorDescription, ...] = (
    OspaBinarySensorDescription(
        key="compressor_active",
        name="Compressor",
        section="components",
        data_key="compressor_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    OspaBinarySensorDescription(
        key="fan_active",
        name="Fan",
        section="components",
        data_key="fan_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    OspaBinarySensorDescription(
        key="water_pump_active",
        name="Water Pump",
        section="components",
        data_key="water_pump_active",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    OspaBinarySensorDescription(
        key="defrost_active",
        name="Defrost",
        section="components",
        data_key="defrost_active",
    ),
    OspaBinarySensorDescription(
        key="four_way_valve",
        name="Four-Way Valve",
        section="components",
        data_key="four_way_valve",
    ),
    OspaBinarySensorDescription(
        key="antifreeze_active",
        name="Antifreeze",
        section="components",
        data_key="antifreeze_active",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OspaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        OspaBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class OspaBinarySensor(CoordinatorEntity[OspaCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OspaCoordinator,
        entry: ConfigEntry,
        description: OspaBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.entity_description: OspaBinarySensorDescription = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    @property
    def available(self) -> bool:
        desc = self.entity_description
        return (
            super().available
            and desc.data_key in self.coordinator.data.get(desc.section, {})
        )

    @property
    def is_on(self) -> bool:
        desc = self.entity_description
        return bool(
            self.coordinator.data.get(desc.section, {}).get(desc.data_key, False)
        )
