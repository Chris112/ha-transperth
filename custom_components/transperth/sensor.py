"""Sensors: next departures, departure boards, diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiotransperth import BusDeparture, TrainDeparture
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import TransperthConfigEntry
from .const import BOARD_SIZE, CONF_ROUTES
from .coordinator import BusCoordinator, TrainCoordinator
from .entity import TransperthEntity
from .journey import journey_target, short_name, tracked_directions

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransperthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    if isinstance(coordinator, BusCoordinator):
        entities.append(BusNextDepartureSensor(coordinator))
        entities.append(BusDepartureBoardSensor(coordinator))
        entities.extend(
            BusRouteSensor(coordinator, route)
            for route in entry.options.get(CONF_ROUTES, [])
        )
    else:
        target = journey_target(entry)
        if target is not None:
            # The device is already named "A → B", so the entity needn't be.
            entities.append(TrainDirectionSensor(coordinator, target, "next_train"))
            entities.append(TrainDepartureBoardSensor(coordinator, target))
        else:
            entities.extend(
                TrainDirectionSensor(
                    coordinator,
                    endpoint,
                    f"towards_{slugify(endpoint)}",
                    name=f"Next train towards {short_name(endpoint)}",
                )
                for endpoint in tracked_directions(entry)
            )
            entities.append(TrainDepartureBoardSensor(coordinator))
    entities.append(StatusSensor(coordinator))
    async_add_entities(entities)


class StatusSensor(TransperthEntity, SensorEntity):
    """Last successful update + rate-limit flag; reports even while the API is down."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Status"

    def __init__(self, coordinator: BusCoordinator | TrainCoordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"rate_limited": self.coordinator.rate_limited}


def _bus_attrs(dep: BusDeparture) -> dict[str, Any]:
    return {
        "route": dep.route,
        "destination": dep.destination,
        "delay_minutes": dep.delay_minutes,
        "is_live": dep.live.is_live,
    }


class BusNextDepartureSensor(TransperthEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: BusCoordinator,
        key: str = "next_departure",
        name: str = "Next departure",
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name

    def _departure(self) -> BusDeparture | None:
        departures = self.coordinator.data.departures
        return departures[0] if departures else None

    @property
    def native_value(self) -> datetime | None:
        dep = self._departure()
        return (dep.estimated or dep.scheduled) if dep else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        dep = self._departure()
        return _bus_attrs(dep) if dep else None


class BusRouteSensor(BusNextDepartureSensor):
    def __init__(self, coordinator: BusCoordinator, route: str) -> None:
        super().__init__(coordinator, f"route_{route}_next", f"Next {route}")
        self._route = route

    def _departure(self) -> BusDeparture | None:
        for dep in self.coordinator.data.departures:
            if dep.route == self._route:
                return dep
        return None


def _train_attrs(dep: TrainDeparture) -> dict[str, Any]:
    return {
        "destination": dep.destination,
        "platform": dep.platform,
        "cars": dep.cars,
        "delay_minutes": dep.delay_minutes,
        "is_live": dep.live.is_live,
    }


class TrainDirectionSensor(TransperthEntity, SensorEntity):
    """The next train from here that actually reaches `target`."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: TrainCoordinator,
        target: str,
        key: str,
        name: str = "Next train",
    ) -> None:
        super().__init__(coordinator, key)
        self._target = target
        self._attr_name = name

    def _departure(self) -> TrainDeparture | None:
        departures = self.coordinator.departures_towards(self._target)
        return departures[0] if departures else None

    @property
    def native_value(self) -> datetime | None:
        dep = self._departure()
        return (dep.estimated or dep.scheduled) if dep else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        dep = self._departure()
        return _train_attrs(dep) if dep else None


class TrainDepartureBoardSensor(TransperthEntity, SensorEntity):
    """Upcoming trains — filtered to the journey when the entry has one."""

    _attr_name = "Departures"

    def __init__(
        self, coordinator: TrainCoordinator, target: str | None = None
    ) -> None:
        super().__init__(coordinator, "departures")
        self._target = target

    def _departures(self) -> tuple[TrainDeparture, ...]:
        if self._target is None:
            return self.coordinator.data
        return self.coordinator.departures_towards(self._target)

    @property
    def native_value(self) -> str | None:
        departures = self._departures()
        if not departures:
            return None
        dep = departures[0]
        return f"{(dep.estimated or dep.scheduled):%H:%M}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "departures": [
                {
                    "destination": dep.destination,
                    "platform": dep.platform,
                    "time": f"{(dep.estimated or dep.scheduled):%H:%M}",
                    "delay_minutes": dep.delay_minutes,
                    "is_live": dep.live.is_live,
                }
                for dep in self._departures()[:BOARD_SIZE]
            ]
        }


class BusDepartureBoardSensor(TransperthEntity, SensorEntity):
    _attr_name = "Departures"

    def __init__(self, coordinator: BusCoordinator) -> None:
        super().__init__(coordinator, "departures")

    @property
    def native_value(self) -> str | None:
        departures = self.coordinator.data.departures
        if not departures:
            return None
        dep = departures[0]
        return f"{(dep.estimated or dep.scheduled):%H:%M}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "departures": [
                {
                    "route": dep.route,
                    "destination": dep.destination,
                    "time": f"{(dep.estimated or dep.scheduled):%H:%M}",
                    "delay_minutes": dep.delay_minutes,
                    "is_live": dep.live.is_live,
                }
                for dep in self.coordinator.data.departures[:BOARD_SIZE]
            ]
        }
