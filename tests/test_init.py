from unittest.mock import MagicMock

from aiotransperth import RateLimitError, TransperthError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_bus_entry_sets_up_and_unloads(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    await _setup(hass, bus_entry)
    assert bus_entry.state is ConfigEntryState.LOADED
    assert bus_entry.runtime_data.data.stop.code == "12627"
    assert await hass.config_entries.async_unload(bus_entry.entry_id)
    assert bus_entry.state is ConfigEntryState.NOT_LOADED


async def test_train_entry_sets_up(
    hass: HomeAssistant, mock_client: MagicMock, train_entry: MockConfigEntry
) -> None:
    await _setup(hass, train_entry)
    assert train_entry.state is ConfigEntryState.LOADED
    assert train_entry.runtime_data.data[0].destination == "Perth"


async def test_version_1_entry_migrates_and_keeps_working(
    hass: HomeAssistant, mock_client: MagicMock, legacy_train_entry: MockConfigEntry
) -> None:
    await _setup(hass, legacy_train_entry)
    assert legacy_train_entry.state is ConfigEntryState.LOADED
    assert legacy_train_entry.version == 2
    # The tracked-destinations option is gone; the entry now reports both ways.
    assert "destinations" not in legacy_train_entry.options
    assert (
        hass.states.get("sensor.maylands_stn_midland_line_next_train_towards_perth")
        is not None
    )


async def test_rate_limit_marks_coordinator(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    await _setup(hass, bus_entry)
    coordinator = bus_entry.runtime_data
    mock_client.get_stop_timetable.side_effect = RateLimitError("429")
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.rate_limited is True


async def test_rate_limit_backs_off_and_recovers(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    # Transperth sends no Retry-After and its cooldown is sticky, so polling
    # straight through a 429 just feeds it. Each consecutive one waits longer.
    await _setup(hass, bus_entry)
    coordinator = bus_entry.runtime_data
    mock_client.get_stop_timetable.side_effect = RateLimitError("429")

    waits = []
    for _ in range(6):
        await coordinator.async_refresh()
        waits.append(coordinator.last_exception.retry_after)

    # Doubling from the bus interval (120s), capped at 15 minutes.
    assert waits == [240.0, 480.0, 900.0, 900.0, 900.0, 900.0]

    # A success clears it, so a later blip starts from the short wait again.
    mock_client.get_stop_timetable.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.rate_limited is False

    mock_client.get_stop_timetable.side_effect = RateLimitError("429")
    await coordinator.async_refresh()
    assert coordinator.last_exception.retry_after == 240.0


async def test_other_errors_do_not_trigger_backoff(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    # Only 429 means "you are asking too often"; a parse failure doesn't.
    await _setup(hass, bus_entry)
    coordinator = bus_entry.runtime_data
    mock_client.get_stop_timetable.side_effect = TransperthError("bad payload")
    await coordinator.async_refresh()
    assert coordinator.last_exception.retry_after is None
    assert coordinator.rate_limited is False
