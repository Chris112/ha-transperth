"""Data update coordinators: one per config entry."""

from __future__ import annotations

from datetime import datetime, timedelta

from aiotransperth import (
    RateLimitError,
    StopTimetable,
    TrainDeparture,
    TransperthError,
    is_known_journey,
    serves_journey,
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
    RATE_LIMIT_BACKOFF_MAX,
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
        self._backoff: timedelta | None = None

    async def _fetch(self) -> T:
        raise NotImplementedError

    def _next_backoff(self) -> timedelta:
        """Double the wait each consecutive 429, starting from our interval."""
        previous = self._backoff or self.update_interval or RATE_LIMIT_BACKOFF_MAX
        self._backoff = min(previous * 2, RATE_LIMIT_BACKOFF_MAX)
        return self._backoff

    async def _async_update_data(self) -> T:
        try:
            data = await self._fetch()
        except RateLimitError as err:
            self.rate_limited = True
            backoff = self._next_backoff()
            LOGGER.debug(
                "Rate limited by Transperth; next %s poll in %s",
                self.name,
                backoff,
            )
            raise UpdateFailed(
                f"Transperth rate limit: {err}",
                retry_after=backoff.total_seconds(),
            ) from err
        except TransperthError as err:
            self.rate_limited = False
            raise UpdateFailed(f"Transperth error: {err}") from err
        self.rate_limited = False
        self._backoff = None
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

    def departures_towards(self, target: str) -> tuple[TrainDeparture, ...]:
        """Departures that actually carry you to `target`, soonest first.

        Falls back to every departure when the ordering table doesn't know
        both stations — the network occasionally gains one before the table is
        regenerated, and showing too much beats showing nothing.
        """
        line = self.config_entry.data[CONF_LINE]
        station = self.config_entry.data[CONF_STATION]
        if not is_known_journey(line, station, target):
            LOGGER.debug(
                "No station ordering for %s → %s on %s; not filtering by direction",
                station,
                target,
                line,
            )
            return self.data
        return tuple(
            dep
            for dep in self.data
            if serves_journey(line, station, dep.destination, target)
        )


TransperthCoordinator = BusCoordinator | TrainCoordinator
