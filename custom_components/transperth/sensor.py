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
from .const import (
    BOARD_SIZE,
    CONF_DESTINATIONS,
    CONF_MODE,
    CONF_ROUTES,
    MODE_BUS,
)
from .coordinator import BusCoordinator, TrainCoordinator
from .entity import TransperthEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TransperthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    if entry.data[CONF_MODE] == MODE_BUS:
        assert isinstance(coordinator, BusCoordinator)
        entities.append(BusNextDepartureSensor(coordinator))
        entities.append(BusDepartureBoardSensor(coordinator))
        entities.extend(
            BusRouteSensor(coordinator, route)
            for route in entry.options.get(CONF_ROUTES, [])
        )
    else:
        assert isinstance(coordinator, TrainCoordinator)
        entities.append(TrainNextDepartureSensor(coordinator))
        entities.append(TrainDepartureBoardSensor(coordinator))
        entities.extend(
            TrainDestinationSensor(coordinator, dest)
            for dest in entry.options.get(CONF_DESTINATIONS, [])
        )
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
    _attr_name = "Next departure"

    def __init__(self, coordinator: BusCoordinator) -> None:
        super().__init__(coordinator, "next_departure")

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
        TransperthEntity.__init__(self, coordinator, f"route_{route}_next")
        self._route = route
        self._attr_name = f"Next {route}"

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


class TrainNextDepartureSensor(TransperthEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Next departure"

    def __init__(self, coordinator: TrainCoordinator) -> None:
        super().__init__(coordinator, "next_departure")

    def _departure(self) -> TrainDeparture | None:
        departures = self.coordinator.data
        return departures[0] if departures else None

    @property
    def native_value(self) -> datetime | None:
        dep = self._departure()
        return (dep.estimated or dep.scheduled) if dep else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        dep = self._departure()
        return _train_attrs(dep) if dep else None


class TrainDestinationSensor(TrainNextDepartureSensor):
    def __init__(self, coordinator: TrainCoordinator, destination: str) -> None:
        TransperthEntity.__init__(
            self, coordinator, f"dest_{slugify(destination)}_next"
        )
        self._destination = destination
        self._attr_name = f"Next train to {destination}"

    def _departure(self) -> TrainDeparture | None:
        for dep in self.coordinator.data:
            if dep.destination == self._destination:
                return dep
        return None


class TrainDepartureBoardSensor(TransperthEntity, SensorEntity):
    _attr_name = "Departures"

    def __init__(self, coordinator: TrainCoordinator) -> None:
        super().__init__(coordinator, "departures")

    @property
    def native_value(self) -> str | None:
        departures = self.coordinator.data
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
                for dep in self.coordinator.data[:BOARD_SIZE]
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
