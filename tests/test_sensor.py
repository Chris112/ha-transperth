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


async def test_train_next_and_destination_sensors(
    hass: HomeAssistant, mock_client: MagicMock, train_entry: MockConfigEntry
) -> None:
    await _setup(hass, train_entry)
    nxt = hass.states.get("sensor.maylands_stn_midland_line_next_departure")
    assert nxt is not None and nxt.state == "2026-07-07T00:10:00+00:00"
    assert nxt.attributes["platform"] == "1"
    assert nxt.attributes["cars"] == 4
    to_perth = hass.states.get(
        "sensor.maylands_stn_midland_line_next_train_to_perth"
    )
    assert to_perth is not None and to_perth.state == "2026-07-07T00:10:00+00:00"
    board = hass.states.get("sensor.maylands_stn_midland_line_departures")
    assert board is not None and board.state == "08:10"
    assert board.attributes["departures"][1]["destination"] == "Midland"


async def test_status_sensor_reports_rate_limit(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    from aiotransperth import RateLimitError

    await _setup(hass, bus_entry)
    entity_id = "sensor.main_st_after_royal_st_12627_status"
    state = hass.states.get(entity_id)
    assert state is not None and state.attributes["rate_limited"] is False

    mock_client.get_stop_timetable.side_effect = RateLimitError("429")
    await bus_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["rate_limited"] is True
