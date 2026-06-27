"""Coordinator for O Spa Heat Pump — polls the bridge HTTP service."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OspaCoordinator(DataUpdateCoordinator[dict]):
    """Polls GET / on the bridge and exposes async_set_dps for write commands."""

    def __init__(self, hass: HomeAssistant, url: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.url = url

    async def _async_update_data(self) -> dict:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                self.url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
        except Exception as err:
            raise UpdateFailed(f"Error fetching data from bridge: {err}") from err

        status = payload.get("status", "unknown")
        if status not in ("online", "reconnecting"):
            raise UpdateFailed(f"Bridge reports device status: {status}")

        return payload.get("data", {})

    async def async_set_dps(self, dps: dict) -> None:
        """POST a write command to the bridge service then request a refresh."""
        set_url = self.url.rstrip("/") + "/set"
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                set_url,
                json={"dps": dps},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
        except Exception as err:
            _LOGGER.error("Failed to send set command %s: %s", dps, err)
            raise

        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        pass
