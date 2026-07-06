from unittest.mock import MagicMock

from aiotransperth import RateLimitError
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


async def test_rate_limit_marks_coordinator(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    await _setup(hass, bus_entry)
    coordinator = bus_entry.runtime_data
    mock_client.get_stop_timetable.side_effect = RateLimitError("429")
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.rate_limited is True
