"""Sensor platform (populated in a later task)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry,  # type: ignore[no-untyped-def]
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities (added in later tasks)."""
