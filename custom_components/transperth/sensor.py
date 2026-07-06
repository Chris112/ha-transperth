"""Sensors: next departures, departure boards, diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiotransperth import BusDeparture
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TransperthConfigEntry
from .const import BOARD_SIZE, CONF_MODE, CONF_ROUTES, MODE_BUS
from .coordinator import BusCoordinator
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
    async_add_entities(entities)


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
