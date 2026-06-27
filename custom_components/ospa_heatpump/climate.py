"""Climate entity for O Spa Heat Pump."""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DP_MODE,
    DP_POWER,
    DP_TARGET_TEMP,
    TEMP_SCALE,
    TUYA_MODE_COOLING,
    TUYA_MODE_HEATING,
)
from .coordinator import OspaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OspaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OspaClimate(coordinator, entry)])


class OspaClimate(CoordinatorEntity[OspaCoordinator], ClimateEntity):
    """Climate entity representing the heat pump."""

    _attr_has_entity_name = True
    _attr_name = None  # Use the device name as the entity name
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 10.0
    _attr_max_temp = 45.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: OspaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_climate"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="O Spa Heat Pump",
            manufacturer="O Spa",
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and "system" in self.coordinator.data
            and "temperatures" in self.coordinator.data
        )

    @property
    def hvac_mode(self) -> HVACMode | None:
        system = self.coordinator.data.get("system", {})
        if not system.get("power_on", False):
            return HVACMode.OFF
        mode = system.get("mode", "")
        if mode == TUYA_MODE_HEATING:
            return HVACMode.HEAT
        if mode == TUYA_MODE_COOLING:
            return HVACMode.COOL
        return HVACMode.HEAT  # fallback for unknown mode strings

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.get("temperatures", {}).get("current_temp_c")

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.get("temperatures", {}).get("target_temp_c")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_dps({DP_POWER: False})
        elif hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_set_dps(
                {DP_POWER: True, DP_MODE: TUYA_MODE_HEATING}
            )
        elif hvac_mode == HVACMode.COOL:
            await self.coordinator.async_set_dps(
                {DP_POWER: True, DP_MODE: TUYA_MODE_COOLING}
            )

    async def async_set_temperature(self, **kwargs) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            raw = int(round(float(temp) * TEMP_SCALE))
            await self.coordinator.async_set_dps({DP_TARGET_TEMP: raw})
