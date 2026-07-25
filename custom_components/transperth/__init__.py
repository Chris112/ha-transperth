"""The Transperth integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DESTINATIONS, CONF_MODE, DOMAIN, LOGGER, MODE_BUS
from .coordinator import BusCoordinator, TrainCoordinator, TransperthCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TransperthConfigEntry = ConfigEntry[TransperthCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: TransperthConfigEntry
) -> bool:
    """Drop the tracked-destinations option that version 2 replaced.

    Train entries predating direction filtering keep working: without a
    destination station they simply report both ways along the line.
    """
    if entry.version == 1:
        options = {k: v for k, v in entry.options.items() if k != CONF_DESTINATIONS}
        hass.config_entries.async_update_entry(entry, options=options, version=2)
        LOGGER.debug("Migrated %s to version 2", entry.title)
    return True


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
