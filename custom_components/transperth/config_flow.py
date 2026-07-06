"""Config flow for Transperth."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from aiotransperth import (
    InvalidStopError,
    RateLimitError,
    Stop,
    TransperthClient,
    TransperthError,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_MODE,
    CONF_ROUTES,
    CONF_STOP_CODE,
    CONF_STOP_NAME,
    CONF_WALK_MINUTES,
    DOMAIN,
    MODE_BUS,
)


class TransperthConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a bus stop or train station."""

    VERSION = 1

    def __init__(self) -> None:
        self._stop: Stop | None = None
        self._routes: list[str] = []

    def _client(self) -> TransperthClient:
        return TransperthClient(session=async_get_clientsession(self.hass))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["bus", "train"])

    async def async_step_bus(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            code = str(user_input[CONF_STOP_CODE]).strip()
            try:
                timetable = await self._client().get_stop_timetable(code)
            except InvalidStopError:
                errors["base"] = "invalid_stop"
            except RateLimitError:
                errors["base"] = "rate_limited"
            except TransperthError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"bus_{timetable.stop.code}")
                self._abort_if_unique_id_configured()
                self._stop = timetable.stop
                self._routes = sorted({d.route for d in timetable.departures})
                return await self.async_step_bus_tracking()
        return self.async_show_form(
            step_id="bus",
            data_schema=vol.Schema({vol.Required(CONF_STOP_CODE): str}),
            errors=errors,
        )

    async def async_step_bus_tracking(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._stop is not None
        if user_input is not None:
            return self.async_create_entry(
                title=f"{self._stop.name} ({self._stop.code})",
                data={
                    CONF_MODE: MODE_BUS,
                    CONF_STOP_CODE: self._stop.code,
                    CONF_STOP_NAME: self._stop.name,
                },
                options={
                    CONF_ROUTES: user_input.get(CONF_ROUTES, []),
                    CONF_WALK_MINUTES: int(user_input.get(CONF_WALK_MINUTES, 0)),
                },
            )
        schema = vol.Schema(
            {
                vol.Optional(CONF_ROUTES, default=[]): SelectSelector(
                    SelectSelectorConfig(options=self._routes, multiple=True)
                ),
                vol.Optional(CONF_WALK_MINUTES, default=0): NumberSelector(
                    NumberSelectorConfig(min=0, max=60, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="bus_tracking", data_schema=schema)

    async def async_step_train(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_abort(reason="not_implemented")  # replaced in Task 4
