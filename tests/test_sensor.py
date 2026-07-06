from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_bus_next_departure_uses_estimate(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    await _setup(hass, bus_entry)
    state = hass.states.get("sensor.main_st_after_royal_st_12627_next_departure")
    assert state is not None
    assert state.state == "2026-07-07T00:12:00+00:00"  # 08:12 Perth == 00:12 UTC
    assert state.attributes["route"] == "414"
    assert state.attributes["delay_minutes"] == 2
    assert state.attributes["is_live"] is True


async def test_bus_route_sensor_filters(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    await _setup(hass, bus_entry)
    state = hass.states.get("sensor.main_st_after_royal_st_12627_next_414")
    assert state is not None and state.state == "2026-07-07T00:12:00+00:00"


async def test_departure_board(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    await _setup(hass, bus_entry)
    state = hass.states.get("sensor.main_st_after_royal_st_12627_departures")
    assert state is not None and state.state == "08:12"
    board = state.attributes["departures"]
    assert len(board) == 3
    assert board[1] == {
        "route": "402",
        "destination": "Perth Busport",
        "time": "08:15",
        "delay_minutes": None,
        "is_live": False,
    }
