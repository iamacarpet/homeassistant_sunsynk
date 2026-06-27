"""Switch entities for O Spa Heat Pump."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DP_ELEC_HEAT, DP_POWER
from .coordinator import OspaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OspaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        OspaPowerSwitch(coordinator, entry),
        OspaElecHeatSwitch(coordinator, entry),
    ])


class OspaPowerSwitch(CoordinatorEntity[OspaCoordinator], SwitchEntity):
    """Master power switch (DP 1)."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: OspaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_power"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    @property
    def available(self) -> bool:
        return super().available and "system" in self.coordinator.data

    @property
    def is_on(self) -> bool:
        return bool(
            self.coordinator.data.get("system", {}).get("power_on", False)
        )

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_dps({DP_POWER: True})

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_dps({DP_POWER: False})


class OspaElecHeatSwitch(CoordinatorEntity[OspaCoordinator], SwitchEntity):
    """Switch for the manual electric heater element."""

    _attr_has_entity_name = True
    _attr_name = "Electric Heater"
    _attr_icon = "mdi:heating-coil"

    def __init__(self, coordinator: OspaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_elec_heat"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    @property
    def available(self) -> bool:
        return super().available and "components" in self.coordinator.data

    @property
    def is_on(self) -> bool:
        return bool(
            self.coordinator.data.get("components", {}).get("elec_heat_active", False)
        )

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_dps({DP_ELEC_HEAT: True})

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_dps({DP_ELEC_HEAT: False})
