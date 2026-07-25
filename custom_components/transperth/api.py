"""One shared aiotransperth client per Home Assistant instance.

Transperth's rate-limit cooldown is sticky and shared with their public
website, and every fresh client re-scrapes a CSRF token page before its
first bus call. One shared client keeps the token and train-catalog
caches warm across coordinators, config flows, and services.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from aiotransperth import TrainDeparture, TransperthClient
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TRAIN_CACHE_TTL

DATA_CLIENT = f"{DOMAIN}_client"
DATA_TRAIN_CACHE = f"{DOMAIN}_train_departures"

type _Fetch = tuple[datetime, asyncio.Task[tuple[TrainDeparture, ...]]]


@callback
def async_shared_client(hass: HomeAssistant) -> TransperthClient:
    """Return the instance-wide client, creating it on first use."""
    if DATA_CLIENT not in hass.data:
        hass.data[DATA_CLIENT] = TransperthClient(
            session=async_get_clientsession(hass)
        )
    return hass.data[DATA_CLIENT]


async def async_train_departures(
    hass: HomeAssistant, line: str, station: str
) -> tuple[TrainDeparture, ...]:
    """Live departures at a station, shared by every entry boarding there.

    What Transperth returns depends only on the line and station — which way
    you're travelling is applied afterwards — so several journeys from one
    station would otherwise each poll for identical data every minute.

    The window is a little under the poll interval, so each station is fetched
    once per cycle no matter how the entries' schedules are staggered. Callers
    arriving mid-flight await the same request rather than starting another.
    """
    store: dict[tuple[str, str], _Fetch] = hass.data.setdefault(DATA_TRAIN_CACHE, {})
    key = (line, station)
    now = dt_util.utcnow()

    cached = store.get(key)
    if cached is not None:
        started, task = cached
        if not task.done() or now - started < TRAIN_CACHE_TTL:
            return await task

    task = hass.async_create_task(
        async_shared_client(hass).get_train_departures(line, station)
    )
    store[key] = (now, task)
    try:
        return await task
    except Exception:
        # A failure must not be served to the next poll — it should retry,
        # and back off on its own terms.
        if store.get(key, (None, None))[1] is task:
            del store[key]
        raise
