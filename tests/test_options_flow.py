from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.transperth.const import (
    CONF_ROUTES,
    CONF_WALK_MINUTES,
)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_bus_options_update(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    await _setup(hass, bus_entry)
    result = await hass.config_entries.options.async_init(bus_entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "bus"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ROUTES: ["402", "414"], CONF_WALK_MINUTES: 7}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert bus_entry.options == {CONF_ROUTES: ["402", "414"], CONF_WALK_MINUTES: 7}


async def test_journey_options_set_walk_time(
    hass: HomeAssistant, mock_client: MagicMock, journey_entry: MockConfigEntry
) -> None:
    await _setup(hass, journey_entry)
    result = await hass.config_entries.options.async_init(journey_entry.entry_id)
    assert result["step_id"] == "train"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WALK_MINUTES: 9}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert journey_entry.options == {CONF_WALK_MINUTES: 9}


async def test_station_entry_has_nothing_to_configure(
    hass: HomeAssistant, mock_client: MagicMock, train_entry: MockConfigEntry
) -> None:
    await _setup(hass, train_entry)
    result = await hass.config_entries.options.async_init(train_entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_options"
