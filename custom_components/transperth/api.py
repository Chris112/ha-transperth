"""One shared aiotransperth client per Home Assistant instance.

Transperth's rate-limit cooldown is sticky and shared with their public
website, and every fresh client re-scrapes a CSRF token page before its
first bus call. One shared client keeps the token and train-catalog
caches warm across coordinators, config flows, and services.
"""

from __future__ import annotations

from aiotransperth import TransperthClient
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_CLIENT = f"{DOMAIN}_client"


@callback
def async_shared_client(hass: HomeAssistant) -> TransperthClient:
    """Return the instance-wide client, creating it on first use."""
    if DATA_CLIENT not in hass.data:
        hass.data[DATA_CLIENT] = TransperthClient(
            session=async_get_clientsession(hass)
        )
    return hass.data[DATA_CLIENT]
