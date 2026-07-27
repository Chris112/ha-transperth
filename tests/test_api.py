import asyncio
from contextlib import suppress
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from aiotransperth import RateLimitError, TransperthError
from homeassistant.core import HomeAssistant

from custom_components.transperth.api import (
    DATA_TRAIN_CACHE,
    async_shared_client,
    async_train_departures,
)
from custom_components.transperth.const import TRAIN_CACHE_TTL

from .conftest import TRAINS

LINE = "Midland Line"
STATION = "Maylands Stn"


def _blocking_fetch(mock_client: MagicMock) -> tuple[asyncio.Event, asyncio.Event]:
    """Hold get_train_departures open so callers can pile up behind it."""
    started, release = asyncio.Event(), asyncio.Event()

    async def _slow(line: str, station: str) -> tuple:
        started.set()
        await release.wait()
        return TRAINS

    mock_client.get_train_departures.side_effect = _slow
    return started, release


async def test_shared_client_is_reused(hass: HomeAssistant) -> None:
    assert async_shared_client(hass) is async_shared_client(hass)


async def test_callers_arriving_mid_flight_join_the_same_request(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    started, release = _blocking_fetch(mock_client)

    first = asyncio.create_task(async_train_departures(hass, LINE, STATION))
    await started.wait()
    second = asyncio.create_task(async_train_departures(hass, LINE, STATION))
    await asyncio.sleep(0)
    release.set()

    assert (await first).departures == TRAINS
    assert (await second).departures == TRAINS
    assert mock_client.get_train_departures.call_count == 1


async def test_the_shared_window_expires(
    hass: HomeAssistant, mock_client: MagicMock, freezer
) -> None:
    await async_train_departures(hass, LINE, STATION)

    freezer.tick(TRAIN_CACHE_TTL - timedelta(seconds=1))
    await async_train_departures(hass, LINE, STATION)
    assert mock_client.get_train_departures.call_count == 1

    freezer.tick(timedelta(seconds=2))
    await async_train_departures(hass, LINE, STATION)
    assert mock_client.get_train_departures.call_count == 2


async def test_a_clock_step_backwards_does_not_freeze_the_window(
    hass: HomeAssistant, mock_client: MagicMock, freezer
) -> None:
    # dt_util.utcnow() is wall clock, so an NTP correction can move it
    # backwards. That must expire the window, not extend it indefinitely.
    await async_train_departures(hass, LINE, STATION)

    freezer.tick(-timedelta(minutes=10))
    await async_train_departures(hass, LINE, STATION)
    assert mock_client.get_train_departures.call_count == 2


async def test_a_cancelled_caller_leaves_the_shared_fetch_alone(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    # Reloading one entry cancels its refresh mid-flight. The other journeys
    # boarding at that station are waiting on the same request and must not be
    # dragged down with it.
    started, release = _blocking_fetch(mock_client)

    leaver = asyncio.create_task(async_train_departures(hass, LINE, STATION))
    await started.wait()
    stayer = asyncio.create_task(async_train_departures(hass, LINE, STATION))
    await asyncio.sleep(0)

    leaver.cancel()
    with suppress(asyncio.CancelledError):
        await leaver
    release.set()

    assert (await stayer).departures == TRAINS


async def test_a_cancelled_fetch_is_not_served_to_the_next_caller(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    # Shutdown cancels the shared task itself. A cancelled task is done, so
    # without a guard the next caller inside the window inherits its corpse.
    started, release = _blocking_fetch(mock_client)

    caller = asyncio.create_task(async_train_departures(hass, LINE, STATION))
    await started.wait()
    hass.data[DATA_TRAIN_CACHE][(LINE, STATION)][1].cancel()
    with suppress(asyncio.CancelledError):
        await caller

    release.set()
    mock_client.get_train_departures.side_effect = None
    assert (await async_train_departures(hass, LINE, STATION)).departures == TRAINS


async def test_a_rate_limit_is_shared_rather_than_asked_again(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    # Every entry at the station is equally blocked, and Transperth's cooldown
    # is sticky — asking again on their behalf only feeds it.
    mock_client.get_train_departures.side_effect = RateLimitError("429")

    for _ in range(2):
        with pytest.raises(RateLimitError):
            await async_train_departures(hass, LINE, STATION)

    assert mock_client.get_train_departures.call_count == 1


async def test_a_transient_failure_is_retried_rather_than_served(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    mock_client.get_train_departures.side_effect = TransperthError("bad payload")
    with pytest.raises(TransperthError):
        await async_train_departures(hass, LINE, STATION)

    mock_client.get_train_departures.side_effect = None
    assert (await async_train_departures(hass, LINE, STATION)).departures == TRAINS
    assert mock_client.get_train_departures.call_count == 2


async def test_a_shared_result_reports_when_it_was_fetched(
    hass: HomeAssistant, mock_client: MagicMock, freezer
) -> None:
    # The second caller is handed data half a minute old; saying so is the
    # difference between an honest freshness reading and a fabricated one.
    first = await async_train_departures(hass, LINE, STATION)

    freezer.tick(timedelta(seconds=30))
    second = await async_train_departures(hass, LINE, STATION)

    assert second.at == first.at


async def test_forgetting_a_station_drops_its_cached_fetch(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    from custom_components.transperth.api import async_forget_train_departures

    await async_train_departures(hass, LINE, STATION)
    async_forget_train_departures(hass, LINE, STATION)

    await async_train_departures(hass, LINE, STATION)
    assert mock_client.get_train_departures.call_count == 2
