"""Power-user services: ad-hoc queries for unconfigured places."""

from __future__ import annotations

from datetime import datetime, timedelta

import voluptuous as vol
from aiotransperth import (
    PERTH_TZ,
    InvalidStopError,
    RateLimitError,
    TransperthError,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .api import async_shared_client
from .const import DOMAIN


def resolve_reference_time(at: str | None) -> datetime:
    """None -> now; 'HH:MM' -> next occurrence (rolls to tomorrow);
    'YYYY-MM-DD HH:MM' -> exact moment. Always Australia/Perth-aware."""
    if not at:
        return datetime.now(tz=PERTH_TZ)
    text = str(at).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=PERTH_TZ)
        except ValueError:
            continue
    try:
        parsed = datetime.strptime(text, "%H:%M")
    except ValueError:
        raise ValueError(
            f"Invalid time {at!r}. Use 'HH:MM' or 'YYYY-MM-DD HH:MM'."
        ) from None
    now = datetime.now(tz=PERTH_TZ)
    candidate = now.replace(
        hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0
    )
    if candidate < now:
        candidate += timedelta(days=1)
    return candidate


def _reference(call: ServiceCall) -> datetime:
    try:
        return resolve_reference_time(call.data.get("at"))
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def _stop_departures(call: ServiceCall) -> dict:
        when = _reference(call)
        client = async_shared_client(hass)
        try:
            tt = await client.get_stop_timetable(call.data["stop_code"], when=when)
        except InvalidStopError as err:
            raise ServiceValidationError(str(err)) from err
        except RateLimitError as err:
            raise HomeAssistantError(f"Rate limited: {err}") from err
        except TransperthError as err:
            raise HomeAssistantError(str(err)) from err
        return {
            "stop_name": tt.stop.name,
            "departures": [
                {
                    "route": d.route,
                    "destination": d.destination,
                    "time": f"{(d.estimated or d.scheduled):%H:%M}",
                    "delay_minutes": d.delay_minutes,
                    "is_live": d.live.is_live,
                }
                for d in tt.departures
            ],
        }

    async def get_bus_departures(call: ServiceCall) -> ServiceResponse:
        return await _stop_departures(call)

    async def get_bus_schedule(call: ServiceCall) -> ServiceResponse:
        base = await _stop_departures(call)
        route = call.data["bus_number"]
        return {
            "stop_name": base["stop_name"],
            "bus_number": route,
            "times": [d for d in base["departures"] if d["route"] == route],
        }

    async def get_bus_stops(call: ServiceCall) -> ServiceResponse:
        when = _reference(call)
        client = async_shared_client(hass)
        try:
            trips = await client.get_route_trips(call.data["bus_number"], when=when)
            if not trips:
                raise ServiceValidationError(
                    f"No upcoming trips for bus {call.data['bus_number']}"
                )
            stops = await client.get_trip_stops(trips[0])
        except RateLimitError as err:
            raise HomeAssistantError(f"Rate limited: {err}") from err
        except TransperthError as err:
            raise HomeAssistantError(str(err)) from err
        return {
            "bus_number": call.data["bus_number"],
            "direction": trips[0].direction,
            "stops": [
                {
                    "code": s.code,
                    "name": s.name,
                    "time": s.time,
                    "can_board": s.can_board,
                    "can_alight": s.can_alight,
                }
                for s in stops
            ],
        }

    async def get_train_departures(call: ServiceCall) -> ServiceResponse:
        try:
            deps = await async_shared_client(hass).get_train_departures(
                call.data["line"], call.data["station"]
            )
        except InvalidStopError as err:
            raise ServiceValidationError(str(err)) from err
        except RateLimitError as err:
            raise HomeAssistantError(f"Rate limited: {err}") from err
        except TransperthError as err:
            raise HomeAssistantError(str(err)) from err
        return {
            "departures": [
                {
                    "destination": d.destination,
                    "platform": d.platform,
                    "time": f"{(d.estimated or d.scheduled):%H:%M}",
                    "delay_minutes": d.delay_minutes,
                    "status": d.live.description,
                }
                for d in deps
            ]
        }

    for name, handler, schema in (
        (
            "get_bus_departures",
            get_bus_departures,
            vol.Schema({vol.Required("stop_code"): str, vol.Optional("at"): str}),
        ),
        (
            "get_bus_schedule",
            get_bus_schedule,
            vol.Schema(
                {
                    vol.Required("stop_code"): str,
                    vol.Required("bus_number"): str,
                    vol.Optional("at"): str,
                }
            ),
        ),
        (
            "get_bus_stops",
            get_bus_stops,
            vol.Schema({vol.Required("bus_number"): str, vol.Optional("at"): str}),
        ),
        (
            "get_train_departures",
            get_train_departures,
            vol.Schema({vol.Required("line"): str, vol.Required("station"): str}),
        ),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema,
            supports_response=SupportsResponse.ONLY,
        )
