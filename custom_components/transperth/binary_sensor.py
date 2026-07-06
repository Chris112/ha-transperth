"""Time-to-leave binary sensors (bus entries only)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from aiotransperth import BusDeparture
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from . import TransperthConfigEntry
from .const import CONF_MODE, CONF_ROUTES, CONF_WALK_MINUTES, MODE_BUS
from .coordinator import BusCoordinator
from .entity import TransperthEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransperthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    if entry.data[CONF_MODE] != MODE_BUS:
        return
    coordinator = entry.runtime_data
    assert isinstance(coordinator, BusCoordinator)
    walk = int(entry.options.get(CONF_WALK_MINUTES, 0))
    async_add_entities(
        TimeToLeaveBinarySensor(coordinator, route, walk)
        for route in entry.options.get(CONF_ROUTES, [])
    )


class TimeToLeaveBinarySensor(TransperthEntity, BinarySensorEntity):
    def __init__(
        self, coordinator: BusCoordinator, route: str, walk_minutes: int
    ) -> None:
        super().__init__(coordinator, f"route_{route}_leave")
        self._route = route
        self._walk = timedelta(minutes=walk_minutes)
        self._attr_name = f"Time to leave for the {route}"
        self._unsub_timer: Callable[[], None] | None = None

    def _departure(self) -> BusDeparture | None:
        for dep in self.coordinator.data.departures:
            if dep.route == self._route:
                return dep
        return None

    def _threshold(self) -> datetime | None:
        dep = self._departure()
        if dep is None:
            return None
        return (dep.estimated or dep.scheduled) - self._walk

    @property
    def is_on(self) -> bool:
        threshold = self._threshold()
        return threshold is not None and dt_util.now() >= threshold

    @callback
    def _schedule_flip(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        threshold = self._threshold()
        if threshold is not None and threshold > dt_util.now():
            self._unsub_timer = async_track_point_in_time(
                self.hass, self._handle_flip, threshold
            )

    @callback
    def _handle_flip(self, _now: datetime) -> None:
        self._unsub_timer = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._schedule_flip()
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._schedule_flip()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
