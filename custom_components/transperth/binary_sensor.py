"""Time-to-leave binary sensors.

Buses track a route; trains track a journey, which is why a train entry only
gets one once it names where it is going.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from aiotransperth import BusDeparture, TrainDeparture
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from . import TransperthConfigEntry
from .const import CONF_ROUTES, CONF_WALK_MINUTES
from .coordinator import BusCoordinator, TrainCoordinator, TransperthCoordinator
from .entity import TransperthEntity
from .journey import journey_target, short_name

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransperthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    walk = int(entry.options.get(CONF_WALK_MINUTES, 0))
    if isinstance(coordinator, BusCoordinator):
        async_add_entities(
            BusTimeToLeaveBinarySensor(coordinator, route, walk)
            for route in entry.options.get(CONF_ROUTES, [])
        )
        return
    target = journey_target(entry)
    if target is not None:
        async_add_entities([TrainTimeToLeaveBinarySensor(coordinator, target, walk)])


class _TimeToLeaveBinarySensor(TransperthEntity, BinarySensorEntity):
    """Flips punctually at `departure - walk`, not on the next poll."""

    def __init__(
        self, coordinator: TransperthCoordinator, key: str, walk_minutes: int
    ) -> None:
        super().__init__(coordinator, key)
        self._walk = timedelta(minutes=walk_minutes)
        self._unsub_timer: Callable[[], None] | None = None

    def _departure(self) -> BusDeparture | TrainDeparture | None:
        raise NotImplementedError

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


class BusTimeToLeaveBinarySensor(_TimeToLeaveBinarySensor):
    def __init__(
        self, coordinator: BusCoordinator, route: str, walk_minutes: int
    ) -> None:
        super().__init__(coordinator, f"route_{route}_leave", walk_minutes)
        self._route = route
        self._attr_name = f"Time to leave for the {route}"

    def _departure(self) -> BusDeparture | None:
        for dep in self.coordinator.data.departures:
            if dep.route == self._route:
                return dep
        return None


class TrainTimeToLeaveBinarySensor(_TimeToLeaveBinarySensor):
    def __init__(
        self, coordinator: TrainCoordinator, target: str, walk_minutes: int
    ) -> None:
        super().__init__(coordinator, "leave", walk_minutes)
        self._target = target
        self._attr_name = f"Time to leave for {short_name(target)}"

    def _departure(self) -> TrainDeparture | None:
        departures = self.coordinator.departures_towards(self._target)
        return departures[0] if departures else None
