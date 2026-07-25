"""Which directions a train entry tracks.

An entry either names a destination station — a commute, one direction — or
doesn't, in which case it reports both ways along the line like a departure
board. Everything that needs to know which is shared from here.
"""

from __future__ import annotations

from aiotransperth import line_endpoints
from homeassistant.config_entries import ConfigEntry

from .const import CONF_LINE, CONF_STATION, CONF_TO_STATION, LOGGER


def short_name(station: str) -> str:
    """Station name without the catalog's `Stn` suffix, for display."""
    return station.removesuffix(" Stn")


def journey_target(entry: ConfigEntry) -> str | None:
    """The station this entry travels to, or None for a whole-station entry."""
    target = entry.data.get(CONF_TO_STATION)
    return str(target) if target else None


def tracked_directions(entry: ConfigEntry) -> list[str]:
    """The line ends this entry reports towards, for a whole-station entry.

    One per direction, minus any end the entry already sits at — there is no
    "towards Yanchep" sensor at Yanchep. Empty when the line has no ordering
    data, which leaves the entry with just its board.
    """
    line = entry.data.get(CONF_LINE, "")
    station = entry.data.get(CONF_STATION, "")
    try:
        endpoints = line_endpoints(line)
    except KeyError:
        LOGGER.warning(
            "No station ordering for %s; %s gets no direction sensors",
            line,
            station,
        )
        return []
    return [end for end in endpoints if end != station]
