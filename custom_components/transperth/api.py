"""One shared aiotransperth client per Home Assistant instance.

Transperth's rate-limit cooldown is sticky and shared with their public
website, and every fresh client re-scrapes a CSRF token page before its
first bus call. One shared client keeps the token and train-catalog
caches warm across coordinators, config flows, and services.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import NamedTuple

from aiotransperth import RateLimitError, TrainDeparture, TransperthClient
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TRAIN_CACHE_TTL

DATA_CLIENT = f"{DOMAIN}_client"
DATA_TRAIN_CACHE = f"{DOMAIN}_train_departures"

type _Departures = tuple[TrainDeparture, ...]
type _Shared = tuple[datetime, asyncio.Task[_Departures]]


class TrainFetch(NamedTuple):
    """Departures, plus when Transperth actually served them.

    Sharing means a caller can be handed data most of a cycle old, so `at` is
    the only honest answer to "how fresh is this?" — see coordinator's
    `last_success`, which the Status entity reports verbatim.
    """

    at: datetime
    departures: _Departures


@callback
def async_shared_client(hass: HomeAssistant) -> TransperthClient:
    """Return the instance-wide client, creating it on first use."""
    if DATA_CLIENT not in hass.data:
        hass.data[DATA_CLIENT] = TransperthClient(session=async_get_clientsession(hass))
    return hass.data[DATA_CLIENT]


def _servable(task: asyncio.Task[_Departures], age: timedelta) -> bool:
    """Whether a finished fetch may stand in for a fresh one.

    `age` is measured on the wall clock, so an NTP correction can make it
    negative; that expires the window rather than extending it forever.
    """
    if task.cancelled() or not timedelta() <= age < TRAIN_CACHE_TTL:
        return False
    exc = task.exception()
    # A 429 blocks every entry at the station equally, and the cooldown is
    # sticky — asking again on the next one's behalf only feeds it, so the
    # rejection is shared like a result. Other failures are one-offs.
    return exc is None or isinstance(exc, RateLimitError)


async def async_train_departures(
    hass: HomeAssistant, line: str, station: str
) -> TrainFetch:
    """Live departures at a station, shared by every entry boarding there.

    What Transperth returns depends only on the line and station — which way
    you're travelling is applied afterwards — so several journeys from one
    station would otherwise each poll for identical data every minute.

    The window is a little under the poll interval, so in steady state each
    station is fetched once per cycle however the entries are staggered.
    Callers arriving mid-flight await the same request rather than starting
    another, and one of them giving up doesn't take the request with it.
    """
    store: dict[tuple[str, str], _Shared] = hass.data.setdefault(DATA_TRAIN_CACHE, {})
    key = (line, station)
    now = dt_util.utcnow()

    cached = store.get(key)
    if cached is not None:
        started, task = cached
        if not task.done():
            return TrainFetch(started, await asyncio.shield(task))
        if _servable(task, now - started):
            # Re-raises a shared rate limit rather than returning departures.
            return TrainFetch(started, task.result())

    task = hass.async_create_task(
        async_shared_client(hass).get_train_departures(line, station)
    )
    store[key] = (now, task)
    return TrainFetch(now, await asyncio.shield(task))


@callback
def async_forget_train_departures(hass: HomeAssistant, line: str, station: str) -> None:
    """Drop a station's shared fetch so the next caller contacts Transperth.

    Called as a train entry unloads: reloading is how a user asks for fresh
    departures, and nothing shared should outlive the entries that wanted it.
    """
    store: dict[tuple[str, str], _Shared] | None = hass.data.get(DATA_TRAIN_CACHE)
    if store is not None:
        store.pop((line, station), None)
