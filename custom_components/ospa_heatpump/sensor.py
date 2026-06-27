"""Sensor entities for O Spa Heat Pump."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OspaCoordinator


@dataclass(frozen=True, kw_only=True)
class OspaSensorDescription(SensorEntityDescription):
    section: str = ""
    data_key: str = ""


SENSOR_DESCRIPTIONS: tuple[OspaSensorDescription, ...] = (
    OspaSensorDescription(
        key="coil_temp",
        name="Coil Temperature",
        section="temperatures",
        data_key="coil_temp_c",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OspaSensorDescription(
        key="exhaust_temp",
        name="Exhaust Temperature",
        section="temperatures",
        data_key="exhaust_temp_c",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OspaSensorDescription(
        key="ambient_temp",
        name="Ambient Temperature",
        section="temperatures",
        data_key="ambient_temp_c",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OspaSensorDescription(
        key="work_state",
        name="Work State",
        section="system",
        data_key="work_state",
    ),
    OspaSensorDescription(
        key="fault_bitmap",
        name="Fault Code",
        section="system",
        data_key="fault_bitmap",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OspaSensorDescription(
        key="eev_step_count",
        name="EEV Step Count",
        section="diagnostics",
        data_key="eev_step_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OspaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        OspaSensor(coordinator, entry, desc) for desc in SENSOR_DESCRIPTIONS
    )


class OspaSensor(CoordinatorEntity[OspaCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OspaCoordinator,
        entry: ConfigEntry,
        description: OspaSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.entity_description: OspaSensorDescription = description
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
    def native_value(self) -> float | str | int | None:
        desc = self.entity_description
        return self.coordinator.data.get(desc.section, {}).get(desc.data_key)
