from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from aiotransperth import PERTH_TZ, InvalidStopError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from custom_components.transperth.const import DOMAIN
from custom_components.transperth.services import resolve_reference_time


def test_resolve_reference_time_shapes() -> None:
    assert resolve_reference_time(None).tzinfo is PERTH_TZ
    exact = resolve_reference_time("2026-07-08 09:30")
    assert exact == datetime(2026, 7, 8, 9, 30, tzinfo=PERTH_TZ)
    hhmm = resolve_reference_time("23:59")
    now = datetime.now(tz=PERTH_TZ)
    assert hhmm >= now - timedelta(minutes=1)  # never in the past
    with pytest.raises(ValueError):
        resolve_reference_time("not a time")


async def _setup_domain(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_get_bus_schedule_service(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup_domain(hass)
    response = await hass.services.async_call(
        DOMAIN,
        "get_bus_schedule",
        {"stop_code": "12627", "bus_number": "414"},
        blocking=True,
        return_response=True,
    )
    assert response["stop_name"] == "Main St After Royal St"
    assert [t["time"] for t in response["times"]] == ["08:12", "08:25"]


async def test_get_train_departures_service(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup_domain(hass)
    response = await hass.services.async_call(
        DOMAIN,
        "get_train_departures",
        {"line": "Midland Line", "station": "Maylands Stn"},
        blocking=True,
        return_response=True,
    )
    assert response["departures"][0]["destination"] == "Perth"


async def test_get_bus_stops_service(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup_domain(hass)
    response = await hass.services.async_call(
        DOMAIN,
        "get_bus_stops",
        {"bus_number": "414"},
        blocking=True,
        return_response=True,
    )
    assert response["bus_number"] == "414"
    assert response["direction"] == "outbound"
    assert response["stops"][0] == {
        "code": "29720",
        "name": "Stirling Stn Stand B",
        "time": "08:05",
        "can_board": True,
        "can_alight": False,
    }


async def test_get_bus_stops_no_trips_raises_validation_error(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup_domain(hass)
    mock_client.get_route_trips.return_value = ()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "get_bus_stops",
            {"bus_number": "999"},
            blocking=True,
            return_response=True,
        )


async def test_invalid_stop_raises_service_validation_error(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    await _setup_domain(hass)
    mock_client.get_stop_timetable.side_effect = InvalidStopError("nope")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "get_bus_departures",
            {"stop_code": "00000"},
            blocking=True,
            return_response=True,
        )
