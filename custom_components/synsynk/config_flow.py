"""Config flow for Synsynk Solar Inverter."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_FILE_PATH, DEFAULT_FILE_PATH, DOMAIN

_STEP_SCHEMA = vol.Schema(
    {vol.Required(CONF_FILE_PATH, default=DEFAULT_FILE_PATH): str}
)


class SynsynkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            file_path = user_input[CONF_FILE_PATH].strip()
            parent = Path(file_path).parent

            if not parent.is_dir():
                errors[CONF_FILE_PATH] = "invalid_path"
            else:
                await self.async_set_unique_id(file_path)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Synsynk ({Path(file_path).name})",
                    data={CONF_FILE_PATH: file_path},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_SCHEMA,
            errors=errors,
        )
