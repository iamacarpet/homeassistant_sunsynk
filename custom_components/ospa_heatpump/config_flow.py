"""Config flow for O Spa Heat Pump."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_URL, DEFAULT_URL, DOMAIN

_STEP_SCHEMA = vol.Schema(
    {vol.Required(CONF_URL, default=DEFAULT_URL): str}
)


class OspaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            parsed = urlparse(url)

            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                errors[CONF_URL] = "invalid_url"
            else:
                session = async_get_clientsession(self.hass)
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        resp.raise_for_status()
                except Exception:
                    errors[CONF_URL] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"O Spa Heat Pump ({parsed.hostname})",
                    data={CONF_URL: url},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_SCHEMA,
            errors=errors,
        )
