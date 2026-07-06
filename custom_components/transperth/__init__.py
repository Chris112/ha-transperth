"""The Transperth integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_MODE, MODE_BUS
from .coordinator import BusCoordinator, TrainCoordinator, TransperthCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type TransperthConfigEntry = ConfigEntry[TransperthCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TransperthConfigEntry) -> bool:
    coordinator: TransperthCoordinator
    if entry.data[CONF_MODE] == MODE_BUS:
        coordinator = BusCoordinator(hass, entry)
    else:
        coordinator = TrainCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: TransperthConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TransperthConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
