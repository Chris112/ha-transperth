from datetime import datetime, timedelta
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

PERTH_0800_UTC = datetime.fromisoformat("2026-07-07T00:00:00+00:00")


async def test_time_to_leave_flips_at_threshold(
    hass: HomeAssistant,
    mock_client: MagicMock,
    bus_entry: MockConfigEntry,
    freezer,
) -> None:
    freezer.move_to(PERTH_0800_UTC)  # 08:00 Perth; 414 estimated 08:12, walk 5
    bus_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(bus_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "binary_sensor.main_st_after_royal_st_12627_time_to_leave_for_the_414"
    state = hass.states.get(entity_id)
    assert state is not None and state.state == "off"  # threshold is 08:07

    freezer.move_to(PERTH_0800_UTC + timedelta(minutes=8))  # 08:08 Perth
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"


async def test_train_journey_gets_time_to_leave(
    hass: HomeAssistant,
    mock_client: MagicMock,
    journey_entry: MockConfigEntry,
    freezer,
) -> None:
    # City-bound train at 08:10, walk 5 → threshold 08:05.
    freezer.move_to(PERTH_0800_UTC)
    journey_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(journey_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "binary_sensor.maylands_perth_time_to_leave_for_perth"
    state = hass.states.get(entity_id)
    assert state is not None and state.state == "off"

    freezer.move_to(PERTH_0800_UTC + timedelta(minutes=6))  # 08:06 Perth
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"


async def test_station_entry_has_no_time_to_leave(
    hass: HomeAssistant, mock_client: MagicMock, train_entry: MockConfigEntry
) -> None:
    # Without a direction, a walk time can't mean anything.
    train_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(train_entry.entry_id)
    await hass.async_block_till_done()
    assert not [
        e for e in hass.states.async_entity_ids("binary_sensor") if "maylands" in e
    ]
