"""Config flow (steps implemented in a later task)."""

from aiotransperth import TransperthClient  # noqa: F401  (patch target)
from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class TransperthConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a bus stop or train station."""

    VERSION = 1
