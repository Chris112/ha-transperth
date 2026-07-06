"""Data update coordinators: one per config entry."""

from __future__ import annotations

from datetime import datetime, timedelta

from aiotransperth import (
    RateLimitError,
    StopTimetable,
    TrainDeparture,
    TransperthError,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import async_shared_client
from .const import (
    BUS_SCAN_INTERVAL,
    CONF_LINE,
    CONF_STATION,
    CONF_STOP_CODE,
    LOGGER,
    TRAIN_SCAN_INTERVAL,
)


class _BaseCoordinator[T](DataUpdateCoordinator[T]):
    """Shared client + failure bookkeeping."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, interval: timedelta
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )
        self.client = async_shared_client(hass)
        self.rate_limited = False
        self.last_success: datetime | None = None

    async def _fetch(self) -> T:
        raise NotImplementedError

    async def _async_update_data(self) -> T:
        try:
            data = await self._fetch()
        except RateLimitError as err:
            self.rate_limited = True
            raise UpdateFailed(f"Transperth rate limit: {err}") from err
        except TransperthError as err:
            self.rate_limited = False
            raise UpdateFailed(f"Transperth error: {err}") from err
        self.rate_limited = False
        self.last_success = dt_util.utcnow()
        return data


class BusCoordinator(_BaseCoordinator[StopTimetable]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, BUS_SCAN_INTERVAL)

    async def _fetch(self) -> StopTimetable:
        return await self.client.get_stop_timetable(
            self.config_entry.data[CONF_STOP_CODE]
        )


class TrainCoordinator(_BaseCoordinator[tuple[TrainDeparture, ...]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, TRAIN_SCAN_INTERVAL)

    async def _fetch(self) -> tuple[TrainDeparture, ...]:
        return await self.client.get_train_departures(
            self.config_entry.data[CONF_LINE], self.config_entry.data[CONF_STATION]
        )


TransperthCoordinator = BusCoordinator | TrainCoordinator
